"""The browser box: network yes, your files never.  `S-03.01.01`

An agent that holds your real LinkedIn session can do anything you can do. That
is only an acceptable thing to build if losing control of it costs nothing, and
this file is where that claim is checked.

Two acceptance criteria, and they are enforced in two different places on
purpose:

**"No host path is mounted, and the CRM database is not mounted at all."** The
container. Checked by inspecting the exact `docker run` invocation, the way
`test_ai_sandbox.py` already checks the code box — composition is testable
without a daemon, and a flag that is missing from the command is missing whether
or not Docker is installed.

**"A domain not on the allow-list is requested, and the request does not leave
the box."** The browser's own network stack, via DevTools `Fetch`. Checked
against a real Chromium, because an interception that is never exercised by a
real page is a theory.

The dangerous failure mode here is a check that passes because nothing happened.
So the live test asserts a request was *paused and refused*, not merely that it
failed — a request to a domain that does not resolve fails either way.
"""
from __future__ import annotations

import asyncio
import os
import tempfile

import pytest

from offsetx_apollo_builder.ai.sandbox import (
    PolicyViolation,
    SandboxPolicy,
    SandboxWorkspace,
    validate_network,
)
from offsetx_apollo_builder.browser.box import (
    BROWSER_SHM,
    DEFAULT_IMAGE,
    PROFILE_PATH,
    BrowserBox,
    BrowserProfile,
    volume_for,
)
from offsetx_apollo_builder.browser.guard import RequestGuard
from offsetx_apollo_builder.browser.page import Page
from offsetx_apollo_builder.browser.session import (
    BrowserUnavailable,
    find_browser,
    free_port,
    open_session,
)


def command_for(**kwargs) -> list[str]:
    return BrowserBox(**kwargs).command()


# ── AC1: no host path is mounted, and the store is absent ───────────────────


def test_the_only_mount_is_a_docker_volume_and_not_a_path_on_your_disk():
    """A bind mount would put your session cookies at a path on your disk, which
    is the thing this box exists to avoid. A named volume has no host path to
    traverse and cannot be reached by a relative path out of the container."""
    command = command_for(workspace_id="local")
    mounts = [command[index + 1] for index, part in enumerate(command) if part == "-v"]
    assert mounts == [f"offcrm-browser-local:{PROFILE_PATH}"]
    for mount in mounts:
        source = mount.split(":")[0]
        assert not source.startswith("/"), "a mount source starting with / is a host path"
        assert not source.startswith("."), "a relative mount source is a host path too"


def test_no_home_directory_or_absolute_path_appears_anywhere_in_the_invocation():
    """Broader than the mount check on purpose: a host path could arrive through
    a flag nobody thought of, and this catches it wherever it appears."""
    command = command_for(workspace_id="local")
    home = os.path.expanduser("~")
    joined = " ".join(command)
    assert home not in joined
    for part in command:
        # `/profile` and `/tmp` are inside the container; `127.0.0.1:...` is a
        # published port. Nothing else may look like a path from this machine.
        if part.startswith("/") and not part.startswith((PROFILE_PATH, "/tmp")):
            pytest.fail(f"{part!r} looks like a host path in the invocation")


def test_the_crm_database_and_keys_are_absent_rather_than_read_only():
    """`store` is not mounted read-only. It is not mounted. A mount that exists
    can be reached, and the encrypted keys and the egress log are not things a
    container should be able to reach at all."""
    command = " ".join(command_for(workspace_id="local"))
    for forbidden in ("store", "inbox", "/work", ".db", "data_dir"):
        assert forbidden not in command, f"{forbidden!r} reaches the browser box"


def test_every_hardening_flag_from_the_code_box_is_inherited():
    """Composed from `SandboxPolicy` rather than written again, because two flag
    lists drift and the one that drifts is the one that stops protecting."""
    command = command_for(workspace_id="local")
    for flag in (
        "--rm", "--pull=never", "--read-only", "--cap-drop=ALL",
        "--security-opt=no-new-privileges", "--user=65534:65534",
    ):
        assert flag in command, f"{flag} is missing from the browser box"


def test_the_box_asks_for_the_network_and_the_code_box_still_cannot_have_it():
    """The default is `none`, so a box that needs the network says so out loud
    and a box that does not cannot acquire it by anyone forgetting."""
    assert "--network=bridge" in command_for(workspace_id="local")
    assert SandboxPolicy().network == "none"
    code_box = SandboxPolicy().docker_command(
        image="python:3.12",
        command=["python", "-c", "print(1)"],
        workspace=SandboxWorkspace(root=__import__("pathlib").Path(tempfile.mkdtemp())),
    )
    assert "--network=none" in code_box


def test_host_networking_cannot_be_asked_for_at_all():
    """`--network=host` would put the container on this machine's own network
    stack, which is the single thing every other flag exists to prevent."""
    with pytest.raises(PolicyViolation, match="host"):
        validate_network("host")
    for attempt in ("container:other", "--privileged", "", "NONE; rm -rf /"):
        with pytest.raises(PolicyViolation):
            validate_network(attempt)


def test_the_devtools_port_is_published_to_loopback_only():
    """A DevTools port is remote control of a logged-in browser. Bound to
    0.0.0.0 — which is Docker's default when you publish a port — it is remote
    control of a logged-in browser for the whole network."""
    command = command_for(workspace_id="local", port=9781)
    published = command[command.index("-p") + 1]
    assert published == "127.0.0.1:9781:9781"
    assert "0.0.0.0:" not in " ".join(command)


def test_chromium_gets_the_shared_memory_it_actually_needs():
    """The classic symptom of leaving this at Docker's 64m default is tabs
    crashing with no message on any page with images on it."""
    command = command_for(workspace_id="local")
    assert command[command.index("--shm-size") + 1] == BROWSER_SHM


def test_the_profile_is_named_explicitly_because_chrome_requires_it():
    """Chrome refuses to open a debugging port on a *default* profile — a
    deliberate change that stopped malware reading cookies out of a running
    browser."""
    command = command_for(workspace_id="local")
    assert f"--user-data-dir={PROFILE_PATH}" in command
    assert "--remote-debugging-port=9776" in command


def test_each_workspace_gets_its_own_profile_volume():
    """Two people's session cookies in one place is not a multi-user product; it
    is one account with two users."""
    assert volume_for("alice") != volume_for("bob")
    assert volume_for("alice") == "offcrm-browser-alice"


def test_a_workspace_id_that_would_not_make_a_volume_name_is_refused():
    """Refused rather than sanitised: a name that had to be cleaned up is one
    somebody chose badly, and silently changing it makes two workspaces collide."""
    for bad in ("", "  ", "../../etc", "a/b", "x;rm -rf /", "-leading-dash"):
        with pytest.raises(PolicyViolation):
            volume_for(bad)


def test_a_volume_name_is_checked_again_at_the_moment_it_is_used():
    with pytest.raises(PolicyViolation):
        BrowserProfile(volume="../escape").prepare()


def test_the_image_must_be_declared_and_present_locally():
    """`--pull=never` is inherited: without it a crafted image name is a way to
    make a network fetch happen from a box whose network is the thing under
    control."""
    assert "--pull=never" in command_for(workspace_id="local")
    with pytest.raises(Exception):
        BrowserBox(workspace_id="local", image="evil image; rm -rf /").command()


def test_what_the_owner_is_shown_before_anything_starts():
    described = BrowserBox(workspace_id="local").describe()
    assert described["network"] == "bridge"
    assert described["devtools_port"] == "127.0.0.1:9776"
    assert described["image"] == DEFAULT_IMAGE
    assert any("not a path on your disk" in line for line in described["mounted"])
    for absent in ("the CRM databases", "the encrypted keys", "the egress log"):
        assert absent in described["unmounted"]


# ── AC2: an off-list domain does not leave the box ──────────────────────────


def test_an_unattended_run_reaches_only_declared_domains():
    guard = RequestGuard(allowed_hosts=frozenset({"example.com"}), unattended=True)
    assert guard.verdict("https://example.com/a").allowed is True
    assert guard.verdict("https://www.example.com/a").allowed is True, "subdomains inherit"
    assert guard.verdict("https://elsewhere.test/a").allowed is False


def test_an_empty_allow_list_when_unattended_reaches_nothing():
    """Correct rather than broken. A run that declared no domains asked for
    nothing, and failing closed is the only safe reading of that."""
    guard = RequestGuard(unattended=True)
    assert guard.verdict("https://example.com/").allowed is False


def test_a_lookalike_domain_does_not_pass_as_the_real_one():
    """`linkedin.com.evil.test` ends with neither `linkedin.com` nor
    `.linkedin.com`, and a naive `in` check would let it straight through."""
    guard = RequestGuard(allowed_hosts=frozenset({"linkedin.com"}), unattended=True)
    assert guard.verdict("https://linkedin.com.evil.test/steal").allowed is False
    assert guard.verdict("https://notlinkedin.com/steal").allowed is False


def test_the_allow_list_narrows_and_can_never_widen():
    """The property that makes a platform rule worth having: a config file
    cannot vote itself past one. LinkedIn is attended-only, so an unattended run
    cannot reach it even with `linkedin.com` explicitly allowed."""
    guard = RequestGuard(allowed_hosts=frozenset({"linkedin.com"}), unattended=True)
    decision = guard.verdict("https://www.linkedin.com/feed/")
    assert decision.allowed is False
    assert "attended-only" in decision.reason


def test_an_attended_run_reaches_the_open_web_but_not_this_machine():
    guard = RequestGuard(unattended=False)
    assert guard.verdict("https://anything.test/page").allowed is True
    for blocked in ("http://127.0.0.1:8000/admin", "http://169.254.169.254/",
                    "file:///etc/passwd", "https://db.internal/"):
        assert guard.verdict(blocked).allowed is False, blocked


def test_inline_content_is_not_treated_as_network_traffic():
    """`data:` and `blob:` never leave the browser. Refusing them would break
    every inline image on the web for no security gain at all."""
    guard = RequestGuard(unattended=True)
    for inert in ("data:image/png;base64,AAAA", "blob:https://x.test/abc", "about:blank"):
        assert guard.verdict(inert).allowed is True, inert


def test_a_url_that_will_not_parse_is_refused_rather_than_guessed_at():
    guard = RequestGuard(unattended=False)
    for nonsense in ("", "   ", "http://[oops"):
        assert guard.verdict(nonsense).allowed is False


def test_the_guard_fails_closed_when_it_cannot_decide():
    """A guard that fails open is absent exactly when something unusual is
    happening, which is the only time it mattered. So a decision that raises
    becomes a refusal, not a shrug."""

    class Exploding(RequestGuard):
        def verdict(self, url: str):
            raise RuntimeError("something unexpected in the request shape")

    guard = Exploding(unattended=True)
    listener = guard._make_listener(_NullConnection(), "s1")
    asyncio.run(listener("Fetch.requestPaused",
                         {"requestId": "r1", "request": {"url": "https://x.test/"}}, "s1"))
    assert guard.blocked_count == 1
    assert "could not decide" in guard.blocked[0][1]


class _NullConnection:
    """Records what the guard told the browser to do, and nothing else."""

    def __init__(self):
        self.sent: list[tuple[str, dict]] = []

    async def send(self, method, params=None, *, session_id="", timeout=30.0):
        self.sent.append((method, params or {}))
        return {}


def test_a_refusal_reaches_the_browser_as_a_real_network_error():
    """`AccessDenied` rather than a silent drop: the page sees an error and
    reports it, instead of hanging until something times out and nobody knows
    why."""
    guard = RequestGuard(allowed_hosts=frozenset({"example.com"}), unattended=True)
    connection = _NullConnection()
    listener = guard._make_listener(connection, "s1")
    asyncio.run(listener("Fetch.requestPaused",
                         {"requestId": "r1", "request": {"url": "https://nope.test/"}}, "s1"))
    assert connection.sent == [
        ("Fetch.failRequest", {"requestId": "r1", "errorReason": "AccessDenied"})
    ]


def test_an_allowed_request_is_continued_and_not_merely_ignored():
    """An ignored paused request hangs the page forever. Continuing it is the
    other half of interception and is easy to leave out."""
    guard = RequestGuard(unattended=False)
    connection = _NullConnection()
    listener = guard._make_listener(connection, "s1")
    asyncio.run(listener("Fetch.requestPaused",
                         {"requestId": "r7", "request": {"url": "https://fine.test/"}}, "s1"))
    assert connection.sent == [("Fetch.continueRequest", {"requestId": "r7"})]


def test_events_for_another_tab_are_left_alone():
    """One connection drives many tabs. Answering another tab's paused request
    would continue or fail a request this guard never judged."""
    guard = RequestGuard(unattended=True)
    connection = _NullConnection()
    listener = guard._make_listener(connection, "s1")
    asyncio.run(listener("Fetch.requestPaused",
                         {"requestId": "r1", "request": {"url": "https://x.test/"}}, "s2"))
    assert connection.sent == []
    assert guard.blocked_count == 0


def test_the_guard_reports_what_it_refused():
    guard = RequestGuard(allowed_hosts=frozenset({"example.com"}), unattended=True)
    guard._record("https://example.com/a", guard.verdict("https://example.com/a"))
    for index in range(3):
        url = f"https://bad{index}.test/"
        guard._record(url, guard.verdict(url))
    report = guard.report()
    assert report["mode"] == "unattended"
    assert report["allowed"] == 1
    assert report["blocked"] == 3
    assert report["blocked_examples"][0][0] == "https://bad0.test/"


def test_a_page_firing_thousands_of_refused_requests_cannot_bloat_the_trace():
    guard = RequestGuard(unattended=True)
    for index in range(500):
        url = f"https://bad{index}.test/"
        guard._record(url, guard.verdict(url))
    assert guard.blocked_count == 500
    assert len(guard.blocked) <= 200
    assert guard.report()["truncated"] is True


# ── AC2, against a real browser ─────────────────────────────────────────────


def _browser() -> str:
    try:
        return find_browser()
    except BrowserUnavailable:
        return ""


needs_browser = pytest.mark.skipif(
    not _browser(), reason="no Chrome, Edge, Brave or Chromium on this machine"
)


async def _with_guard(guard: RequestGuard, work):
    with tempfile.TemporaryDirectory() as profile:
        flags = ("--no-sandbox",) if os.geteuid() == 0 else ()
        session = await open_session(
            profile_dir=profile, port=free_port(), headless=True, extra_flags=flags
        )
        try:
            _, session_id = await session.new_tab()
            page = Page(connection=session.connection, session_id=session_id)
            await page.start()
            await guard.attach(session.connection, session_id)
            return await work(page)
        finally:
            await session.close(quit_browser=True)


@needs_browser
def test_a_real_browser_cannot_reach_an_off_list_domain():
    """The strongest evidence available without a Docker daemon: a real page
    calls `fetch()` at a domain the run did not declare, and the request is
    paused and refused before Chrome dispatches it.

    Asserting the guard *recorded a refusal* rather than that the fetch failed:
    a request to a domain that does not resolve fails either way, so a test that
    only checked for failure would pass with the guard removed."""

    async def work(page: Page):
        await page.goto("data:text/html,<p>guarded</p>")
        result = await page.connection.send(
            "Runtime.evaluate",
            {
                "expression": (
                    "fetch('https://blocked-by-the-guard.test/steal')"
                    ".then(() => 'reached').catch(e => 'refused: ' + e.message)"
                ),
                "awaitPromise": True,
                "returnByValue": True,
            },
            session_id=page.session_id,
            timeout=20,
        )
        return str((result.get("result") or {}).get("value") or "")

    guard = RequestGuard(allowed_hosts=frozenset({"example.com"}), unattended=True)
    answer = asyncio.run(_with_guard(guard, work))

    assert answer.startswith("refused:"), answer
    blocked = [url for url, _ in guard.blocked]
    assert any("blocked-by-the-guard.test" in url for url in blocked), guard.blocked
    reason = next(r for u, r in guard.blocked if "blocked-by-the-guard.test" in u)
    assert "not on this run's allow-list" in reason


@needs_browser
def test_the_guard_lets_a_request_through_rather_than_blocking_everything():
    """The other direction, and the one that catches a guard which "passes" by
    refusing everything.

    The assertion is `allowed_count`, not whether the fetch succeeded. A
    request to a domain that does not resolve fails either way, so checking the
    fetch would prove nothing — but the counter only moves if the request was
    genuinely paused, decided, and continued.

    An earlier version of this test navigated to a `data:` URL and asserted the
    page rendered. It passed with both counters at zero: `data:` never touches
    the network, so no interception happened and the test would have passed with
    the guard removed entirely."""

    async def work(page: Page):
        await page.goto("data:text/html,<p>attended</p>")
        await page.connection.send(
            "Runtime.evaluate",
            {
                "expression": "fetch('https://elsewhere.test/thing').catch(() => 'network')",
                "awaitPromise": True,
                "returnByValue": True,
            },
            session_id=page.session_id,
            timeout=20,
        )
        return True

    # Attended: the open web is reachable, so this domain is allowed through
    # even though it is on no list.
    guard = RequestGuard(unattended=False)
    asyncio.run(_with_guard(guard, work))
    assert guard.allowed_count >= 1, "the guard never saw a request — interception is not on"
    assert guard.blocked_count == 0, guard.blocked


@needs_browser
def test_a_tab_is_guarded_by_default_without_the_caller_asking():
    """The box's network boundary must not depend on the caller remembering to
    switch it on. `Page.start()` attaches a guard, so a tab that was merely
    opened is already enforcing the rules."""

    async def work():
        with tempfile.TemporaryDirectory() as profile:
            flags = ("--no-sandbox",) if os.geteuid() == 0 else ()
            session = await open_session(
                profile_dir=profile, port=free_port(), headless=True, extra_flags=flags
            )
            try:
                _, session_id = await session.new_tab()
                # Nothing is passed but the allow-list: no guard, no attach call.
                page = Page(
                    connection=session.connection,
                    session_id=session_id,
                    unattended=True,
                    allowed_hosts=frozenset({"example.com"}),
                )
                await page.start()
                await page.goto("data:text/html,<p>x</p>")
                await page.connection.send(
                    "Runtime.evaluate",
                    {
                        "expression": "fetch('https://not-declared.test/x').catch(() => 'no')",
                        "awaitPromise": True, "returnByValue": True,
                    },
                    session_id=session_id, timeout=20,
                )
                return page.guard
            finally:
                await session.close(quit_browser=True)

    guard = asyncio.run(work())
    assert guard is not None, "start() left the tab unguarded"
    assert guard.blocked_count >= 1, guard.report()
    assert any("not-declared.test" in url for url, _ in guard.blocked)
