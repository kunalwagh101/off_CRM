"""Enter is gated like the button beside it.  `S-11.03.03`

`D-25`, found on 2026-09-10 while building something else and verified then:
`check_action` was called exactly once in `browser/page.py`, inside `click`.
`press` called it zero times. Enter in a compose form is pressing Send — so the
gate that stopped the agent clicking Send did not stop it sending.

That is the defect log's pattern 3 again: **two lists that must match, drifting
apart.** The fix is therefore not a second copy of the check inside `press`. It
is one gate that both callers go through, so the set of things that need a human
and the set of things that get asked about are the same set by construction.

The second acceptance criterion is the one that keeps this usable: *a key that
cannot submit anything asks nothing new*. A gate that interrupts every keystroke
is worse than no gate, because people switch off things that ask too often.
"""
from __future__ import annotations

import asyncio

import pytest

from offsetx_apollo_builder.browser.countdown import Countdown
from offsetx_apollo_builder.browser.page import (
    SUBMITTING_KEYS,
    ActionRefused,
    Page,
)
from offsetx_apollo_builder.browser.perceive import Node, Snapshot

PAGE = Snapshot(
    url="https://acme.test/contact",
    title="Contact Acme",
    nodes=[Node(handle=1, role="textbox", name="Message"),
           Node(handle=2, role="button", name="Send")],
)


class _Connection:
    """A page that answers "what would Enter do?" with whatever the test says."""

    def __init__(self, enter_target=None, *, evaluate_fails: bool = False):
        self.enter_target = enter_target if enter_target is not None else {
            "role": "", "label": ""}
        self.evaluate_fails = evaluate_fails
        self.sent: list[str] = []
        self.events: list[dict] = []

    async def send(self, method, params=None, *, session_id="", timeout=None):
        self.sent.append(method)
        if method == "Input.dispatchKeyEvent":
            self.events.append(dict(params or {}))
        if method == "Runtime.evaluate":
            if self.evaluate_fails:
                raise RuntimeError("this frame refuses evaluation")
            return {"result": {"value": self.enter_target}}
        if method == "DOM.getBoxModel":
            return {"model": {"content": [0, 0, 10, 0, 10, 10, 0, 10]}}
        return {}

    @property
    def keys_dispatched(self) -> int:
        return self.sent.count("Input.dispatchKeyEvent")


def _page(enter_target=None, *, unattended=False, evaluate_fails=False) -> Page:
    page = Page(connection=_Connection(enter_target, evaluate_fails=evaluate_fails),
                session_id="s", unattended=unattended)
    page.url = PAGE.url
    page._snapshot = PAGE
    return page


@pytest.fixture(autouse=True)
def _no_real_dom(monkeypatch):
    """Everything below the gate, stubbed. These tests are about the gate."""
    async def _none(*args, **kwargs):
        return None

    async def _backend(self, handle):
        return 42

    async def _point(self, backend_id):
        return (5.0, 5.0)

    monkeypatch.setattr(Page, "_settle", _none)
    monkeypatch.setattr(Page, "_resolve", _backend)
    monkeypatch.setattr(Page, "_scroll_into_view", _none)
    monkeypatch.setattr(Page, "_box", _point)


# ── Enter must be gated where Send is ───────────────────────────────────────


def test_enter_on_a_focused_send_button_needs_confirmation():
    page = _page({"role": "button", "label": "Send"})
    result = asyncio.run(page.press("Enter"))

    assert result.needs_confirmation is True
    assert result.ok is False
    assert page.connection.keys_dispatched == 0, "the key was sent anyway"


def test_enter_in_a_field_whose_form_submits_with_send_needs_confirmation():
    """The criterion, word for word: *when the agent presses Enter in the same
    form*. The accessibility tree cannot answer this — it knows what is focused
    and not what form it belongs to — so the page is asked."""
    page = _page({"role": "button", "label": "Send message"})
    result = asyncio.run(page.press("Enter"))

    assert result.needs_confirmation is True
    assert page.connection.keys_dispatched == 0


@pytest.mark.parametrize("label", ["Delete account", "Publish now", "Buy it",
                                   "Submit application", "Pay now"])
def test_every_consequential_label_is_caught_the_same_way_a_click_would_be(label):
    """Enter and click ask the same function, so this list cannot drift from
    the one `click` honours."""
    page = _page({"role": "button", "label": label})
    assert asyncio.run(page.press("Enter")).needs_confirmation is True


def test_if_the_page_cannot_be_asked_it_fails_closed():
    """A gate that fails open is not a gate. `_intent` says why in its own
    words: a false positive costs five seconds and a false negative sends an
    email nobody wrote."""
    page = _page(evaluate_fails=True)
    result = asyncio.run(page.press("Enter"))

    assert result.needs_confirmation is True
    assert page.connection.keys_dispatched == 0


def test_a_nonsense_answer_from_the_page_also_fails_closed():
    page = _page("not a dict at all")
    assert asyncio.run(page.press("Enter")).needs_confirmation is True


# ── and must not be gated anywhere else ─────────────────────────────────────


@pytest.mark.parametrize("key", ["Tab", "Escape", "Backspace", "ArrowDown",
                                 "ArrowUp", "PageDown", "Home", "End"])
def test_a_key_that_cannot_submit_asks_nothing(key):
    """The second criterion. A gate that interrupts every keystroke is worse
    than no gate, because people switch off things that ask too often."""
    page = _page({"role": "button", "label": "Send"})
    result = asyncio.run(page.press(key))

    assert result.ok is True
    assert result.needs_confirmation is False
    assert page.connection.keys_dispatched == 2, "keyDown and keyUp"


def test_only_enter_is_treated_as_able_to_submit():
    assert SUBMITTING_KEYS == {"Enter"}


def test_a_key_that_cannot_submit_does_not_even_ask_the_page():
    """Not just "is not gated" — costs nothing at all. A round trip per
    arrow key would make scrolling through a feed absurd."""
    page = _page({"role": "button", "label": "Send"})
    asyncio.run(page.press("ArrowDown"))
    assert "Runtime.evaluate" not in page.connection.sent


def test_enter_with_nothing_focused_is_ordinary():
    page = _page({"role": "", "label": ""})
    result = asyncio.run(page.press("Enter"))

    assert result.ok is True
    assert page.connection.keys_dispatched == 2


def test_enter_in_a_search_box_is_ordinary():
    """The commonest Enter there is. If this asks, the feature is unusable."""
    page = _page({"role": "button", "label": "Search"})
    assert asyncio.run(page.press("Enter")).ok is True


def test_enter_on_an_ordinary_link_is_ordinary():
    page = _page({"role": "link", "label": "About us"})
    assert asyncio.run(page.press("Enter")).ok is True


def test_an_unknown_key_is_still_refused_outright():
    page = _page()
    with pytest.raises(ActionRefused):
        asyncio.run(page.press("F13"))


# ── the same gate, not a second copy of it ──────────────────────────────────


def test_enter_and_click_agree_about_what_needs_a_human():
    """The actual fix. Not "press now also checks" — *press asks the same
    function*, so these two can never disagree again."""
    for label in ("Send", "Delete", "Publish", "About us", "Search", "Next page"):
        click_page = _page()
        click_page._snapshot = Snapshot(
            url=PAGE.url, title="x",
            nodes=[Node(handle=1, role="button", name=label)])
        press_page = _page({"role": "button", "label": label})

        clicked = asyncio.run(click_page.click(1))
        pressed = asyncio.run(press_page.press("Enter"))

        assert clicked.needs_confirmation == pressed.needs_confirmation, (
            f"click and Enter disagree about {label!r}"
        )


def test_enter_can_be_cleared_by_a_countdown_like_a_click_can():
    page = _page({"role": "button", "label": "Send"})
    result = asyncio.run(page.press("Enter", countdown=Countdown(seconds=0.1)))

    assert result.ok is True
    assert page.connection.keys_dispatched == 2


def test_a_cancelled_countdown_sends_no_keystroke():
    page = _page({"role": "button", "label": "Send"})
    countdown = Countdown(seconds=5.0)

    async def go():
        task = asyncio.get_running_loop().create_task(
            page.press("Enter", countdown=countdown))
        await asyncio.sleep(0.05)
        countdown.cancel("no")
        return await task

    result = asyncio.run(go())
    assert result.ok is False
    assert page.connection.keys_dispatched == 0


def test_an_unattended_run_cannot_countdown_its_way_past_enter_either():
    page = _page({"role": "button", "label": "Send"}, unattended=True)
    result = asyncio.run(page.press("Enter", countdown=Countdown(seconds=0.01)))

    assert result.needs_confirmation is True
    assert page.connection.keys_dispatched == 0


# ── the key has to actually do something  `D-40` ────────────────────────────


def test_enter_is_sent_with_the_character_it_produces():
    """Found by the live check, which could not demonstrate the hole it was
    closing. A key event dispatched without `text` is raised on the page and
    then does **nothing** — Chrome performs no default action — so Enter had
    never submitted a form. Measured key by key: Tab and Backspace work either
    way, Enter only with this."""
    page = _page({"role": "", "label": ""})
    asyncio.run(page.press("Enter"))

    down = [e for e in page.connection.events if e["type"] == "keyDown"]
    assert len(down) == 1
    assert down[0]["text"] == "\r"
    assert down[0]["unmodifiedText"] == "\r"


def test_tab_carries_its_character_too():
    page = _page()
    asyncio.run(page.press("Tab"))
    down = [e for e in page.connection.events if e["type"] == "keyDown"]
    assert down[0]["text"] == "\t"


@pytest.mark.parametrize("key", ["Escape", "Backspace", "ArrowDown", "Home"])
def test_a_key_that_produces_no_character_sends_none(key):
    """Only the keys that type something get `text`. Backspace and the arrows
    are commands, and they were measured working without it."""
    page = _page()
    asyncio.run(page.press(key))
    down = [e for e in page.connection.events if e["type"] == "keyDown"]
    assert "text" not in down[0], f"{key} was given a character it does not produce"


def test_every_key_the_agent_may_press_has_a_code():
    """The set, not the member. `KEY_TEXT` is allowed to be a subset of
    `KEY_CODES`; the reverse would be a key that cannot be dispatched."""
    from offsetx_apollo_builder.browser.page import KEY_CODES, KEY_TEXT

    assert set(KEY_TEXT) <= set(KEY_CODES)
    assert all(isinstance(code, int) and code > 0 for code in KEY_CODES.values())

