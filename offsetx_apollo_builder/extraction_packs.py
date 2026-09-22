"""Declarative, validated extraction packs for public HTML sources.

Packs are data, not code. They may select records and read text/attributes from
already-fetched public HTML. They cannot execute expressions, perform network
requests, import modules, run JavaScript, or change crawler policy.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import urlsplit

PACK_VERSION = 1
MAX_PACKS = 500
MAX_SELECTOR_CHARS = 256
MAX_FIELD_CHARS = 128
ALLOWED_FIELDS = frozenset({
    "full_name",
    "first_name",
    "last_name",
    "email",
    "company",
    "company_url",
    "title",
    "country",
    "linkedin_url",
    "public_hook",
})
ALLOWED_MODES = frozenset({"text", "attr"})
_SAFE_ATTR = re.compile(r"^(?:href|content|datetime|title|aria-label|data-[a-z0-9_.:-]+)$", re.I)


class ExtractionPackError(ValueError):
    """An extraction-pack registry is invalid and must not be partially loaded."""


def normalize_pack_domain(value: str) -> str:
    text = str(value or "").strip().lower().rstrip(".")
    if "://" in text:
        text = urlsplit(text).hostname or ""
    text = text.removeprefix("www.").strip().rstrip(".")
    if not text or "/" in text or any(ch.isspace() for ch in text):
        raise ExtractionPackError(f"Invalid extraction-pack domain: {value!r}")
    try:
        return text.encode("idna").decode("ascii")
    except UnicodeError as exc:
        raise ExtractionPackError(f"Invalid extraction-pack domain: {value!r}") from exc


def _host_matches(host: str, domain: str) -> bool:
    return host == domain or host.endswith("." + domain)


def _bounded_text(value: Any, *, label: str, limit: int) -> str:
    text = str(value or "").strip()
    if not text:
        raise ExtractionPackError(f"{label} must not be empty")
    if "\x00" in text or len(text) > limit:
        raise ExtractionPackError(f"{label} exceeds its allowed size")
    return text


def _validated_css_selector(value: Any, *, label: str) -> str:
    selector = _bounded_text(value, label=label, limit=MAX_SELECTOR_CHARS)
    try:
        from scrapling.parser import Selector

        probe = Selector(
            content=b"<html><body><div class='probe'></div></body></html>",
            url="https://selector-validation.invalid/",
            encoding="utf-8",
            huge_tree=False,
            adaptive=False,
        )
        probe.css(selector)
        # Packs declare element selectors. Text/attribute extraction belongs to
        # the bounded rule contract below. Asking the same parser to append an
        # attribute pseudo-element rejects an already-terminal ::text/::attr
        # selector without us inventing a second CSS grammar.
        probe.css(f"{selector}::attr(data-validation)")
    except Exception as exc:
        raise ExtractionPackError(
            f"{label} is an invalid CSS selector or does not select elements: "
            f"{selector!r}"
        ) from exc
    return selector


@dataclass(frozen=True, slots=True)
class ExtractionRule:
    selector: str
    mode: str = "text"
    attribute: str = ""

    @classmethod
    def from_data(cls, data: Any, *, field_name: str) -> "ExtractionRule":
        if not isinstance(data, dict):
            raise ExtractionPackError(f"Field {field_name!r} must be an object")
        unknown = set(data) - {"selector", "mode", "attribute"}
        if unknown:
            raise ExtractionPackError(
                f"Field {field_name!r} has unknown keys: {', '.join(sorted(unknown))}"
            )
        selector = _validated_css_selector(
            data.get("selector"), label=f"selector for {field_name}"
        )
        mode = str(data.get("mode") or "text").strip().lower()
        if mode not in ALLOWED_MODES:
            raise ExtractionPackError(
                f"Field {field_name!r} uses unsupported extraction mode {mode!r}"
            )
        attribute = str(data.get("attribute") or "").strip()
        if mode == "text":
            if attribute:
                raise ExtractionPackError(
                    f"Field {field_name!r} is text mode and cannot declare an attribute"
                )
        else:
            if not _SAFE_ATTR.fullmatch(attribute):
                raise ExtractionPackError(
                    f"Field {field_name!r} uses unsupported attribute {attribute!r}"
                )
        return cls(selector=selector, mode=mode, attribute=attribute)


@dataclass(frozen=True, slots=True)
class ExtractionPack:
    id: str
    domains: tuple[str, ...]
    record_selector: str
    fields: dict[str, ExtractionRule]

    @classmethod
    def from_data(cls, data: Any) -> "ExtractionPack":
        if not isinstance(data, dict):
            raise ExtractionPackError("Each extraction pack must be an object")
        unknown = set(data) - {"id", "domains", "record_selector", "fields"}
        if unknown:
            raise ExtractionPackError(
                f"Extraction pack has unknown keys: {', '.join(sorted(unknown))}"
            )
        pack_id = _bounded_text(data.get("id"), label="pack id", limit=MAX_FIELD_CHARS)
        domains_raw = data.get("domains")
        if not isinstance(domains_raw, list) or not domains_raw:
            raise ExtractionPackError(f"Pack {pack_id!r} must declare at least one domain")
        domains = tuple(dict.fromkeys(normalize_pack_domain(value) for value in domains_raw))
        record_selector = _validated_css_selector(
            data.get("record_selector"),
            label=f"record_selector for {pack_id}",
        )
        fields_raw = data.get("fields")
        if not isinstance(fields_raw, dict) or not fields_raw:
            raise ExtractionPackError(f"Pack {pack_id!r} must declare fields")
        unknown_fields = set(fields_raw) - ALLOWED_FIELDS
        if unknown_fields:
            raise ExtractionPackError(
                f"Pack {pack_id!r} declares unknown fields: {', '.join(sorted(unknown_fields))}"
            )
        if not {"full_name", "first_name", "last_name"} & set(fields_raw):
            raise ExtractionPackError(
                f"Pack {pack_id!r} must declare full_name or a first/last name field"
            )
        fields = {
            name: ExtractionRule.from_data(rule, field_name=name)
            for name, rule in fields_raw.items()
        }
        return cls(id=pack_id, domains=domains, record_selector=record_selector, fields=fields)


class ExtractionPackRegistry:
    """Immutable, all-or-nothing registry of validated extraction packs."""

    def __init__(self, packs: Iterable[ExtractionPack] = ()) -> None:
        materialized = tuple(packs)
        if len(materialized) > MAX_PACKS:
            raise ExtractionPackError(f"At most {MAX_PACKS} extraction packs are allowed")
        ids: set[str] = set()
        domains: dict[str, str] = {}
        for pack in materialized:
            if pack.id in ids:
                raise ExtractionPackError(f"Duplicate extraction-pack id: {pack.id}")
            ids.add(pack.id)
            for domain in pack.domains:
                owner = domains.get(domain)
                if owner is not None:
                    raise ExtractionPackError(
                        f"Domain {domain!r} is declared by both {owner!r} and {pack.id!r}"
                    )
                domains[domain] = pack.id
        self._packs = materialized

    @classmethod
    def empty(cls) -> "ExtractionPackRegistry":
        return cls(())

    @classmethod
    def from_data(cls, data: Any) -> "ExtractionPackRegistry":
        if not isinstance(data, dict):
            raise ExtractionPackError("Extraction-pack registry must be a JSON object")
        unknown = set(data) - {"version", "packs"}
        if unknown:
            raise ExtractionPackError(
                f"Extraction-pack registry has unknown keys: {', '.join(sorted(unknown))}"
            )
        version = data.get("version")
        if version != PACK_VERSION:
            raise ExtractionPackError(
                f"Unsupported extraction-pack version {version!r}; expected {PACK_VERSION}"
            )
        raw_packs = data.get("packs")
        if not isinstance(raw_packs, list):
            raise ExtractionPackError("Extraction-pack registry 'packs' must be a list")
        return cls(ExtractionPack.from_data(item) for item in raw_packs)

    @classmethod
    def from_file(
        cls,
        path: Path | str,
        *,
        missing_ok: bool = False,
    ) -> "ExtractionPackRegistry":
        source = Path(path)
        if not source.exists():
            if missing_ok:
                return cls.empty()
            raise ExtractionPackError(f"Extraction-pack file does not exist: {source}")
        try:
            payload = json.loads(source.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise ExtractionPackError(f"Could not read extraction-pack file {source}") from exc
        return cls.from_data(payload)

    def match(self, url: str) -> ExtractionPack | None:
        host = normalize_pack_domain(urlsplit(str(url)).hostname or "")
        matches = [
            (len(domain), pack)
            for pack in self._packs
            for domain in pack.domains
            if _host_matches(host, domain)
        ]
        if not matches:
            return None
        matches.sort(key=lambda item: item[0], reverse=True)
        return matches[0][1]

    def ids(self) -> tuple[str, ...]:
        return tuple(pack.id for pack in self._packs)
