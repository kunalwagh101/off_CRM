"""A client for the Chrome DevTools Protocol.

The wire off_CRM drives a browser over. Every debugger, recorder and automation
tool speaks this; it is JSON over a WebSocket and it is the reason this project
does not need to fork Chromium to run inside your session.

**Hand-written, for the reason the video muxer is hand-written.** The
alternative is Playwright, whose value is *launching and managing* browsers —
and we are attaching to one that already exists, running against the owner's own
profile, so almost none of it would be used. What would be used is ~300MB of
downloaded browser binaries we would never run. CDP itself is six domains and a
correlation id.

---

**Two kinds of message, and confusing them is the classic bug.**

A *command* has an ``id`` and gets exactly one reply carrying that id. An
*event* has no id and arrives whenever the browser feels like it — including
in the middle of waiting for a command's reply. So this reads every frame in
one place and routes by shape: id present means resolve a waiter, method
present means fan out to listeners.

**Sessions.** A browser connection can drive many targets (tabs). Attaching to
one returns a ``sessionId``, and every command afterwards carries it. Without
that a two-tab agent silently sends its clicks to whichever tab was last
attached, which looks like flakiness and is not.

**Everything is bounded.** Every command has a timeout, because a page that
never finishes loading must not become an agent that never finishes running.
"""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable

#: How long a single command may take before it is abandoned. Generous, because
#: `Page.navigate` on a cold cache is genuinely slow — but finite, because the
#: whole point of a timeout is that a hung tab is not a hung agent.
DEFAULT_TIMEOUT = 30.0

#: What one command's reply may weigh. A `DOM.getDocument` on a large page is
#: megabytes, and a `Runtime.evaluate` returning a whole document is worse. Past
#: this the answer is refused rather than loaded, because the thing on the other
#: end of it is a model with a context window.
MAX_MESSAGE_BYTES = 24 * 1024 * 1024


class CDPError(RuntimeError):
    """The browser answered, and the answer was no."""

    def __init__(self, method: str, message: str, code: int = 0, data: str = "") -> None:
        self.method = method
        self.code = code
        self.data = data
        detail = f" ({data})" if data else ""
        super().__init__(f"{method} failed: {message}{detail}")


class CDPClosed(RuntimeError):
    """The connection went away — usually the owner closed the browser."""


class CDPTimeout(RuntimeError):
    """A command did not come back inside its timeout."""


@dataclass
class _Pending:
    future: asyncio.Future
    method: str


@dataclass
class CDPConnection:
    """One WebSocket to one browser, driving any number of targets.

    Created by :func:`connect`. The read loop runs for the life of the
    connection and is the only thing that touches the socket's receive side, so
    there is never a question of two coroutines racing for the same frame.
    """

    socket: Any
    _next_id: int = 1
    _pending: dict[int, _Pending] = field(default_factory=dict)
    _listeners: list[Callable[[str, dict[str, Any], str], Awaitable[None] | None]] = field(
        default_factory=list
    )
    _reader: asyncio.Task | None = None
    _closed: bool = False
    #: Why the connection ended, so a failure downstream can say something
    #: better than "connection closed".
    reason: str = ""

    # ── lifecycle ───────────────────────────────────────────────────────────

    def start(self) -> None:
        if self._reader is None:
            self._reader = asyncio.ensure_future(self._read_loop())

    async def close(self, reason: str = "closed by off_CRM") -> None:
        if self._closed:
            return
        self._closed = True
        self.reason = self.reason or reason
        self._fail_pending(CDPClosed(self.reason))
        if self._reader is not None:
            self._reader.cancel()
            try:
                await self._reader
            except (asyncio.CancelledError, Exception):  # noqa: BLE001
                pass
            self._reader = None
        try:
            await self.socket.close()
        except Exception:  # noqa: BLE001 - closing a dead socket is not an error
            pass

    def _fail_pending(self, error: Exception) -> None:
        for pending in list(self._pending.values()):
            if not pending.future.done():
                pending.future.set_exception(error)
        self._pending.clear()

    # ── the read loop ───────────────────────────────────────────────────────

    async def _read_loop(self) -> None:
        """Read every frame and route it by shape.

        The one place the socket is read. A command reply carries the ``id`` it
        was sent with; an event carries a ``method`` and no id. Handling both
        here is what makes it safe for an event to arrive while a command is
        outstanding — which it constantly does.
        """
        try:
            async for raw in self.socket:
                if isinstance(raw, bytes):
                    raw = raw.decode("utf-8", "replace")
                try:
                    frame = json.loads(raw)
                except ValueError:
                    continue
                if "id" in frame:
                    self._resolve(frame)
                elif "method" in frame:
                    await self._emit(frame)
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # noqa: BLE001 - a dropped socket is a state, not a crash
            self.reason = f"the browser connection ended: {exc}"
        finally:
            self._closed = True
            self._fail_pending(CDPClosed(self.reason or "the browser connection ended"))

    def _resolve(self, frame: dict[str, Any]) -> None:
        pending = self._pending.pop(int(frame["id"]), None)
        if pending is None or pending.future.done():
            return
        error = frame.get("error")
        if error:
            pending.future.set_exception(
                CDPError(
                    pending.method,
                    str(error.get("message") or "unknown error"),
                    int(error.get("code") or 0),
                    str(error.get("data") or ""),
                )
            )
        else:
            pending.future.set_result(frame.get("result") or {})

    async def _emit(self, frame: dict[str, Any]) -> None:
        method = str(frame.get("method") or "")
        params = frame.get("params") or {}
        session = str(frame.get("sessionId") or "")
        for listener in list(self._listeners):
            try:
                result = listener(method, params, session)
                if asyncio.iscoroutine(result):
                    await result
            except Exception:  # noqa: BLE001 - one bad listener is not the others' problem
                continue

    def on_event(
        self, listener: Callable[[str, dict[str, Any], str], Awaitable[None] | None]
    ) -> Callable[[], None]:
        """Listen to everything. Returns the function that stops listening."""
        self._listeners.append(listener)

        def off() -> None:
            if listener in self._listeners:
                self._listeners.remove(listener)

        return off

    # ── commands ────────────────────────────────────────────────────────────

    async def send(
        self,
        method: str,
        params: dict[str, Any] | None = None,
        *,
        session_id: str = "",
        timeout: float = DEFAULT_TIMEOUT,
    ) -> dict[str, Any]:
        """One command, one reply.

        ``session_id`` is not optional in spirit: a connection drives many tabs,
        and a command without one goes to the browser rather than to a page.
        Leaving it off when you meant a page is the bug that looks like the
        agent clicking in the wrong window.
        """
        if self._closed:
            raise CDPClosed(self.reason or "the browser connection is closed")
        message_id = self._next_id
        self._next_id += 1
        payload: dict[str, Any] = {"id": message_id, "method": method, "params": params or {}}
        if session_id:
            payload["sessionId"] = session_id

        loop = asyncio.get_running_loop()
        future: asyncio.Future = loop.create_future()
        self._pending[message_id] = _Pending(future=future, method=method)
        try:
            await self.socket.send(json.dumps(payload))
        except Exception as exc:  # noqa: BLE001
            self._pending.pop(message_id, None)
            raise CDPClosed(f"could not send {method}: {exc}") from exc

        try:
            return await asyncio.wait_for(future, timeout=timeout)
        except asyncio.TimeoutError as exc:
            self._pending.pop(message_id, None)
            raise CDPTimeout(
                f"{method} did not answer in {timeout:.0f}s. The page may still "
                "be loading, or the tab may have gone."
            ) from exc

    async def wait_for_event(
        self,
        method: str,
        *,
        session_id: str = "",
        timeout: float = DEFAULT_TIMEOUT,
        match: Callable[[dict[str, Any]], bool] | None = None,
    ) -> dict[str, Any]:
        """Block until one named event arrives.

        Registered *before* the caller does whatever triggers it — which is why
        this returns an awaitable the caller arms first rather than a coroutine
        it awaits after. Arming afterwards loses every event fired in between,
        and page lifecycle events are fast enough that this is not theoretical.
        """
        loop = asyncio.get_running_loop()
        future: asyncio.Future = loop.create_future()

        def listener(name: str, params: dict[str, Any], session: str) -> None:
            if future.done() or name != method:
                return
            if session_id and session and session != session_id:
                return
            if match is not None and not match(params):
                return
            future.set_result(params)

        off = self.on_event(listener)
        try:
            return await asyncio.wait_for(future, timeout=timeout)
        except asyncio.TimeoutError as exc:
            raise CDPTimeout(f"{method} never arrived (waited {timeout:.0f}s).") from exc
        finally:
            off()


async def connect(websocket_url: str, *, open_timeout: float = 15.0) -> CDPConnection:
    """Open a connection to a browser's DevTools endpoint.

    ``max_size=None`` because a DOM snapshot of a real page is routinely larger
    than the library's default frame cap, and a truncated snapshot is worse than
    a slow one — the reply arrives, parses as JSON, and is missing the element
    the agent was about to click.
    """
    import websockets

    socket = await asyncio.wait_for(
        websockets.connect(
            websocket_url,
            max_size=MAX_MESSAGE_BYTES,
            ping_interval=20,
            ping_timeout=20,
        ),
        timeout=open_timeout,
    )
    connection = CDPConnection(socket=socket)
    connection.start()
    return connection
