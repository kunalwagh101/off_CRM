"""S-06.02.16: real campaign writes, browser selection and independent readback.

Only response timing and selected transport errors are injected. All successful
campaigns, imports and video projects are persisted by the actual application.
"""
import json
import re
import time

import pytest
import requests
from playwright.sync_api import expect

from test_live import EVIDENCE, TEST_API_TOKEN, app_server, chrome, create_campaign, page  # noqa: F401

LIST_URL = re.compile(r"/api/v1/campaigns\?")
SELECTION_KEY = "offsetx-active-campaign"


@pytest.fixture
def workspace(tmp_path):
    with app_server(tmp_path, evidence_name=tmp_path.name + "-server.log") as (url, _):
        with requests.Session() as client:
            client.headers["Authorization"] = "Bearer " + TEST_API_TOKEN
            yield url, client


def seed(client, url, name, kind="email"):
    response = client.post(url + "/api/v1/campaigns", json={"name": name, "kind": kind}, timeout=10)
    response.raise_for_status()
    return response.json()


def read(client, url, path):
    response = client.get(url + "/api/v1" + path, timeout=10)
    response.raise_for_status()
    return response.json()


def wait_for_held_routes(page, pending, count):
    until = time.monotonic() + 10
    while len(pending) < count and time.monotonic() < until:
        page.wait_for_timeout(20)
    assert len(pending) >= count, "The expected campaign refresh never started"


def import_contact(page, name="Correct campaign contact"):
    page.get_by_role("button", name="Import CSV / Excel", exact=True).click()
    dialog = page.get_by_role("dialog", name="Import contacts", exact=True)
    dialog.locator('input[type="file"]').set_input_files({
        "name": "selection-check.csv", "mimeType": "text/csv",
        "buffer": ("full_name,email,company,title,public_hook\n"
                   f"{name},selection@example.test,Example Test,Engineer,Synthetic public hook\n").encode(),
    })
    dialog.get_by_role("button", name="Import contacts", exact=True).click()
    expect(dialog).not_to_be_visible()
    expect(page.get_by_text(name, exact=True)).to_be_visible()


def test_create_refresh_import_and_switch_never_use_the_previous_campaign(page, workspace):
    url, client = workspace
    previous = seed(client, url, "Previous email campaign")
    page.goto(url + "/#campaigns")
    selected = page.get_by_role("combobox", name="Active campaign", exact=True)
    expect(selected).to_have_value(previous["id"])
    old_list = read(client, url, "/campaigns?limit=200")

    pending = []
    page.route(LIST_URL, lambda route: pending.append(route))
    create_campaign(page, url, "New intended campaign")
    wait_for_held_routes(page, pending, 1)
    expect(selected.locator("option:checked")).to_have_text("New intended campaign")
    created_id = selected.input_value()
    assert created_id != previous["id"]

    card = page.locator("section").filter(has=page.get_by_role("heading", name="New intended campaign", exact=True))
    card.get_by_role("button", name="Pause", exact=True).click()
    wait_for_held_routes(page, pending, 2)
    pending[1].fulfill(json=read(client, url, "/campaigns?limit=200"))
    expect(card.get_by_role("button", name="Resume", exact=True)).to_be_visible()
    pending[0].fulfill(json=old_list)
    expect(selected).to_have_value(created_id)
    assert page.evaluate("localStorage.getItem('offsetx-active-campaign')") == created_id
    page.unroute(LIST_URL)
    page.reload()
    expect(selected).to_have_value(created_id)

    page.goto(url + "/#contacts")
    import_contact(page)
    assert read(client, url, f"/campaigns/{created_id}/contacts")["total"] == 1
    assert read(client, url, f"/campaigns/{previous['id']}/contacts")["total"] == 0

    # A form opened for one campaign cannot survive under another campaign's
    # heading or send its old contact ID to that campaign's update endpoint.
    page.get_by_role("button", name="Correct campaign contact", exact=True).click()
    dialog = page.get_by_role("dialog", name="Edit contact", exact=True)
    expect(dialog).to_be_visible()
    dialog.get_by_label("Full name", exact=True).fill("Unsaved edit from previous context")
    selected.select_option(previous["id"])
    expect(dialog).not_to_be_visible()
    expect(page.get_by_text("Correct campaign contact", exact=True)).not_to_be_visible()
    expect(page.get_by_text("No contacts found", exact=True)).to_be_visible()
    selected.select_option(created_id)
    expect(page.get_by_text("Correct campaign contact", exact=True)).to_be_visible()
    assert read(client, url, f"/campaigns/{created_id}/contacts")["items"][0]["full_name"] == "Correct campaign contact"
    (EVIDENCE / "campaign-selection-import.json").write_text(json.dumps({
        "created_campaign": created_id, "previous_campaign": previous["id"],
        "created_contacts": 1, "previous_contacts": 0,
        "out_of_order_responses": "ignored", "stale_edit_form": "closed", "reload": "preserved",
    }, indent=2))


def test_a_successful_creation_survives_a_failed_list_refresh(page, workspace):
    url, client = workspace
    previous = seed(client, url, "Existing campaign")
    page.goto(url + "/#campaigns")
    selected = page.get_by_role("combobox", name="Active campaign", exact=True)
    expect(selected).to_have_value(previous["id"])
    page.route(LIST_URL, lambda route: route.fulfill(status=429, json={"detail": "Synthetic refresh rate limit; retry the request."}))
    create_campaign(page, url, "Saved before refresh failed")
    expect(page.get_by_text("Could not refresh campaigns", exact=True)).to_be_visible()
    expect(selected.locator("option:checked")).to_have_text("Saved before refresh failed")
    created_id = selected.input_value()
    assert read(client, url, f"/campaigns/{created_id}")["name"] == "Saved before refresh failed"
    page.unroute(LIST_URL)
    page.get_by_role("button", name="Retry campaigns", exact=True).click()
    expect(page.get_by_text("Could not refresh campaigns", exact=True)).not_to_be_visible()
    page.reload()
    expect(selected).to_have_value(created_id)


def test_manual_switch_wins_over_an_earlier_creation_response(page, workspace):
    url, client = workspace
    first = seed(client, url, "First campaign")
    second = seed(client, url, "User's chosen campaign")
    page.goto(url + "/#campaigns")
    selected = page.get_by_role("combobox", name="Active campaign", exact=True)
    expect(selected).to_be_enabled()
    selected.select_option(first["id"])
    pending = []

    def hold_created_response(route):
        if route.request.method == "POST":
            # The real server has saved the row. Hold only its response to the UI.
            response = route.fetch()
            assert response.status == 201
            pending.append((route, response))
        else:
            route.continue_()

    page.route(re.compile(r"/api/v1/campaigns$"), hold_created_response)
    page.get_by_role("button", name="Create campaign", exact=True).first.click()
    dialog = page.get_by_role("dialog", name="Create campaign", exact=True)
    dialog.get_by_label("Campaign name", exact=True).fill("Slow creation")
    dialog.get_by_role("button", name="Create campaign", exact=True).click()
    wait_for_held_routes(page, pending, 1)
    dialog.get_by_role("button", name="Cancel", exact=True).click()
    selected.select_option(second["id"])
    route, response = pending[0]
    route.fulfill(response=response)
    expect(page.get_by_role("heading", name="Slow creation", exact=True)).to_be_visible()
    expect(selected).to_have_value(second["id"])
    page.reload()
    expect(selected).to_have_value(second["id"])


def test_saved_campaign_beyond_first_page_owns_the_video_project(page, workspace):
    url, client = workspace
    saved = seed(client, url, "Older image campaign", kind="image")
    # Campaign ordering uses whole-second timestamps. Put later fixtures in a
    # later second so a tie cannot accidentally keep this row on the first page.
    time.sleep(1.05)
    for index in range(200):
        seed(client, url, f"Newer email campaign {index:03d}")
    first_page = read(client, url, "/campaigns?limit=200")
    assert first_page["total"] == 201
    assert saved["id"] not in {row["id"] for row in first_page["items"]}
    page.add_init_script(f"localStorage.setItem({json.dumps(SELECTION_KEY)}, {json.dumps(saved['id'])});")
    page.goto(url + "/#videoeditor")
    selected = page.get_by_role("combobox", name="Active campaign", exact=True)
    expect(selected).to_have_value(saved["id"])
    with page.expect_response(lambda response: response.request.method == "POST" and response.url.endswith(f"/campaigns/{saved['id']}/video-projects")) as event:
        page.get_by_role("button", name="Empty project", exact=True).click()
    response = event.value
    assert response.status == 201, response.text()
    project_id = response.json()["id"]
    assert read(client, url, f"/campaigns/{saved['id']}/video-projects")["items"][0]["id"] == project_id
    page.reload()
    expect(selected).to_have_value(saved["id"])
    (EVIDENCE / "campaign-selection-video.json").write_text(json.dumps({
        "saved_campaign": saved["id"], "campaign_total": 201, "first_page_limit": 200,
        "project": project_id, "campaign_kind": "image", "reload": "preserved",
    }, indent=2))


@pytest.mark.parametrize("has_fallback", [False, True])
def test_a_confirmed_missing_saved_campaign_has_a_visible_fallback(page, workspace, has_fallback):
    url, client = workspace
    fallback = seed(client, url, "Remaining campaign") if has_fallback else None
    page.add_init_script("localStorage.setItem('offsetx-active-campaign', 'confirmed-missing-campaign');")
    page.goto(url + "/#contacts")
    selected = page.get_by_role("combobox", name="Active campaign", exact=True)
    expect(selected).to_be_enabled()
    expect(page.get_by_text(re.compile("The previous campaign is no longer available"))).to_be_visible()
    if fallback:
        expect(selected).to_have_value(fallback["id"])
        assert page.evaluate("localStorage.getItem('offsetx-active-campaign')") == fallback["id"]
    else:
        expect(selected).to_have_value("")
        expect(page.get_by_role("heading", name="Create your first campaign", exact=True)).to_be_visible()
        assert page.evaluate("localStorage.getItem('offsetx-active-campaign')") is None
