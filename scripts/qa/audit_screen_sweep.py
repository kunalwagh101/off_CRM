"""Replay and extend the archived real-browser screen audit on develop.

Disposable local state; no provider credentials, outbound sends or customer
database. Missing infrastructure or an untested navigation route is a failure.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import secrets
import shutil
import socket
import subprocess
import sys
import tempfile
import time
from urllib.parse import urlsplit

import httpx
from playwright.sync_api import expect, sync_playwright

from scripts.qa.hosted_tool_browser import child_environment
from scripts.qa.route_coverage import validate_routes

# Explicit inventory: keep all current routes and all 18 archived audit routes.
# New navigation routes must be consciously added to this acceptance gate.
ROUTES = (
    "dashboard", "campaigns", "discovery", "contacts", "readiness", "activity",
    "replies", "followups", "priorities", "crmsearch", "accounts", "attribution",
    "crmquality", "campaigncompare", "followupmetrics", "drafts", "queue",
    "deliverability", "sales", "experiments", "imagereview", "videoeditor",
    "posting", "product", "strategy", "connectors", "egress", "memory",
    "meetings", "recall", "ai", "agentteam", "settings",
)


def verify_screens(chromium, base, token, *, skip_link_only=False):
    with sync_playwright() as playwright:
        # Keep Chromium's own sandbox enabled, as in the archived audit.
        with playwright.chromium.launch(
            executable_path=chromium, headless=True, chromium_sandbox=True,
            args=["--disable-dev-shm-usage"],
        ) as browser:
            for width in (1280, 390):
                with browser.new_context(viewport={"width": width, "height": 900}) as context:
                    context.add_init_script(
                        "sessionStorage.setItem('offsetx-api-token', " + json.dumps(token) + ")"
                    )
                    page = context.new_page()
                    page.set_default_timeout(15_000)
                    errors = []
                    server_errors = []
                    page.on("pageerror", lambda _: errors.append(True))

                    def on_response(response):
                        if response.status >= 500 or (
                            response.status == 401 and "/api/v1/" in response.url
                        ):
                            server_errors.append((response.status, urlsplit(response.url).path))

                    page.on("response", on_response)
                    page.route("**/*", lambda route: route.continue_()
                               if route.request.url.startswith((base + "/", "blob:" + base + "/"))
                               else route.abort())
                    initial = page.goto(base + "/#dashboard", wait_until="domcontentloaded")
                    assert initial is not None and initial.status == 200
                    nav = page.get_by_role("navigation", name="Main navigation" if width >= 860 else "Mobile navigation", exact=True)
                    expect(nav).to_be_visible()
                    expect(nav).to_have_count(1)
                    expect(nav.locator("a[href^='#']")).to_have_count(len(ROUTES))
                    routes = validate_routes(ROUTES, nav.locator("a").evaluate_all(
                        "(links) => links.map(link => link.getAttribute('href'))"
                    ))
                    selected_routes = ('settings', 'contacts') if skip_link_only else routes
                    for name in selected_routes:
                        stage = "navigation"
                        try:
                            # Use the actual app route, not a mocked response or iframe.
                            previous = urlsplit(page.url).fragment
                            nav.locator(f'a[href="#{name}"]').click()
                            expect(nav.locator("a[aria-current='page']")).to_have_attribute("href", "#" + name)
                            main = page.locator("#main-content")
                            if previous != name:
                                expect(main).to_be_focused()
                            stage = "render"
                            expect(main).to_be_visible()
                            expect(main.locator("h1, h2, .state-panel").first).to_be_visible()
                            page.wait_for_load_state("networkidle", timeout=15_000)
                            expect(main).to_contain_text(re.compile(r"\S"))
                            stage = "keyboard skip"
                            skip = page.get_by_role("link", name="Skip to main content")
                            skip.focus()
                            skip.press("Enter")
                            expect(main).to_be_focused()
                            assert urlsplit(page.url).fragment == name, f"Skip changed {name} route"
                            expect(nav.locator("a[aria-current='page']")).to_have_attribute("href", "#" + name)
                            stage = "pointer skip"
                            skip.focus()
                            skip.click()
                            expect(main).to_be_focused()
                            assert urlsplit(page.url).fragment == name, f"Pointer skip changed {name} route"
                            assert page.evaluate("window.scrollY") == 0, f"Skip did not reach top: {name}"
                            stage = "browser and API errors"
                            assert not errors, f"{width}px {name}: JavaScript errors: {len(errors)}"
                            assert not server_errors, f"{width}px {name}: API errors: {server_errors}"
                            print(f"SCREEN PASS {width}px {name}: rendered; keyboard and pointer skip preserved route", flush=True)
                        except Exception as error:
                            print(f"SCREEN FAIL {width}px {name}: {stage}; {type(error).__name__}; JS errors={len(errors)}; API errors={server_errors}", flush=True)
                            raise
                    label = "SKIP LINK" if skip_link_only else "SCREEN SWEEP"
                    print(f"{label} PASS {width}px: {len(selected_routes)}/{len(selected_routes)}", flush=True)


def main(*, skip_link_only=False):
    root = Path(__file__).resolve().parents[2]
    chromium = (os.getenv("OFF_CRM_QA_CHROMIUM") or shutil.which("google-chrome")
                or shutil.which("chromium") or shutil.which("chromium-browser"))
    assert chromium, "Screen audit requires Chromium"
    assert os.geteuid() != 0, "Run as an ordinary user with Chromium sandbox enabled"
    assert (root / "frontend/dist/index.html").is_file(), "Build the frontend before audit"
    with tempfile.TemporaryDirectory(prefix="offcrm-audit-screens-") as directory:
        work = Path(directory)
        token = secrets.token_urlsafe(48)
        env = child_environment(root, work / "data", str(work / "unused.db"), token)
        env.pop("OFFSETX_DATABASE_URL")
        env.pop("OFFSETX_SECRETS_KEY")
        with socket.socket() as listener:
            listener.bind(("127.0.0.1", 0))
            port = listener.getsockname()[1]
        env["OFF_CRM_QA_PORT"] = str(port)
        base = f"http://127.0.0.1:{port}"
        with (work / "server.log").open("w", encoding="utf-8") as log:
            with subprocess.Popen(
                [sys.executable, "-m", "uvicorn",
                 "scripts.qa.wp1_browser_recovery:create_disposable_app",
                 "--factory", "--host", "127.0.0.1", "--port", str(port), "--no-access-log"],
                cwd=work, env=env, stdout=log, stderr=subprocess.STDOUT,
            ) as server:
                try:
                    with httpx.Client(base_url=base, headers={"X-Offsetx-Token": token},
                                      timeout=10, trust_env=False) as client:
                        deadline = time.monotonic() + 40
                        while True:
                            try:
                                response = client.get("/health/ready")
                                if response.status_code == 200 and response.json().get("status") == "ready":
                                    break
                            except httpx.TransportError:
                                pass
                            assert server.poll() is None, "Screen audit server exited"
                            assert time.monotonic() < deadline, "Screen audit server did not become ready"
                            time.sleep(0.1)
                        # A selected campaign exercises the real campaign-scoped pages.
                        created = client.post("/api/v1/campaigns", json={"name": "Synthetic audit campaign"})
                        assert created.status_code == 201, created.status_code
                        verify_screens(chromium, base, token, skip_link_only=skip_link_only)
                finally:
                    if server.poll() is None:
                        server.terminate()
                        try:
                            server.wait(timeout=10)
                        except subprocess.TimeoutExpired:
                            server.kill()
                            server.wait(timeout=5)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--skip-link-only", action="store_true", help="Run the two specific S-06.02.37 routes; full inventory still checked.")
    main(skip_link_only=parser.parse_args().skip_link_only)
