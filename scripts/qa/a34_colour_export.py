"""A34: export and decode the default Colour clip in disposable Chromium QA."""
from __future__ import annotations

import json
import os
from pathlib import Path
import secrets
import shutil
import socket
import subprocess
import sys
import tempfile
import time

import httpx
from playwright.sync_api import expect, sync_playwright

from scripts.qa.hosted_tool_browser import child_environment


def main() -> None:
    root = Path(__file__).resolve().parents[2]
    chromium = (
        os.getenv("OFF_CRM_QA_CHROMIUM")
        or shutil.which("chromium")
        or shutil.which("google-chrome")
        or shutil.which("chromium-browser")
    )
    assert chromium, "A34 needs Chromium"
    assert shutil.which("ffprobe"), "A34 needs ffprobe to decode the export"
    assert (root / "frontend/dist/index.html").is_file(), "Build frontend before A34 QA"

    with tempfile.TemporaryDirectory(prefix="offcrm-a34-") as directory:
        work = Path(directory)
        token = secrets.token_urlsafe(48)
        env = child_environment(root, work / "data", str(work / "hosted.db"), token)
        with socket.socket() as listener:
            listener.bind(("127.0.0.1", 0))
            port = listener.getsockname()[1]
        env["OFF_CRM_QA_PORT"] = str(port)
        base = f"http://127.0.0.1:{port}"
        with (work / "server.log").open("w", encoding="utf-8") as server_log:
            with subprocess.Popen(
                [
                    sys.executable, "-m", "uvicorn",
                    "scripts.qa.hosted_tool_browser:create_disposable_app",
                    "--factory", "--host", "127.0.0.1", "--port", str(port),
                    "--no-access-log",
                ],
                cwd=work, env=env, stdout=server_log, stderr=subprocess.STDOUT,
            ) as server:
                try:
                    verify_export(base, token, server, chromium, work)
                finally:
                    if server.poll() is None:
                        server.terminate()
                        try:
                            server.wait(timeout=10)
                        except subprocess.TimeoutExpired:
                            server.kill()
                            server.wait(timeout=5)


def verify_export(base: str, token: str, server, chromium: str, work: Path) -> None:
    with httpx.Client(base_url=base, headers={"X-Offsetx-Token": token}, timeout=10) as client:
        deadline = time.monotonic() + 40
        while True:
            try:
                if client.get("/health/ready").status_code == 200:
                    break
            except httpx.TransportError:
                pass
            assert server.poll() is None, "A34 disposable server exited"
            assert time.monotonic() < deadline, "A34 disposable server did not start"
            time.sleep(0.1)

        created = client.post("/api/v1/campaigns", json={"name": "A34 QA", "kind": "image"})
        assert created.status_code == 201, created.status_code
        campaign_id = created.json()["id"]

        with sync_playwright() as playwright:
            with playwright.chromium.launch(
                executable_path=chromium, headless=True,
                args=["--no-sandbox", "--disable-dev-shm-usage"],
            ) as browser:
                context = browser.new_context(viewport={"width": 1280, "height": 900})
                context.add_init_script(
                    "sessionStorage.setItem('offsetx-api-token', " + json.dumps(token) + ")"
                )
                page = context.new_page()
                page.route(
                    "**/*",
                    lambda route: route.continue_()
                    if route.request.url.startswith(base + "/")
                    else route.abort(),
                )
                page.goto(base + "/#videoeditor", wait_until="domcontentloaded")
                expect(page.get_by_label("Active campaign")).to_have_value(campaign_id)
                page.get_by_role("button", name="Empty project", exact=True).click()
                with page.expect_response(
                    lambda response: response.request.method == "POST"
                    and response.url.endswith("/edit")
                ) as edit:
                    page.get_by_role("button", name="Colour", exact=True).click()
                assert edit.value.ok, edit.value.status

                with page.expect_response(
                    lambda response: response.request.method == "POST"
                    and response.url.endswith("/renders"),
                    timeout=90_000,
                ) as upload:
                    page.get_by_role("button", name="Export", exact=True).click()
                assert upload.value.status == 201, upload.value.status
                render = upload.value.json()
                assert render["passed"], render["summary"]

        served = client.get(f"/api/v1/video-renders/{render['render_id']}/file")
        assert served.status_code == 200, served.status_code
        assert served.headers["content-type"].startswith("video/webm")
        file = work / "colour.webm"
        file.write_bytes(served.content)

    result = subprocess.run(
        [
            "ffprobe", "-v", "error", "-select_streams", "v:0", "-count_frames",
            "-show_entries", "stream=width,height,nb_read_frames", "-of", "json", str(file),
        ],
        check=True, capture_output=True, text=True, timeout=30,
    )
    assert not result.stderr, result.stderr
    streams = json.loads(result.stdout)["streams"]
    assert len(streams) == 1, streams
    stream = streams[0]
    assert (stream["width"], stream["height"], int(stream["nb_read_frames"])) == (1080, 1920, 60), stream
    print(f"A34 PASS: Colour export stored and decoded, 60 frames, {len(served.content)} bytes")


if __name__ == "__main__":
    main()
