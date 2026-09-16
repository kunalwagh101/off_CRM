"""Configuration-driven browser platform registry.  `S-03.02.05`.

A platform is data, not a branch in three different Python modules. One row owns
how sign-in is recognised, which hosts inherit its browser policy, and the
default action budget for an account. Adding a platform therefore means editing
`config/platforms.yaml`; `identity.py`, `policy.py` and `budget.py` consume the
same validated row.

The registry is validated when this module is imported. A malformed deployment
fails at startup/import with the platform's name instead of waiting for an agent
to reach the bad row mid-run.
"""
from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

_PACKAGE_DIR = Path(__file__).resolve().parent
_SOURCE_ROOT = _PACKAGE_DIR.parents[1]
PACKAGED_REGISTRY_PATH = _PACKAGE_DIR / "platforms.yaml"
SOURCE_REGISTRY_PATH = _SOURCE_ROOT / "config" / "platforms.yaml"
_ID = re.compile(r"^[a-z0-9][a-z0-9_-]*$")


class PlatformRegistryError(ValueError):
    """A platform declaration is unsafe or incomplete."""


@dataclass(frozen=True, slots=True)
class DomainDeclaration:
    suffix: str
    min_seconds_between_actions: float
    unattended: bool
    refuse: tuple[str, ...] = ()
    confirm: tuple[str, ...] = ()
    note: str = ""


@dataclass(frozen=True, slots=True)
class Platform:
    id: str
    label: str
    login_url: str
    home_url: str
    signed_in: tuple[str, ...]
    signed_out: tuple[str, ...]
    aliases: tuple[str, ...] = ()
    domains: tuple[DomainDeclaration, ...] = ()
    actions_per_hour: int = 0
    actions_per_day: int = 0
    note: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "label": self.label,
            "login_url": self.login_url,
            "home_url": self.home_url,
            "note": self.note,
            "aliases": list(self.aliases),
            "budget": {
                "actions_per_hour": self.actions_per_hour,
                "actions_per_day": self.actions_per_day,
            },
            "domains": [
                {
                    "suffix": item.suffix,
                    "min_seconds_between_actions": item.min_seconds_between_actions,
                    "unattended": item.unattended,
                    "refuse": list(item.refuse),
                    "confirm": list(item.confirm),
                    "note": item.note,
                }
                for item in self.domains
            ],
        }


def default_registry_path() -> Path:
    override = os.environ.get("OFFSETX_PLATFORM_REGISTRY", "").strip()
    if override:
        return Path(override)
    for candidate in (
        Path.cwd() / "config" / "platforms.yaml",
        SOURCE_REGISTRY_PATH,
        PACKAGED_REGISTRY_PATH,
    ):
        if candidate.exists():
            return candidate
    return PACKAGED_REGISTRY_PATH


def _document(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise PlatformRegistryError(f"Platform registry not found at {path}")
    text = path.read_text(encoding="utf-8")
    if path.suffix.lower() in {".yaml", ".yml"}:
        try:
            import yaml
            payload = yaml.safe_load(text)
        except Exception as exc:
            raise PlatformRegistryError(f"Platform registry is not valid YAML: {exc}") from exc
    else:
        try:
            payload = json.loads(text)
        except json.JSONDecodeError as exc:
            raise PlatformRegistryError(f"Platform registry is not valid JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise PlatformRegistryError("Platform registry must be a mapping at the top level")
    return payload


def _text(raw: dict[str, Any], field: str, platform_id: str) -> str:
    value = str(raw.get(field, "")).strip()
    if not value:
        raise PlatformRegistryError(
            f"Platform {platform_id!r} is missing required field {field!r}"
        )
    return value


def _strings(raw: dict[str, Any], field: str, platform_id: str, *, required: bool = True) -> tuple[str, ...]:
    value = raw.get(field)
    if value is None and not required:
        return ()
    if not isinstance(value, list) or (required and not value):
        raise PlatformRegistryError(
            f"Platform {platform_id!r} field {field!r} must be a non-empty list"
        )
    cleaned = tuple(str(item).strip() for item in value if str(item).strip())
    if required and not cleaned:
        raise PlatformRegistryError(
            f"Platform {platform_id!r} field {field!r} must contain text values"
        )
    return cleaned


def _url(raw: dict[str, Any], field: str, platform_id: str) -> str:
    value = _text(raw, field, platform_id)
    parsed = urlsplit(value)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise PlatformRegistryError(
            f"Platform {platform_id!r} field {field!r} must be an absolute http(s) URL"
        )
    return value


def _positive_int(raw: dict[str, Any], field: str, platform_id: str) -> int:
    try:
        value = int(raw.get(field))
    except (TypeError, ValueError):
        value = 0
    if value <= 0:
        raise PlatformRegistryError(
            f"Platform {platform_id!r} budget field {field!r} must be a positive integer"
        )
    return value


def _parse_domain(raw: object, platform_id: str, index: int) -> DomainDeclaration:
    if not isinstance(raw, dict):
        raise PlatformRegistryError(
            f"Platform {platform_id!r} domain #{index + 1} must be a mapping"
        )
    suffix = str(raw.get("suffix", "")).strip().lower().lstrip(".")
    if not suffix or ":" in suffix or "/" in suffix or "." not in suffix:
        raise PlatformRegistryError(
            f"Platform {platform_id!r} has invalid domain suffix {suffix!r}"
        )
    try:
        pace = float(raw.get("min_seconds_between_actions"))
    except (TypeError, ValueError):
        pace = -1.0
    if pace < 0:
        raise PlatformRegistryError(
            f"Platform {platform_id!r} domain {suffix!r} needs a non-negative pace"
        )
    unattended = raw.get("unattended")
    if not isinstance(unattended, bool):
        raise PlatformRegistryError(
            f"Platform {platform_id!r} domain {suffix!r} needs boolean 'unattended'"
        )
    return DomainDeclaration(
        suffix=suffix,
        min_seconds_between_actions=pace,
        unattended=unattended,
        refuse=_strings(raw, "refuse", platform_id, required=False),
        confirm=_strings(raw, "confirm", platform_id, required=False),
        note=str(raw.get("note", "")).strip(),
    )


def _parse_platform(raw: object, index: int) -> Platform:
    if not isinstance(raw, dict):
        raise PlatformRegistryError(f"Platform entry #{index + 1} must be a mapping")
    platform_id = str(raw.get("id", "")).strip().lower()
    if not platform_id:
        raise PlatformRegistryError(f"Platform entry #{index + 1} is missing required field 'id'")
    if not _ID.fullmatch(platform_id):
        raise PlatformRegistryError(f"Platform {platform_id!r} has an invalid id")

    aliases = tuple(item.lower() for item in _strings(raw, "aliases", platform_id, required=False))
    for alias in aliases:
        if not _ID.fullmatch(alias):
            raise PlatformRegistryError(f"Platform {platform_id!r} has invalid alias {alias!r}")

    signed_in = _strings(raw, "signed_in", platform_id)
    signed_out = _strings(raw, "signed_out", platform_id)
    overlap = {item.casefold() for item in signed_in} & {item.casefold() for item in signed_out}
    if overlap:
        raise PlatformRegistryError(
            f"Platform {platform_id!r} uses the same sign-in and sign-out signal: {sorted(overlap)[0]!r}"
        )

    domains_raw = raw.get("domains")
    if not isinstance(domains_raw, list) or not domains_raw:
        raise PlatformRegistryError(f"Platform {platform_id!r} needs at least one domain")
    domains = tuple(_parse_domain(item, platform_id, i) for i, item in enumerate(domains_raw))

    budget = raw.get("budget")
    if not isinstance(budget, dict):
        raise PlatformRegistryError(f"Platform {platform_id!r} is missing required field 'budget'")
    per_hour = _positive_int(budget, "actions_per_hour", platform_id)
    per_day = _positive_int(budget, "actions_per_day", platform_id)
    if per_hour > per_day:
        raise PlatformRegistryError(
            f"Platform {platform_id!r} budget allows more actions per hour than per day"
        )

    return Platform(
        id=platform_id,
        label=_text(raw, "label", platform_id),
        login_url=_url(raw, "login_url", platform_id),
        home_url=_url(raw, "home_url", platform_id),
        signed_in=signed_in,
        signed_out=signed_out,
        aliases=aliases,
        domains=domains,
        actions_per_hour=per_hour,
        actions_per_day=per_day,
        note=str(raw.get("note", "")).strip(),
    )


@lru_cache(maxsize=8)
def load_platforms(path: str | Path | None = None) -> dict[str, Platform]:
    registry_path = Path(path) if path is not None else default_registry_path()
    document = _document(registry_path)
    raw_entries = document.get("platforms")
    if not isinstance(raw_entries, list) or not raw_entries:
        raise PlatformRegistryError("Platform registry needs a non-empty 'platforms' list")

    result: dict[str, Platform] = {}
    names: dict[str, str] = {}
    domains: dict[str, str] = {}
    for index, raw in enumerate(raw_entries):
        entry = _parse_platform(raw, index)
        for name in (entry.id, *entry.aliases):
            if name in names:
                raise PlatformRegistryError(
                    f"Platform {entry.id!r} reuses id or alias {name!r} from platform {names[name]!r}"
                )
            names[name] = entry.id
        for domain in entry.domains:
            if domain.suffix in domains:
                raise PlatformRegistryError(
                    f"Platform {entry.id!r} reuses domain {domain.suffix!r} from platform {domains[domain.suffix]!r}"
                )
            domains[domain.suffix] = entry.id
        result[entry.id] = entry
    return result


def resolve_platform(platform_id: str, entries: dict[str, Platform] | None = None) -> Platform:
    declared = entries if entries is not None else load_platforms()
    key = str(platform_id or "").strip().lower()
    if key in declared:
        return declared[key]
    for entry in declared.values():
        if key in entry.aliases:
            return entry
    raise PlatformRegistryError(
        f"Unknown platform {platform_id!r}. Declared: {', '.join(sorted(declared))}."
    )
