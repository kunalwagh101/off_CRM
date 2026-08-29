"""The browser agent: off_CRM's hands on the web.

Read `docs/architecture/BROWSER_AGENT_BLUEPRINT.md` first. The short version is
that this drives *your* browser against *your* profile over the Chrome DevTools
Protocol, which buys what a Chromium fork buys — your cookies, your SSO, your
passkeys — without shipping a browser.

Four things are protected here.

**The vocabulary is closed.** A model names one of ten verbs and an integer
handle a snapshot gave it. It cannot supply a selector, cannot supply
JavaScript, and cannot reach an element the snapshot did not offer. If that ever
stops holding, a prompt injection on any page becomes arbitrary action inside a
logged-in session — and the open web will eventually serve one.

**A stale handle is refused, never guessed.** Clicking "whatever is at position
12 now" after the page moved is how the wrong record gets deleted.

**The policy is enforced in code, not asked for in a prompt.** Pacing, the
attended-only rule for session-gated platforms, and the refusal to touch
localhost or a cloud metadata endpoint are all checks, because a limit that
lives in an instruction is a suggestion.

**The trace cannot be edited.** An audit log with an eraser in it is not one.
"""
from __future__ import annotations

import asyncio
import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

from offsetx_apollo_builder.browser import cdp, perceive, policy
from offsetx_apollo_builder.browser.page import ACTIONS, ActionRefused, Page
from offsetx_apollo_builder.browser.session import (
    BrowserUnavailable,
    find_browser,
    clear_stale_lock,
    profile_is_locked,
)
from offsetx_apollo_builder.browser.trace import Step, Trace


# ── the policy, which is the part that must never be wrong ──────────────────


def test_the_open_web_is_open_and_paced_rather_than_blocked():
    rule = policy.rule_for("https://example.com/about")
    assert rule.label == "the open web"
    assert rule.unattended is True
    assert rule.min_seconds_between_actions > 0, "polite, not fast"


def test_a_subdomain_inherits_its_parents_rule():
    """`uk.linkedin.com` is LinkedIn. A rule matched on the exact host only
    would be walked around by a country subdomain."""
    for host in ("https://linkedin.com/in/x", "https://uk.linkedin.com/in/x",
                 "https://www.linkedin.com/in/x"):
        assert policy.rule_for(host).label == "LinkedIn"


def test_session_gated_platforms_are_slowed_to_reading_pace():
    """What gets an account restricted is rhythm. Thirty profile views a minute
    is not something a person does."""
    for host, floor in (("https://linkedin.com/feed", 6.0),
                        ("https://instagram.com/x", 5.0),
                        ("https://x.com/x", 4.0)):
        assert policy.rule_for(host).min_seconds_between_actions >= floor


def test_they_are_reachable_when_you_ask_and_not_on_a_schedule():
    """The whole distinction this policy turns on: you reading a page is not
    scraping, and a routine firing at 3am is a different act."""
    assert policy.check_navigation("https://linkedin.com/feed", unattended=False)
    with pytest.raises(policy.Refused, match="attended-only"):
        policy.check_navigation("https://linkedin.com/feed", unattended=True)


def test_youtube_is_open_because_it_has_a_real_api():
    rule = policy.check_navigation("https://youtube.com/watch?v=x", unattended=True)
    assert rule.unattended is True


def test_the_machine_itself_is_never_reachable():
    """An agent that can be pointed at localhost is a way into the network it
    runs on, and the metadata endpoint is the specific reason this list exists."""
    for url in ("http://localhost:8000/admin", "http://127.0.0.1/",
                "http://169.254.169.254/latest/meta-data/",
                "http://metadata.google.internal/", "https://db.internal/"):
        with pytest.raises(policy.Refused):
            policy.check_navigation(url)


def test_local_files_and_browser_internals_are_refused():
    """A page that can talk the agent into opening a file: URL can read the
    machine, and chrome:// can change the browser's own settings."""
    for url in ("file:///etc/passwd", "chrome://settings",
                "devtools://devtools/bundled/x.html", "view-source:https://a.test"):
        with pytest.raises(policy.Refused):
            policy.check_navigation(url)


def test_an_action_that_sends_or_deletes_asks_first_wherever_it_is():
    for action in ("send", "delete", "purchase", "publish", "submit"):
        _, needs = policy.check_action(action, "https://example.com")
        assert needs is True, f"{action} must ask"
    _, needs = policy.check_action("click", "https://example.com")
    assert needs is False


def test_the_catalogue_is_readable_by_a_settings_screen():
    body = policy.catalogue()
    assert body["default"]["label"] == "the open web"
    assert {rule["label"] for rule in body["rules"]} >= {"LinkedIn", "Instagram", "YouTube"}
    assert "169.254.169.254" in body["never"]


# ── perception: the accessibility tree, not the markup ──────────────────────


def _tree(*nodes: dict) -> list[dict]:
    return list(nodes)


def _node(node_id, role, name="", *, children=(), backend=1, ignored=False, **properties):
    return {
        "nodeId": str(node_id),
        "role": {"type": "role", "value": role},
        "name": {"type": "computedString", "value": name},
        "childIds": [str(child) for child in children],
        "backendDOMNodeId": backend,
        "ignored": ignored,
        "properties": [
            {"name": key, "value": {"type": "boolean", "value": value}}
            for key, value in properties.items()
        ],
    }


def test_a_snapshot_reads_in_document_order_and_not_cdps_order():
    """CDP returns the tree flat and not in document order — a link can arrive
    before the paragraph above it. The snapshot is prose to a model, and prose
    whose sentences are shuffled is prose that gets misread."""
    nodes = _tree(
        _node("1", "RootWebArea", "Page", children=["2", "5"]),
        # Deliberately out of order in the list: the link is listed second and
        # belongs last.
        _node("5", "link", "Pricing"),
        _node("2", "heading", "Acme"),
    )
    snapshot = perceive.build(nodes, url="https://acme.test", title="Page")
    assert [node.name for node in snapshot.nodes] == ["Acme", "Pricing"]


def test_nesting_survives_so_a_flat_list_still_reads_as_a_page():
    nodes = _tree(
        _node("1", "RootWebArea", "Page", children=["2"]),
        _node("2", "form", "Sign in", children=["3"]),
        _node("3", "textbox", "Email"),
    )
    depths = {node.name: node.depth for node in perceive.build(nodes).nodes}
    # The document root is carried as `snapshot.title`, not as a node.
    assert depths == {"Sign in": 1, "Email": 2}


def test_only_things_worth_acting_on_get_a_handle():
    nodes = _tree(
        _node("1", "RootWebArea", "Page", children=["2", "3", "4"]),
        _node("2", "button", "Send"),
        _node("3", "StaticText", "Some words"),
        _node("4", "textbox", "Email"),
    )
    snapshot = perceive.build(nodes)
    assert [node.name for node in snapshot.actions] == ["Send", "Email"]


def test_a_disabled_control_is_shown_and_is_not_actionable():
    """Hiding it would make the model wonder where the button went; offering it
    would make the model click something that does nothing."""
    nodes = _tree(
        _node("1", "RootWebArea", "Page", children=["2"]),
        _node("2", "button", "Send", disabled="true"),
    )
    snapshot = perceive.build(nodes)
    assert snapshot.nodes[0].disabled is True
    assert snapshot.actions == []


def test_ignored_and_meaningless_nodes_are_dropped():
    nodes = _tree(
        _node("1", "RootWebArea", "Page", children=["2", "3", "4"]),
        _node("2", "generic", "wrapper"),
        _node("3", "button", "Hidden", ignored=True),
        _node("4", "StaticText", ""),
    )
    assert perceive.build(nodes).nodes == []


def test_whitespace_from_the_markup_is_collapsed():
    """Accessible names come from HTML, so they arrive with its indentation in
    them. Left alone a forty-line snapshot becomes four hundred."""
    nodes = _tree(_node("1", "button", "  Send\n\n   message  "))
    assert perceive.build(nodes).nodes[0].name == "Send message"


def test_a_very_long_label_is_cut_rather_than_carried():
    nodes = _tree(_node("1", "button", "x" * 900))
    name = perceive.build(nodes).nodes[0].name
    assert len(name) <= perceive.MAX_LABEL_CHARS
    assert name.endswith("…")


def test_an_enormous_page_is_truncated_and_says_so():
    nodes = _tree(*[_node(str(i), "button", f"Button {i}") for i in range(perceive.MAX_NODES + 50)])
    snapshot = perceive.build(nodes)
    assert snapshot.truncated is True
    assert len(snapshot.nodes) == perceive.MAX_NODES
    assert "more than" in snapshot.render()


def test_a_handle_nobody_issued_is_refused_with_the_ones_that_exist():
    """Not guessed at. Clicking whatever is at position 12 now, after the page
    moved, is how the wrong record gets deleted."""
    snapshot = perceive.build(_tree(_node("1", "button", "Send")))
    with pytest.raises(LookupError) as caught:
        snapshot.find(99)
    assert "no element 99" in str(caught.value)
    assert "1" in str(caught.value), "the refusal names what does exist"


def test_a_cycle_in_the_tree_does_not_lose_nodes_or_hang():
    """A malformed tree is a page's fault, not a reason to drop half of it."""
    nodes = _tree(
        _node("1", "heading", "A", children=["2"]),
        _node("2", "button", "B", children=["1"]),
    )
    assert {node.name for node in perceive.build(nodes).nodes} == {"A", "B"}


# ── the action vocabulary ───────────────────────────────────────────────────


def test_the_vocabulary_is_ten_verbs_and_none_of_them_runs_code():
    """The rule the whole design rests on: a model names one of these and
    cannot describe a new one. An `evaluate` verb would make the policy layer
    the only thing between a prompt injection and a logged-in session."""
    assert len(ACTIONS) == 10
    for forbidden in ("evaluate", "eval", "exec", "script", "javascript", "query"):
        assert forbidden not in ACTIONS
    assert not any(hasattr(Page, forbidden) for forbidden in ("evaluate", "exec", "query"))


def test_every_verb_in_the_list_is_actually_implemented():
    """The other direction — a vocabulary advertising something that is not
    there is a model being told to use a tool that does not exist."""
    for action in ACTIONS:
        assert callable(getattr(Page, action, None)), f"{action} is advertised and missing"


# ── the trace ───────────────────────────────────────────────────────────────


def test_a_trace_is_append_only_with_no_way_to_remove_a_step():
    """An audit log with an eraser in it is not an audit log."""
    for forbidden in ("delete", "remove", "edit", "truncate", "clear", "update"):
        assert not hasattr(Trace, forbidden), f"Trace should not offer {forbidden}"


def test_steps_survive_a_round_trip_through_the_file(tmp_path):
    trace = Trace.open(tmp_path)
    trace.append(Step(kind="goto", detail="opened Acme", url="https://acme.test", took_ms=120))
    trace.append(Step(kind="click", detail="clicked Send", ok=True, took_ms=40))
    trace.append(Step(kind="model", detail="chose next step", provider_id="nvidia",
                      model_id="llama-3.1", tokens_in=900, tokens_out=40))

    reopened = Trace.open(tmp_path, run_id=trace.run_id)
    assert [step.kind for step in reopened.steps] == ["goto", "click", "model"]
    summary = reopened.summary()
    assert summary["steps"] == 3
    assert summary["tokens_in"] == 900
    assert summary["models"] == ["llama-3.1"]


def test_a_screenshot_lands_beside_the_log_and_not_inside_it(tmp_path):
    """A base64 PNG per step turns a readable log into an unreadable one."""
    trace = Trace.open(tmp_path)
    step = trace.append(Step(kind="screenshot"), screenshot=b"\x89PNG\r\n\x1a\n" + b"\x00" * 32)
    assert step.screenshot == "0000.png"
    shot = trace.directory / step.screenshot
    assert shot.exists()
    assert oct(shot.stat().st_mode)[-3:] == "600"
    assert "PNG" not in trace.path.read_text(encoding="utf-8")


def test_a_half_written_last_line_does_not_cost_the_whole_trace(tmp_path):
    """What a hard kill leaves behind. Everything before it is still good, and
    refusing to read a trace because its final byte is missing is worse."""
    trace = Trace.open(tmp_path)
    trace.append(Step(kind="goto", detail="one"))
    trace.append(Step(kind="click", detail="two"))
    with trace.path.open("a", encoding="utf-8") as handle:
        handle.write('{"kind": "click", "detail": "thr')

    reopened = Trace.open(tmp_path, run_id=trace.run_id)
    assert [step.detail for step in reopened.steps] == ["one", "two"]


def test_a_trace_directory_is_not_world_readable(tmp_path):
    """It holds screenshots of whatever the agent was looking at, which on a
    logged-in session is your mail and your CRM."""
    trace = Trace.open(tmp_path)
    assert oct(trace.directory.stat().st_mode)[-3:] == "700"


# ── the session, without a browser ──────────────────────────────────────────


def test_a_missing_browser_is_refused_with_something_to_do():
    with pytest.raises(BrowserUnavailable, match="already has your logins"):
        find_browser("/no/such/browser")


def _lock(profile_dir, holder: str) -> None:
    """Write a lock the shape Chrome writes: a symlink whose target is the
    record. There is no file to read — the target `hostname-pid` is the data."""
    os.symlink(holder, profile_dir / "SingletonLock")


def test_a_profile_another_browser_has_open_is_detected(tmp_path):
    """Launching a second process against it does not fail loudly — Chrome hands
    off to the running one and exits, and off_CRM would wait forever for a port
    that never opens."""
    assert profile_is_locked(tmp_path) is False
    _lock(tmp_path, f"{socket.gethostname()}-{os.getpid()}")
    assert profile_is_locked(tmp_path) is True


def test_a_lock_left_behind_by_a_browser_that_died_is_not_a_lock(tmp_path):
    """The bug with teeth. A browser stopped by a signal leaves the symlink,
    nothing ever removes it, and counting it as a lock would refuse a profile
    nobody holds — for good. In the box that is the login persisting in the
    volume and becoming unreachable on the next restart."""
    dead = subprocess.Popen([sys.executable, "-c", "pass"])
    dead.wait()

    _lock(tmp_path, f"{socket.gethostname()}-{dead.pid}")
    assert profile_is_locked(tmp_path) is False


def test_a_lock_from_another_host_with_nothing_listening_is_not_a_lock(tmp_path):
    """Every restart of the box. A container's hostname is its id, so the pid in
    the lock is meaningless here and the socket is the only real question — and
    the socket the old container listened on went with it."""
    _lock(tmp_path, "some-other-container-1")
    os.symlink(str(tmp_path / "nothing-is-listening-here"), tmp_path / "SingletonSocket")
    assert profile_is_locked(tmp_path) is False


def test_a_socket_we_are_forbidden_to_probe_stays_locked(tmp_path, monkeypatch):
    """Unknown is not stale. Removing a possibly-live lock lets two browsers
    write the same cookie database, which is worse than refusing to start."""
    _lock(tmp_path, "some-other-container-1")
    target = tmp_path / "still-present.sock"
    target.touch()
    os.symlink(str(target), tmp_path / "SingletonSocket")

    def refused_socket(*_args, **_kwargs):
        raise PermissionError("AF_UNIX is denied by this host")

    monkeypatch.setattr(
        "offsetx_apollo_builder.browser.session.socket.socket",
        refused_socket,
    )
    assert profile_is_locked(tmp_path) is True


def test_clearing_a_stale_lock_removes_it_and_refuses_while_it_is_held(tmp_path):
    """A predicate that deletes is how a caller deletes something by asking, so
    the two are separate — and the deleting one will not act on a live lock."""
    _lock(tmp_path, f"{socket.gethostname()}-{os.getpid()}")
    assert clear_stale_lock(tmp_path) == []
    assert os.path.lexists(tmp_path / "SingletonLock")

    (tmp_path / "SingletonLock").unlink()
    dead = subprocess.Popen([sys.executable, "-c", "pass"])
    dead.wait()
    _lock(tmp_path, f"{socket.gethostname()}-{dead.pid}")
    os.symlink("/no/such/socket", tmp_path / "SingletonCookie")

    # The cookie jar is a file called `Cookies`, and nothing here touches it.
    (tmp_path / "Cookies").write_bytes(b"the logins")

    assert sorted(clear_stale_lock(tmp_path)) == ["SingletonCookie", "SingletonLock"]
    assert not os.path.lexists(tmp_path / "SingletonLock")
    assert (tmp_path / "Cookies").read_bytes() == b"the logins"


# ── against a real browser ──────────────────────────────────────────────────


def _browser_path() -> str:
    try:
        return find_browser()
    except BrowserUnavailable:
        return ""


REAL_BROWSER = _browser_path()
needs_browser = pytest.mark.skipif(
    not REAL_BROWSER, reason="no Chrome, Edge, Brave or Chromium on this machine"
)

PAGE = (
    "data:text/html,<html><head><title>Acme</title></head><body>"
    "<h1>Acme Ltd</h1><p>We make things.</p>"
    "<form><label for=e>Email</label><input id=e type=text>"
    "<button id=go type=button onclick=\"document.getElementById('out')"
    ".textContent='sent to '+document.getElementById('e').value\">Send message</button>"
    "</form><a href='https://example.test/pricing'>Pricing</a><div id=out></div>"
    "</body></html>"
)


async def _drive(work):
    from offsetx_apollo_builder.browser.session import free_port, open_session

    with tempfile.TemporaryDirectory() as profile:
        # `--no-sandbox` only because CI runs as root. Never on a real machine:
        # the sandbox is what stops a page reaching the computer.
        flags = ("--no-sandbox",) if os.geteuid() == 0 else ()
        # A fresh port per test. Sharing one means the second test *attaches* to
        # the first test's browser instead of launching its own — which is the
        # attach-first path working correctly and making the tests share state.
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
def test_a_real_browser_is_driven_end_to_end():
    """The whole stack against a real Chromium: navigate, perceive, type with
    real key events, refuse an unconfirmed send, then send, then read the result
    the page itself produced."""

    async def work(page: Page):
        await page.goto(PAGE)
        snapshot = await page.snapshot()
        names = [node.name for node in snapshot.actions]
        assert "Email" in names and "Send message" in names

        field = next(node for node in snapshot.actions if node.name == "Email")
        await page.type(field.handle, "hello@acme.test")

        # A field whose value was *assigned* looks filled and behaves empty, so
        # this asserts the browser's own view of it after real key events.
        refreshed = await page.snapshot()
        typed = next(node for node in refreshed.nodes if node.role == "textbox")
        assert typed.value == "hello@acme.test"

        send = next(node for node in refreshed.actions if node.name == "Send message")
        blocked = await page.click(send.handle)
        assert blocked.ok is False and blocked.needs_confirmation is True

        done = await page.click(send.handle, confirmed=True)
        assert done.ok is True

        text = (await page.read()).text
        assert "sent to hello@acme.test" in text

        shot = await page.screenshot()
        assert shot.screenshot[:8] == b"\x89PNG\r\n\x1a\n"

        # A number the *current* snapshot never issued, as opposed to one a
        # previous snapshot did — the two refusals are different and both real.
        await page.snapshot()
        with pytest.raises(LookupError):
            await page.click(9999)
        return True

    assert asyncio.run(_drive(work))


@needs_browser
def test_a_dropdown_is_chosen_by_its_visible_label():
    """`select` is the one action that goes through the DOM rather than the
    mouse, because a native dropdown opens an OS-drawn menu no input event can
    reach. It is still not a code path for the model: the function is fixed and
    written in `page.py`, and the model supplies a handle and a label."""

    async def work(page: Page):
        await page.goto(
            "data:text/html,<select id=c>"
            "<option value=gb>United Kingdom</option>"
            "<option value=de>Germany</option></select>"
            "<div id=out></div>"
            "<script>document.getElementById('c').addEventListener('change',"
            "e=>document.getElementById('out').textContent='picked '+e.target.value)</script>"
        )
        snapshot = await page.snapshot()
        dropdown = next(node for node in snapshot.actions
                        if node.role in ("combobox", "listbox", "menuitem"))

        result = await page.select(dropdown.handle, "Germany")
        assert result.ok is True

        # The change event fired, which is the half a value assignment skips.
        assert "picked de" in (await page.read()).text

        # Choosing changed the page, so the old handle is spent and the agent
        # looks again before acting again.
        snapshot = await page.snapshot()
        dropdown = next(node for node in snapshot.actions
                        if node.role in ("combobox", "listbox", "menuitem"))
        with pytest.raises(Exception, match="not one of that dropdown"):
            await page.select(dropdown.handle, "Atlantis")
        return True

    assert asyncio.run(_drive(work))


@needs_browser
def test_a_command_the_browser_does_not_know_raises_rather_than_hangs():
    async def work(page: Page):
        with pytest.raises(cdp.CDPError, match="Nonsense.method"):
            await page.connection.send("Nonsense.method", session_id=page.session_id)
        # And the connection is still usable afterwards, which is the point of
        # failing one waiter rather than the socket.
        result = await page.connection.send(
            "Runtime.evaluate", {"expression": "1+1", "returnByValue": True},
            session_id=page.session_id,
        )
        return result["result"]["value"]

    assert asyncio.run(_drive(work)) == 2


@needs_browser
def test_the_policy_is_enforced_against_the_live_browser_too():
    """Not only in the pure functions — the page object checks before it acts."""

    async def work(page: Page):
        with pytest.raises(policy.Refused):
            await page.goto("file:///etc/passwd")
        page.unattended = True
        with pytest.raises(policy.Refused, match="attended-only"):
            await page.goto("https://www.linkedin.com/feed/")
        return True

    assert asyncio.run(_drive(work))


@needs_browser
def test_a_handle_from_before_the_page_changed_is_refused():
    """The dangerous version of a stale handle, and the reason `_resolve` will
    not re-capture on its own.

    Handles are assigned in document order, so a page that gains one node
    renumbers everything after it. A handle taken before an action then resolves
    against a tree taken after it and points at a *different element* — not at
    nothing. The click succeeds, reports success, and hit the wrong thing.

    Found by typing into a password field: Chrome adds a "reveal password"
    control the moment one has content."""

    async def work(page: Page):
        await page.goto(
            "data:text/html,<button id=a>Alpha</button>"
            "<button id=b onclick=\"document.body.insertAdjacentHTML("
            "'afterbegin','<button>Inserted</button>')\">Beta</button>"
        )
        snapshot = await page.snapshot()
        beta = next(node for node in snapshot.actions if node.name == "Beta")
        alpha = next(node for node in snapshot.actions if node.name == "Alpha")

        # Beta inserts a node at the top, so every handle shifts.
        await page.click(beta.handle, confirmed=True)

        with pytest.raises(ActionRefused, match="page changed"):
            await page.click(alpha.handle, confirmed=True)

        # And the caller's correct move — look again — works.
        fresh = await page.snapshot()
        alpha_again = next(node for node in fresh.actions if node.name == "Alpha")
        result = await page.click(alpha_again.handle, confirmed=True)
        return result.ok, alpha.handle, alpha_again.handle

    ok, before, after = asyncio.run(_drive(work))
    assert ok is True
    assert before != after, "the handles should have shifted, or this proves nothing"
