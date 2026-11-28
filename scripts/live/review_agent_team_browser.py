"""Disposable actual-app acceptance for the agent-team owner screens.

No paid model, email, image generation or publishing call is made here.
"""

import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

from playwright.sync_api import expect, sync_playwright
from review_contacts_browser import ROOT, BASE, TOKEN, _wait_for_server


def verify(page, width):
    page.goto(BASE + "/#agentteam", wait_until="domcontentloaded")
    page.get_by_role("heading", name="Agent team", exact=True).wait_for(timeout=5000)
    with page.expect_response(
        lambda response: "/agent-team/provision" in response.url
    ) as provision:
        page.get_by_role("button", name="Set up five roles").click()
    assert provision.value.status == 200, provision.value.text()
    page.get_by_label("Companion", exact=True).select_option(label="Scout")
    page.get_by_label("Profile name", exact=True).fill("Research " + str(width))
    page.get_by_label("Profile instructions", exact=True).fill(
        "Check public sources before drawing conclusions."
    )
    page.get_by_role("button", name="Create companion", exact=True).click()
    page.get_by_label("Companion", exact=True).select_option(
        label="Research " + str(width)
    )
    page.get_by_label("Procedure name", exact=True).fill("Citations " + str(width))
    page.get_by_label("Procedure text", exact=True).fill(
        "Cite two independent public sources."
    )
    page.get_by_role("button", name="Create procedure", exact=True).click()
    page.get_by_label("Citations " + str(width), exact=True).check()
    page.get_by_role("button", name="Preview selected context", exact=True).click()
    page.get_by_label("Context preview", exact=True).get_by_text(
        "Cite two independent public sources.", exact=False
    ).wait_for()
    page.reload(wait_until="domcontentloaded")
    page.get_by_label("Companion", exact=True).select_option(
        label="Research " + str(width)
    )
    assert not page.get_by_label("Citations " + str(width), exact=True).is_checked()
    page.get_by_label("Role", exact=True).select_option("Scout")
    page.get_by_role("button", name="Run selected role", exact=True).click()
    page.get_by_label("Role result", exact=True).get_by_text(
        "Observed topics", exact=False
    ).wait_for()
    # F-04.01/D-480 RED: switching companions must not leave the previous
    # role's result visible as if it belonged to the newly selected profile.
    page.get_by_label("Companion", exact=True).select_option(label="Scout")
    expect(page.get_by_label("Role result", exact=True)).to_have_count(0)
    page.get_by_label("Companion", exact=True).select_option(
        label="Research " + str(width)
    )
    page.get_by_label("Role", exact=True).select_option("Maker")
    role_campaign = page.get_by_label("Role campaign", exact=True)
    expect(role_campaign).to_contain_text("QA image")
    assert (
        "QA email" not in role_campaign.inner_text()
        and "QA distribution" not in role_campaign.inner_text()
    )
    role_campaign.select_option(label="QA image")
    # D-490: simulate a lost HTTP response to a consequential Maker action.
    # Abort BEFORE backend execution, then reload and replay a synthetic
    # response. Both browser requests must carry exactly the same receipt.
    topic = "Safe synthetic Maker retry with no provider calls"
    page.get_by_label("Video topic", exact=True).fill(topic)
    maker_keys = []
    def intercept_maker(route):
        if route.request.post_data_json.get("role") != "Maker":
            route.continue_()
            return
        maker_keys.append(route.request.headers.get("idempotency-key"))
        if len(maker_keys) == 1:
            route.abort("failed")
        else:
            route.fulfill(
                status=200, content_type="application/json",
                body='{"role":"Maker","status":"needs_review","project":{"name":"Synthetic result only"}}',
            )
    page.route("**/api/v1/agent-team/execute", intercept_maker)
    page.get_by_role("button", name="Run selected role", exact=True).click()
    expect(page.get_by_role("alert")).to_be_visible()
    page.reload(wait_until="domcontentloaded")
    # D-494: the chosen companion is unrelated to the role endpoint. Switch
    # profiles after a lost response; this still must replay the same key.
    page.get_by_label("Companion", exact=True).select_option(label="Scout")
    page.get_by_label("Role", exact=True).select_option("Maker")
    page.get_by_label("Role campaign", exact=True).select_option(label="QA image")
    page.get_by_label("Video topic", exact=True).fill(topic)
    page.get_by_role("button", name="Run selected role", exact=True).click()
    expect(page.get_by_label("Role result", exact=True)).to_contain_text("Timeline ready for review")
    assert len(maker_keys) == 2 and maker_keys[0] and maker_keys[0] == maker_keys[1], (
        "A browser reload changed the key for the same uncertain Maker action"
    )
    assert page.evaluate(
        "Object.keys(sessionStorage).filter(k => k.startsWith('offcrm-agent-role-pending-v1-')).length"
    ) == 0, "Successful retry must clear the pending receipt from the tab"
    page.unroute("**/api/v1/agent-team/execute", intercept_maker)

    # A v1 tab may already have an uncertain receipt hashed with an earlier
    # companion ID. Recreate that old storage record, reload and switch the
    # picker. The migrated request MUST reuse the old key, not create a new
    # paid/media effect. Everything is synthetic and intercepted.
    legacy_topic = "Synthetic old receipt after companion change"
    legacy_key = "legacy-role-once-" + str(width)
    page.get_by_label("Companion", exact=True).select_option(label="Research " + str(width))
    page.get_by_label("Video topic", exact=True).fill(legacy_topic)
    page.evaluate("""async ({key, topic}) => {
      const companion = document.querySelector('select[aria-label="Companion"]').value;
      const campaign_id = document.querySelector('select[aria-label="Role campaign"]').value;
      const intent = {workspace: "local", actor: "", companion,
                      payload: {role: "Maker", campaign_id, topic}};
      const bytes = new TextEncoder().encode(JSON.stringify(intent));
      const hash = await crypto.subtle.digest("SHA-256", bytes);
      const digest = [...new Uint8Array(hash)].map(n => n.toString(16).padStart(2,"0")).join("");
      sessionStorage.setItem("offcrm-agent-role-pending-v1-" + digest,
                             JSON.stringify({fingerprint: JSON.stringify(digest), key}));
    }""", {"key": legacy_key, "topic": legacy_topic})
    page.reload(wait_until="domcontentloaded")
    page.get_by_label("Companion", exact=True).select_option(label="Scout")
    page.get_by_label("Role", exact=True).select_option("Maker")
    page.get_by_label("Role campaign", exact=True).select_option(label="QA image")
    page.get_by_label("Video topic", exact=True).fill(legacy_topic)
    legacy_keys = []
    def intercept_legacy(route):
        if route.request.post_data_json.get("role") == "Maker":
            legacy_keys.append(route.request.headers.get("idempotency-key"))
            route.fulfill(status=200, content_type="application/json",
                          body='{"role":"Maker","status":"needs_review","project":{"name":"Synthetic legacy result"}}')
        else:
            route.continue_()
    page.route("**/api/v1/agent-team/execute", intercept_legacy)
    page.get_by_role("button", name="Run selected role", exact=True).click()
    expect(page.get_by_label("Role result", exact=True)).to_contain_text("Timeline ready for review")
    assert legacy_keys == [legacy_key], "Migrating a v1 receipt changed the original request key"
    assert page.evaluate(
        "Object.keys(sessionStorage).filter(k => k.startsWith('offcrm-agent-role-pending-v1-')).length"
    ) == 0, "Migrated legacy and canonical receipts must both clear on success"
    page.unroute("**/api/v1/agent-team/execute", intercept_legacy)
    page.get_by_label("Companion", exact=True).select_option(label="Research " + str(width))
    page.get_by_label("Role", exact=True).select_option("Poster")
    expect(role_campaign).to_have_value("")
    assert "QA image" not in role_campaign.inner_text()
    expect(role_campaign).to_contain_text("QA distribution")
    # Real read-only Analyst path: existing distribution campaign, no provider
    # credential, model request, external post or mutation.
    page.get_by_label("Role", exact=True).select_option("Analyst")
    page.get_by_label("Role campaign", exact=True).select_option(label="QA distribution")
    page.get_by_role("button", name="Run selected role", exact=True).click()
    page.get_by_label("Role result", exact=True).get_by_text(
        "Measured campaign performance", exact=False
    ).wait_for()
    page.get_by_label("Role", exact=True).select_option("Scout")
    # Simulate a concurrent owner changing the memory scope after this form
    # loaded. Renaming must not write the old scope back from the stale tab.
    profile_id = page.get_by_label("Companion", exact=True).input_value()
    new_scope = "qa-scope-" + str(width)
    updated = page.request.patch(
        BASE + "/api/v1/companions/" + profile_id,
        headers={"Authorization": "Bearer " + TOKEN},
        data={"memory_scope": new_scope},
    )
    assert updated.status == 200, updated.text()
    page.get_by_label("Edit profile name", exact=True).fill(
        "Research revised " + str(width)
    )
    with page.expect_response(
        lambda response: response.url.endswith("/companions/" + profile_id)
        and response.request.method == "PATCH"
    ) as renamed:
        page.get_by_role("button", name="Save profile", exact=True).click()
    assert renamed.value.status == 200, renamed.value.text()
    assert renamed.value.request.post_data_json == {"name": "Research revised " + str(width)}
    assert renamed.value.json()["memory_scope"] == new_scope
    page.get_by_label("Companion", exact=True).select_option(
        label="Research revised " + str(width)
    )
    expect(page.get_by_label("Memory scope", exact=True)).to_have_value(new_scope)
    page.get_by_role("button", name="Disable companion", exact=True).click()
    page.get_by_role("button", name="Enable companion", exact=True).wait_for()
    expect(page.get_by_role("button", name="Preview selected context")).to_be_disabled()
    page.get_by_role("button", name="Enable companion", exact=True).click()
    expect(page.get_by_role("button", name="Preview selected context")).to_be_enabled()
    page.get_by_role("button", name="Edit Citations " + str(width), exact=True).click()
    page.get_by_label("Procedure text", exact=True).fill(
        "Revised: verify two independent citations."
    )
    page.get_by_role("button", name="Save procedure", exact=True).click()
    checkbox = page.get_by_label("Citations " + str(width), exact=True)
    checkbox.check()
    page.get_by_role("button", name="Preview selected context", exact=True).click()
    expect(page.get_by_label("Context preview", exact=True)).to_contain_text(
        "Revised: verify two independent citations."
    )
    page.get_by_role(
        "button", name="Disable Citations " + str(width), exact=True
    ).click()
    expect(checkbox).to_be_disabled()
    expect(checkbox).not_to_be_checked()
    page.get_by_role(
        "button", name="Enable Citations " + str(width), exact=True
    ).click()
    expect(checkbox).to_be_enabled()
    expect(checkbox).not_to_be_checked()
    page.get_by_label("Companion fact", exact=True).fill(
        "Approved verification fact " + str(width)
    )
    page.get_by_label("Approve this fact for future context", exact=True).check()
    with page.expect_response(
        lambda response: (
            response.url.endswith("/memory") and response.request.method == "POST"
        )
    ) as saved_memory:
        page.get_by_role("button", name="Save scoped memory", exact=True).click()
    assert saved_memory.value.status == 201, saved_memory.value.text()
    page.get_by_role("button", name="Preview selected context", exact=True).click()
    expect(page.get_by_label("Context preview", exact=True)).to_contain_text(
        "Approved verification fact " + str(width)
    )
    page.get_by_label("Child 1 companion", exact=True).select_option(label="Scout")
    page.get_by_label("Child 1 goal", exact=True).fill("Verify source quality")
    page.get_by_role("button", name="Add child", exact=True).click()
    page.get_by_label("Child 2 companion", exact=True).select_option(label="Scout")
    page.get_by_label("Child 2 goal", exact=True).fill("Check counter-evidence")
    page.get_by_role("button", name="Run bounded reasoning", exact=True).click()
    expect(page.get_by_role("alert")).to_contain_text("Choose different children")
    page.get_by_role("button", name="Add child", exact=True).click()
    expect(page.get_by_role("button", name="Add child", exact=True)).to_be_disabled()
    assert (
        "Research revised"
        not in page.get_by_label("Child 1 companion", exact=True).inner_text()
    )
    page.get_by_role(
        "button", name="Delete Citations " + str(width), exact=True
    ).click()
    page.get_by_role("button", name="Confirm deletion", exact=True).click()
    expect(checkbox).to_have_count(0)
    assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
    screenshots = ROOT / "work" / "three-features"
    screenshots.mkdir(parents=True, exist_ok=True)
    page.screenshot(path=str(screenshots / f"agent-team-{width}.png"))
    page.get_by_role("button", name="Delete companion", exact=True).click()
    page.get_by_role("button", name="Confirm deletion", exact=True).click()
    expect(page.get_by_label("Companion", exact=True)).not_to_contain_text(
        "Research revised " + str(width)
    )
    print(
        f"PASS Agent team {width}px: profile/procedure CRUD, enable/disable, scoped approved memory, explicit context, role prerequisites, child bounds, deletion and Scout read-only",
        flush=True,
    )


def main():
    with tempfile.TemporaryDirectory(prefix="offcrm-agent-team-") as folder:
        env = os.environ.copy()
        for key in (
            "OFFSETX_DATABASE_URL",
            "OFFSETX_SECRETS_KEY",
            "OFFSETX_DEMO_USERNAME",
            "OFFSETX_DEMO_PASSWORD",
            "OFFSETX_SESSION_SECRET",
            "RENDER_EXTERNAL_HOSTNAME",
        ):
            env.pop(key, None)
        env.update(
            {
                "OFFSETX_DATA_DIR": str(Path(folder) / "data"),
                "OFFSETX_OUTREACH_DB": str(Path(folder) / "data" / "crm.db"),
                "OFFSETX_LOCAL_API_TOKEN": TOKEN,
                "OFFSETX_WEB_HOST": "127.0.0.1",
                "OFFSETX_ALLOWED_HOSTS": "127.0.0.1,localhost",
                "OFFSETX_PRODUCTION": "0",
            }
        )
        proc = subprocess.Popen(
            [
                str(ROOT / ".venv/bin/python"),
                "-m",
                "offsetx_apollo_builder.web_cli",
                "--host",
                "127.0.0.1",
                "--port",
                "8766",
            ],
            cwd=ROOT,
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.STDOUT,
        )
        try:
            _wait_for_server(proc)
            import httpx

            with httpx.Client(
                base_url=BASE, headers={"Authorization": "Bearer " + TOKEN}
            ) as client:
                for kind in ("email", "image", "distribution"):
                    response = client.post(
                        "/api/v1/campaigns", json={"name": "QA " + kind, "kind": kind}
                    )
                    assert response.status_code == 201, response.text
            with sync_playwright() as p:
                browser = p.chromium.launch(
                    executable_path=shutil.which("chromium"),
                    headless=True,
                    args=["--no-sandbox", "--disable-dev-shm-usage"],
                )
                try:
                    for width in (1280, 390):
                        context = browser.new_context(
                            viewport={"width": width, "height": 1000}
                        )
                        context.add_init_script(
                            'sessionStorage.setItem("offsetx-api-token", '
                            + json.dumps(TOKEN)
                            + ")"
                        )
                        page = context.new_page()
                        page.set_default_timeout(10000)
                        try:
                            verify(page, width)
                        except Exception:
                            print(page.locator("body").inner_text(), flush=True)
                            raise
                        finally:
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
