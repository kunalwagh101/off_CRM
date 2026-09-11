"""What the agent can do to a page. A closed set, and that is the point.

Ten verbs. ``goto``, ``click``, ``type``, ``press``, ``scroll``, ``select``,
``wait_for``, ``read``, ``screenshot``, ``back``.

**A model names one of these. It cannot describe a new one.** The same sentence
`ai/tools.py` is built around, and the reason is identical: if a model could
supply arbitrary JavaScript to run in a logged-in browser session, the policy
layer would be the only thing between a prompt injection on some page and your
Gmail. And a page *will* contain a prompt injection eventually — that is what
the open web is.

So there is no ``evaluate`` verb. Nothing here takes code. Every action names an
element by the integer handle a snapshot gave it, and a handle the snapshot did
not give is refused rather than guessed at.

---

**Every action is real input, not a JavaScript shortcut.**

``element.click()`` in JavaScript dispatches a click event. A real click through
``Input.dispatchMouseEvent`` moves the pointer, presses and releases — which
fires the hover handlers, the focus change and the pointer events that a great
many sites depend on, and which a synthetic event silently skips. The same for
typing: ``Input.insertText`` sets a value; real key events fire the keydown
handlers that search-as-you-type boxes are built on.

It is slower. It is also the difference between an agent that works on real
sites and one that works on the demo.

**Pacing is enforced here, not asked for.** The policy gives a per-host floor
and this file sleeps to meet it. A rate limit that lives in a prompt is a
suggestion.
"""

from __future__ import annotations

import asyncio
import base64
import time
from dataclasses import dataclass, field
from typing import Any

from .budget import COSTED_ACTIONS, Budget, BudgetLedger
from .cdp import CDPConnection, CDPTimeout
from .countdown import Countdown
from .guard import RequestGuard
from .perceive import Snapshot, capture
from .policy import DomainRule, Refused, check_action, check_navigation, rule_for

#: The complete vocabulary. Anything not in here is refused by name.
ACTIONS = (
    "goto", "click", "type", "press", "scroll", "select",
    "wait_for", "read", "screenshot", "back",
)

#: How long a page gets to settle after something that changes it. Not a fixed
#: sleep — the shortest wait that ends when the network goes quiet.
SETTLE_SECONDS = 2.0

#: What `read` may return. A page can contain a novel; a model has a context
#: window. Past this the text is cut and says so.
MAX_READ_CHARS = 20_000


class ActionRefused(ValueError):
    """The action could not be performed, and the message says why."""


@dataclass
class ActionResult:
    """What happened, in a form the trace can store and a model can read."""

    action: str
    ok: bool
    detail: str = ""
    url: str = ""
    text: str = ""
    screenshot: bytes = b""
    took_ms: int = 0
    #: Set when the action needed a countdown and the caller has not run one.
    needs_confirmation: bool = False

    def to_dict(self) -> dict[str, Any]:
        item = {
            "action": self.action,
            "ok": self.ok,
            "detail": self.detail,
            "url": self.url,
            "took_ms": self.took_ms,
        }
        if self.text:
            item["text"] = self.text
        if self.needs_confirmation:
            item["needs_confirmation"] = True
        return item


@dataclass
class Page:
    """One tab, and everything the agent may do to it."""

    connection: CDPConnection
    session_id: str
    #: Whether this is a scheduled run. Decides whether attended-only hosts are
    #: reachable at all — see `policy.py`.
    unattended: bool = False
    #: When each host was last acted on, so the per-host floor can be met.
    _last_action_at: dict[str, float] = field(default_factory=dict)
    _snapshot: Snapshot | None = None
    url: str = ""

    #: Enforces the allow-list, per request, before Chrome dispatches anything.
    #: Attached by :meth:`start` — a tab with no guard is a tab that can reach
    #: anywhere, and defaulting to that would make the box's network boundary
    #: depend on the caller remembering.
    guard: RequestGuard | None = None
    #: Reachable when unattended. Ignored when a person is watching, because
    #: then `policy.py` alone decides.
    allowed_hosts: frozenset[str] = field(default_factory=frozenset)

    #: The account this tab is acting as, and what it has left.  `S-03.02.04`
    #: Both or neither: an account with no ledger cannot be counted, and a
    #: ledger with no account does not know whose budget to spend. Absent means
    #: an unattributed tab — no account is at risk, so nothing is charged.
    ledger: "BudgetLedger | None" = None
    account: str = ""
    budget: "Budget | None" = None

    async def start(self) -> None:
        for domain in ("Page", "Runtime", "DOM", "Network"):
            await self.connection.send(f"{domain}.enable", session_id=self.session_id)
        if self.guard is None:
            self.guard = RequestGuard(
                allowed_hosts=self.allowed_hosts, unattended=self.unattended
            )
        await self.guard.attach(self.connection, self.session_id)

    # ── pacing ──────────────────────────────────────────────────────────────

    def _spend(self, action: str) -> None:
        """Charge one action to this tab's account, or refuse.  `S-03.02.04`

        **Pace and budget answer different questions.** Pace is *how fast* — a
        floor between actions, so the rhythm is human. Budget is *how much* — a
        ceiling per hour and per day, because a human at reading pace for eleven
        hours is still not a human, and that is what gets an account closed
        rather than rate-limited.

        Checked before the action and recorded after it, so an action refused
        further down the method never spends anything. Only the verbs in
        `COSTED_ACTIONS` are charged: `read`, `screenshot` and `wait_for`
        observe what is already on the screen, and charging for looking pushes
        an agent towards acting blind to save budget.
        """
        if self.ledger is None or not self.account or action not in COSTED_ACTIONS:
            return
        budget = self.budget or Budget.for_platform(str(self.account).split(":", 1)[0])
        allowed, reason = self.ledger.check(self.account, budget)
        if not allowed:
            raise ActionRefused(reason)

    async def _pace(self, rule: DomainRule, host: str, action: str = "") -> None:
        """Meet the per-host floor before acting, and stay inside the budget.

        Enforced rather than requested. On a site being driven through your own
        session the thing that gets an account restricted is rhythm — thirty
        actions a minute is not something a person does, and a limit that lives
        in a prompt is a suggestion the model may reasonably decide to ignore.
        """
        if action:
            self._spend(action)
        floor = float(rule.min_seconds_between_actions or 0.0)
        if floor > 0:
            last = self._last_action_at.get(host, 0.0)
            wait = floor - (time.monotonic() - last)
            if wait > 0:
                await asyncio.sleep(wait)
        self._last_action_at[host] = time.monotonic()

    def _charge(self, action: str) -> None:
        """Record an action that actually happened.

        After, not before. An action that raised on the way down — a stale
        handle, an element with no shape — never reached the site, and a budget
        that counts attempts rather than actions would drain on a page the agent
        could not use.
        """
        if self.ledger is not None and self.account and action in COSTED_ACTIONS:
            self.ledger.record(self.account)

    async def _settle(self, timeout: float = SETTLE_SECONDS) -> None:
        """Wait for the page to stop changing, or give up quietly.

        A timeout here is not a failure: plenty of pages keep a socket open
        forever and never go idle. The agent takes a snapshot either way.
        """
        try:
            await self.connection.wait_for_event(
                "Page.loadEventFired", session_id=self.session_id, timeout=timeout
            )
        except CDPTimeout:
            pass
        await asyncio.sleep(0.25)

    # ── seeing ──────────────────────────────────────────────────────────────

    async def snapshot(self) -> Snapshot:
        """What is on the page, with a handle on everything actionable.

        Always a fresh capture. There is no "give me the cached one" flag,
        because that flag was the bug: it captured silently when the cache had
        been dropped, which is exactly the case `_current` exists to refuse.
        """
        self._snapshot = await capture(self.connection, self.session_id)
        self.url = self._snapshot.url
        return self._snapshot

    def _current(self, handle: int) -> Snapshot:
        """The snapshot a handle was numbered against — never a fresh one.

        Handles are assigned in document order, so a page that gained or lost
        one node renumbers everything after it. Every action that changes the
        page therefore drops the cached snapshot, and this refuses rather than
        quietly capturing a new one.

        That distinction is the whole guard. Re-capturing here would resolve a
        handle taken *before* an action against a tree taken *after* it —
        pointing at a **different element** rather than at nothing, so the
        action succeeds and reports success while hitting the wrong thing.
        Found by typing into a password field: Chrome adds a "reveal password"
        control the moment one has content, and every handle after it shifted
        by one.

        So an action after the page changed is refused and the caller looks
        again. That is also how an agent should behave: perceive, act, perceive.
        """
        if self._snapshot is None:
            raise ActionRefused(
                f"The page changed since element {handle} was numbered, so that "
                "number now means something else. Take a fresh snapshot and use "
                "the handle from it."
            )
        return self._snapshot

    async def _resolve(self, handle: int) -> int:
        """Turn a snapshot handle into a live DOM node, or refuse."""
        node = self._current(handle).find(int(handle))
        if not node.backend_id:
            raise ActionRefused(
                f"Element {handle} ({node.role} {node.name!r}) has no position on "
                "the page any more. Take a fresh snapshot."
            )
        return node.backend_id

    async def _box(self, backend_id: int) -> tuple[float, float]:
        """The centre of an element, in viewport coordinates."""
        try:
            result = await self.connection.send(
                "DOM.getBoxModel", {"backendNodeId": int(backend_id)},
                session_id=self.session_id,
            )
        except Exception as exc:  # noqa: BLE001
            raise ActionRefused(
                "That element is not visible on the page — it may have moved, or "
                "need scrolling to. Take a fresh snapshot."
            ) from exc
        quad = (result.get("model") or {}).get("content") or []
        if len(quad) < 8:
            raise ActionRefused("That element has no shape on the page.")
        xs, ys = quad[0::2], quad[1::2]
        return sum(xs) / 4.0, sum(ys) / 4.0

    async def _scroll_into_view(self, backend_id: int) -> None:
        try:
            await self.connection.send(
                "DOM.scrollIntoViewIfNeeded", {"backendNodeId": int(backend_id)},
                session_id=self.session_id,
            )
        except Exception:  # noqa: BLE001 - not every node supports it, and that is fine
            pass

    # ── doing ───────────────────────────────────────────────────────────────

    async def goto(self, url: str) -> ActionResult:
        started = time.monotonic()
        rule = check_navigation(url, unattended=self.unattended)
        await self._pace(rule, rule.suffix, "goto")
        await self.connection.send("Page.navigate", {"url": url}, session_id=self.session_id)
        await self._settle()
        self._snapshot = None
        snapshot = await self.snapshot()
        self._charge("goto")
        return ActionResult(
            action="goto", ok=True, url=snapshot.url,
            detail=f"opened {snapshot.title or snapshot.url}",
            took_ms=int((time.monotonic() - started) * 1000),
        )

    async def click(
        self,
        handle: int,
        *,
        confirmed: bool = False,
        countdown: "Countdown | None" = None,
    ) -> ActionResult:
        """A real mouse click: move, press, release.

        Not ``element.click()``. A synthetic event skips the hover, focus and
        pointer handlers a great many sites are built on, and the failure is
        silent — the click "works" and nothing happens.

        `countdown` is how an *attended* caller clears a sensitive action: a
        visible delay the owner can cancel, instead of a dialog they learn to
        click through.  `S-02.02.04`
        """
        started = time.monotonic()
        node = self._current(handle).find(int(handle))
        rule, needs = check_action(_intent(node.role, node.name), self.url,
                                   unattended=self.unattended)

        if needs and countdown is not None:
            # A countdown with nobody watching is the human gate deleted while
            # looking like it is still there. The rule lives here rather than
            # only in the architecture note that states it.  `S-02.02.04`
            if self.unattended:
                return ActionResult(
                    action="click", ok=False, needs_confirmation=True, url=self.url,
                    detail=(
                        "A countdown cannot stand in for confirmation in an "
                        "unattended run — there is nobody to cancel it. This "
                        "action needs the owner."
                    ),
                )
            if not await countdown.run():
                # Nothing was sent and nothing is charged: a cancelled
                # countdown must not cost the account a thing, or cancelling
                # becomes expensive and people stop doing it.
                return ActionResult(
                    action="click", ok=False, url=self.url,
                    detail=(
                        f"Cancelled during the countdown before clicking "
                        f"{node.name or node.role!r}: {countdown.reason}"
                    ),
                    took_ms=int((time.monotonic() - started) * 1000),
                )
            confirmed = True

        if needs and not confirmed:
            # No charge: this is a refusal asking for confirmation, and nothing
            # was sent to the site. Charging here would let a countdown the
            # owner cancels still eat the account's budget.
            return ActionResult(
                action="click", ok=False, needs_confirmation=True, url=self.url,
                detail=f"clicking {node.name or node.role!r} sends or changes "
                       "something. Confirm it first.",
            )
        await self._pace(rule, rule.suffix, "click")
        backend_id = await self._resolve(handle)
        await self._scroll_into_view(backend_id)
        x, y = await self._box(backend_id)

        await self.connection.send(
            "Input.dispatchMouseEvent",
            {"type": "mouseMoved", "x": x, "y": y, "button": "none"},
            session_id=self.session_id,
        )
        for kind in ("mousePressed", "mouseReleased"):
            await self.connection.send(
                "Input.dispatchMouseEvent",
                {"type": kind, "x": x, "y": y, "button": "left", "clickCount": 1},
                session_id=self.session_id,
            )
        await self._settle(timeout=1.5)
        self._snapshot = None
        self._charge("click")
        return ActionResult(
            action="click", ok=True, url=self.url,
            detail=f"clicked {node.role} {node.name!r}".rstrip(),
            took_ms=int((time.monotonic() - started) * 1000),
        )

    async def type(self, handle: int, text: str, *, clear: bool = True) -> ActionResult:
        """Focus a field and type into it, key by key.

        Real key events rather than setting a value, because search-as-you-type
        boxes, validators and autocomplete are all built on keydown — and a field
        whose value was assigned looks filled and behaves empty.
        """
        started = time.monotonic()
        rule = rule_for(self.url)
        await self._pace(rule, rule.suffix, "type")
        backend_id = await self._resolve(handle)
        await self._scroll_into_view(backend_id)
        await self.connection.send(
            "DOM.focus", {"backendNodeId": backend_id}, session_id=self.session_id
        )
        if clear:
            # Select-all then type over it. Sending an empty value would not
            # fire the handlers that notice a field being emptied.
            for key, code in (("a", 65),):
                for kind in ("keyDown", "keyUp"):
                    await self.connection.send(
                        "Input.dispatchKeyEvent",
                        {"type": kind, "key": key, "code": "KeyA",
                         "windowsVirtualKeyCode": code, "modifiers": 2},
                        session_id=self.session_id,
                    )
        for character in str(text):
            await self.connection.send(
                "Input.dispatchKeyEvent",
                {"type": "keyDown", "text": character, "key": character},
                session_id=self.session_id,
            )
            await self.connection.send(
                "Input.dispatchKeyEvent",
                {"type": "keyUp", "key": character},
                session_id=self.session_id,
            )
        self._snapshot = None
        self._charge("type")
        return ActionResult(
            action="type", ok=True, url=self.url,
            detail=f"typed {len(str(text))} character(s)",
            took_ms=int((time.monotonic() - started) * 1000),
        )

    async def select(self, handle: int, option: str) -> ActionResult:
        """Choose an option in a dropdown.

        A native `<select>` opens an OS-drawn menu that `Input` events cannot
        reach, so this one action goes through the DOM rather than the mouse.

        **It is still not a code path for the model.** The function below is
        fixed, written here, and takes the option as a *string argument*; the
        model supplies a handle and a label, exactly as it does for a click. The
        difference from an `evaluate` verb is the difference between a catalogue
        and a constructor, which is the same line `ai/tools.py` draws.
        """
        started = time.monotonic()
        rule = rule_for(self.url)
        await self._pace(rule, rule.suffix, "select")
        backend_id = await self._resolve(handle)
        resolved = await self.connection.send(
            "DOM.resolveNode", {"backendNodeId": backend_id}, session_id=self.session_id
        )
        object_id = str((resolved.get("object") or {}).get("objectId") or "")
        if not object_id:
            raise ActionRefused("That element is no longer on the page.")

        result = await self.connection.send(
            "Runtime.callFunctionOn",
            {
                "objectId": object_id,
                # Matches on the visible label first and the value second,
                # because an instruction says "choose United Kingdom" and not
                # "choose GB".
                "functionDeclaration": """
                    function (wanted) {
                      if (this.tagName !== 'SELECT') return 'not-a-dropdown';
                      const want = String(wanted).trim().toLowerCase();
                      for (const option of this.options) {
                        const label = (option.label || option.text || '').trim().toLowerCase();
                        if (label === want || String(option.value).toLowerCase() === want) {
                          this.value = option.value;
                          this.dispatchEvent(new Event('input', {bubbles: true}));
                          this.dispatchEvent(new Event('change', {bubbles: true}));
                          return 'ok:' + (option.label || option.text);
                        }
                      }
                      return 'no-option:' + [...this.options]
                        .map(o => (o.label || o.text || '').trim()).slice(0, 20).join(' | ');
                    }
                """,
                "arguments": [{"value": str(option)}],
                "returnByValue": True,
            },
            session_id=self.session_id,
        )
        answer = str((result.get("result") or {}).get("value") or "")
        if answer == "not-a-dropdown":
            raise ActionRefused(f"Element {handle} is not a dropdown.")
        if answer.startswith("no-option:"):
            raise ActionRefused(
                f"{option!r} is not one of that dropdown's options. It offers: "
                + answer[len("no-option:"):]
            )
        self._snapshot = None
        self._charge("select")
        return ActionResult(
            action="select", ok=True, url=self.url,
            detail=f"chose {answer[len('ok:'):]!r}",
            took_ms=int((time.monotonic() - started) * 1000),
        )

    async def press(self, key: str) -> ActionResult:
        """One named key. Enter, Tab, Escape, the arrows."""
        started = time.monotonic()
        name = str(key or "").strip()
        codes = {
            "Enter": 13, "Tab": 9, "Escape": 27, "Backspace": 8,
            "ArrowDown": 40, "ArrowUp": 38, "ArrowLeft": 37, "ArrowRight": 39,
            "PageDown": 34, "PageUp": 33, "Home": 36, "End": 35,
        }
        if name not in codes:
            raise ActionRefused(
                f"{name!r} is not a key the agent may press. Known: "
                + ", ".join(sorted(codes))
            )
        # `press` was previously the one interaction that skipped the pace gate,
        # so Enter could be sent at machine speed on a host slowed everywhere
        # else. Found while wiring budgets: the list of verbs that spend was not
        # the list of verbs that were paced.
        await self._pace(rule_for(self.url), rule_for(self.url).suffix, "press")
        for kind in ("keyDown", "keyUp"):
            await self.connection.send(
                "Input.dispatchKeyEvent",
                {"type": kind, "key": name, "code": name,
                 "windowsVirtualKeyCode": codes[name], "nativeVirtualKeyCode": codes[name]},
                session_id=self.session_id,
            )
        await self._settle(timeout=1.5)
        self._snapshot = None
        self._charge("press")
        return ActionResult(
            action="press", ok=True, url=self.url, detail=f"pressed {name}",
            took_ms=int((time.monotonic() - started) * 1000),
        )

    async def scroll(self, *, down: int = 1) -> ActionResult:
        """A wheel, not a scrollTop assignment — infinite feeds listen for it."""
        started = time.monotonic()
        rule = rule_for(self.url)
        await self._pace(rule, rule.suffix, "scroll")
        await self.connection.send(
            "Input.dispatchMouseEvent",
            {"type": "mouseWheel", "x": 400, "y": 400,
             "deltaX": 0, "deltaY": 600 * int(down)},
            session_id=self.session_id,
        )
        await asyncio.sleep(0.4)
        self._snapshot = None
        self._charge("scroll")
        return ActionResult(
            action="scroll", ok=True, url=self.url,
            detail=f"scrolled {'down' if down > 0 else 'up'}",
            took_ms=int((time.monotonic() - started) * 1000),
        )

    async def read(self, *, limit: int = MAX_READ_CHARS) -> ActionResult:
        """The page's text, for when the agent needs the content and not the shape."""
        started = time.monotonic()
        result = await self.connection.send(
            "Runtime.evaluate",
            {"expression": "document.body ? document.body.innerText : ''",
             "returnByValue": True},
            session_id=self.session_id,
        )
        text = str((result.get("result") or {}).get("value") or "")
        cut = len(text) > limit
        return ActionResult(
            action="read", ok=True, url=self.url,
            text=text[:limit] + ("\n… (cut)" if cut else ""),
            detail=f"read {min(len(text), limit)} characters" + (" (cut)" if cut else ""),
            took_ms=int((time.monotonic() - started) * 1000),
        )

    async def screenshot(self) -> ActionResult:
        """A picture, for the trace and for a person watching."""
        started = time.monotonic()
        result = await self.connection.send(
            "Page.captureScreenshot", {"format": "png"}, session_id=self.session_id
        )
        raw = base64.b64decode(str(result.get("data") or ""))
        return ActionResult(
            action="screenshot", ok=True, url=self.url, screenshot=raw,
            detail=f"{len(raw)} bytes",
            took_ms=int((time.monotonic() - started) * 1000),
        )

    async def back(self) -> ActionResult:
        started = time.monotonic()
        history = await self.connection.send("Page.getNavigationHistory",
                                             session_id=self.session_id)
        index = int(history.get("currentIndex") or 0)
        entries = history.get("entries") or []
        if index <= 0 or not entries:
            raise ActionRefused("There is nothing to go back to.")
        await self._pace(rule_for(self.url), rule_for(self.url).suffix, "back")
        await self.connection.send(
            "Page.navigateToHistoryEntry", {"entryId": entries[index - 1]["id"]},
            session_id=self.session_id,
        )
        await self._settle()
        self._snapshot = None
        snapshot = await self.snapshot()
        self._charge("back")
        return ActionResult(
            action="back", ok=True, url=snapshot.url, detail="went back",
            took_ms=int((time.monotonic() - started) * 1000),
        )

    async def wait_for(self, text: str, *, timeout: float = 10.0) -> ActionResult:
        """Poll until some text appears. The honest version of `sleep`."""
        started = time.monotonic()
        needle = str(text or "").strip().lower()
        if not needle:
            raise ActionRefused("wait_for needs something to wait for.")
        deadline = time.monotonic() + float(timeout)
        while time.monotonic() < deadline:
            result = await self.connection.send(
                "Runtime.evaluate",
                {"expression": "document.body ? document.body.innerText : ''",
                 "returnByValue": True},
                session_id=self.session_id,
            )
            if needle in str((result.get("result") or {}).get("value") or "").lower():
                self._snapshot = None
                return ActionResult(
                    action="wait_for", ok=True, url=self.url,
                    detail=f"{text!r} appeared",
                    took_ms=int((time.monotonic() - started) * 1000),
                )
            await asyncio.sleep(0.3)
        return ActionResult(
            action="wait_for", ok=False, url=self.url,
            detail=f"{text!r} did not appear in {timeout:.0f}s",
            took_ms=int((time.monotonic() - started) * 1000),
        )


def _intent(role: str, name: str) -> str:
    """What clicking this thing probably does, for the countdown rule.

    Deliberately crude and deliberately cautious: it reads the label, and a
    false positive costs five seconds while a false negative sends an email
    nobody wrote.
    """
    label = f"{role} {name}".lower()
    for word in ("delete", "remove", "send", "submit", "publish", "buy", "purchase",
                 "pay", "confirm", "apply", "connect", "invite", "post"):
        if word in label:
            return {"buy": "purchase", "pay": "purchase", "post": "publish",
                    "remove": "delete", "confirm": "submit", "apply": "submit",
                    "invite": "send"}.get(word, word)
    return "click"
