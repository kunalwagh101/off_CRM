"""A visible, cancellable delay before something irreversible.  `S-02.02.04`

One acceptance criterion — *it does not fire until the countdown elapses, and it
can be cancelled during it* — and the dangerous way to pass it is to build a
sleep. A sleep satisfies "does not fire until" and fails the half that matters.

So the tests here are mostly about the cancel: that it works, that it works
promptly, that it works from another thread, that a cancelled action sends
nothing and costs nothing, and that a countdown cannot be reused to wave
through a second action.

And one that is not about the countdown at all: **an unattended run cannot use
one.** `AUTONOMOUS_BROWSING.md` says E-11 does not auto-confirm anything, and a
countdown with nobody watching is the human gate deleted while still looking
like it is there. That rule is worth more than the feature.
"""
from __future__ import annotations

import asyncio
import threading
import time

import pytest

from offsetx_apollo_builder.browser.countdown import (
    DEFAULT_SECONDS,
    Countdown,
    CountdownSpent,
)
from offsetx_apollo_builder.browser.page import ActionResult, Page
from offsetx_apollo_builder.browser.perceive import Node, Snapshot


# ── the countdown on its own ────────────────────────────────────────────────


def test_it_waits_the_whole_time_before_saying_yes():
    countdown = Countdown(seconds=0.3)
    started = time.monotonic()
    assert asyncio.run(countdown.run()) is True
    assert time.monotonic() - started >= 0.3


def test_policy_says_five_seconds_and_that_is_the_default():
    """The number is stated in `policy.py`'s own docstring. If it changes there
    and not here, the document is describing something that does not exist."""
    assert DEFAULT_SECONDS == 5.0
    assert Countdown().seconds == 5.0


def test_cancelling_stops_it_and_says_so():
    countdown = Countdown(seconds=5.0)

    async def go():
        task = asyncio.get_running_loop().create_task(countdown.run())
        await asyncio.sleep(0.05)
        countdown.cancel("changed my mind")
        return await task

    assert asyncio.run(go()) is False
    assert countdown.cancelled
    assert countdown.reason == "changed my mind"


def test_cancelling_is_prompt_rather_than_eventually():
    """A control that takes a second to notice is a decoration. The whole
    feature is somebody reaching for a button and it working."""
    countdown = Countdown(seconds=30.0)

    async def go():
        task = asyncio.get_running_loop().create_task(countdown.run())
        await asyncio.sleep(0.05)
        started = time.monotonic()
        countdown.cancel()
        await task
        return time.monotonic() - started

    assert asyncio.run(go()) < 0.5


def test_it_can_be_cancelled_from_another_thread():
    """The cancel comes from a person, and a person is never on the event
    loop — it arrives from a request handler on some other thread."""
    countdown = Countdown(seconds=5.0)

    async def go():
        task = asyncio.get_running_loop().create_task(countdown.run())
        await asyncio.sleep(0.05)
        threading.Thread(target=countdown.cancel, args=("from the UI",)).start()
        return await task

    assert asyncio.run(go()) is False
    assert countdown.reason == "from the UI"


def test_cancelled_before_it_starts_is_still_cancelled():
    countdown = Countdown(seconds=5.0)
    countdown.cancel("too late, I saw it")
    assert asyncio.run(countdown.run()) is False


def test_somebody_watching_sees_it_count_down():
    """"Visible" is the other half of the criterion. A silent delay is a sleep."""
    seen: list[int] = []
    countdown = Countdown(seconds=0.3, on_tick=seen.append)
    asyncio.run(countdown.run())

    assert seen, "nothing was reported to the watcher"
    assert seen == sorted(seen, reverse=True), f"it did not count down: {seen}"
    assert seen[-1] == 0, "it never announced that it had finished"


def test_the_watcher_is_told_once_a_second_not_once_a_poll():
    """A watcher wants 5, 4, 3, 2, 1 — not two hundred callbacks."""
    seen: list[int] = []
    asyncio.run(Countdown(seconds=1.0, on_tick=seen.append).run())
    assert len(seen) <= 4, f"far too chatty: {len(seen)} ticks"


def test_a_watcher_that_throws_cannot_fire_or_stop_the_action():
    """The same rule the trace listener follows: somebody's terminal going away
    must not decide whether something irreversible happens."""
    def explode(_remaining):
        raise RuntimeError("the terminal went away")

    assert asyncio.run(Countdown(seconds=0.2, on_tick=explode).run()) is True


def test_a_countdown_covers_one_action_and_no_more():
    """Otherwise "the owner watched this one elapse" becomes a token that waves
    through something they never saw."""
    countdown = Countdown(seconds=0.1)
    assert asyncio.run(countdown.run()) is True
    with pytest.raises(CountdownSpent):
        asyncio.run(countdown.run())


def test_a_cancelled_countdown_is_also_spent():
    countdown = Countdown(seconds=5.0)
    countdown.cancel()
    assert asyncio.run(countdown.run()) is False
    with pytest.raises(CountdownSpent):
        asyncio.run(countdown.run())


# ── through the action gate ─────────────────────────────────────────────────


#: A plain site rather than Gmail. `send` is in `SENSITIVE_ACTIONS`, so it needs
#: a countdown wherever it appears — and a host with no rule of its own keeps
#: these tests about the countdown instead of about Gmail's attended-only rule,
#: which refuses first and would make the unattended test pass for the wrong
#: reason.
SEND_BUTTON = Snapshot(
    url="https://acme.test/contact",
    title="Contact Acme",
    nodes=[Node(handle=1, role="button", name="Send")],
)


class _Connection:
    def __init__(self):
        self.sent: list[str] = []

    async def send(self, method, params=None, *, session_id="", timeout=None):
        self.sent.append(method)
        if method == "DOM.getBoxModel":
            return {"model": {"content": [0, 0, 10, 0, 10, 10, 0, 10]}}
        if method == "DOM.resolveNode":
            return {"object": {"objectId": "o1"}}
        return {}


def _page(*, unattended: bool = False) -> Page:
    page = Page(connection=_Connection(), session_id="s", unattended=unattended)
    page.url = SEND_BUTTON.url
    page._snapshot = SEND_BUTTON
    return page


async def _resolve(self, handle):  # a backend id without a real DOM
    return 42


@pytest.fixture(autouse=True)
def _no_real_dom(monkeypatch):
    monkeypatch.setattr(Page, "_resolve", _resolve)
    monkeypatch.setattr(Page, "_scroll_into_view", lambda self, backend_id: _none())
    monkeypatch.setattr(Page, "_box", lambda self, backend_id: _point())
    monkeypatch.setattr(Page, "_settle", lambda self, timeout=1.5: _none())


async def _none():
    return None


async def _point():
    return (5.0, 5.0)


def test_without_a_countdown_a_send_still_refuses_and_asks(tmp_path):
    """The behaviour that was already there must not have changed. This story
    adds a way through the gate; it does not widen it."""
    page = _page()
    result = asyncio.run(page.click(1))
    assert result.needs_confirmation is True
    assert result.ok is False
    assert "Input.dispatchMouseEvent" not in page.connection.sent


def test_a_countdown_that_elapses_lets_the_click_through():
    page = _page()
    result = asyncio.run(page.click(1, countdown=Countdown(seconds=0.1)))
    assert result.ok is True
    assert "Input.dispatchMouseEvent" in page.connection.sent


def test_a_cancelled_countdown_sends_nothing_to_the_site():
    """The point of the whole feature. Not "reports failure" — sends nothing."""
    page = _page()
    countdown = Countdown(seconds=5.0)

    async def go():
        task = asyncio.get_running_loop().create_task(
            page.click(1, countdown=countdown))
        await asyncio.sleep(0.05)
        countdown.cancel("no, wait")
        return await task

    result = asyncio.run(go())
    assert result.ok is False
    assert "no, wait" in result.detail
    assert "Input.dispatchMouseEvent" not in page.connection.sent


def test_an_unattended_run_cannot_use_a_countdown():
    """The rule that matters more than the feature. `AUTONOMOUS_BROWSING.md`:
    E-11 does not auto-confirm anything. A countdown with nobody watching is a
    sleep, and the human gate deleted while looking like it is still there."""
    page = _page(unattended=True)
    result = asyncio.run(page.click(1, countdown=Countdown(seconds=0.01)))

    assert result.ok is False
    assert result.needs_confirmation is True
    assert "nobody to cancel it" in result.detail
    assert "Input.dispatchMouseEvent" not in page.connection.sent


def test_an_ordinary_click_never_waits_for_anything():
    """A countdown on every link would make the agent unusable, and people
    disable things that are unusable."""
    page = _page()
    page._snapshot = Snapshot(url="https://acme.test/", title="Acme",
                              nodes=[Node(handle=1, role="link", name="About us")])
    page.url = "https://acme.test/"

    started = time.monotonic()
    result = asyncio.run(page.click(1, countdown=Countdown(seconds=5.0)))

    assert result.ok is True
    assert time.monotonic() - started < 1.0, "a harmless link was made to wait"
