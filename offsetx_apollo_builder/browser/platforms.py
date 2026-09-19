"""Validated browser-platform registry for S-03.02.05.

A platform declaration owns the pieces that must move together: sign-in signals,
domains/pacing policy and the default per-account action budget.  The registry is
repository-controlled data.  It cannot execute code, import modules or widen the
browser's closed action vocabulary.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from functools import lru_cache
from importlib.resources import files
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import urlsplit

REGISTRY_VERSION = 1
_ID = re.compile(r"^[a-z0-9][a-z0-9_-]{0,39}$")
_DOMAIN = re.compile(r"^(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}$")
_ALLOWED_KEYS = frozenset({
    "id", "aliases", "label", "login_url", "home_url", "signed_in", "signed_out",
    "domains", "policy", "budget", "note",
})
_POLICY_KEYS = frozenset({
    "min_seconds_between_actions", "unattended", "refuse", "confirm", "note",
})
_BUDGET_KEYS = frozenset({"actions_per_hour", "actions_per_day"})
_ALLOWED_POLICY_ACTIONS = frozenset({
    "submit", "send", "delete", "purchase", "publish", "upload",
    "connect", "bulk_export",
})


class PlatformRegistryError(ValueError):
    """The registry is invalid and must not be partially loaded."""


def _text(value: Any, *, name: str, limit: int = 500) -> str:
    text = str(value or "").strip()
    if not text:
        raise PlatformRegistryError(f"{name} must not be empty")
    if "\x00" in text or len(text) > limit:
        raise PlatformRegistryError(f"{name} exceeds its allowed size")
    return text


def _string_list(value: Any, *, name: str, required: bool = True) -> tuple[str, ...]:
    if not isinstance(value, list) or (required and not value):
        raise PlatformRegistryError(f"{name} must be a {'non-empty ' if required else ''}list")
    result: list[str] = []
    for item in value:
        text = _text(item, name=name, limit=120).lower()
        if text not in result:
            result.append(text)
    return tuple(result)


def _url(value: Any, *, name: str) -> str:
    text = _text(value, name=name, limit=1000)
    try:
        parts = urlsplit(text)
    except ValueError as exc:
        raise PlatformRegistryError(f"{name} is not a valid URL") from exc
    if parts.scheme != "https" or not parts.hostname:
        raise PlatformRegistryError(f"{name} must be an absolute https URL")
    host = parts.hostname.lower().rstrip(".")
    if host in {"localhost", "127.0.0.1", "0.0.0.0", "::1", "169.254.169.254"}:
        raise PlatformRegistryError(f"{name} may not target a local/metadata host")
    if host.endswith(".internal"):
        raise PlatformRegistryError(f"{name} may not target an internal host")
    return text


def _domain(value: Any, *, name: str) -> str:
    text = str(value or "").strip().lower().rstrip(".")
    if not _DOMAIN.fullmatch(text):
        raise PlatformRegistryError(f"{name} contains invalid domain {value!r}")
    return text


def _positive_int(value: Any, *, name: str, maximum: int = 100_000) -> int:
    if isinstance(value, bool):
        raise PlatformRegistryError(f"{name} must be a positive integer")
    try:
        number = int(value)
    except (TypeError, ValueError) as exc:
        raise PlatformRegistryError(f"{name} must be a positive integer") from exc
    if number <= 0 or number > maximum or str(number) != str(value).strip():
        raise PlatformRegistryError(f"{name} must be a positive integer")
    return number


@dataclass(frozen=True, slots=True)
class Platform:
    id: str
    label: str
    login_url: str
    home_url: str
    signed_in: tuple[str, ...]
    signed_out: tuple[str, ...]
    domains: tuple[str, ...]
    aliases: tuple[str, ...] = ()
    min_seconds_between_actions: float = 0.4
    unattended: bool = False
    refuse: tuple[str, ...] = ()
    confirm: tuple[str, ...] = ()
    actions_per_hour: int = 60
    actions_per_day: int = 300
    note: str = ""
    policy_note: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "label": self.label,
            "login_url": self.login_url,
            "home_url": self.home_url,
            "note": self.note,
        }

    @classmethod
    def from_data(cls, raw: Any) -> "Platform":
        if not isinstance(raw, dict):
            raise PlatformRegistryError("Each platform must be an object")
        unknown = set(raw) - _ALLOWED_KEYS
        if unknown:
            raise PlatformRegistryError(
                "Platform has unknown fields: " + ", ".join(sorted(unknown))
            )
        pid = _text(raw.get("id"), name="platform id", limit=40).lower()
        if not _ID.fullmatch(pid):
            raise PlatformRegistryError(f"Invalid platform id {pid!r}")

        aliases_raw = raw.get("aliases", [])
        aliases = _string_list(aliases_raw, name=f"{pid}.aliases", required=False)
        for alias in aliases:
            if not _ID.fullmatch(alias):
                raise PlatformRegistryError(f"Invalid platform alias {alias!r}")

        domains_raw = raw.get("domains")
        if not isinstance(domains_raw, list) or not domains_raw:
            raise PlatformRegistryError(f"{pid}.domains must be a non-empty list")
        domains = tuple(dict.fromkeys(_domain(v, name=f"{pid}.domains") for v in domains_raw))

        policy = raw.get("policy")
        if not isinstance(policy, dict):
            raise PlatformRegistryError(f"{pid}.policy must be an object")
        unknown_policy = set(policy) - _POLICY_KEYS
        if unknown_policy:
            raise PlatformRegistryError(
                f"{pid}.policy has unknown fields: {', '.join(sorted(unknown_policy))}"
            )
        pace = policy.get("min_seconds_between_actions")
        if isinstance(pace, bool):
            raise PlatformRegistryError(f"{pid}.policy.min_seconds_between_actions must be numeric")
        try:
            pace_number = float(pace)
        except (TypeError, ValueError) as exc:
            raise PlatformRegistryError(
                f"{pid}.policy.min_seconds_between_actions must be numeric"
            ) from exc
        if pace_number < 0.1 or pace_number > 120:
            raise PlatformRegistryError(
                f"{pid}.policy.min_seconds_between_actions must be between 0.1 and 120"
            )
        unattended = policy.get("unattended")
        if not isinstance(unattended, bool):
            raise PlatformRegistryError(f"{pid}.policy.unattended must be true or false")

        def actions(key: str) -> tuple[str, ...]:
            values = _string_list(policy.get(key, []), name=f"{pid}.policy.{key}", required=False)
            unknown_actions = set(values) - _ALLOWED_POLICY_ACTIONS
            if unknown_actions:
                raise PlatformRegistryError(
                    f"{pid}.policy.{key} has unsupported actions: "
                    + ", ".join(sorted(unknown_actions))
                )
            return values

        budget = raw.get("budget")
        if not isinstance(budget, dict):
            raise PlatformRegistryError(f"{pid}.budget must be an object")
        unknown_budget = set(budget) - _BUDGET_KEYS
        if unknown_budget:
            raise PlatformRegistryError(
                f"{pid}.budget has unknown fields: {', '.join(sorted(unknown_budget))}"
            )
        per_hour = _positive_int(budget.get("actions_per_hour"), name=f"{pid}.budget.actions_per_hour")
        per_day = _positive_int(budget.get("actions_per_day"), name=f"{pid}.budget.actions_per_day")
        if per_hour > per_day:
            raise PlatformRegistryError(f"{pid}.budget cannot allow more per hour than per day")

        return cls(
            id=pid,
            aliases=aliases,
            label=_text(raw.get("label"), name=f"{pid}.label", limit=100),
            login_url=_url(raw.get("login_url"), name=f"{pid}.login_url"),
            home_url=_url(raw.get("home_url"), name=f"{pid}.home_url"),
            signed_in=_string_list(raw.get("signed_in"), name=f"{pid}.signed_in"),
            signed_out=_string_list(raw.get("signed_out"), name=f"{pid}.signed_out"),
            domains=domains,
            min_seconds_between_actions=pace_number,
            unattended=unattended,
            refuse=actions("refuse"),
            confirm=actions("confirm"),
            actions_per_hour=per_hour,
            actions_per_day=per_day,
            note=str(raw.get("note") or "").strip()[:1000],
            policy_note=str(policy.get("note") or "").strip()[:2000],
        )


class PlatformRegistry:
    def __init__(self, platforms: Iterable[Platform]) -> None:
        materialized = tuple(platforms)
        ids: dict[str, str] = {}
        domains: dict[str, str] = {}
        for item in materialized:
            for key in (item.id, *item.aliases):
                owner = ids.get(key)
                if owner:
                    raise PlatformRegistryError(
                        f"Platform name/alias {key!r} belongs to both {owner!r} and {item.id!r}"
                    )
                ids[key] = item.id
            for domain in item.domains:
                owner = domains.get(domain)
                if owner:
                    raise PlatformRegistryError(
                        f"Domain {domain!r} belongs to both {owner!r} and {item.id!r}"
                    )
                domains[domain] = item.id
        self._items = materialized
        self._lookup = {
            key: next(item for item in materialized if item.id == owner)
            for key, owner in ids.items()
        }

    @classmethod
    def from_data(cls, raw: Any) -> "PlatformRegistry":
        if not isinstance(raw, dict):
            raise PlatformRegistryError("Platform registry must be an object")
        unknown = set(raw) - {"version", "platforms"}
        if unknown:
            raise PlatformRegistryError(
                "Platform registry has unknown fields: " + ", ".join(sorted(unknown))
            )
        if raw.get("version") != REGISTRY_VERSION:
            raise PlatformRegistryError(
                f"Unsupported platform registry version {raw.get('version')!r}"
            )
        rows = raw.get("platforms")
        if not isinstance(rows, list) or not rows:
            raise PlatformRegistryError("Platform registry must contain platforms")
        return cls(Platform.from_data(item) for item in rows)

    @classmethod
    def from_file(cls, path: Path | str) -> "PlatformRegistry":
        source = Path(path)
        try:
            raw = json.loads(source.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise PlatformRegistryError(f"Could not read platform registry {source}") from exc
        return cls.from_data(raw)

    def get(self, platform_id: str) -> Platform:
        key = str(platform_id or "").strip().lower()
        try:
            return self._lookup[key]
        except KeyError as exc:
            raise PlatformRegistryError(
                f"Unknown platform {platform_id!r}. Declared: "
                + ", ".join(sorted(item.id for item in self._items))
            ) from exc

    def maybe(self, platform_id: str) -> Platform | None:
        return self._lookup.get(str(platform_id or "").strip().lower())

    def all(self) -> tuple[Platform, ...]:
        return self._items


@lru_cache(maxsize=1)
def default_registry() -> PlatformRegistry:
    source = files("offsetx_apollo_builder.browser").joinpath("platforms.json")
    return PlatformRegistry.from_data(json.loads(source.read_text(encoding="utf-8")))


def platform_map() -> dict[str, Platform]:
    return {item.id: item for item in default_registry().all()}


def budget_map() -> dict[str, tuple[int, int]]:
    result: dict[str, tuple[int, int]] = {}
    for item in default_registry().all():
        result[item.id] = (item.actions_per_hour, item.actions_per_day)
        for alias in item.aliases:
            result[alias] = result[item.id]
    return result
