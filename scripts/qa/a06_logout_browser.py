"""A06: verify failure, retry, stolen-cookie replay and restart in Chromium."""
from __future__ import annotations

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

from offsetx_apollo_builder.api.auth import SESSION_COOKIE
from scripts.qa.hosted_tool_browser import child_environment


def create_disposable_app():
    from offsetx_apollo_builder.api.app import create_app
    from offsetx_apollo_builder.api.config import AppSettings

    root = Path(os.environ["OFF_CRM_QA_PROJECT_ROOT"])
    data = Path(os.environ["OFF_CRM_QA_DATA_ROOT"])
    return create_app(AppSettings(
        project_root=root, database_path=data / "crm.db",
        data_dir=data, export_dir=data / "exports",
        frontend_dist=root / "frontend/dist",
        host="127.0.0.1", port=int(os.environ["OFF_CRM_QA_PORT"]),
        demo_username=os.environ["OFF_CRM_QA_USER"],
        demo_password=os.environ["OFF_CRM_QA_PASSWORD"],
        session_secret=os.environ["OFFSETX_SESSION_SECRET"],
        secrets_key=os.environ["OFFSETX_SECRETS_KEY"],
        allowed_hosts=("127.0.0.1", "localhost"),
    ))


def run() -> None:
    root = Path(__file__).resolve().parents[2]
    chrome = (os.getenv("OFF_CRM_QA_CHROMIUM") or shutil.which("chromium")
              or shutil.which("google-chrome") or shutil.which("chromium-browser"))
    assert chrome, "A06 needs actual Chromium"
    assert (root / "frontend/dist/index.html").is_file(), "Build frontend first"

    with tempfile.TemporaryDirectory(prefix="offcrm-a06-") as folder:
        work = Path(folder)
        user, password = "test-owner", secrets.token_urlsafe(32)
        env = child_environment(root, work / "data", str(work / "hosted.db"),
                                secrets.token_urlsafe(48))
        env.update(OFF_CRM_QA_USER=user, OFF_CRM_QA_PASSWORD=password)
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            port = sock.getsockname()[1]
        env["OFF_CRM_QA_PORT"] = str(port)
        base = f"http://127.0.0.1:{port}"
        server = None

        def stop():
            nonlocal server
            if server:
                server.terminate()
                try:
                    server.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    server.kill()
                    server.wait(timeout=5)
                server = None

        def start(client):
            nonlocal server
            with (work / "private-server.log").open("a", encoding="utf-8") as output:
                server = subprocess.Popen(
                    [sys.executable, "-m", "uvicorn",
                     "scripts.qa.a06_logout_browser:create_disposable_app",
                     "--factory", "--host", "127.0.0.1", "--port", str(port),
                     "--no-access-log"],
                    cwd=work, env=env, stdout=output, stderr=subprocess.STDOUT,
                )
            deadline = time.monotonic() + 40
            while True:
                try:
                    if client.get("/health/live").status_code == 200:
                        return
                except httpx.TransportError:
                    pass
                assert server.poll() is None, "A06 server exited; inspect private log"
                assert time.monotonic() < deadline, "A06 server did not start"
                time.sleep(0.1)

        try:
            with httpx.Client(base_url=base, timeout=10) as client:
                start(client)
                with sync_playwright() as playwright:
                    with playwright.chromium.launch(
                        executable_path=chrome, headless=True,
                        args=["--no-sandbox", "--disable-dev-shm-usage"],
                    ) as browser:
                        normal = browser.new_context(viewport={"width": 1280, "height": 900})
                        page = normal.new_page()
                        page.route("**/*", lambda route: route.continue_()
                                   if route.request.url.startswith(base + "/")
                                   else route.abort())
                        page.goto(base + "/#dashboard")
                        page.get_by_role("heading", name="Sign in to the CRM").wait_for()
                        page.get_by_label("Username").fill(user)
                        page.get_by_label("Password").fill(password)
                        page.get_by_role("button", name="Sign in").click()
                        page.get_by_role("button", name="Log out").wait_for()
                        copied = next(cookie["value"] for cookie in normal.cookies(base)
                                      if cookie["name"] == SESSION_COOKIE)
                        stolen = browser.new_context()
                        stolen.add_cookies([{"name": SESSION_COOKIE, "value": copied, "url": base}])
                        stolen_page = stolen.new_page()
                        stolen_page.goto(base + "/#dashboard")
                        stolen_page.get_by_role("button", name="Log out").wait_for()

                        other = client.post("/api/v1/auth/login", json={
                            "username": user, "password": password,
                        })
                        assert other.status_code == 200
                        second = other.cookies.get(SESSION_COOKIE)
                        assert second and second != copied

                        def failed_request(route):
                            route.fulfill(status=503, content_type="application/json",
                                          body='{"detail":"Revocation unavailable"}')

                        page.route("**/api/v1/auth/logout", failed_request)
                        page.get_by_role("button", name="Log out").click()
                        expect(page.get_by_role("alert")).to_contain_text(
                            "session may still be active"
                        )
                        expect(page.get_by_role("button", name="Log out")).to_be_visible()
                        assert client.get("/api/v1/dashboard", headers={
                            "Cookie": f"{SESSION_COOKIE}={copied}",
                        }).status_code == 200

                        page.unroute("**/api/v1/auth/logout", failed_request)
                        page.get_by_role("button", name="Log out").click()
                        page.get_by_role("heading", name="Sign in to the CRM").wait_for()
                        assert client.get("/api/v1/dashboard", headers={
                            "Cookie": f"{SESSION_COOKIE}={copied}",
                        }).status_code == 401
                        assert client.get("/api/v1/dashboard", headers={
                            "Cookie": f"{SESSION_COOKIE}={second}",
                        }).status_code == 200
                        stolen_page.reload()
                        stolen_page.get_by_role("heading", name="Sign in to the CRM").wait_for()
                        stolen.close()
                        normal.close()
                stop()
                start(client)
                assert client.get("/api/v1/dashboard", headers={
                    "Cookie": f"{SESSION_COOKIE}={copied}",
                }).status_code == 401
                assert client.get("/api/v1/dashboard", headers={
                    "Cookie": f"{SESSION_COOKIE}={second}",
                }).status_code == 200
            print("A06 PASS: failed logout keeps session; retry revokes copied "
                  "cookie across browsers and restart")
        finally:
            stop()


if __name__ == "__main__":
    run()
