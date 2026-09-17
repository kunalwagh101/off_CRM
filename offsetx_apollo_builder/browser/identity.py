"""Which platforms this workspace is signed in to — and never how.

`S-03.02.01` owns the sign-in-state model. `S-03.02.05` moves the platform
catalogue itself into a validated declaration so adding a platform does not mean
adding another branch in this module.

**The rule this module exists to keep: off_CRM never handles a password.**

Not encrypted, not hashed, not held in memory for a moment and discarded. The
person types it into the browser inside the box, with their own fingers, and the
only thing that crosses back is *whether it worked*. There is no field here for
a credential and no public function accepts one.

**Signed-in is observed, never assumed.** A cookie that exists is not a session
that works; it expires, gets revoked from another device, or trips a security
check. The check is empirical: open the platform's own page and read what a
screen reader would read. Unknown is never rounded to connected or disconnected,
and a signed-out signal wins a tie.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from typing import Any, Iterable

from ..ai.workspace import atomic_json
from .budget import Budget, BudgetLedger
from .perceive import Snapshot
from .platform_registry import Platform, PLATFORMS, UnknownPlatform, platform

#: Never stored, never accepted as an argument, never logged. The test
#: `test_no_function_here_accepts_a_credential` reads this list and checks every
#: public signature in the module against it.
FORBIDDEN_FIELDS = (
    "password", "passwd", "secret", "token", "cookie", "session_id",
    "credential", "otp", "totp", "pin", "passphrase",
)


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


# ── reading the page ────────────────────────────────────────────────────────


@dataclass(frozen=True)
class Reading:
    """What the page said about whether you are signed in."""

    #: `connected`, `disconnected` or `unknown`. Never a bare boolean, because
    #: two of the three answers would then be the same answer.
    state: str
    #: The accessible name that decided it, so a wrong answer can be argued with.
    evidence: str = ""
    url: str = ""

    @property
    def connected(self) -> bool:
        return self.state == "connected"

    def to_dict(self) -> dict[str, Any]:
        return {"state": self.state, "evidence": self.evidence, "url": self.url}


@lru_cache(maxsize=256)
def _word(signal: str) -> "re.Pattern[str]":
    """Match a signal on **word boundaries**, never as a bare substring.

    Found by a page whose only text was "Something else" being reported as
    signed in: the signal `me` matched inside `so-me-thing`. A short signal is
    exactly the kind that is most useful ("post", "inbox", "me") and most likely
    to appear inside an unrelated word, so the boundary is not optional.
    """
    return re.compile(rf"\b{re.escape(signal)}\b")


def read_state(snapshot: Snapshot, target: Platform) -> Reading:
    """Decide from what a screen reader would read.

    Signed-out first, deliberately. If a page shows both a "Sign in" button and
    something that looks like a signed-in control, the sign-in prompt is the
    thing that is actually true.
    """
    names = snapshot.names

    def matched(signals: Iterable[str]) -> str:
        for signal in signals:
            pattern = _word(signal)
            for name in names:
                if pattern.search(name):
                    return signal
        return ""

    out = matched(target.signed_out)
    if out:
        return Reading("disconnected", f"the page offers {out!r}", snapshot.url)
    inside = matched(target.signed_in)
    if inside:
        return Reading("connected", f"the page offers {inside!r}", snapshot.url)
    return Reading(
        "unknown",
        "neither a signed-in nor a signed-out signal was on the page — it may "
        "have changed, or something may be in the way",
        snapshot.url,
    )


# ── what is written down ────────────────────────────────────────────────────


def _suffix(platform: str, key: str) -> str:
    """The account label back out of a key. `linkedin:work` -> `work`."""
    return key.split(":", 1)[1] if ":" in key else ""


def account_id(platform_id: str, account: str = "") -> str:
    """The key one account is filed under.  `S-03.02.04`

    The **default account for a platform is named after the platform**, so
    `linkedin` and `linkedin` are the same account and every record written
    before accounts existed keeps working with no migration step. A second
    account is `linkedin:work`, a third `linkedin:personal`.

    The owner picks the suffix, because only they know which is which, and it is
    normalised rather than validated away — a name with a colon in it would
    otherwise collide with another account.
    """
    platform_id = str(platform_id).strip().lower()
    label = str(account or "").strip().lower().replace(":", "-")
    label = "".join(ch for ch in label if ch.isalnum() or ch in "-_")[:40]
    return f"{platform_id}:{label}" if label and label != platform_id else platform_id


@dataclass
class Connection:
    """A record that one account is signed in. **Holds no secret.**"""

    platform: str
    #: Which account on that platform. Defaults to the platform id, so a
    #: single-account setup reads exactly as it did before accounts existed.
    account: str = ""
    state: str = "unknown"
    checked_at: str = ""
    evidence: str = ""
    #: Optional, and only ever a public display name the page itself shows.
    handle: str = ""

    def __post_init__(self) -> None:
        if not self.account:
            self.account = self.platform

    def to_dict(self) -> dict[str, Any]:
        return {
            "platform": self.platform,
            "account": self.account,
            "state": self.state,
            "checked_at": self.checked_at,
            "evidence": self.evidence,
            "handle": self.handle,
        }


class ConnectionStore:
    """Which platforms a workspace is signed in to, as one small JSON file.

    Deliberately not a database table. The whole document is a handful of
    sentences with no secret in it, losing it costs a re-check rather than a
    re-login, and a file the owner can open and read is the point — this is the
    record of *what has access to their accounts*.
    """

    def __init__(self, data_dir: Path | str) -> None:
        self.path = Path(data_dir) / "browser_connections.json"

    def _document(self) -> dict[str, Any]:
        if not self.path.exists():
            return {}
        try:
            import json

            loaded = json.loads(self.path.read_text(encoding="utf-8"))
            return loaded if isinstance(loaded, dict) else {}
        except (ValueError, OSError):
            # A corrupt record costs a re-check, not a crash. It holds nothing
            # that cannot be rebuilt by looking at the browser again.
            return {}

    def record(
        self,
        workspace_id: str,
        reading: Reading,
        target: Platform,
        *,
        handle: str = "",
        account: str = "",
    ) -> Connection:
        """Write down what was observed. The only writer here.

        Takes a `Reading` rather than fields, so there is no signature on this
        class that a credential could be passed to even by mistake. `account`
        is a label the owner chose, never anything the platform returned.
        """
        key = account_id(target.id, account)
        connection = Connection(
            platform=target.id,
            account=key,
            state=reading.state,
            checked_at=_now(),
            evidence=reading.evidence,
            handle=str(handle or "")[:120],
        )
        document = self._document()
        document.setdefault(str(workspace_id), {})[key] = connection.to_dict()
        atomic_json(self.path, document)
        return connection

    def get(self, workspace_id: str, platform_id: str, account: str = "") -> Connection:
        key = account_id(platform_id, account)
        raw = self._document().get(str(workspace_id), {}).get(key)
        if not isinstance(raw, dict):
            return Connection(platform=str(platform_id).lower(), account=key)
        return Connection(
            platform=str(raw.get("platform") or platform_id),
            # Records written before accounts existed have no `account` field;
            # their key *is* the platform, which is what `account_id` returns.
            account=str(raw.get("account") or key),
            state=str(raw.get("state") or "unknown"),
            checked_at=str(raw.get("checked_at") or ""),
            evidence=str(raw.get("evidence") or ""),
            handle=str(raw.get("handle") or ""),
        )

    def forget(self, workspace_id: str, platform_id: str, account: str = "") -> None:
        """Drop the record for one account.

        Note what this does **not** do: it does not sign you out. The session
        lives in the browser's own volume, and removing that is the box's job —
        see `S-03.02.03`. Pretending otherwise would leave a live session behind
        a screen that says disconnected.
        """
        document = self._document()
        document.get(str(workspace_id), {}).pop(account_id(platform_id, account), None)
        atomic_json(self.path, document)

    def accounts(self, workspace_id: str, platform_id: str) -> list[Connection]:
        """Every account connected on one platform, default first."""
        platform_id = str(platform_id).strip().lower()
        keys = [
            key
            for key in self._document().get(str(workspace_id), {})
            if key == platform_id or key.startswith(f"{platform_id}:")
        ]
        return [
            self.get(workspace_id, platform_id, _suffix(platform_id, key))
            for key in sorted(keys)
        ]

    def all(self, workspace_id: str) -> list[Connection]:
        """Every account in the workspace, plus every platform with none.

        Declared platforms always appear even when nothing is connected,
        because a catalogue that hides what you have *not* done is a catalogue
        that cannot be used to decide what to do next.
        """
        found: list[Connection] = []
        seen: set[str] = set()
        for platform_id in sorted(PLATFORMS):
            connected = self.accounts(workspace_id, platform_id)
            if connected:
                found.extend(connected)
                seen.update(row.account for row in connected)
            else:
                found.append(self.get(workspace_id, platform_id))
        # Accounts on platforms that are no longer declared still belong to the
        # owner and must not vanish from their own record.
        for key in sorted(self._document().get(str(workspace_id), {})):
            if key in seen or key.split(":", 1)[0] in PLATFORMS:
                continue
            raw = self._document()[str(workspace_id)][key]
            if isinstance(raw, dict):
                found.append(
                    Connection(
                        platform=str(raw.get("platform") or key.split(":", 1)[0]),
                        account=key,
                        state=str(raw.get("state") or "unknown"),
                        checked_at=str(raw.get("checked_at") or ""),
                        evidence=str(raw.get("evidence") or ""),
                        handle=str(raw.get("handle") or ""),
                    )
                )
        return found


def catalogue(
    store: ConnectionStore,
    workspace_id: str,
    ledger: "BudgetLedger | None" = None,
) -> dict[str, Any]:
    """Every account, where this workspace stands with it, and what is left.

    `ledger` is optional so a screen that only wants connection state does not
    have to construct one — but when it is given, each row carries how much of
    that account's budget is spent. That is the answer to "what are this
    account's limits", and it belongs next to the account rather than in a
    separate call a caller can forget to make.
    """
    rows = []
    for connection in store.all(workspace_id):
        declared = PLATFORMS.get(connection.platform)
        row = {
            **(
                declared.to_dict()
                if declared
                else {"id": connection.platform, "label": connection.platform}
            ),
            **connection.to_dict(),
        }
        if ledger is not None:
            budget = Budget.for_platform(connection.platform)
            row["budget"] = ledger.remaining(connection.account, budget)
        rows.append(row)
    return {
        "platforms": rows,
        "accounts": len(rows),
        "stores_no_credentials": True,
    }
