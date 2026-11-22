"""A33: real desktop/mobile campaign selection, reload and persistence proof.

Runs only against a disposable local app and SQLite. No real mail, provider or
customer storage is used. Requires built frontend, Chromium and Playwright.
"""
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
    assert chromium, "A33 needs the real Chromium browser"
    assert (root / "frontend/dist/index.html").is_file(), "Build frontend before A33 browser QA"

    with tempfile.TemporaryDirectory(prefix="offcrm-a33-") as directory:
        work = Path(directory)
        data = work / "data"
        token = secrets.token_urlsafe(48)
        env = child_environment(root, data, str(work / "hosted.db"), token)
        with socket.socket() as listener:
            listener.bind(("127.0.0.1", 0))
            port = listener.getsockname()[1]
        env["OFF_CRM_QA_PORT"] = str(port)
        base = f"http://127.0.0.1:{port}"
        log_path = work / "server.log"

        with log_path.open("w", encoding="utf-8") as server_log:
            server = subprocess.Popen(
                [
                    sys.executable, "-m", "uvicorn",
                    "scripts.qa.hosted_tool_browser:create_disposable_app",
                    "--factory", "--host", "127.0.0.1", "--port", str(port),
                    "--no-access-log",
                ],
                cwd=work, env=env, stdout=server_log, stderr=subprocess.STDOUT,
            )
            try:
                with httpx.Client(base_url=base, headers={"X-Offsetx-Token": token}, timeout=10) as client:
                    deadline = time.monotonic() + 40
                    while True:
                        try:
                            if client.get("/health/live").status_code == 200:
                                break
                        except httpx.TransportError:
                            pass
                        assert server.poll() is None, "A33 disposable server exited; inspect private server log"
                        assert time.monotonic() < deadline, "A33 disposable server did not start"
                        time.sleep(0.1)

                    first_response = client.post("/api/v1/campaigns", json={"name": "A33 Existing QA"})
                    assert first_response.status_code == 201, first_response.status_code
                    first_id = first_response.json()["id"]

                    with sync_playwright() as playwright:
                        with playwright.chromium.launch(
                            executable_path=chromium,
                            headless=True, args=["--no-sandbox", "--disable-dev-shm-usage"],
                        ) as browser:
                            for width in (1280, 390):
                                context = browser.new_context(viewport={"width": width, "height": 900})
                                context.add_init_script(
                                    "sessionStorage.setItem('offsetx-api-token', " + json.dumps(token) + ")"
                                )
                                page = context.new_page()
                                errors: list[str] = []
                                page.on("pageerror", lambda error: errors.append(str(error)))
                                page.route(
                                    "**/*",
                                    lambda route: route.continue_()
                                    if route.request.url.startswith(base + "/")
                                    else route.abort(),
                                )
                                try:
                                    page.goto(base + "/#campaigns", wait_until="domcontentloaded")
                                    page.get_by_role("heading", name="Campaigns", exact=True).wait_for()
                                    active = page.get_by_label("Active campaign")
                                    # A fresh mobile browser has different local storage.
                                    # Do not assume it starts on the seed campaign after the
                                    # desktop run created another (newer) campaign.
                                    expect(active).to_be_enabled()
                                    existing = client.get("/api/v1/campaigns?limit=200")
                                    assert existing.status_code == 200
                                    assert active.input_value() in {
                                        row["id"] for row in existing.json()["items"]
                                    }
                                    page.get_by_role("button", name="Create campaign", exact=True).first.click()
                                    modal = page.get_by_role("dialog", name="Create campaign")
                                    modal.get_by_label("Campaign name").fill(f"A33 New QA {width}")
                                    modal.get_by_role("button", name="Create campaign", exact=True).click()
                                    page.get_by_role("status").filter(has_text="Campaign created").wait_for()
                                    found = client.get("/api/v1/campaigns?limit=200")
                                    assert found.status_code == 200
                                    new_rows = [
                                        row for row in found.json()["items"]
                                        if row["name"] == f"A33 New QA {width}"
                                    ]
                                    assert len(new_rows) == 1, "A33 creation must persist exactly once"
                                    new_id = new_rows[0]["id"]
                                    expect(active).to_have_value(new_id)

                                    page.goto(base + "/#contacts", wait_until="domcontentloaded")
                                    page.get_by_role("heading", name="Contacts", exact=True).wait_for()
                                    expect(page.get_by_label("Active campaign")).to_have_value(new_id)
                                    page.reload()
                                    expect(page.get_by_label("Active campaign")).to_have_value(new_id)

                                    page.get_by_label("Active campaign").select_option(first_id)
                                    expect(page.get_by_label("Active campaign")).to_have_value(first_id)
                                    page.reload()
                                    expect(page.get_by_label("Active campaign")).to_have_value(first_id)
                                    assert not errors, f"A33 browser JavaScript error(s): {len(errors)}"
                                    print(
                                        f"A33 PASS: Chromium {width}px, create/select/contacts/reload/manual-switch",
                                        flush=True,
                                    )
                                finally:
                                    context.close()
            finally:
                server.terminate()
                try:
                    server.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    server.kill()
                    server.wait(timeout=5)


if __name__ == "__main__":
    main()
