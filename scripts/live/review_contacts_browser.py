"""Review-only real Chromium acceptance for S-06.02.41; never use customer data.

Run from the repository root after the frontend build:
    uv run python scripts/live/review_contacts_browser.py

The QA image supplies Playwright and a system Chromium separately. This script
starts a disposable local server on loopback and never contacts a provider.
"""
from __future__ import annotations

import csv
import io
import json
import os
import shutil
import subprocess
import tempfile
import time
from pathlib import Path

import httpx
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[2]
BASE = "http://127.0.0.1:8766"
TOKEN = "qa-only-local-token-" + "t" * 32


def _wait_for_server(process: subprocess.Popen) -> None:
    with httpx.Client(timeout=2.0) as client:
        for _ in range(80):
            if process.poll() is not None:
                raise AssertionError(f"Disposable app exited with {process.returncode}")
            try:
                response = client.get(BASE + "/")
                if response.status_code == 200:
                    return
            except httpx.TransportError:
                pass
            time.sleep(0.25)
    raise AssertionError("Disposable web application did not start on loopback")


def _dataset() -> bytes:
    text = io.StringIO()
    writer = csv.writer(text)
    writer.writerow(["Full Name", "Email", "Company", "Category"])
    for index in range(503):
        writer.writerow([f"Pagination Person {index:03d}", f"pagination{index:03d}@example.test", "Example", "CBAM"])
    return text.getvalue().encode("utf-8")


def main() -> None:
    chromium = shutil.which("chromium")
    assert chromium, "Chromium must be installed in the review-only image"
    with tempfile.TemporaryDirectory(prefix="offcrm-browser-qa-") as folder:
        env = os.environ.copy()
        for key in ("OFFSETX_DATABASE_URL", "OFFSETX_SECRETS_KEY", "OFFSETX_DEMO_USERNAME",
                    "OFFSETX_DEMO_PASSWORD", "OFFSETX_SESSION_SECRET", "RENDER_EXTERNAL_HOSTNAME"):
            env.pop(key, None)
        env.update({
            "OFFSETX_DATA_DIR": str(Path(folder) / "data"),
            "OFFSETX_OUTREACH_DB": str(Path(folder) / "data" / "crm.sqlite3"),
            "OFFSETX_LOCAL_API_TOKEN": TOKEN,
            "OFFSETX_WEB_HOST": "127.0.0.1",
            "OFFSETX_ALLOWED_HOSTS": "127.0.0.1,localhost",
            "OFFSETX_PRODUCTION": "0",
            "PYTHONUNBUFFERED": "1",
        })
        proc = subprocess.Popen(
            [str(ROOT / ".venv/bin/python"), "-m", "offsetx_apollo_builder.web_cli",
             "--host", "127.0.0.1", "--port", "8766"],
            cwd=ROOT,
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.STDOUT,
        )
        try:
            _wait_for_server(proc)
            headers = {"Authorization": "Bearer " + TOKEN}
            with httpx.Client(base_url=BASE, headers=headers, timeout=30.0) as client:
                result = client.post("/api/v1/campaigns", json={"name": "Chromium 503-contact QA"})
                assert result.status_code == 201, result.text
                campaign_id = result.json()["id"]

            with sync_playwright() as p:
                browser = p.chromium.launch(
                    executable_path=chromium, headless=True,
                    args=["--no-sandbox", "--disable-dev-shm-usage"],
                )
                try:
                    for width in (1280, 390):
                        context = browser.new_context(viewport={"width": width, "height": 900})
                        context.add_init_script(
                            "sessionStorage.setItem('offsetx-api-token', " + json.dumps(TOKEN) + ")"
                        )
                        page = context.new_page()
                        page.goto(BASE + "/#contacts", wait_until="domcontentloaded")
                        page.get_by_role("heading", name="Contacts").wait_for(timeout=30000)

                        if width == 1280:
                            page.get_by_role("button", name="Import CSV / Excel").click()
                            page.locator('input[name="contacts-file"]').set_input_files({
                                "name": "503-qa-contacts.csv",
                                "mimeType": "text/csv",
                                "buffer": _dataset(),
                            })
                            page.locator('form:has(input[name="contacts-file"])').get_by_role(
                                "button", name="Import contacts", exact=True
                            ).click()
                            with httpx.Client(base_url=BASE, headers=headers, timeout=30.0) as client:
                                for _ in range(40):
                                    response = client.get(
                                        f"/api/v1/campaigns/{campaign_id}/contacts",
                                        params={"limit": 1},
                                    )
                                    if response.status_code == 200 and response.json()["total"] == 503:
                                        break
                                    time.sleep(0.25)
                                else:
                                    raise AssertionError("Browser import did not persist 503 contacts")
                        nav = page.get_by_role("navigation", name="Contacts pages")
                        nav.wait_for(timeout=30000)
                        assert "Showing 1–100 of 503" in nav.inner_text()
                        assert nav.get_by_role("button", name="Previous page").is_disabled()
                        for n in range(5):
                            nav.get_by_role("button", name="Next page").click()
                            page.get_by_role("status").filter(has_text=f"Page {n + 2} of 6").wait_for(timeout=30000)
                        assert "Showing 501–503 of 503" in nav.inner_text()
                        assert nav.get_by_role("button", name="Next page").is_disabled()
                        page.get_by_role("button", name="Pagination Person 502").wait_for(timeout=30000)
                        page.get_by_role("textbox", name="Search contacts").fill("Person 502")
                        page.get_by_role("button", name="Search", exact=True).click()
                        page.locator(".toolbar-count").filter(has_text="1 contacts").wait_for(timeout=30000)
                        page.get_by_role("button", name="Pagination Person 502").wait_for(timeout=30000)
                        assert nav.count() == 0, "Search must reset the page index to the sole result page"
                        print(f"PASS Chromium {width}px: 503 persisted import, six pages, final row, search and controls", flush=True)
                        context.close()
                finally:
                    browser.close()
        finally:
            proc.terminate()
            try:
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait(timeout=5)


if __name__ == "__main__":
    main()
