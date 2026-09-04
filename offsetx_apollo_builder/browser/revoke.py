"""Destroy one connected platform session and record the revocation.

S-03.02.03 deliberately stays inside trusted host orchestration. A model cannot
call this module as a browser verb and never receives the session material.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse

from .identity import ConnectionStore, Platform, platform as lookup_platform
from .trace import Step, Trace
from .vault import SessionVault, VaultError, VaultLocked, _cookie_belongs


class RevokeError(RuntimeError):
    """A session could not be destroyed completely and safely."""


@dataclass(frozen=True)
class Revocation:
    """Non-secret result of one completed disconnect."""

    workspace_id: str
    platform_id: str
    cookies_removed: int
    vault_destroyed: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "workspace_id": self.workspace_id,
            "platform_id": self.platform_id,
            "cookies_removed": self.cookies_removed,
            "vault_destroyed": self.vault_destroyed,
        }


def _origin(url: str) -> str:
    parsed = urlparse(str(url or ""))
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise RevokeError(f"Cannot clear browser storage for invalid platform URL {url!r}.")
    default = (parsed.scheme == "https" and parsed.port in {None, 443}) or (
        parsed.scheme == "http" and parsed.port in {None, 80}
    )
    port = "" if default else f":{parsed.port}"
    return f"{parsed.scheme}://{parsed.hostname}{port}"


def _session_origins(target: Platform, cookies: list[dict[str, Any]]) -> tuple[str, ...]:
    """Every declared platform/cookie origin that can hold this login.

    Chromium's browser-level Storage domain exposes `clearDataForOrigin`, not a
    `deleteCookies` method. Clearing the unique origins is both supported by the
    real browser and broader than deleting only the cookie rows: local/session
    storage associated with the declared login origins is removed too.
    """
    declared = {_origin(target.home_url), _origin(target.login_url)}
    schemes = {urlparse(origin).scheme for origin in declared}
    for cookie in cookies:
        domain = str(cookie.get("domain") or "").strip().lower().lstrip(".")
        if not domain:
            raise RevokeError("The vaulted session contains a cookie with no domain.")
        for scheme in schemes:
            declared.add(f"{scheme}://{domain}")
    return tuple(sorted(declared))


async def disconnect(
    page: Any,
    target: Platform | str,
    store: ConnectionStore,
    vault: SessionVault,
    trace: Trace,
    workspace_id: str,
) -> Revocation:
    """Clear Chrome, destroy the wrapped account key, forget the public record.

    Ordering is intentional. Chrome is cleared first while the vault still
    contains enough encrypted material to retry if DevTools refuses. Only after
    every browser deletion succeeds is the account envelope unlinked; deleting
    that envelope is cryptographic erasure because its per-account key exists
    nowhere else except wrapped inside the same file.
    """
    resolved = target if isinstance(target, Platform) else lookup_platform(target)

    try:
        material = vault.unseal(workspace_id, resolved.id)
    except (VaultError, VaultLocked) as exc:
        raise RevokeError(
            f"Cannot disconnect {resolved.label}: its vaulted session cannot be opened safely: {exc}"
        ) from exc

    raw = material.get("cookies") if isinstance(material, dict) else None
    if not isinstance(raw, list) or not raw:
        raise RevokeError(
            f"Cannot disconnect {resolved.label}: the vaulted session contains no cookies to revoke."
        )

    cookies: list[dict[str, Any]] = []
    for item in raw:
        if not isinstance(item, dict) or not _cookie_belongs(item, resolved):
            raise RevokeError(
                f"Cannot disconnect {resolved.label}: the vault contains material for another platform."
            )
        cookies.append(item)

    origins = _session_origins(resolved, cookies)

    # Record the request before destructive work. If the process dies halfway,
    # the append-only trace says that revocation was attempted rather than
    # leaving an unexplained change to a logged-in account.
    trace.append(Step(kind="revoke", detail=f"Disconnect requested for {resolved.label}.", ok=True))

    try:
        for origin in origins:
            await page.connection.send(
                "Storage.clearDataForOrigin",
                {"origin": origin, "storageTypes": "all"},
            )
    except Exception as exc:
        trace.append(
            Step(
                kind="revoke",
                detail=f"Disconnect failed for {resolved.label}; encrypted vault retained for retry.",
                ok=False,
            )
        )
        raise RevokeError(
            f"Could not clear {resolved.label} from the browser. The encrypted vault was retained so the disconnect can be retried."
        ) from exc

    envelope = vault._path(workspace_id, resolved.id)
    try:
        envelope.unlink()
    except FileNotFoundError as exc:
        raise RevokeError(
            f"Could not destroy {resolved.label}'s vault envelope because it disappeared during revocation."
        ) from exc
    except OSError as exc:
        raise RevokeError(
            f"Browser storage was cleared, but off_CRM could not destroy {resolved.label}'s encrypted vault envelope: {exc}"
        ) from exc

    if envelope.exists():
        raise RevokeError(f"The {resolved.label} vault envelope still exists after deletion.")

    store.forget(workspace_id, resolved.id)
    trace.append(
        Step(
            kind="revoke",
            detail=(
                f"Disconnected {resolved.label}: browser storage cleared, "
                "per-account vault envelope destroyed, connection record forgotten."
            ),
            ok=True,
        )
    )
    return Revocation(
        workspace_id=str(workspace_id),
        platform_id=resolved.id,
        cookies_removed=len(cookies),
    )
