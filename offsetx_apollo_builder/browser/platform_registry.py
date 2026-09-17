"""Declarative connected-platform registry.  `S-03.02.05`

A connected platform is one row of trusted configuration: where the owner signs
in, which accessible names prove the session state, how quickly the browser may
act, and the per-account action ceiling.

The loader is intentionally strict. A bad declaration fails while the process is
starting, before an agent can reach a browser. Generic web safety remains in
`policy.py`; this registry cannot relax localhost/metadata refusals.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

import yaml

DEFAULT_REGISTRY_PATH = Path(__file__).with_name("platforms.yaml")
REGISTRY_ENV = "OFF_CRM_PLATFORM_REGISTRY"
DEFAULT_FALLBACK_BUDGET = (60, 300)
_ID = re.compile(r"^[a-z0-9][a-z0-9_-]*$")
_ACTION = re.compile(r"^[a-z][a-z0-9_-]*$")
_REQUIRED_PLATFORM = {
    "id", "label", "login_url", "home_url", "signed_in", "signed_out", "budget", "domains",
}
_ALLOWED_PLATFORM = _REQUIRED_PLATFORM | {"note", "aliases"}
_ALLOWED_BUDGET = {"actions_per_hour", "actions_per_day"}
_ALLOWED_DOMAIN = {
    "suffix", "min_seconds_between_actions", "unattended", "refuse", "confirm", "note", "label",
}


class PlatformRegistryError(ValueError):
    """The platform declaration is invalid; the message names the row and field."""


class UnknownPlatform(ValueError):
    """A platform nobody declared. Never assumed safe to sign in to."""


@dataclass(frozen=True, slots=True)
class DomainSpec:
    suffix: str
    label: str
    min_seconds_between_actions: float
    unattended: bool
    refuse: tuple[str, ...] = ()
    confirm: tuple[str, ...] = ()
    note: str = ""


@dataclass(frozen=True)
class Platform:
    """One connected platform and all policy needed to use it safely."""

    id: str
    label: str
    login_url: str
    home_url: str
    signed_in: tuple[str, ...]
    signed_out: tuple[str, ...]
    note: str = ""
    aliases: tuple[str, ...] = ()
    budget_actions_per_hour: int = 0
    budget_actions_per_day: int = 0
    domains: tuple[DomainSpec, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        # Keep the public connection catalogue stable. Budget and policy are
        # displayed by their owning modules, not duplicated into this object.
        return {
            "id": self.id,
            "label": self.label,
            "login_url": self.login_url,
            "home_url": self.home_url,
            "note": self.note,
        }


def _where(path: Path | str | None) -> Path:
    if path is not None:
        return Path(path)
    override = str(os.getenv(REGISTRY_ENV, "") or "").strip()
    return Path(override).expanduser() if override else DEFAULT_REGISTRY_PATH


def _fail(row: str, message: str) -> "NoReturn":
    raise PlatformRegistryError(f"Platform {row!r}: {message}")


def _mapping(value: Any, *, row: str, field: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        _fail(row, f"{field!r} must be a mapping")
    return value


def _string(value: Any, *, row: str, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        _fail(row, f"{field!r} must be a non-empty string")
    return value.strip()


def _strings(value: Any, *, row: str, field: str, required: bool = False) -> tuple[str, ...]:
    if value is None and not required:
        return ()
    if not isinstance(value, list) or (required and not value):
        _fail(row, f"{field!r} must be a non-empty list of strings")
    result: list[str] = []
    for item in value:
        text = _string(item, row=row, field=field).lower()
        if text not in result:
            result.append(text)
    if required and not result:
        _fail(row, f"{field!r} must contain at least one signal")
    return tuple(result)


def _actions(value: Any, *, row: str, field: str) -> tuple[str, ...]:
    if value is None:
        return ()
    result = _strings(value, row=row, field=field)
    for action in result:
        if not _ACTION.fullmatch(action):
            _fail(row, f"{field!r} contains invalid action {action!r}")
    return result


def _nonnegative_int(value: Any, *, row: str, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        _fail(row, f"{field!r} must be a non-negative integer")
    return value


def _https(value: Any, *, row: str, field: str) -> str:
    text = _string(value, row=row, field=field)
    try:
        parsed = urlsplit(text)
    except ValueError as exc:
        _fail(row, f"{field!r} is not a valid URL: {exc}")
    if parsed.scheme.lower() != "https" or not parsed.hostname:
        _fail(row, f"{field!r} must be an absolute https URL")
    if parsed.username or parsed.password:
        _fail(row, f"{field!r} must not contain credentials")
    return text


def _domain(value: Any, *, row: str, label: str) -> DomainSpec:
    raw = _mapping(value, row=row, field="domain")
    unknown = set(raw) - _ALLOWED_DOMAIN
    if unknown:
        _fail(row, f"domain has unknown field(s): {', '.join(sorted(unknown))}")
    for required in ("suffix", "min_seconds_between_actions", "unattended"):
        if required not in raw:
            _fail(row, f"domain is missing required field {required!r}")

    suffix = _string(raw["suffix"], row=row, field="domain.suffix").lower().rstrip(".")
    if "://" in suffix or "/" in suffix or ":" in suffix or suffix.startswith("."):
        _fail(row, f"domain suffix {suffix!r} must be a bare hostname suffix")
    if "." not in suffix:
        _fail(row, f"domain suffix {suffix!r} is too broad")
    pace = raw["min_seconds_between_actions"]
    if isinstance(pace, bool) or not isinstance(pace, (int, float)) or float(pace) < 0:
        _fail(row, "'domain.min_seconds_between_actions' must be a non-negative number")
    unattended = raw["unattended"]
    if not isinstance(unattended, bool):
        _fail(row, "'domain.unattended' must be true or false")

    return DomainSpec(
        suffix=suffix,
        label=_string(raw.get("label", label), row=row, field="domain.label"),
        min_seconds_between_actions=float(pace),
        unattended=unattended,
        refuse=_actions(raw.get("refuse"), row=row, field="domain.refuse"),
        confirm=_actions(raw.get("confirm"), row=row, field="domain.confirm"),
        note=str(raw.get("note") or "").strip(),
    )


def _platform(value: Any, *, index: int) -> Platform:
    raw = _mapping(value, row=f"row-{index}", field="platform")
    row = str(raw.get("id") or f"row-{index}").strip().lower()
    unknown = set(raw) - _ALLOWED_PLATFORM
    if unknown:
        _fail(row, f"unknown field(s): {', '.join(sorted(unknown))}")
    for field in sorted(_REQUIRED_PLATFORM):
        if field not in raw:
            _fail(row, f"missing required field {field!r}")

    platform_id = _string(raw["id"], row=row, field="id").lower()
    if not _ID.fullmatch(platform_id):
        _fail(row, "'id' must contain only lowercase letters, numbers, '-' or '_'")
    label = _string(raw["label"], row=row, field="label")
    login_url = _https(raw["login_url"], row=row, field="login_url")
    home_url = _https(raw["home_url"], row=row, field="home_url")
    signed_in = _strings(raw["signed_in"], row=row, field="signed_in", required=True)
    signed_out = _strings(raw["signed_out"], row=row, field="signed_out", required=True)
    if set(signed_in) & set(signed_out):
        _fail(row, "the same signal cannot mean both signed in and signed out")

    aliases = _strings(raw.get("aliases"), row=row, field="aliases")
    for alias in aliases:
        if not _ID.fullmatch(alias):
            _fail(row, f"alias {alias!r} is invalid")
        if alias == platform_id:
            _fail(row, f"alias {alias!r} duplicates the platform id")

    budget = _mapping(raw["budget"], row=row, field="budget")
    unknown_budget = set(budget) - _ALLOWED_BUDGET
    if unknown_budget:
        _fail(row, f"budget has unknown field(s): {', '.join(sorted(unknown_budget))}")
    for field in _ALLOWED_BUDGET:
        if field not in budget:
            _fail(row, f"budget is missing required field {field!r}")
    per_hour = _nonnegative_int(
        budget["actions_per_hour"], row=row, field="budget.actions_per_hour"
    )
    per_day = _nonnegative_int(
        budget["actions_per_day"], row=row, field="budget.actions_per_day"
    )
    if per_hour and per_day and per_hour > per_day:
        _fail(row, "hourly action budget cannot exceed the daily budget")

    raw_domains = raw["domains"]
    if not isinstance(raw_domains, list) or not raw_domains:
        _fail(row, "'domains' must be a non-empty list")
    domains = tuple(_domain(item, row=row, label=label) for item in raw_domains)

    home_host = (urlsplit(home_url).hostname or "").lower()
    if not any(
        home_host == domain.suffix or home_host.endswith("." + domain.suffix)
        for domain in domains
    ):
        _fail(row, f"home_url host {home_host!r} is not covered by any declared domain")

    return Platform(
        id=platform_id,
        label=label,
        login_url=login_url,
        home_url=home_url,
        signed_in=signed_in,
        signed_out=signed_out,
        note=str(raw.get("note") or "").strip(),
        aliases=aliases,
        budget_actions_per_hour=per_hour,
        budget_actions_per_day=per_day,
        domains=domains,
    )


def load_registry(path: Path | str | None = None) -> dict[str, Platform]:
    source = _where(path)
    try:
        payload = yaml.safe_load(source.read_text(encoding="utf-8"))
    except OSError as exc:
        raise PlatformRegistryError(f"Platform registry {source}: {exc}") from exc
    except yaml.YAMLError as exc:
        raise PlatformRegistryError(f"Platform registry {source}: invalid YAML: {exc}") from exc

    if not isinstance(payload, dict):
        raise PlatformRegistryError(f"Platform registry {source}: top level must be a mapping")
    unknown_top = set(payload) - {"version", "platforms"}
    if unknown_top:
        raise PlatformRegistryError(
            f"Platform registry {source}: unknown field(s): {', '.join(sorted(unknown_top))}"
        )
    if payload.get("version") != 1:
        raise PlatformRegistryError(f"Platform registry {source}: version must be 1")
    rows = payload.get("platforms")
    if not isinstance(rows, list) or not rows:
        raise PlatformRegistryError(f"Platform registry {source}: 'platforms' must be non-empty")

    platforms: dict[str, Platform] = {}
    aliases: set[str] = set()
    domains: set[str] = set()
    for index, raw in enumerate(rows, 1):
        target = _platform(raw, index=index)
        if target.id in platforms or target.id in aliases:
            _fail(target.id, "duplicate platform id")
        for alias in target.aliases:
            if alias in platforms or alias in aliases:
                _fail(target.id, f"alias {alias!r} collides with another platform")
        for domain in target.domains:
            if domain.suffix in domains:
                _fail(target.id, f"domain {domain.suffix!r} is declared more than once")
        platforms[target.id] = target
        aliases.update(target.aliases)
        domains.update(domain.suffix for domain in target.domains)
    return platforms


PLATFORMS: dict[str, Platform] = load_registry()
ALIASES: dict[str, Platform] = {
    alias: target for target in PLATFORMS.values() for alias in target.aliases
}


def platform(platform_id: str) -> Platform:
    key = str(platform_id or "").strip().lower()
    target = PLATFORMS.get(key) or ALIASES.get(key)
    if target is None:
        declared = sorted(set(PLATFORMS) | set(ALIASES))
        raise UnknownPlatform(
            f"Unknown platform {platform_id!r}. Declared: {', '.join(declared)}."
        )
    return target


def budget_for_platform(platform_id: str) -> tuple[int, int]:
    try:
        target = platform(platform_id)
    except UnknownPlatform:
        return DEFAULT_FALLBACK_BUDGET
    return target.budget_actions_per_hour, target.budget_actions_per_day


def budget_defaults() -> dict[str, tuple[int, int]]:
    result = {
        target.id: (target.budget_actions_per_hour, target.budget_actions_per_day)
        for target in PLATFORMS.values()
    }
    for alias, target in ALIASES.items():
        result[alias] = (target.budget_actions_per_hour, target.budget_actions_per_day)
    return result


def platform_domains() -> tuple[DomainSpec, ...]:
    return tuple(domain for target in PLATFORMS.values() for domain in target.domains)
