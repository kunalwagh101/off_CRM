"""Per-workspace AI settings and encrypted provider keys.

off_CRM is multi-user and heading for a shared server, so nothing here is
global.  Two colleagues can enable different providers, sit at different
policies, and hold different keys, without either one's choice changing what the
other's calls send.

Keys are encrypted with Fernet outside the CRM database, reusing the pattern
already proven in ``outreach/provider_profiles.py``.
"""
from __future__ import annotations

import json
import os
import sqlite3
import threading
from contextlib import contextmanager
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any, Callable, Iterator

from cryptography.fernet import Fernet, InvalidToken

from ..db.hosted import PROVIDER_KEYS, SETTINGS, HostedStorage, HostedStorageError
from ..outreach.models import to_utc_iso
from .broker import WorkspaceEgressSettings
from .errors import RegistryError
from .quota import QuotaLimits
from .registry import ProviderOverride, ProviderRegistry
from .tiers import (
    MAILBOX_UNLOCK_PHRASE,
    DataPolicy,
    TrustTier,
    coerce_policy,
    coerce_tier,
    default_policy_for_tier,
    describe_tier,
    policy_ceiling_for_tier,
)

DEFAULT_WORKSPACE = "local"


def _atomic_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
        temporary = Path(handle.name)
    os.replace(temporary, path)


#: The public name. Every store in off_CRM that keeps a JSON document needs
#: exactly this — write beside the target, then rename — and a second copy of it
#: is a second place for the "write then crash" bug to be fixed only once.
atomic_json = _atomic_json


#: Trust settings made on the trust route, kept when the override route
#: records a different decision for the same provider.
_TRUST_KEYS = (
    "trust_tier", "trust_reason", "trust_decided_by", "trust_decided_at", "model_tiers",
    "trust_history",
)

#: How many trust decisions a provider keeps. Clearing a setting deleted its
#: who and why; the history is what stays. Bounded because the document it
#: lives in is read on every request (D-170).
_TRUST_HISTORY = 20

#: How many models of one provider may carry their own trust setting (D-180).
_MODEL_SETTINGS = 50

#: Said for every way the stored keys can become unreadable (D-178, D-189).
#: Every login can see it, and the file holds every workspace's keys, so it
#: says whose step each one is.
_KEY_STORE_HELP = (
    "Stored AI provider keys cannot be read: {fault}. Until this is fixed no key can "
    "be read or saved. The install owner can restore the whole data folder from one "
    "backup — the master key is a hidden file, so copy the folder, not its files — or "
    "remove ai_provider_keys.enc and .ai_master.key, which clears the stored keys of "
    "every workspace, after which each workspace pastes its keys again."
)


def _remember(record: dict[str, Any], kind: str, model_id: str, decision: dict[str, Any]) -> None:
    history = list(record.get("trust_history") or [])
    history.append({
        "kind": kind,
        "model": model_id,
        "tier": decision.get("tier", ""),
        "reason": decision.get("reason", ""),
        "by": decision.get("decided_by", ""),
        "at": decision.get("decided_at", ""),
    })
    record["trust_history"] = history[-_TRUST_HISTORY:]


class ReasonRequired(ValueError):
    """A trust raise with no reason: the screen asks for one and retries."""


def _host_tier(entry: Any, override: dict[str, Any]) -> TrustTier:
    """The provider's own trust: the owner's setting, else config's."""
    if override.get("trust_tier"):
        return coerce_tier(override["trust_tier"], default=entry.derived_tier)
    return entry.derived_tier


def _grant_active(entry: Any, override: dict[str, Any]) -> bool:
    """Whether the owner's full-data grant lifts this provider's ceiling now.

    Only at its default trust or higher (DD-67): lowering the provider pauses
    the grant, and a blocked provider receives nothing at any level. The
    router applies the same rule per model (`ProviderRegistry.resolve`).
    """
    host = _host_tier(entry, override)
    return (
        bool(override.get("allow_above_ceiling"))
        and host is not TrustTier.D
        and host.rank >= entry.derived_tier.rank
    )


def _host_ceiling(entry: Any, override: dict[str, Any]) -> DataPolicy:
    """The most this provider may be sent, before any per-model limit."""
    ceiling = policy_ceiling_for_tier(_host_tier(entry, override))
    if _grant_active(entry, override):
        granted = coerce_policy(override.get("data_policy") or DataPolicy.FULL.value)
        if granted.rank > ceiling.rank:
            ceiling = granted
    return ceiling


def _raise_needs_reason(name: str, before: Any, after: Any) -> str:
    return (
        f"Raising {name} from {before.label} to {after.label} lets more of your data "
        "reach it. Type why; the reason is recorded with who made the change."
    )


class WorkspaceAISettingsStore:
    """Reads and writes one JSON document per install, keyed by workspace.

    The document and the encrypted keys are files in the data folder, or —
    given hosted storage (`S-06.03.02`) — documents in the hosted database,
    the keys encrypted with `OFFSETX_SECRETS_KEY`. Only where they are read and
    written differs; everything the store decides is the same code.
    """

    def __init__(
        self,
        data_dir: Path | str,
        registry: ProviderRegistry,
        *,
        hosted: HostedStorage | None = None,
    ) -> None:
        self.data_dir = Path(data_dir)
        self.registry = registry
        self._hosted = hosted
        self.settings_path = self.data_dir / "ai_workspaces.json"
        self.secret_path = self.data_dir / "ai_provider_keys.enc"
        self.key_path = self.data_dir / ".ai_master.key"
        self.write_lock_path = self.data_dir / ".ai_workspace_write_lock.sqlite3"
        self._lock = threading.RLock()

    @contextmanager
    def _exclusive_write(self) -> Iterator[None]:
        """Serialize the complete read-modify-replace window across processes."""
        if self._hosted is not None:
            with self._lock, self._hosted.exclusive():
                yield
            return
        self.data_dir.mkdir(parents=True, exist_ok=True)
        with self._lock:
            connection = sqlite3.connect(
                self.write_lock_path,
                timeout=30,
                isolation_level=None,
            )
            try:
                connection.execute("PRAGMA busy_timeout=30000")
                connection.execute("BEGIN IMMEDIATE")
                yield
                connection.commit()
            except Exception:
                if connection.in_transaction:
                    connection.rollback()
                raise
            finally:
                connection.close()

    # ── encrypted keys ──────────────────────────────────────────────────────

    def _fernet(self, *, create: bool) -> Fernet:
        if self._hosted is not None:
            return self._hosted.fernet
        if not self.key_path.exists():
            if not create:
                raise RegistryError(_KEY_STORE_HELP.format(fault="its master key, .ai_master.key, is missing"))
            self.data_dir.mkdir(parents=True, exist_ok=True)
            self.key_path.write_bytes(Fernet.generate_key())
            try:
                self.key_path.chmod(0o600)
            except OSError:
                pass
        try:
            return Fernet(self.key_path.read_bytes().strip())
        except (OSError, ValueError) as exc:
            raise RegistryError(_KEY_STORE_HELP.format(fault="its master key, .ai_master.key, is not a valid key")) from exc

    def _secrets(self) -> dict[str, str]:
        if self._hosted is not None:
            token = self._hosted.read(PROVIDER_KEYS)
            if token is None:
                return {}
            try:
                payload = json.loads(self._hosted.open(token).decode("utf-8"))
            except HostedStorageError as exc:
                # Checked at start-up; only a key changed underneath a running
                # app lands here, and it gets the same next step.
                raise RegistryError(str(exc)) from exc
            return {str(k): str(v) for k, v in payload.items()} if isinstance(payload, dict) else {}
        if not self.secret_path.exists():
            return {}
        try:
            decrypted = self._fernet(create=False).decrypt(self.secret_path.read_bytes())
            payload = json.loads(decrypted.decode("utf-8"))
        except (OSError, InvalidToken, UnicodeDecodeError, json.JSONDecodeError) as exc:
            # A next step, not just the fault: nothing else on screen can say
            # it, and until it is done no key can be stored (D-178).
            raise RegistryError(_KEY_STORE_HELP.format(
                fault="they were saved under a different master key, as when only part of a backup is restored"
            )) from exc
        return {str(k): str(v) for k, v in payload.items()} if isinstance(payload, dict) else {}

    def _write_secrets(self, secrets: dict[str, str]) -> None:
        token = self._fernet(create=True).encrypt(
            json.dumps(secrets, ensure_ascii=False).encode("utf-8")
        )
        if self._hosted is not None:
            self._hosted.write(PROVIDER_KEYS, token.decode("ascii"))
            return
        self.data_dir.mkdir(parents=True, exist_ok=True)
        with NamedTemporaryFile("wb", dir=self.data_dir, delete=False) as handle:
            handle.write(token)
            temporary = Path(handle.name)
        os.replace(temporary, self.secret_path)
        try:
            self.secret_path.chmod(0o600)
        except OSError:
            pass

    @staticmethod
    def _secret_key(workspace_id: str, provider_id: str) -> str:
        return f"{workspace_id}::{provider_id}"

    def set_key(self, workspace_id: str, provider_id: str, api_key: str) -> None:
        with self._exclusive_write():
            self._store_key_locked(workspace_id, provider_id, api_key)

    def _store_key_locked(self, workspace_id: str, provider_id: str, api_key: str) -> None:
        """Write one key; the caller holds `_exclusive_write` (it does not nest)."""
        secrets = self._secrets()
        slot = self._secret_key(workspace_id, provider_id)
        if api_key.strip():
            secrets[slot] = api_key.strip()
        else:
            secrets.pop(slot, None)
        self._write_secrets(secrets)

    def key_for(self, workspace_id: str, provider_id: str) -> str:
        """The key this workspace stored in Connectors, or "".

        Only that. An `OFFSETX_AI_<PROVIDER>_KEY` fallback used to answer for any
        workspace with none stored — so every login, other clients' included,
        spent the owner's key (D-151). A user cannot reach the server's
        environment anyway; keys are typed in the app (DD-64).
        """
        with self._lock:
            try:
                return self._secrets().get(self._secret_key(workspace_id, provider_id), "")
            except RegistryError:
                return ""

    def snapshot(self) -> tuple[dict[str, Any], dict[str, str]]:
        """The whole settings document and every stored key, for moving an
        install's stores into the hosted database (`offsetx-db import-local`).
        Raises the key store's own sentence if the keys cannot be read."""
        with self._lock:
            return self._document(), self._secrets()

    def credential_resolver(self, workspace_id: str):
        def resolve(provider_id: str) -> str:
            return self.key_for(workspace_id, provider_id)

        return resolve

    # ── settings document ───────────────────────────────────────────────────

    def _document(self, *, strict: bool = False) -> dict[str, Any]:
        try:
            if self._hosted is not None:
                body = self._hosted.read(SETTINGS)
                payload = json.loads(body) if body is not None else {}
            elif self.settings_path.exists():
                payload = json.loads(self.settings_path.read_text(encoding="utf-8"))
            else:
                return {}
        except (OSError, json.JSONDecodeError):
            if strict:
                raise
            return {}
        if not isinstance(payload, dict):
            if strict:
                raise ValueError("Stored workspace settings are invalid")
            return {}
        return payload

    def _write_document(self, document: dict[str, Any]) -> None:
        if self._hosted is not None:
            self._hosted.write(SETTINGS, json.dumps(document, ensure_ascii=False))
        else:
            _atomic_json(self.settings_path, document)

    def _blank(self, workspace_id: str) -> dict[str, Any]:
        return {
            "workspace_id": workspace_id,
            "providers": {},
            "positioning_line": "",
            "owner_domains": [],
            "owner_addresses": [],
            "mailbox_unlock_phrase": "",
            "created_at": to_utc_iso(),
            "updated_at": to_utc_iso(),
        }

    def raw(self, workspace_id: str = DEFAULT_WORKSPACE) -> dict[str, Any]:
        with self._lock:
            return dict(self._document().get(workspace_id) or self._blank(workspace_id))

    def raw_permissions(self, workspace_id: str = DEFAULT_WORKSPACE) -> dict[str, Any]:
        """Read current policy without hiding settings corruption or read failures.

        Other non-security consumers keep the historical lenient raw() contract.
        A browser permission check must not turn malformed state into allow.
        """
        with self._lock:
            record = self._document(strict=True).get(workspace_id)
            if record is None:
                return self._blank(workspace_id)
            if not isinstance(record, dict):
                raise ValueError("Stored workspace permissions are invalid")
            return dict(record)

    def _update_workspace(
        self,
        workspace_id: str,
        mutate: Callable[[dict[str, Any]], None],
    ) -> dict[str, Any]:
        with self._exclusive_write():
            document = self._document()
            current = dict(document.get(workspace_id) or self._blank(workspace_id))
            mutate(current)
            current["workspace_id"] = workspace_id
            current["updated_at"] = to_utc_iso()
            document[workspace_id] = current
            self._write_document(document)
            return dict(current)

    def save(self, workspace_id: str, values: dict[str, Any]) -> dict[str, Any]:
        def apply(current: dict[str, Any]) -> None:
            current.update(values)

        return self._update_workspace(workspace_id, apply)

    # ── provider enable / configure ─────────────────────────────────────────

    def connect_provider(
        self,
        workspace_id: str,
        provider_id: str,
        *,
        api_key: str = "",
        model_id: str = "",
        model_ids: list[str] | None = None,
        data_policy: str = "",
        enabled: bool = True,
        requests_per_minute: int | None = None,
        requests_per_day: int | None = None,
        max_spend_usd_per_day: float | None = None,
    ) -> dict[str, Any]:
        entry = self.registry.require(provider_id)
        # A key unlocks many models. `model_id` is kept for older stored records
        # and single-model callers; `model_ids` is the list the UI sends.
        chosen: list[str] = [str(item).strip() for item in (model_ids or []) if str(item).strip()]
        if not chosen:
            chosen = [model_id.strip() or entry.default_model]

        # Refuse a model the trust rules cannot place. Unknown is not safe, and
        # failing here is far better than failing at call time (§5.5.7).
        unusable: list[str] = []
        for candidate in chosen:
            if entry.model(candidate) is not None:
                continue
            if not self.registry.classify_model(candidate)["known"]:
                unusable.append(candidate)
        if unusable:
            raise ValueError(
                "These models do not match any rule in config/providers.yaml, so "
                "off_CRM cannot tell who built them and will not use them: "
                + ", ".join(unusable)
                + ". Add a model_origin_rules entry for them first."
            )

        free = entry.free_tier
        record = {
            "provider_id": provider_id,
            "enabled": bool(enabled),
            "model_id": chosen[0],
            "model_ids": chosen,
            "connected_at": to_utc_iso(),
        }
        # A cap not sent keeps the one already saved: the Models panel sends
        # only the models, and resetting here removed the owner's caps.
        # A first connect starts from the provider's free tier.
        given_caps = {
            "requests_per_minute": requests_per_minute,
            "requests_per_day": requests_per_day,
            "max_spend_usd_per_day": (
                float(max_spend_usd_per_day) if max_spend_usd_per_day is not None else None
            ),
        }
        first_caps = {
            "requests_per_minute": free.requests_per_minute if free else 0,
            "requests_per_day": free.requests_per_day if free else 0,
            "max_spend_usd_per_day": 0.0,
        }

        decided: dict[str, Any] = {}

        def apply(current: dict[str, Any]) -> None:
            # The ceiling follows the owner's trust for this provider, not the
            # config default — read under the write lock, so a trust change
            # cannot land between the read and this write.
            # Checked under the lock with the key write below: a disconnect
            # landing between a check and a write left a keyless connection.
            slot = self._secret_key(workspace_id, provider_id)
            if not api_key.strip() and not entry.local_only and not self._secrets().get(slot):
                raise ValueError(
                    f"Paste your {entry.name} API key first. The key page link on this "
                    "card shows where to get one."
                )
            stored = dict(current.get("overrides") or {}).get(provider_id) or {}
            tier = _host_tier(entry, stored)
            providers = dict(current.get("providers") or {})
            existing = dict(providers.get(provider_id) or {})
            # What is sent, kept like the caps when not sent again.
            wanted_policy = data_policy or str(existing.get("data_policy") or "")
            policy = (
                coerce_policy(wanted_policy, default=default_policy_for_tier(tier))
                if wanted_policy
                else default_policy_for_tier(tier)
            )
            standing = policy_ceiling_for_tier(
                tier if tier.rank >= entry.derived_tier.rank else entry.derived_tier
            )
            # Reported against what is stored, so a cut is never silent: the
            # grant-lifted ceiling said "not cut" while Standard was stored
            # for a choice of Full (D-184). What leaves is on the card.
            clamped = policy.rank > standing.rank
            decided.update(tier=tier, ceiling=standing, clamped=clamped)
            caps = {
                key: value if value is not None else existing.get(key, first_caps[key])
                for key, value in given_caps.items()
            }
            # Stored as chosen, up to what the provider's own standing trust
            # allows — its default, or the owner's raise — never cut to a
            # temporary lowering: storing that cut value lost the owner's
            # choice once trust was restored or a grant resumed (D-176). What
            # leaves is cut again to the current ceiling when each call is
            # routed.
            existing.update(record, **caps, data_policy=min(policy, standing, key=lambda item: item.rank).value)
            providers[provider_id] = existing
            current["providers"] = providers
            if api_key.strip():
                self._store_key_locked(workspace_id, provider_id, api_key)

        saved = self._update_workspace(workspace_id, apply)
        existing = dict((saved.get("providers") or {}).get(provider_id) or {})

        return {
            "provider": existing,
            "policy_was_clamped": decided["clamped"],
            "tier": decided["tier"].value,
            "policy_ceiling": decided["ceiling"].value,
            "workspace": saved["workspace_id"],
        }

    def disconnect_provider(self, workspace_id: str, provider_id: str) -> None:
        def apply(current: dict[str, Any]) -> None:
            providers = dict(current.get("providers") or {})
            providers.pop(provider_id, None)
            current["providers"] = providers
            # In the same locked window as the record: in a second one, a
            # Models-panel save landing between them re-created the
            # connection with no key (D-169). The key goes first, so a
            # failure part-way leaves nothing that can be spent.
            try:
                self._store_key_locked(workspace_id, provider_id, "")
            except RegistryError:
                # Keys that cannot be decrypted cannot be spent either. The
                # connection still goes, so nothing is routed to it; failing
                # here kept the provider connected with no way out (D-178).
                pass

        self._update_workspace(workspace_id, apply)

    def set_override(
        self,
        workspace_id: str,
        provider_id: str,
        *,
        trust_tier: str = "",
        data_policy: str = "",
        allow_above_ceiling: bool = False,
        reason: str = "",
        decided_by: str = "",
    ) -> dict[str, Any]:
        """Record an explicit decision to depart from the config default.

        Raising a provider above its ceiling is allowed — the owner asked to keep
        that freedom — but it is never silent: a reason is required and the
        decision is stored with who made it and when.
        """
        entry = self.registry.require(provider_id)
        if trust_tier and coerce_tier(trust_tier).rank > entry.derived_tier.rank and not reason.strip():
            raise ReasonRequired(_raise_needs_reason(entry.name, entry.derived_tier, coerce_tier(trust_tier)))
        if allow_above_ceiling and not reason.strip():
            raise ValueError(
                "Raising a provider above its trust ceiling needs a reason. "
                "It is recorded so you can see later why the decision was made."
            )
        granted = coerce_policy(data_policy) if data_policy else DataPolicy.FULL

        def apply(current: dict[str, Any]) -> None:
            overrides = dict(current.get("overrides") or {})
            previous = dict(overrides.get(provider_id) or {})
            if not (trust_tier or data_policy or allow_above_ceiling):
                # Withdraws this route's own decision — what may be sent —
                # and keeps the trust settings: the card's reset link used to
                # delete the owner's blocks along with the grant.
                if not (previous.get("allow_above_ceiling") or previous.get("data_policy")):
                    # Nothing to withdraw. Each click used to leave a
                    # "withdrawn" entry in a record holding nothing else (D-170).
                    return
                record = {key: value for key, value in previous.items() if key in _TRUST_KEYS}
                record["provider_id"] = provider_id
                _remember(record, "full_access", "", {
                    "tier": "", "reason": "withdrawn", "decided_by": decided_by or workspace_id,
                    "decided_at": to_utc_iso(),
                })
                overrides[provider_id] = record
                current["overrides"] = overrides
                return
            if allow_above_ceiling:
                # A grant that can change nothing is refused rather than
                # shown as "full access" while nothing more is sent (D-171,
                # D-179). The screen offers it by the same rule.
                standing = {**previous, "trust_tier": trust_tier} if trust_tier else previous
                connected = (dict(current.get("providers") or {})).get(provider_id)
                refusal = self._grant_refusal(entry, standing, connected, granted)
                if refusal:
                    raise ValueError(refusal)
            decision = ProviderOverride(
                provider_id=provider_id,
                trust_tier=coerce_tier(trust_tier) if trust_tier else None,
                data_policy=coerce_policy(data_policy) if data_policy else None,
                allow_above_ceiling=bool(allow_above_ceiling),
                reason=reason.strip(),
                decided_by=decided_by or workspace_id,
                decided_at=to_utc_iso(),
            ).to_dict()
            # Rebuilt from scratch, this record dropped the trust settings
            # made on the trust route — a per-model tier vanished when full
            # access was granted. They are kept unless this call sets them.
            for key in _TRUST_KEYS:
                if key in previous:
                    decision[key] = previous[key]
            if trust_tier:
                decision["trust_tier"] = coerce_tier(trust_tier).value
                decision["trust_reason"] = reason.strip()
                decision["trust_decided_by"] = decided_by or workspace_id
                decision["trust_decided_at"] = decision["decided_at"]
            _remember(decision, "full_access" if allow_above_ceiling else "override", "", {
                "tier": decision.get("trust_tier", ""), "reason": reason.strip(),
                "decided_by": decided_by or workspace_id, "decided_at": decision["decided_at"],
            })
            overrides[provider_id] = decision
            current["overrides"] = overrides

        return self._update_workspace(workspace_id, apply)

    def _switched_on(self, entry: Any, connected: dict[str, Any] | None) -> list[str]:
        """The models calls go to — the router's own rule for "none chosen"."""
        record = connected or {}
        return [
            str(item)
            for item in (record.get("model_ids") or ([record["model_id"]] if record.get("model_id") else []))
        ] or [entry.default_model]

    @staticmethod
    def _grant_state(entry: Any, override: dict[str, Any], routed: list[Any]) -> str:
        """Why the owner's grant is, or is not, deciding what is sent."""
        if not override.get("allow_above_ceiling"):
            return ""
        host = _host_tier(entry, override)
        if host is TrustTier.D:
            return "provider_blocked"
        if host.rank < entry.derived_tier.rank:
            return "provider_lowered"
        if not any(item.grant_applied for item in routed):
            return "no_model"
        return "active"

    def _grant_refusal(
        self,
        entry: Any,
        override: dict[str, Any],
        connected: dict[str, Any] | None,
        granted: DataPolicy,
    ) -> str:
        """Why a full-data grant now would change nothing, or "" if it would."""
        host = _host_tier(entry, override)
        if host is TrustTier.D:
            return f"{entry.name} is blocked, so it receives nothing at any level. Raise its trust first."
        if host.rank < entry.derived_tier.rank:
            return (
                f"You trust {entry.name} less than its default. Return it to its default "
                "trust before sending it more data."
            )
        if granted.rank <= policy_ceiling_for_tier(host).rank:
            return (
                f"{entry.name} is {host.label}, which already allows {granted.label}. "
                "Choose it under How much to send."
            )
        lifted = ProviderOverride.from_dict({
            **override, "provider_id": entry.id, "allow_above_ceiling": True, "data_policy": granted.value,
        })
        if not any(
            self.registry.resolve(entry.id, model_id=model_id, override=lifted).grant_applied
            for model_id in self._switched_on(entry, connected)
        ):
            return (
                f"None of the models you switched on for {entry.name} is trusted at its default, "
                "so full data would reach none of them."
            )
        return ""

    def set_trust(
        self,
        workspace_id: str,
        provider_id: str,
        *,
        tier: str = "",
        model_id: str = "",
        reason: str = "",
        decided_by: str = "",
    ) -> dict[str, Any]:
        """Set or clear trust for a provider, or for one model under it (DD-65).

        Lowering is never refused. A tier above the one this setting departs
        from needs a reason, stored with who and when. "" returns that level
        to its default. No tier opens the mailbox: that is its own unlock.
        """
        entry = self.registry.require(provider_id)
        model_id = model_id.strip()
        wanted = coerce_tier(tier) if tier.strip() else None

        def apply(current: dict[str, Any]) -> None:
            # Everything decided from the locked snapshot: a baseline read
            # before the lock could let a concurrent change skip the reason.
            # A ValueError here aborts the update before anything is written.
            overrides = dict(current.get("overrides") or {})
            record = dict(overrides.get(provider_id) or {})
            record["provider_id"] = provider_id
            if model_id:
                offered = (dict(current.get("providers") or {}).get(provider_id) or {}).get("model_ids") or []
                if entry.model(model_id) is None and model_id not in offered:
                    raise ValueError(
                        f"{entry.name} does not offer {model_id}, so it has no trust to change."
                    )
                standing = dict(record.get("model_tiers") or {}).get(model_id)
                standing_tier = str((standing.get("tier") if isinstance(standing, dict) else standing) or "")
                standing_reason = str(standing.get("reason") or "") if isinstance(standing, dict) else ""
            else:
                standing_tier = str(record.get("trust_tier") or "")
                standing_reason = str(record.get("trust_reason") or "")
            if standing_tier == (wanted.value if wanted else "") and (
                wanted is None or not reason.strip() or reason.strip() == standing_reason
            ):
                # Nothing changes, so nothing is recorded: every such click
                # used to add a history entry (D-170). The same tier with a
                # new reason is a new decision, and is kept below.
                return
            if wanted is not None:
                if model_id:
                    # DD-65 as amended: never above the host, which sees
                    # every byte — a reason cannot fix that, raising the
                    # provider can. Past the cap from who built it is a
                    # raise; the cap, not the path taken, is the baseline.
                    host = _host_tier(entry, record)
                    if wanted.rank > host.rank:
                        raise ValueError(
                            f"A model cannot be trusted more than the provider that runs it: "
                            f"{entry.name} is {host.label}. Raise {entry.name} first."
                        )
                    known, cap = self.registry.model_origin(provider_id, model_id)
                    if not known:
                        raise ValueError(
                            f"off_CRM cannot tell who built {model_id}, so it stays blocked. "
                            "Add a model_origin_rules entry for it first."
                        )
                    if cap is not None and wanted.rank > cap.rank and not reason.strip():
                        raise ReasonRequired(
                            _raise_needs_reason(f"{model_id} on {entry.name}", cap, wanted)
                        )
                elif wanted.rank > entry.derived_tier.rank and not reason.strip():
                    raise ReasonRequired(_raise_needs_reason(entry.name, entry.derived_tier, wanted))
            decision = {
                "tier": wanted.value if wanted else "",
                "reason": reason.strip(),
                "decided_by": decided_by or workspace_id,
                "decided_at": to_utc_iso(),
            }
            if model_id:
                models = dict(record.get("model_tiers") or {})
                if wanted is None:
                    models.pop(model_id, None)
                else:
                    if model_id not in models and len(models) >= _MODEL_SETTINGS:
                        # Each is kept with its reason in a document read on
                        # every request; one login grew it without end (D-180).
                        raise ValueError(
                            f"You have set trust for {_MODEL_SETTINGS} models of {entry.name}. "
                            "Set one back to Same as provider first."
                        )
                    models[model_id] = decision
                record["model_tiers"] = models
            elif wanted is None:
                for key in ("trust_tier", "trust_reason", "trust_decided_by", "trust_decided_at"):
                    record.pop(key, None)
            else:
                record["trust_tier"] = decision["tier"]
                record["trust_reason"] = decision["reason"]
                record["trust_decided_by"] = decision["decided_by"]
                record["trust_decided_at"] = decision["decided_at"]
            _remember(record, "trust", model_id, decision)
            overrides[provider_id] = record
            current["overrides"] = overrides

        return self._update_workspace(workspace_id, apply)

    def unlock_mailbox(self, workspace_id: str, phrase: str) -> dict[str, Any]:
        cleaned = str(phrase or "").strip()
        if cleaned and cleaned != MAILBOX_UNLOCK_PHRASE:
            raise ValueError(
                f'To let mailbox content reach an AI provider, type exactly: "{MAILBOX_UNLOCK_PHRASE}"'
            )
        return self.save(workspace_id, {"mailbox_unlock_phrase": cleaned})

    # ── the shape the broker wants ──────────────────────────────────────────

    def egress_settings(self, workspace_id: str = DEFAULT_WORKSPACE) -> WorkspaceEgressSettings:
        document = self.raw(workspace_id)
        providers = dict(document.get("providers") or {})
        enabled = tuple(
            provider_id
            for provider_id, record in providers.items()
            if bool(record.get("enabled", True))
        )
        overrides = {
            # Keyed by the provider either way: a record written without its
            # own `provider_id` must still be this provider's (D-170).
            provider_id: ProviderOverride.from_dict({**payload, "provider_id": provider_id})
            for provider_id, payload in (document.get("overrides") or {}).items()
            if isinstance(payload, dict)
        }
        quota_limits = {
            provider_id: QuotaLimits(
                requests_per_minute=int(record.get("requests_per_minute", 0) or 0),
                requests_per_day=int(record.get("requests_per_day", 0) or 0),
                max_spend_usd_per_day=float(record.get("max_spend_usd_per_day", 0.0) or 0.0),
            )
            for provider_id, record in providers.items()
        }
        policies = {
            provider_id: coerce_policy(record.get("data_policy"))
            for provider_id, record in providers.items()
            if record.get("data_policy")
        }
        # Previously the chosen model was stored and displayed but never reached
        # the broker, so every call silently used the provider's default. Older
        # records hold a single `model_id`; both shapes are read here.
        enabled_models = {
            provider_id: tuple(
                str(item)
                for item in (
                    record.get("model_ids")
                    or ([record["model_id"]] if record.get("model_id") else [])
                )
            )
            for provider_id, record in providers.items()
        }
        return WorkspaceEgressSettings(
            workspace_id=workspace_id,
            enabled_provider_ids=enabled,
            overrides=overrides,
            quota_limits=quota_limits,
            owner_domains=tuple(document.get("owner_domains") or ()),
            owner_addresses=tuple(document.get("owner_addresses") or ()),
            positioning_line=str(document.get("positioning_line", "")),
            mailbox_unlock_phrase=str(document.get("mailbox_unlock_phrase", "")),
            default_policy_by_provider=policies,
            enabled_models=enabled_models,
        )

    def describe(self, workspace_id: str = DEFAULT_WORKSPACE) -> dict[str, Any]:
        """Everything the Connectors screen needs, in one call."""
        document = self.raw(workspace_id)
        connected = dict(document.get("providers") or {})
        overrides = dict(document.get("overrides") or {})
        rows: list[dict[str, Any]] = []
        for entry in self.registry.all():
            record = connected.get(entry.id)
            override = overrides.get(entry.id)
            tier = _host_tier(entry, override or {})
            resolved_override = ProviderOverride.from_dict({**override, "provider_id": entry.id}) if override else None
            # What this provider may be sent now, and what it is: the card
            # showed the config tier's ceiling after the owner changed trust,
            # and the stored choice even where the ceiling cut it (D-172).
            ceiling = _host_ceiling(entry, override or {})
            # What leaves is the router's answer for each model switched on —
            # a model the owner lowered, or one capped by who built it, is
            # sent less than its provider (D-179).
            routed = [
                self.registry.resolve(
                    entry.id,
                    model_id=model_id,
                    requested_policy=(record or {}).get("data_policy") or None,
                    override=resolved_override,
                )
                for model_id in self._switched_on(entry, record)
            ]
            # A blocked model is sent nothing at all, not "strict" (D-188).
            reachable = [item for item in routed if item.tier is not TrustTier.D]
            sent = {item.policy for item in reachable}
            grant_state = self._grant_state(entry, override or {}, routed)
            # The grant lifts the ceiling only while it reaches a model: with
            # it reaching none, the form read "allows up to Full" (D-184).
            if grant_state != "active":
                ceiling = policy_ceiling_for_tier(tier)
            payload = entry.to_dict()
            payload.update(
                {
                    # The trust the owner set, not config's: the card read
                    # "Default trust" for a provider lowered to Restricted.
                    **describe_tier(tier),
                    "policy_ceiling": ceiling.value,
                    # The most "How much to send" can be: the ceiling at the
                    # provider's default or the owner's raise. The form offers
                    # no more, so nothing chosen there is cut when saved.
                    "standing_ceiling": policy_ceiling_for_tier(
                        tier if tier.rank >= entry.derived_tier.rank else entry.derived_tier
                    ).value,
                    "sends": max(sent, key=lambda policy: policy.rank).value if sent else "",
                    "sends_varies": len(sent) > 1,
                    "sends_nothing": not reachable,
                    "grant_state": grant_state,
                    "grant_active": grant_state == "active",
                    "grant_offer": bool(
                        record
                        and not (override or {}).get("allow_above_ceiling")
                        and not self._grant_refusal(entry, override or {}, record, DataPolicy.FULL)
                    ),
                    "connected": record is not None,
                    "enabled": bool(record.get("enabled", False)) if record else False,
                    "has_key": bool(self.key_for(workspace_id, entry.id)),
                    "model_id": (record or {}).get("model_id", entry.default_model),
                    "model_ids": list(
                        (record or {}).get("model_ids")
                        or ([record["model_id"]] if record and record.get("model_id") else [])
                    ),
                    "supports_model_discovery": entry.supports_model_discovery,
                    # Every model this key could run, each with its own tier, so
                    # the card can show that one key spans several trust levels.
                    "available_models": [
                        {
                            **model.to_dict(),
                            # The router's own answer, so the card cannot
                            # show a tier the owner's settings do not give.
                            "tier": self.registry.resolve(
                                entry.id, model_id=model.id, override=resolved_override
                            ).tier.value,
                            "default_tier": entry.tier_for_model(model.id).value,
                        }
                        for model in entry.models
                    ],
                    "default_tier": entry.derived_tier.value,
                    # Every model trust can be set for: config's list, plus any
                    # switched on from the live catalogue, which the list above
                    # does not carry. Tiers are the router's own answer.
                    "trust_models": [
                        {
                            "id": model_id,
                            "tier": self.registry.resolve(
                                entry.id, model_id=model_id, override=resolved_override
                            ).tier.value,
                            "default_tier": self.registry.resolve(entry.id, model_id=model_id).tier.value,
                        }
                        for model_id in dict.fromkeys(
                            [model.id for model in entry.models]
                            + [str(item) for item in ((record or {}).get("model_ids") or [])]
                        )
                    ],
                    "data_policy": (record or {}).get(
                        "data_policy", default_policy_for_tier(tier).value
                    ),
                    "effective_tier": tier.value,
                    "override": override,
                    "requests_per_minute": (record or {}).get("requests_per_minute", 0),
                    "requests_per_day": (record or {}).get("requests_per_day", 0),
                    "max_spend_usd_per_day": (record or {}).get("max_spend_usd_per_day", 0.0),
                }
            )
            rows.append(payload)
        return {
            "workspace_id": workspace_id,
            "positioning_line": document.get("positioning_line", ""),
            "owner_domains": document.get("owner_domains") or [],
            "owner_addresses": document.get("owner_addresses") or [],
            "mailbox_unlocked": str(document.get("mailbox_unlock_phrase", "")).strip()
            == MAILBOX_UNLOCK_PHRASE,
            "mailbox_unlock_phrase_required": MAILBOX_UNLOCK_PHRASE,
            "providers": rows,
            "policy_levels": [
                {
                    "value": policy.value,
                    "label": policy.label,
                    "description": policy.description,
                }
                for policy in DataPolicy
            ],
            "tiers": [
                {
                    "tier": tier.value,
                    "label": tier.label,
                    "policy_ceiling": policy_ceiling_for_tier(tier).value,
                }
                for tier in TrustTier
            ],
        }
