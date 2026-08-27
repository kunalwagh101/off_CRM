"""The allow-list, enforced before a request leaves the browser.

`S-03.01.01`, second acceptance criterion: *a domain not on the allow-list is
requested, and the request does not leave the box.*

**Why here and not in the container.** Docker filters by address; the rule is
about names. `--network=bridge` cannot express "only linkedin.com", and the
address behind a name changes hourly at any CDN. So the enforcement point is
the browser's own network stack, via the DevTools `Fetch` domain: every request
pauses *before* Chrome dispatches it, this decides, and a refusal is
`Fetch.failRequest` — the bytes never go out.

The container and this file protect different things and neither substitutes
for the other:

    the box     stops the browser reaching **your machine**
    the guard   stops the browser reaching **the wrong site**

---

**Two modes, and the difference is who is watching.** The owner's decision,
recorded as Q-02:

*Unattended* — deny by default. A scheduled run follows links nobody read, so
only declared domains are reachable and everything else fails closed. An empty
allow-list means the box reaches nothing, which is correct rather than broken.

*Attended* — allow, with policy. A person watching is itself a control, so the
open web is reachable and only what `policy.py` refuses outright is refused:
this machine, its network, the cloud metadata endpoint, and non-web schemes.

**The allow-list narrows. It can never widen.** `policy.py` is consulted first
and its refusals are final, so putting `linkedin.com` on an unattended run's
allow-list does *not* make LinkedIn reachable — that platform is attended-only
and the reason has nothing to do with this list. A config file cannot vote
itself past a platform rule, which is the property that makes the rule worth
having.

---

**Failing closed is the whole design.** If this module raises, if the browser
sends a request shape it does not recognise, if a URL will not parse — the
request is refused. A guard that fails open is a guard that is absent exactly
when something unusual is happening, which is the only time it mattered.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urlsplit

from .cdp import CDPConnection
from .policy import Refused, check_navigation, host_of

#: Schemes that never touch the network and are never a way out of the box.
#: Refusing them would break every inline image and stylesheet on the web.
INERT_SCHEMES = frozenset({"data", "blob", "about", "chrome-extension"})

#: What the guard reports back, capped so a page that fires ten thousand
#: refused requests cannot turn a run's trace into a log-shaped denial of
#: service.
MAX_RECORDED = 200


@dataclass(slots=True)
class Verdict:
    allowed: bool
    reason: str = ""


@dataclass
class RequestGuard:
    """Decides, per request, whether it may leave.

    Attach it once per tab. It stays attached for the life of the session and
    every request the page makes — pictures, fonts, API calls, the tracking
    beacon nobody asked for — goes through :meth:`verdict`.
    """

    #: Reachable when unattended. Matched on suffix, so `www.linkedin.com` and
    #: `uk.linkedin.com` are both covered by `linkedin.com`.
    allowed_hosts: frozenset[str] = field(default_factory=frozenset)
    unattended: bool = False
    #: `(url, reason)` for what was refused, newest last, capped.
    blocked: list[tuple[str, str]] = field(default_factory=list)
    allowed_count: int = 0
    blocked_count: int = 0

    # ── the decision ────────────────────────────────────────────────────────

    def verdict(self, url: str) -> Verdict:
        """May this request leave? The only place that decides."""
        text = str(url or "").strip()
        if not text:
            return Verdict(False, "a request with no URL")

        try:
            scheme = (urlsplit(text).scheme or "").lower()
        except ValueError:
            # A URL the standard library will not parse is one nothing should
            # act on. Refuse rather than guess at what was meant.
            return Verdict(False, "that URL cannot be parsed")

        if scheme in INERT_SCHEMES:
            # Never leaves the browser. Refusing these would break every inline
            # image on the web for no security gain at all.
            return Verdict(True, "")

        # The refuse-always rules first, in both modes: this machine, its own
        # network, the cloud metadata endpoint, and non-web schemes. `policy.py`
        # already owns that list and is tested against it.
        try:
            check_navigation(text, unattended=self.unattended)
        except Refused as refusal:
            return Verdict(False, str(refusal))

        if not self.unattended:
            # A person is watching, which is a control in itself.
            return Verdict(True, "")

        host = host_of(text)
        if not host:
            return Verdict(False, "no host to check against the allow-list")
        for allowed in self.allowed_hosts:
            if host == allowed or host.endswith("." + allowed):
                return Verdict(True, "")
        return Verdict(
            False,
            f"{host} is not on this run's allow-list. Unattended runs reach only "
            f"declared domains: {', '.join(sorted(self.allowed_hosts)) or 'none'}.",
        )

    def _record(self, url: str, verdict: Verdict) -> None:
        if verdict.allowed:
            self.allowed_count += 1
            return
        self.blocked_count += 1
        if len(self.blocked) < MAX_RECORDED:
            self.blocked.append((url[:300], verdict.reason))

    # ── attaching it to a live tab ──────────────────────────────────────────

    async def attach(self, connection: CDPConnection, session_id: str) -> None:
        """Pause every request on this tab and decide about it.

        `Fetch.enable` with no pattern means *every* request, which is the point:
        a guard that only saw top-level navigations would miss the subresource
        that is doing the exfiltrating.
        """
        connection.on_event(self._make_listener(connection, session_id))
        await connection.send(
            "Fetch.enable", {"patterns": [{"urlPattern": "*"}]}, session_id=session_id
        )

    def _make_listener(self, connection: CDPConnection, session_id: str):
        async def listener(method: str, params: dict[str, Any], session: str) -> None:
            if method != "Fetch.requestPaused":
                return
            if session_id and session and session != session_id:
                return
            request_id = str(params.get("requestId") or "")
            if not request_id:
                return
            url = str((params.get("request") or {}).get("url") or "")

            try:
                decision = self.verdict(url)
            except Exception as exc:  # noqa: BLE001
                # A guard that fails open is absent exactly when something
                # unusual is happening, which is the only time it mattered.
                decision = Verdict(False, f"the guard could not decide: {exc}")

            self._record(url, decision)
            try:
                if decision.allowed:
                    await connection.send(
                        "Fetch.continueRequest", {"requestId": request_id},
                        session_id=session_id,
                    )
                else:
                    # `AccessDenied` rather than a silent drop: the page sees a
                    # real network error and reports it, instead of hanging
                    # until something times out and nobody knows why.
                    await connection.send(
                        "Fetch.failRequest",
                        {"requestId": request_id, "errorReason": "AccessDenied"},
                        session_id=session_id,
                    )
            except Exception:  # noqa: BLE001 - a tab that closed mid-decision
                return

        return listener

    def report(self) -> dict[str, Any]:
        """What the guard did, for the trace and for a person reading it."""
        return {
            "mode": "unattended" if self.unattended else "attended",
            "allowed_hosts": sorted(self.allowed_hosts),
            "allowed": self.allowed_count,
            "blocked": self.blocked_count,
            "blocked_examples": self.blocked[:20],
            "truncated": self.blocked_count > len(self.blocked),
        }
