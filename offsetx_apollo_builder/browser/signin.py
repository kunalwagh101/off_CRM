"""Signing in, with off_CRM out of the way.

`S-03.02.01` owns the attended sign-in flow; `S-03.02.02` adds the vault step
that makes a successful session safe to retain. `identity.py` knows *which*
platforms exist and how to tell whether you are signed in; this is what happens
in between.

---

**The shape of it, and why it is shaped this way.**

    off_CRM   opens the platform's own login page inside the box
    you       type your password, with your own fingers
    off_CRM   watches the page until a signed-in signal appears
    vault     copies only that platform's session cookies into encrypted storage
    off_CRM   writes down "linkedin: connected"

The order of the last two steps is deliberate. A connection is never recorded
as connected until the vault has protected the session material. If vaulting
fails, the flow fails closed and tells the owner; it does not paint a green
connection badge over an unprotected session.

There is no step where a credential passes through a model, because there is no
step where a model types. `page.type()` exists and is deliberately **not used
here** — the agent's ten verbs are for the agent, and an agent that could fill a
password field is an agent that could be talked into filling it somewhere else.

**Your keystrokes reach the browser without being read.** The person types into
a live view of the box and those events are forwarded unopened: not logged, not
stored, not inspected, not put in the trace. The trace records *that you typed*,
never what. That is a weaker claim than "off_CRM never touches the bytes", and
it is the true one: they cross a loopback socket in this process. Saying so is
better than implying a wall that is not there.

**Waiting is bounded and observed.** A sign-in involves a password manager, a
2FA code, a device check, sometimes a phone. So the wait is generous — minutes,
not seconds — and it is a *poll of the page*, not a timer. It ends when the page
says you are in, or when you give up, and never because a clock ran out while
you were reading a text message.
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass
from typing import Any

from .identity import (
    Connection,
    ConnectionStore,
    Platform,
    Reading,
    platform as lookup_platform,
    read_state,
)
from .page import Page
from .policy import Refused
from .vault import SessionVault, VaultError

#: How long a sign-in may take before off_CRM stops watching. Long, because a
#: password manager plus a 2FA code plus a device check is genuinely minutes,
#: and a flow that gives up at ninety seconds is one people abandon.
DEFAULT_TIMEOUT = 600.0

#: How often the page is re-read. Slow enough not to look like automation to the
#: platform, fast enough that the screen updates while you watch it.
POLL_SECONDS = 2.0


class SignInRefused(RuntimeError):
    """The sign-in could not safely complete, and the message says what to do."""


@dataclass
class SignInAttempt:
    """One sign-in, and what happened. **Holds no credential.**"""

    platform: str
    state: str = "waiting"
    reading: Reading | None = None
    #: Seconds spent waiting, so a screen can show progress honestly.
    elapsed: float = 0.0
    polls: int = 0
    detail: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "platform": self.platform,
            "state": self.state,
            "elapsed": round(self.elapsed, 1),
            "polls": self.polls,
            "detail": self.detail,
            "reading": self.reading.to_dict() if self.reading else None,
        }


async def check(page: Page, target: Platform | str) -> Reading:
    """Is this workspace signed in right now?

    Empirical every time. A stored "connected" from last week is a memory, not a
    session — cookies expire, sessions get revoked from another device, and a
    security check can invalidate one between two page loads.
    """
    resolved = target if isinstance(target, Platform) else lookup_platform(target)
    await page.goto(resolved.home_url)
    return read_state(await page.snapshot(), resolved)


async def open_login(page: Page, target: Platform | str) -> Reading:
    """Put the platform's own login page in front of the person.

    Refuses if the run is unattended, and that refusal is the point: a sign-in
    is by definition a thing a person does, so a scheduled run reaching this is
    a scheduled run about to sit at a password prompt forever.
    """
    resolved = target if isinstance(target, Platform) else lookup_platform(target)
    if page.unattended:
        raise SignInRefused(
            f"Signing in to {resolved.label} needs a person at the keyboard, so it "
            "cannot happen in an unattended run. Start it from the Connections "
            "screen instead."
        )
    already = await check(page, resolved)
    if already.connected:
        return already
    try:
        await page.goto(resolved.login_url)
    except Refused as refusal:
        raise SignInRefused(str(refusal)) from refusal
    return await _read(page, resolved)


async def _read(page: Page, target: Platform) -> Reading:
    return read_state(await page.snapshot(), target)


async def wait_for_sign_in(
    page: Page,
    target: Platform | str,
    *,
    timeout: float = DEFAULT_TIMEOUT,
    poll_seconds: float = POLL_SECONDS,
    on_poll: Any = None,
) -> SignInAttempt:
    """Watch the page until the person is signed in, or until they give up.

    A poll of the page rather than a timer on the clock. The person may be
    reading a text message with a code in it, and a flow that decided they had
    failed while they did so would be wrong about the only thing it measures.
    """
    resolved = target if isinstance(target, Platform) else lookup_platform(target)
    attempt = SignInAttempt(platform=resolved.id)
    started = time.monotonic()

    while True:
        attempt.polls += 1
        attempt.elapsed = time.monotonic() - started
        reading = await _read(page, resolved)
        attempt.reading = reading

        if reading.connected:
            attempt.state = "connected"
            attempt.detail = f"Signed in to {resolved.label}."
            return attempt

        if callable(on_poll):
            # A screen showing "still waiting" is the difference between a flow
            # people finish and one they close.
            on_poll(attempt)

        if attempt.elapsed >= float(timeout):
            attempt.state = "timed_out"
            attempt.detail = (
                f"Gave up watching after {attempt.elapsed / 60:.0f} minutes. The "
                "browser is still open and still on that page — nothing was "
                "cancelled, and signing in now will be picked up by the next check."
            )
            return attempt

        await asyncio.sleep(max(0.2, float(poll_seconds)))


async def connect(
    page: Page,
    target: Platform | str,
    store: ConnectionStore,
    workspace_id: str,
    *,
    vault: SessionVault,
    timeout: float = DEFAULT_TIMEOUT,
    on_poll: Any = None,
) -> Connection:
    """Sign in, vault the session, then record the public connection state.

    `vault` is required rather than optional. An optional security boundary is a
    bypass waiting for a caller to forget one keyword. The vault itself is host
    orchestration and is never exposed as an agent tool.
    """
    resolved = target if isinstance(target, Platform) else lookup_platform(target)
    first = await open_login(page, resolved)
    if first.connected:
        reading = first
    else:
        attempt = await wait_for_sign_in(
            page, resolved, timeout=timeout, on_poll=on_poll
        )
        reading = attempt.reading or Reading("unknown")

    if reading.connected:
        try:
            await vault.capture(page, resolved, workspace_id)
        except VaultError as exc:
            raise SignInRefused(
                f"Signed in to {resolved.label}, but off_CRM could not protect the "
                f"session in the vault: {exc}. The connection was not recorded."
            ) from exc

    return store.record(workspace_id, reading, resolved)


async def verify(
    page: Page, target: Platform | str, store: ConnectionStore, workspace_id: str
) -> Connection:
    """Re-check a platform and update the public record.

    Separate from `connect` because it is safe to run unattended: it opens a
    page the person is already signed in to and reads it. No credential is read
    or returned by this path.
    """
    resolved = target if isinstance(target, Platform) else lookup_platform(target)
    return store.record(workspace_id, await check(page, resolved), resolved)
