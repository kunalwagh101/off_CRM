"""Signing in to a platform, inside the box.  `S-03.02.01`

Two acceptance criteria, and the second one is the reason this feature is
buildable at all:

**"The session persists across restarts of the box."** The session lives in
Chrome's own cookie jar inside a Docker named volume, which outlives the
container. off_CRM does not copy it, read it or back it up — so persistence is a
property of the box rather than of any code here, and the test is that nothing
in this module is holding it.

**"My password is present nowhere in off_CRM's storage."** Not encrypted, not
hashed, not held for a moment. The person types it into the browser with their
own fingers and the only thing that crosses back is *whether it worked*.

The dangerous failure mode for that second claim is a signature nobody notices
growing a `password=` parameter six months from now. So it is not tested by
inspecting one flow — it is tested by reading every public function in both
modules and failing on any parameter that could carry one.

The live test drives a login page **served from a `data:` URL in this file**,
never a real platform. It types a password into that page the way a person
would, watches the state flip, and then searches every byte off_CRM wrote for
the password. That is the only honest way to prove a negative.
"""
from __future__ import annotations

import asyncio
import inspect
import json
import os
import tempfile
import time
from pathlib import Path

import pytest

from offsetx_apollo_builder.browser import identity, signin
from offsetx_apollo_builder.browser.identity import (
    PLATFORMS,
    Connection,
    ConnectionStore,
    Reading,
    UnknownPlatform,
    catalogue,
    platform,
    read_state,
)
from offsetx_apollo_builder.browser.page import Page
from offsetx_apollo_builder.browser.perceive import build
from offsetx_apollo_builder.browser.session import (
    BrowserUnavailable,
    find_browser,
    free_port,
    open_session,
)
from offsetx_apollo_builder.browser.signin import SignInRefused

#: The exact string typed into the fake login page below. Every store off_CRM
#: touches is searched for it afterwards.
SECRET = "correct-horse-battery-staple-9f3a"


def node(identifier, role, name):
    return {
        "nodeId": str(identifier), "role": {"value": role}, "name": {"value": name},
        "childIds": [], "backendDOMNodeId": 1, "ignored": False, "properties": [],
    }


def snapshot_of(*names_and_roles):
    return build([node(index, role, name)
                  for index, (role, name) in enumerate(names_and_roles, start=1)])


# ── AC2: no credential can reach this code, by signature ────────────────────


def test_no_function_in_the_sign_in_path_accepts_a_credential():
    """The check that survives me. A flow can be audited once; a signature can
    grow a `password=` parameter six months from now and look reasonable in the
    diff. So every public callable in both modules is read, and any parameter
    that could carry a secret fails the build."""
    for module in (identity, signin):
        for name, member in vars(module).items():
            if name.startswith("_") or not callable(member):
                continue
            if getattr(member, "__module__", "") != module.__name__:
                continue
            try:
                signature = inspect.signature(member)
            except (TypeError, ValueError):
                continue
            for parameter in signature.parameters:
                lowered = parameter.lower()
                for forbidden in identity.FORBIDDEN_FIELDS:
                    assert forbidden not in lowered, (
                        f"{module.__name__}.{name}() takes {parameter!r}, which "
                        "could carry a credential"
                    )


def test_the_stored_record_has_no_field_a_secret_could_live_in():
    stored = Connection(platform="linkedin", state="connected",
                        checked_at="2026-08-25T10:00:00+00:00",
                        evidence="the page offers 'my network'", handle="@someone")
    for key in stored.to_dict():
        for forbidden in identity.FORBIDDEN_FIELDS:
            assert forbidden not in key.lower(), f"{key!r} could hold a credential"


def test_signing_in_does_not_go_through_the_agents_typing_verb():
    """`page.type()` exists and must not be used here. An agent that could fill
    a password field is an agent that could be talked into filling it
    somewhere else."""
    source = Path(signin.__file__).read_text(encoding="utf-8")
    body = source.split('"""', 2)[-1]  # past the module docstring
    assert ".type(" not in body
    assert "dispatchKeyEvent" not in body


# ── reading the page ────────────────────────────────────────────────────────


def test_a_signed_in_page_reads_as_connected():
    reading = read_state(snapshot_of(("link", "My Network"), ("button", "Messaging")),
                         platform("linkedin"))
    assert reading.state == "connected"
    assert "my network" in reading.evidence


def test_a_signed_out_page_reads_as_disconnected():
    reading = read_state(snapshot_of(("button", "Sign in"), ("link", "Join now")),
                         platform("linkedin"))
    assert reading.state == "disconnected"


def test_signed_out_wins_a_tie():
    """If a page shows both, the sign-in prompt is the thing that is true."""
    reading = read_state(snapshot_of(("button", "Sign in"), ("link", "My Network")),
                         platform("linkedin"))
    assert reading.state == "disconnected"


def test_a_page_with_neither_signal_is_unknown_and_never_guessed():
    """The important one. A layout change silently reported as connected would
    let a scheduled run believe it had a session it did not, and that surfaces
    as an agent doing nothing useful for a week."""
    for nodes in ((("heading", "Something else"),), (("paragraph", "Please wait"),)):
        assert read_state(snapshot_of(*nodes), platform("linkedin")).state == "unknown"
    assert read_state(build([]), platform("linkedin")).state == "unknown"


def test_a_short_signal_does_not_match_inside_another_word():
    """Found by "Something else" reading as connected: the signal `me` matched
    inside `so-me-thing`. Short signals are the most useful and the most
    dangerous, so matching is on word boundaries."""
    reading = read_state(snapshot_of(("heading", "Something else meaningful")),
                         platform("linkedin"))
    assert reading.state == "unknown"
    # And a real word still matches, boundaries and all.
    assert read_state(snapshot_of(("link", "My Network")),
                      platform("linkedin")).state == "connected"


def test_matching_ignores_case_because_platforms_do_not_agree_on_it():
    assert read_state(snapshot_of(("link", "MY NETWORK")),
                      platform("linkedin")).state == "connected"


def test_every_declared_platform_has_both_kinds_of_signal():
    """A platform with no signed-out signal can never be observed as logged out,
    so a dead session would read as unknown forever."""
    for target in PLATFORMS.values():
        assert target.signed_in, f"{target.id} cannot be seen as signed in"
        assert target.signed_out, f"{target.id} cannot be seen as signed out"
        assert target.login_url.startswith("https://")
        assert target.home_url.startswith("https://")


def test_a_platform_nobody_declared_is_refused_by_name():
    with pytest.raises(UnknownPlatform, match="myspace"):
        platform("myspace")


# ── what gets written down ──────────────────────────────────────────────────


def test_a_connection_survives_a_round_trip(tmp_path):
    store = ConnectionStore(tmp_path)
    store.record("local", Reading("connected", "the page offers 'messaging'"),
                 platform("linkedin"), handle="@someone")
    reloaded = ConnectionStore(tmp_path).get("local", "linkedin")
    assert reloaded.state == "connected"
    assert reloaded.handle == "@someone"
    assert reloaded.checked_at


def test_two_workspaces_cannot_see_each_others_connections(tmp_path):
    store = ConnectionStore(tmp_path)
    store.record("alice", Reading("connected", "x"), platform("linkedin"))
    assert store.get("bob", "linkedin").state == "unknown"


def test_forgetting_a_record_says_it_does_not_sign_you_out(tmp_path):
    """The session lives in the browser's volume. Pretending otherwise would
    leave a live session behind a screen that says disconnected."""
    store = ConnectionStore(tmp_path)
    store.record("local", Reading("connected", "x"), platform("linkedin"))
    store.forget("local", "linkedin")
    assert store.get("local", "linkedin").state == "unknown"
    assert "does not" in ConnectionStore.forget.__doc__.lower()


def test_a_corrupt_record_costs_a_recheck_and_not_a_crash(tmp_path):
    store = ConnectionStore(tmp_path)
    store.path.write_text("{not json at all", encoding="utf-8")
    assert store.get("local", "linkedin").state == "unknown"
    store.record("local", Reading("connected", "x"), platform("linkedin"))
    assert store.get("local", "linkedin").state == "connected"


def test_the_catalogue_shows_every_platform_and_where_you_stand(tmp_path):
    store = ConnectionStore(tmp_path)
    store.record("local", Reading("connected", "x"), platform("linkedin"))
    body = catalogue(store, "local")
    assert {item["id"] for item in body["platforms"]} == set(PLATFORMS)
    linkedin = next(item for item in body["platforms"] if item["id"] == "linkedin")
    assert linkedin["state"] == "connected"
    assert linkedin["login_url"].startswith("https://www.linkedin.com")


# ── the flow ────────────────────────────────────────────────────────────────


def test_an_unattended_run_cannot_start_a_sign_in():
    """A sign-in is by definition a thing a person does. A scheduled run
    reaching this is a scheduled run about to sit at a password prompt forever."""

    class Unattended:
        unattended = True

        async def goto(self, url):  # pragma: no cover - never reached
            raise AssertionError("an unattended run navigated to a login page")

    with pytest.raises(SignInRefused, match="person at the keyboard"):
        asyncio.run(signin.open_login(Unattended(), "linkedin"))


# ── against a real browser, end to end ──────────────────────────────────────


def _browser() -> str:
    try:
        return find_browser()
    except BrowserUnavailable:
        return ""


needs_browser = pytest.mark.skipif(
    not _browser(), reason="no Chrome, Edge, Brave or Chromium on this machine"
)

#: A login page under this file's control. Never a real platform: this test
#: types a password, and typing one into somebody else's site would be both
#: rude and useless as evidence.
LOGIN_PAGE = (
    "data:text/html,"
    "<html><body>"
    "<h1>Sign in</h1>"
    "<label for=u>Username</label><input id=u>"
    "<label for=p>Password</label><input id=p type=password>"
    "<button id=go onclick=\"document.body.innerHTML="
    "'<a href=%23>My Network</a><button>Messaging</button>'\">Sign in</button>"
    "</body></html>"
)

#: The same platform shape as LinkedIn, pointed at the page above.
FAKE = identity.Platform(
    id="linkedin",
    label="Test platform",
    login_url=LOGIN_PAGE,
    home_url=LOGIN_PAGE,
    signed_in=("my network", "messaging"),
    signed_out=("sign in",),
)


async def _drive(work):
    with tempfile.TemporaryDirectory() as profile:
        flags = ("--no-sandbox",) if os.geteuid() == 0 else ()
        session = await open_session(
            profile_dir=profile, port=free_port(), headless=True, extra_flags=flags
        )
        try:
            _, session_id = await session.new_tab()
            page = Page(connection=session.connection, session_id=session_id)
            await page.start()
            return await work(page)
        finally:
            await session.close(quit_browser=True)


@needs_browser
def test_the_whole_flow_and_the_password_is_nowhere_afterwards(tmp_path):
    """The evidence for both acceptance criteria in one run.

    A real browser opens a login page. A password is typed into it the way a
    person types — real key events, not a value assignment. The page flips to a
    signed-in view. off_CRM notices, writes down that it worked, and then every
    byte it wrote is searched for that password."""
    store = ConnectionStore(tmp_path)

    async def work(page: Page):
        reading = await signin.open_login(page, FAKE)
        assert reading.state == "disconnected", "the login page should read as signed out"

        # The person types. Driven here because a test has no fingers, but note
        # what is doing it: the *test*, through raw CDP, never `signin.py`.
        snapshot = await page.snapshot()
        field = next(n for n in snapshot.actions if "password" in n.name.lower())
        await page.type(field.handle, SECRET)

        # A fresh snapshot between the two actions, because typing changed the
        # page: Chrome adds a "reveal password" control once a password field
        # has content, and every handle after it shifts. Reusing the old numbers
        # is what an agent must not do, and `_resolve` now refuses it.
        snapshot = await page.snapshot()
        button = next(n for n in snapshot.actions if n.name.lower() == "sign in")
        await page.click(button.handle, confirmed=True)

        attempt = await signin.wait_for_sign_in(page, FAKE, timeout=20, poll_seconds=0.3)
        return attempt

    attempt = asyncio.run(_drive(work))
    assert attempt.state == "connected", attempt.to_dict()
    assert attempt.polls >= 1

    connection = store.record("local", attempt.reading, FAKE)
    assert connection.state == "connected"

    # AC2. Every file off_CRM wrote, searched for the password.
    written = [path for path in Path(tmp_path).rglob("*") if path.is_file()]
    assert written, "the store wrote nothing at all, so this proves nothing"
    for path in written:
        blob = path.read_bytes()
        assert SECRET.encode() not in blob, f"the password is in {path.name}"
        assert b"password" not in blob.lower(), f"a password field is in {path.name}"

    # And nowhere in what the flow itself carries back.
    assert SECRET not in json.dumps(attempt.to_dict())
    assert SECRET not in json.dumps(connection.to_dict())


@needs_browser
def test_a_platform_already_signed_in_is_not_asked_to_sign_in_again(tmp_path):
    """`open_login` checks first. Sending someone to a login page they do not
    need is how a flow trains people to re-enter a password out of habit."""

    async def work(page: Page):
        signed_in = identity.Platform(
            id="linkedin", label="Test", signed_in=("my network",), signed_out=("sign in",),
            login_url="data:text/html,<h1>Sign in</h1>",
            home_url="data:text/html,<a href=%23>My Network</a>",
        )
        reading = await signin.open_login(page, signed_in)
        return reading, page.url

    reading, url = asyncio.run(_drive(work))
    assert reading.state == "connected"
    assert "Sign in" not in url, "it navigated to the login page anyway"


@needs_browser
def test_giving_up_leaves_the_browser_open_rather_than_cancelling(tmp_path):
    """A timeout is off_CRM stopping watching, not the sign-in being cancelled.
    The person may still be reading a text message with a code in it."""

    async def work(page: Page):
        never = identity.Platform(
            id="linkedin", label="Test", signed_in=("my network",), signed_out=("sign in",),
            login_url="data:text/html,<h1>Sign in</h1>",
            home_url="data:text/html,<h1>Sign in</h1>",
        )
        return await signin.wait_for_sign_in(page, never, timeout=1.0, poll_seconds=0.2)

    attempt = asyncio.run(_drive(work))
    assert attempt.state == "timed_out"
    assert "still open" in attempt.detail
    assert attempt.polls >= 2, "it should have polled more than once"


@needs_browser
def test_a_session_survives_the_browser_being_restarted(tmp_path):
    """AC1, tested rather than argued.

    A signed-in session *is* a cookie with an expiry in Chrome's own jar, and
    the jar is a file inside `--user-data-dir`. The box points that flag at
    `/profile`, which is a Docker named volume — and a named volume outlives
    the container that mounted it, which `test_browser_box.py` proves
    separately.

    So the half that belongs to this story is the half above the volume: that a
    login survives the browser process dying and coming back against the same
    profile. This starts a real browser, plants a cookie with an expiry the way
    a platform does, kills the browser, starts another one against the same
    profile directory, and asks for the cookie back.

    A cookie with no expiry would *not* survive, and that is correct — that is
    what a session cookie means. Using one here would make this test pass for
    the wrong reason, so the expiry is explicit.
    """
    profile = str(tmp_path / "profile")
    os.makedirs(profile, exist_ok=True)
    flags = ("--no-sandbox",) if os.geteuid() == 0 else ()
    origin = "https://persistence.test/"

    async def plant():
        session = await open_session(
            profile_dir=profile, port=free_port(), headless=True, extra_flags=flags
        )
        try:
            # `Storage`, not `Network`: the jar belongs to the browser, and
            # `Network.setCookie` only exists on a page target.
            await session.connection.send("Storage.setCookies", {
                "cookies": [{
                    "name": "session_token",
                    "value": "a-signed-in-session",
                    "domain": "persistence.test",
                    "path": "/",
                    "expires": time.time() + 86_400,
                    "secure": True,
                }],
            })
            # Chrome writes the jar on a graceful shutdown; ask for it once so
            # the write is ordered after the set rather than racing it.
            await session.connection.send("Storage.getCookies", {})
        finally:
            await session.close(quit_browser=True)

    async def recall():
        session = await open_session(
            profile_dir=profile, port=free_port(), headless=True, extra_flags=flags
        )
        try:
            result = await session.connection.send("Storage.getCookies", {})
            return [cookie for cookie in result.get("cookies", [])
                    if cookie.get("name") == "session_token"]
        finally:
            await session.close(quit_browser=True)

    asyncio.run(plant())
    survivors = asyncio.run(recall())

    assert survivors, "the session did not survive the browser being restarted"
    assert survivors[0]["value"] == "a-signed-in-session"
