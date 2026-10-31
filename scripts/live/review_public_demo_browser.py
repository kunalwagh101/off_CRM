"""Exercise the visitor login in real Chromium at desktop and mobile widths."""
from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from pathlib import Path

from playwright.sync_api import sync_playwright
from review_contacts_browser import ROOT, BASE, _wait_for_server


def verify(browser, base):
    for width, height in ((1440, 1000), (390, 844)):
        context = browser.new_context(viewport={"width": width, "height": height})
        page = context.new_page()
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        try:
            page.goto(base, wait_until="networkidle")
            page.get_by_role("complementary", name="Demo login details").wait_for()
            username = page.get_by_label("Username", exact=True).input_value()
            password = page.get_by_label("Password", exact=True).input_value()
            assert username and len(password) >= 12
            assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
            screenshot_dir = os.getenv("OFF_CRM_DEMO_SCREENSHOTS", "")
            if screenshot_dir:
                target = Path(screenshot_dir)
                target.mkdir(parents=True, exist_ok=True)
                page.screenshot(path=str(target / f"demo-login-{width}.png"), full_page=True)
            page.get_by_role("button", name="Sign in", exact=True).click()
            page.get_by_role("status").filter(has_text="Visitor demo").wait_for()
            page.get_by_role("navigation", name="Main navigation").get_by_role("link", name="Contacts", exact=True).click()
            page.get_by_text("Anita Rao", exact=True).wait_for()
            assert page.request.post(base + "/api/v1/campaigns", data={"name": "blocked"}).status == 403
            if screenshot_dir:
                page.screenshot(path=str(target / f"demo-contacts-{width}.png"), full_page=True)
            page.get_by_role("button", name="Log out", exact=True).click()
            page.get_by_role("complementary", name="Demo login details").wait_for()
            assert page.request.get(base + "/api/v1/dashboard").status == 401
            assert not errors, errors
            print(f"PUBLIC DEMO CHROMIUM PASS {width}px: visible credentials, login, sample contacts, write refusal, logout", flush=True)
        finally:
            context.close()


def main():
    with tempfile.TemporaryDirectory(prefix="offcrm-public-demo-qa-") as folder:
        base = os.getenv("OFF_CRM_DEMO_BASE_URL", BASE).rstrip("/")
        proc = None
        if not os.getenv("OFF_CRM_DEMO_BASE_URL"):
            env = os.environ.copy()
            for key in ("OFFSETX_DATABASE_URL", "OFFSETX_SECRETS_KEY", "OFFSETX_LOCAL_API_TOKEN",
                        "OFFSETX_GMAIL_CLIENT_SECRETS", "OFFSETX_OWN_EMAIL"):
                env.pop(key, None)
            env.update({
                "OFFSETX_PUBLIC_DEMO": "1", "OFFSETX_PRODUCTION": "0",
                "OFFSETX_DATA_DIR": str(Path(folder) / "data"),
                "OFFSETX_OUTREACH_DB": str(Path(folder) / "data" / "crm.db"),
                "OFFSETX_WEB_HOST": "127.0.0.1", "OFFSETX_ALLOWED_HOSTS": "localhost,127.0.0.1",
                "OFFSETX_DEMO_USERNAME": "visitor", "OFFSETX_DEMO_PASSWORD": "qa-public-password-2026",
                "OFFSETX_SESSION_SECRET": "qa-private-session-" + "s" * 48,
            })
            proc = subprocess.Popen(
                [str(ROOT / ".venv/bin/python"), "-m", "offsetx_apollo_builder.web_cli", "--port", "8766"],
                cwd=ROOT, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT,
            )
            _wait_for_server(proc)
        try:
            with sync_playwright() as playwright:
                browser = playwright.chromium.launch(
                    executable_path=shutil.which("chromium"), headless=True,
                    args=["--no-sandbox", "--disable-dev-shm-usage"],
                )
                try:
                    verify(browser, base)
                finally:
                    browser.close()
        finally:
            if proc:
                proc.terminate()
                proc.wait(timeout=10)


if __name__ == "__main__":
    main()
