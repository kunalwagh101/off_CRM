"""Mandatory acceptance tests against real services, using synthetic data only.

Run explicitly. There are no environment skips: missing infrastructure fails.
No provider credentials, customer contacts or production database are used.
"""
from contextlib import contextmanager
import asyncio
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
from urllib.parse import quote

import pytest
import requests
from playwright.sync_api import expect, sync_playwright

from offsetx_apollo_builder.ai.sandbox import SandboxPolicy, SandboxWorkspace
from offsetx_apollo_builder.browser.session import find_browser


ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = Path(os.environ["OFF_CRM_LIVE_EVIDENCE"])
TEST_API_TOKEN = "synthetic-isolated-browser-audit-token-000000"
ROUTES = (
    "dashboard", "campaigns", "discovery", "contacts", "drafts", "queue",
    "deliverability", "sales", "experiments", "imagereview", "videoeditor",
    "posting", "connectors", "egress", "memory", "recall", "ai", "settings",
)


def run(command, timeout=30):
    return subprocess.run(command, capture_output=True, text=True, timeout=timeout)


def container(policy, workspace, source):
    image = os.environ["OFF_CRM_SANDBOX_TEST_IMAGE"]
    assert "@sha256:" in image, "The tested image must be immutable"
    # Code lives in a read-only input file, preserving the argument-size limit.
    (workspace.inbox / "probe.py").write_text(source)
    return run(policy.docker_command(
        image=image, workspace=workspace, command=["python", "/inbox/probe.py"],
    ))


@pytest.fixture
def workspace():
    # Match the real application's mkdir/umask behaviour, including ownership.
    with tempfile.TemporaryDirectory(prefix="offcrm-sandbox-") as folder:
        item = SandboxWorkspace(Path(folder) / "job").prepare()
        yield item


def test_sandbox_code_starts_as_unprivileged_user_with_caps_removed(workspace):
    result = container(SandboxPolicy(), workspace,
        "import os,json\nfrom pathlib import Path\n"
        "status=Path('/proc/self/status').read_text()\n"
        "fields=dict(line.split(':',1) for line in status.splitlines() if ':' in line)\n"
        "assert os.geteuid()==65534\nassert int(fields['CapEff'].strip(),16)==0\n"
        "assert fields['NoNewPrivs'].strip()=='1'\n"
        "print(json.dumps({'started':True,'uid':os.geteuid(),'caps':0,'no_new_privileges':True}))\n")
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["started"] is True


def test_sandbox_work_directory_really_accepts_output(workspace):
    result = container(SandboxPolicy(), workspace,
        "from pathlib import Path\nPath('/work/result.txt').write_text('completed')\nprint('WROTE_OUTPUT')\n")
    assert result.returncode == 0, result.stderr
    assert (workspace.work / "result.txt").read_text() == "completed"


def test_sandbox_root_and_inbox_are_readonly_and_store_is_absent(workspace):
    workspace.store.mkdir()
    (workspace.store / "private-canary").write_text("synthetic-private-canary")
    result = container(SandboxPolicy(), workspace,
        "from pathlib import Path\n"
        "for path in ('/inbox/forbidden.txt','/forbidden.txt'):\n"
        " try:\n  Path(path).write_text('forbidden')\n"
        " except OSError:\n  pass\n"
        " else:\n  raise AssertionError('write unexpectedly allowed: '+path)\n"
        "assert not Path('/store').exists()\n"
        "assert not Path('/var/run/docker.sock').exists()\nprint('BOUNDARIES_VERIFIED')\n")
    assert result.returncode == 0, result.stderr
    assert "BOUNDARIES_VERIFIED" in result.stdout


def test_sandbox_network_is_denied_with_a_working_positive_control(workspace):
    image = os.environ["OFF_CRM_SANDBOX_TEST_IMAGE"]
    name = "offcrm-network-probe-" + secrets.token_hex(5)
    started = run(["docker", "run", "--detach", "--rm", "--pull=never",
        "--name", name, "--network=bridge", "--read-only", "--cap-drop=ALL",
        "--security-opt=no-new-privileges", "--user=65534:65534", image,
        "python", "-m", "http.server", "9000"])
    assert started.returncode == 0, started.stderr
    try:
        inspected = run(["docker", "inspect", name])
        assert inspected.returncode == 0, inspected.stderr
        address = json.loads(inspected.stdout)[0]["NetworkSettings"]["IPAddress"]
        assert address
        probe = (
            "import socket,time\n"
            "for attempt in range(20):\n"
            f" try:\n  s=socket.create_connection(({address!r},9000),timeout=1); s.close(); break\n"
            " except OSError:\n  time.sleep(.1)\n"
            "else:\n raise AssertionError('positive control cannot connect')\n"
            "print('CONNECTED')\n"
        )
        control = container(SandboxPolicy(network="bridge"), workspace, probe)
        assert control.returncode == 0, control.stderr
        assert "CONNECTED" in control.stdout
        denied = container(SandboxPolicy(), workspace,
            "import socket\nprint('PROBE_STARTED',flush=True)\n"
            f"try:\n socket.create_connection(({address!r},9000),timeout=3)\n"
            "except OSError as error:\n print('NETWORK_DENIED',type(error).__name__)\n"
            "else:\n raise AssertionError('network escaped')\n")
        assert denied.returncode == 0, denied.stderr
        assert "PROBE_STARTED" in denied.stdout and "NETWORK_DENIED" in denied.stdout
    finally:
        run(["docker", "rm", "--force", name])


def test_enter_on_a_real_form_requires_confirmation(tmp_path):
    from offsetx_apollo_builder.browser.page import Page
    from offsetx_apollo_builder.browser.session import free_port, open_session

    async def check():
        session = await open_session(profile_dir=str(tmp_path / "profile"),
            port=free_port(), headless=True)
        try:
            _, sid = await session.new_tab()
            page = Page(connection=session.connection, session_id=sid)
            await page.start()
            html = (
                # Chat/composer forms commonly submit from an Enter keydown
                # handler. This is a synthetic local action, never a message.
                '<form onkeydown="if(event.key===\'Enter\'){event.preventDefault();this.requestSubmit()}" '
                'onsubmit="event.preventDefault(); document.getElementById(\'result\').textContent=\'SUBMITTED\'">'
                '<label>Message<input type="text" name="message"></label>'
                '<button type="submit">Send message</button></form><p id="result">UNSENT</p>'
            )
            await page.goto("data:text/html," + quote(html))
            snapshot = await page.snapshot()
            field = next(node for node in snapshot.actions if node.name == "Message")
            await page.type(field.handle, "synthetic message")
            result = await page.press("Enter")
            visible = (await page.read()).text
            assert result.needs_confirmation and "SUBMITTED" not in visible, {
                "needs_confirmation": result.needs_confirmation, "visible_result": visible}
        finally:
            await session.close(quit_browser=True)

    asyncio.run(check())


@contextmanager
def app_server(directory, *, login=False, evidence_name=None):
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        port = listener.getsockname()[1]
    env = {k: v for k, v in os.environ.items() if not k.startswith("OFFSETX_")}
    env.update({"OFFSETX_DATA_DIR": str(directory / "data"),
        "OFFSETX_OUTREACH_DB": str(directory / "crm.db"),
        "PYTHONPATH": str(ROOT)})
    password = "synthetic-test-password-only"
    if login:
        env.update({"OFFSETX_DEMO_USERNAME": "audit-user",
            "OFFSETX_DEMO_PASSWORD": password,
            "OFFSETX_SESSION_SECRET": secrets.token_hex(32)})
    else:
        env["OFFSETX_LOCAL_API_TOKEN"] = TEST_API_TOKEN
    log = open(directory / "server.log", "w")
    process = subprocess.Popen([sys.executable, "-m", "offsetx_apollo_builder.web_cli",
        "--host", "127.0.0.1", "--port", str(port)], cwd=ROOT, env=env,
        stdout=log, stderr=subprocess.STDOUT)
    url = f"http://127.0.0.1:{port}"
    try:
        for _ in range(100):
            assert process.poll() is None, "Test app exited; inspect server.log"
            try:
                if requests.get(url + "/health/ready", timeout=1).status_code == 200:
                    break
            except requests.RequestException:
                pass
            time.sleep(.1)
        else:
            pytest.fail("Test app did not become ready")
        yield url, password
    finally:
        process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()
        log.close()
        log_name = evidence_name or ("login-server.log" if login else "frontend-server.log")
        (EVIDENCE / log_name).write_text(
            (directory / "server.log").read_text())


@pytest.fixture(scope="module")
def app(tmp_path_factory):
    with app_server(tmp_path_factory.mktemp("frontend")) as (url, _):
        yield url


@pytest.fixture(scope="module")
def chrome():
    assert os.geteuid() != 0, "Do not disable the Chromium sandbox to pass these tests"
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(executable_path=find_browser(),
            headless=True, chromium_sandbox=True)
        yield browser
        browser.close()


@pytest.fixture
def page(chrome, request):
    # The default fixture is now authenticated, matching main's secure API.
    # Session-login fixtures do not configure this token, so their login checks
    # still require actual credentials and cookies.
    context = chrome.new_context(viewport={"width": 1440, "height": 1000},
        extra_http_headers={"Authorization": "Bearer " + TEST_API_TOKEN})
    page = context.new_page()
    page.set_default_timeout(15000)
    errors = []
    server_errors = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    page.on("response", lambda response: server_errors.append(
        f"{response.status} {response.url}") if response.status >= 500 else None)
    try:
        yield page
    finally:
        name = request.node.name.replace("/", "_")
        page.screenshot(path=str(EVIDENCE / f"{name}.png"), full_page=True)
        (EVIDENCE / f"{name}.json").write_text(json.dumps({
            "javascript_errors": errors, "server_errors": server_errors,
            "url": page.url}, indent=2))
        context.close()
    assert not errors, errors
    assert not server_errors, server_errors


@pytest.mark.parametrize("route", ROUTES)
def test_every_frontend_screen_renders(page, app, route):
    response = page.goto(app + "/#" + route)
    assert response.status == 200
    expect(page.get_by_role("navigation", name="Main navigation", exact=True)).to_be_visible()
    if route in {"imagereview", "videoeditor"}:
        expect(page.locator("main").get_by_text("Pick a campaign", exact=True)).to_be_visible()
    else:
        expect(page.locator("main").get_by_role("heading").first).to_be_visible()
    page.wait_for_load_state("networkidle")
    assert page.locator("main").inner_text().strip()


def test_connectors_can_load_its_gmail_status(page, app):
    with page.expect_response(lambda response: response.url.endswith("/status")) as loaded:
        page.goto(app + "/#connectors")
    response = loaded.value
    assert response.status == 200, {
        "url": response.url, "status": response.status, "body": response.text()}
    assert "gmail_configured" in response.json(), response.json()


def create_campaign(page, app, name, kind="email"):
    page.goto(app + "/#campaigns")
    page.get_by_role("button", name="Create campaign", exact=True).first.click()
    dialog = page.get_by_role("dialog")
    dialog.get_by_label("Campaign name", exact=True).fill(name)
    dialog.get_by_label("Kind").select_option(kind)
    dialog.get_by_role("button", name="Create campaign", exact=True).click()
    expect(dialog).not_to_be_visible()
    expect(page.get_by_role("heading", name=name, exact=True)).to_be_visible()


def test_campaign_create_pause_and_reload_persist(page, app):
    name = "Synthetic verification " + secrets.token_hex(3)
    create_campaign(page, app, name)
    card = page.locator("section").filter(has=page.get_by_role("heading", name=name, exact=True))
    card.get_by_role("button", name="Pause", exact=True).click()
    expect(card.get_by_role("button", name="Resume", exact=True)).to_be_visible()
    page.reload()
    expect(page.get_by_role("heading", name=name, exact=True)).to_be_visible()
    expect(card.get_by_role("button", name="Resume", exact=True)).to_be_visible()


def test_contacts_import_and_search_work_in_the_browser(page, app):
    name = "Synthetic contact import " + secrets.token_hex(3)
    create_campaign(page, app, name)
    # Verify import into the explicitly selected campaign. Automatic selection
    # after creation has its own regression below, so it cannot hide a failure.
    selected = page.get_by_role("combobox", name="Active campaign", exact=True)
    selected.select_option(label=name)
    campaign_id = selected.input_value()
    page.goto(app + "/#contacts")
    page.get_by_role("button", name="Import CSV / Excel", exact=True).click()
    dialog = page.get_by_role("dialog")
    dialog.locator('input[type="file"]').set_input_files({
        "name": "synthetic-contacts.csv", "mimeType": "text/csv",
        "buffer": b"full_name,email,company,title,public_hook\nAudit Contact,audit@example.test,Example Test,Engineer,Synthetic public hook\n",
    })
    dialog.get_by_role("button", name="Import contacts", exact=True).click()
    expect(dialog).not_to_be_visible()
    expect(page.get_by_text("Audit Contact", exact=True)).to_be_visible()
    # Independent API readback must use the same authenticated identity as
    # the browser; an anonymous 401 cannot verify the saved contact.
    records = requests.get(app + f"/api/v1/campaigns/{campaign_id}/contacts",
        headers={"Authorization": "Bearer " + TEST_API_TOKEN}, timeout=10)
    assert records.status_code == 200
    assert any(row["full_name"] == "Audit Contact" for row in records.json()["items"])
    page.reload()
    expect(page.get_by_text("Audit Contact", exact=True)).to_be_visible()
    page.get_by_label("Search contacts", exact=True).fill("no-matching-record")
    page.get_by_role("button", name="Search", exact=True).click()
    expect(page.get_by_text("Audit Contact", exact=True)).not_to_be_visible()
    page.get_by_label("Search contacts", exact=True).fill("Audit Contact")
    page.get_by_role("button", name="Search", exact=True).click()
    expect(page.get_by_text("Audit Contact", exact=True)).to_be_visible()


def export_video(page, app):
    name = "Synthetic video " + secrets.token_hex(3)
    create_campaign(page, app, name, kind="image")
    page.get_by_role("combobox", name="Active campaign", exact=True).select_option(label=name)
    page.goto(app + "/#videoeditor")
    page.get_by_role("button", name="Empty project", exact=True).click()
    page.get_by_role("button", name="Colour", exact=True).click()
    export = page.get_by_role("button", name="Export", exact=True)
    expect(export).to_be_enabled()
    with page.expect_response(lambda response: "/renders" in response.url and
            response.request.method == "POST", timeout=90000) as completed:
        export.click()
    response = completed.value
    assert response.status == 201, response.text()
    result = response.json()
    render_id = result["render_id"]
    (EVIDENCE / f"video-export-{render_id}.json").write_text(json.dumps(result, indent=2))
    # Preserve failed exports too, and independently count decoded frames.
    # The application's header probe alone cannot establish a playable file.
    stored = requests.get(app + f"/api/v1/video-renders/{render_id}/file",
        headers={"Authorization": "Bearer " + TEST_API_TOKEN}, timeout=10)
    assert stored.status_code == 200, stored.text
    media = EVIDENCE / f"video-export-{render_id}.webm"
    media.write_bytes(stored.content)
    ffprobe = shutil.which("ffprobe")
    assert ffprobe, "Install FFmpeg/ffprobe to verify the actual encoded frames"
    decoded = run([ffprobe, "-v", "error", "-count_frames", "-select_streams", "v:0",
        "-show_entries", "stream=codec_name,width,height,nb_read_frames:format=duration",
        "-of", "json", str(media)])
    (EVIDENCE / f"video-decoded-{render_id}.json").write_text(json.dumps({
        "returncode": decoded.returncode, "stdout": decoded.stdout,
        "stderr": decoded.stderr, "version": run([ffprobe, "-version"]).stdout.splitlines()[0],
    }, indent=2))
    assert decoded.returncode == 0, decoded.stderr
    stream = json.loads(decoded.stdout)["streams"][0]
    assert int(stream["nb_read_frames"]) == 60, stream
    assert (stream["width"], stream["height"]) == (1080, 1920), stream
    assert result["passed"] is True, result


def test_video_editor_exports_a_real_webm_and_passes_server_gates(page, app):
    export_video(page, app)


def test_video_export_in_a_fresh_workspace(page, tmp_path):
    # Separate codec acceptance from the shared-workspace customer journey.
    # Both retain their errors; a success here cannot erase a failure above.
    with app_server(tmp_path, evidence_name="video-export-server.log") as (url, _):
        export_video(page, url)


def test_new_campaign_remains_the_active_campaign(page, app):
    name = "New active campaign " + secrets.token_hex(3)
    create_campaign(page, app, name)
    selected = page.get_by_role("combobox", name="Active campaign", exact=True)
    expect(selected.locator("option:checked")).to_have_text(name)
    page.reload()
    expect(selected.locator("option:checked")).to_have_text(name)


def test_login_refresh_and_logout_work_in_the_browser(page, tmp_path):
    with app_server(tmp_path, login=True) as (url, password):
        page.goto(url)
        expect(page.get_by_role("heading", name="Sign in to the CRM")).to_be_visible()
        page.get_by_label("Username", exact=True).fill("audit-user")
        page.get_by_label("Password", exact=True).fill(password)
        page.get_by_role("button", name="Sign in", exact=True).click()
        expect(page.get_by_role("button", name="Log out", exact=True)).to_be_visible()
        page.reload()
        expect(page.get_by_role("button", name="Log out", exact=True)).to_be_visible()
        page.get_by_role("button", name="Log out", exact=True).click()
        expect(page.get_by_role("heading", name="Sign in to the CRM")).to_be_visible()
