"""Real loopback UI and HTTP acceptance for S-06.02.35 and S-06.02.36.

No external providers, mail or customer state. Seed only pre-ownership legacy
records in an isolated directory, then exercise actual public app endpoints.
"""
from contextlib import contextmanager
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

from offsetx_apollo_builder.outreach.provider_profiles import ProviderProfileStore
from scripts.qa.hosted_tool_browser import child_environment


@contextmanager
def running_server(root, work, env, base):
    with (work / "private-server.log").open("a", encoding="utf-8") as log:
        with subprocess.Popen(
            [sys.executable, "-m", "uvicorn",
             "scripts.qa.wp1_browser_recovery:create_disposable_app",
             "--factory", "--host", "127.0.0.1", "--port", env["OFF_CRM_QA_PORT"],
             "--no-access-log"], cwd=work, env=env, stdout=log,
            stderr=subprocess.STDOUT,
        ) as server:
            try:
                with httpx.Client(base_url=base, trust_env=False, timeout=10) as client:
                    deadline = time.monotonic() + 40
                    while True:
                        try:
                            response = client.get("/health/ready")
                            if response.is_success and response.json().get("status") == "ready":
                                break
                        except httpx.TransportError:
                            pass
                        assert server.poll() is None, "Disposable app exited"
                        assert time.monotonic() < deadline, "Disposable app did not start"
                        time.sleep(.1)
                yield
            finally:
                if server.poll() is None:
                    server.terminate()
                    try:
                        server.wait(timeout=10)
                    except subprocess.TimeoutExpired:
                        server.kill()
                        server.wait(timeout=5)


def seed_legacy(data):
    store = ProviderProfileStore(data)
    key = "synthetic-" + secrets.token_urlsafe(32)
    for identifier, name in (("legacy-confirm", "Old profile to confirm"),
                             ("legacy-remove", "Old profile to remove")):
        store.upsert({"id": identifier, "name": name,
                      "provider_type": "openai_compatible", "model": "synthetic",
                      "base_url": "https://example.invalid/v1"},
                     owner="default", api_key=key)
    # Recreate the historical pre-DD-68 metadata, preserving actual encrypted keys.
    rows = json.loads(store.profile_path.read_text())
    for row in rows:
        row.pop("owner_confirmed")
    store.profile_path.write_text(json.dumps(rows))
    return key


def check_owner_creation(base, token, previous, second):
    with httpx.Client(base_url=base, trust_env=False, timeout=10,
                      headers={"X-Offsetx-Token": token}) as owner:
        assert owner.post("/api/v1/workspaces", json={
            "username": "existing-owner", "workspace_id": "local", "password": previous,
            "confirm_install_owner": True,
        }).status_code == 201
        body = {"username": "second-owner", "workspace_id": "local", "password": second}
        rejected = owner.post("/api/v1/workspaces", json=body)
        assert rejected.status_code == 400 and "install owner" in rejected.text.lower()
        assert owner.post("/api/v1/workspaces", json={**body, "confirm_install_owner": "true"}).status_code == 422
        assert not any(row["username"] == "second-owner" for row in owner.get("/api/v1/workspaces").json()["items"])
        saved = owner.post("/api/v1/workspaces", json={**body, "confirm_install_owner": True})
        assert saved.status_code == 201 and saved.json()["install_owner"] is True
        ordinary = {"username": "ordinary", "workspace_id": "beta", "password": secrets.token_urlsafe(24)}
        assert owner.post("/api/v1/workspaces", json={**ordinary, "confirm_install_owner": True}).status_code == 400
        assert owner.post("/api/v1/workspaces", json=ordinary).status_code == 201
    with httpx.Client(base_url=base, trust_env=False, timeout=10) as visitor:
        assert visitor.post("/api/v1/workspaces", json={**body, "confirm_install_owner": True}).status_code == 401
        assert visitor.post("/api/v1/auth/login", json={"username": ordinary["username"], "password": ordinary["password"]}).status_code == 200
        assert visitor.post("/api/v1/workspaces", json={**body, "confirm_install_owner": True}).status_code == 403
    verify_owner_logins(base, previous, second)


def verify_owner_logins(base, previous, second):
    for username, password in (("existing-owner", previous), ("second-owner", second)):
        with httpx.Client(base_url=base, trust_env=False, timeout=10) as user:
            login = user.post("/api/v1/auth/login", json={"username": username, "password": password})
            assert login.status_code == 200 and login.json()["workspace_id"] == "local"
            assert user.get("/api/v1/workspaces").status_code == 200


def verify_drafts(base, token, key, chromium):
    with httpx.Client(base_url=base, headers={"X-Offsetx-Token": token}, trust_env=False, timeout=10) as owner:
        with sync_playwright() as playwright:
            with playwright.chromium.launch(executable_path=chromium, headless=True,
                                            chromium_sandbox=True, args=["--disable-dev-shm-usage"]) as browser:
                with browser.new_context(viewport={"width": 1280, "height": 900}) as context:
                    context.add_init_script("sessionStorage.setItem('offsetx-api-token', " + json.dumps(token) + ")")
                    page = context.new_page()
                    page.route("**/*", lambda route: route.continue_()
                               if route.request.url.startswith(base + "/") else route.abort())
                    errors = []
                    page.on("pageerror", lambda _: errors.append(True))
                    page.goto(base + "/#drafts")
                    expect(page.get_by_text("Create your first campaign", exact=True)).to_be_visible()
                    setup = page.locator("#main-content").get_by_role("link", name="open Connectors", exact=True)
                    setup.click()
                    expect(page).to_have_url(base + "/#connectors")
                    expect(page.locator("#main-content h1")).to_contain_text("Connectors")
                    created = owner.post("/api/v1/campaigns", json={"name": "Synthetic Drafts acceptance"})
                    assert created.status_code == 201
                    cid = created.json()["id"]
                    page.goto(base + "/#drafts")
                    page.reload()
                    expect(page.get_by_label("Active campaign")).to_have_value(cid)
                    expect(page.get_by_text("No drafts found", exact=True)).to_be_visible()
                    expect(page.locator("#main-content").get_by_role("link", name="open Connectors", exact=True)).to_be_visible()
                    page.get_by_role("button", name="Generate sequence", exact=True).first.click()
                    dialog = page.get_by_role("dialog")
                    expect(dialog.get_by_label("Generation mode")).to_have_value("local")
                    expect(dialog.locator('option[value="connectors"]')).to_be_disabled()
                    page.get_by_role("button", name="Cancel", exact=True).click()
                    page.goto(base + "/#settings")
                    panel = page.locator("section").filter(has=page.get_by_role("heading", name="Provider profiles to confirm", exact=True))
                    expect(panel.get_by_text("Old profile to confirm", exact=True)).to_be_visible()
                    expect(panel.get_by_text("Old profile to remove", exact=True)).to_be_visible()
                    panel.get_by_label("API key of Old profile to confirm").fill(key)
                    with page.expect_response(lambda response: response.url.endswith("/provider-profiles/legacy-confirm/confirm")) as confirmation:
                        panel.get_by_role("button", name="Confirm Old profile to confirm as yours").click()
                    assert confirmation.value.status == 200
                    expect(page.get_by_role("status").filter(has_text="connect the provider explicitly in Connectors")).to_be_visible()
                    expect(panel.get_by_text("Old profile to confirm", exact=True)).to_have_count(0)
                    page.once("dialog", lambda dialog: dialog.accept())
                    with page.expect_response(lambda response: response.url.endswith("/provider-profiles/legacy-remove/delete")) as deletion:
                        panel.get_by_role("button", name="Remove Old profile to remove").click()
                    assert deletion.value.status == 200
                    expect(page.get_by_role("heading", name="Provider profiles to confirm")).to_have_count(0)
                    listed = owner.get("/api/v1/provider-profiles")
                    assert listed.status_code == 200
                    assert [(row["id"], row["owner"], row["owner_confirmed"]) for row in listed.json()["items"]] == [("legacy-confirm", "local", True)]
                    assert key not in listed.text
                    providers = owner.get("/api/v1/ai/providers")
                    assert providers.status_code == 200
                    assert not any(row["connected"] and row["enabled"] for row in providers.json()["providers"])
                    page.goto(base + "/#drafts")
                    page.get_by_role("button", name="Generate sequence", exact=True).first.click()
                    expect(page.get_by_role("dialog").locator('option[value="connectors"]')).to_be_disabled()
                    assert not errors, f"Drafts/Settings browser errors: {len(errors)}"
    print("S-06.02.35 PASS: both empty-state paths, legacy confirm/remove, no implicit connector activation", flush=True)


def main():
    root = Path(__file__).resolve().parents[2]
    chromium = os.getenv("OFF_CRM_QA_CHROMIUM") or shutil.which("google-chrome") or shutil.which("chromium")
    assert chromium and os.geteuid() != 0
    assert (root / "frontend/dist/index.html").is_file()
    with tempfile.TemporaryDirectory(prefix="offcrm-drafts-owner-") as directory:
        work = Path(directory)
        token = secrets.token_urlsafe(48)
        previous, second = secrets.token_urlsafe(24), secrets.token_urlsafe(24)
        data = work / "data"
        key = seed_legacy(data)
        env = child_environment(root, data, str(work / "unused.db"), token)
        env.pop("OFFSETX_DATABASE_URL")
        env.pop("OFFSETX_SECRETS_KEY")
        with socket.socket() as listener:
            listener.bind(("127.0.0.1", 0))
            port = listener.getsockname()[1]
        env["OFF_CRM_QA_PORT"] = str(port)
        base = f"http://127.0.0.1:{port}"
        with running_server(root, work, env, base):
            verify_drafts(base, token, key, chromium)
            check_owner_creation(base, token, previous, second)
        with running_server(root, work, env, base):
            verify_owner_logins(base, previous, second)
        print("S-06.02.36 PASS: explicit owner consent, ordinary/anonymous denial, both owner logins after restart", flush=True)


if __name__ == "__main__":
    main()
