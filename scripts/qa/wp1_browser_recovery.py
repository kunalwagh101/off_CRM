"""Replay WP1 encrypted backup and restore through the current browser UI."""
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
    assert chromium, "WP1 needs Chromium"
    assert (root / "frontend/dist/index.html").is_file(), "Build frontend before WP1"

    with tempfile.TemporaryDirectory(prefix="offcrm-wp1-browser-") as directory:
        work = Path(directory)
        token = secrets.token_urlsafe(48)
        env = child_environment(root, work / "data", str(work / "unused.db"), token)
        env.pop("OFFSETX_DATABASE_URL")
        with socket.socket() as listener:
            listener.bind(("127.0.0.1", 0))
            port = listener.getsockname()[1]
        env["OFF_CRM_QA_PORT"] = str(port)
        base = f"http://127.0.0.1:{port}"

        with (work / "server.log").open("w", encoding="utf-8") as output:
            with subprocess.Popen(
                [
                    sys.executable, "-m", "uvicorn",
                    "scripts.qa.hosted_tool_browser:create_disposable_app",
                    "--factory", "--host", "127.0.0.1", "--port", str(port),
                    "--no-access-log",
                ],
                cwd=work, env=env, stdout=output, stderr=subprocess.STDOUT,
            ) as server:
                try:
                    with httpx.Client(
                        base_url=base, headers={"X-Offsetx-Token": token}, timeout=10,
                        trust_env=False,
                    ) as client:
                        deadline = time.monotonic() + 40
                        while True:
                            try:
                                response = client.get("/health/ready")
                                if response.status_code == 200 and response.json().get("status") == "ready":
                                    break
                            except httpx.TransportError:
                                pass
                            assert server.poll() is None, "Disposable WP1 app exited"
                            assert time.monotonic() < deadline, "Disposable WP1 app did not start"
                            time.sleep(0.1)
                        verify_browser(chromium, base, token, work, client)
                finally:
                    if server.poll() is None:
                        server.terminate()
                        try:
                            server.wait(timeout=10)
                        except subprocess.TimeoutExpired:
                            server.kill()
                            server.wait(timeout=5)


def verify_browser(chromium: str, base: str, token: str, work: Path, client: httpx.Client) -> None:
    first = client.post("/api/v1/campaigns", json={"name": "Retained by backup"})
    assert first.status_code == 201, first.status_code
    campaign_id = first.json()["id"]
    archive = work / "workspace.oxbackup"
    passphrase = secrets.token_urlsafe(32)

    with sync_playwright() as playwright:
        with playwright.chromium.launch(
            executable_path=chromium, headless=True, args=["--disable-dev-shm-usage"],
        ) as browser:
            with browser.new_context(accept_downloads=True) as context:
                context.add_init_script(
                    "sessionStorage.setItem('offsetx-api-token', " + json.dumps(token) + ")"
                )
                page = context.new_page()
                page.route(
                    "**/*", lambda request: request.continue_()
                    if request.request.url.startswith(base + "/") else request.abort(),
                )
                page.goto(base + "/#settings", wait_until="domcontentloaded")
                title = page.get_by_role("heading", name="Encrypted backup", exact=True)
                panel = page.locator("section").filter(has=title)
                export_button = panel.get_by_role("button", name="Create encrypted backup")
                restore_button = panel.get_by_role("button", name="Restore backup", exact=True)
                export_form = panel.locator("form").filter(has=export_button)
                restore_form = panel.locator("form").filter(has=restore_button)
                export_form.get_by_label("Backup passphrase").fill(passphrase)
                with page.expect_download() as backup:
                    export_button.click()
                backup.value.save_as(archive)
                assert archive.stat().st_size > 0
                expect(export_form.get_by_label("Backup passphrase")).to_have_value("")

                later = client.post("/api/v1/campaigns", json={"name": "Created after backup"})
                assert later.status_code == 201, later.status_code
                restore_form.get_by_label("Backup file").set_input_files(str(archive))
                restore_form.get_by_label("Backup passphrase").fill(passphrase)
                page.once("dialog", lambda dialog: dialog.accept())
                with page.expect_response(
                    lambda res: res.request.method == "POST" and res.url.endswith("/backups/restore")
                ) as restore:
                    restore_button.click()
                assert restore.value.status == 200, restore.value.status
                expect(page.get_by_role("status").filter(has_text="Backup restored")).to_be_visible()
                ready = client.get("/health/ready")
                assert ready.is_success and ready.json()["status"] == "ready"
                restored = client.get("/api/v1/campaigns")
                assert restored.is_success
                assert [row["id"] for row in restored.json()["items"]] == [campaign_id]
    print("WP1 PASS: browser export and restore recovered the original workspace campaign")


if __name__ == "__main__":
    main()
