"""Locked OffsetX stakeholder categories.

Keep this file boring and explicit. These names are used in exports,
analytics, outreach templates, and future CRM records. Do not add ad-hoc
categories in feature code.
"""
from __future__ import annotations

LOCKED_CATEGORIES: tuple[str, ...] = (
    "CBAM / Trade Compliance",
    "Carbon Markets / Article 6 / CORSIA",
    "Sustainability / ESG / Climate",
    "Aviation / SAF / CORSIA",
    "Buyers / Importers / Exporters",
    "Consultants / Advisors",
    "Policy / Government / Think Tanks",
    "Verification / Audit / MRV",
    "Finance / Insurance / Risk",
)

DEFAULT_CATEGORY = "Sustainability / ESG / Climate"

_CATEGORY_ALIASES: dict[str, str] = {
    "cbam": "CBAM / Trade Compliance",
    "trade": "CBAM / Trade Compliance",
    "trade compliance": "CBAM / Trade Compliance",
    "customs": "CBAM / Trade Compliance",
    "carbon markets": "Carbon Markets / Article 6 / CORSIA",
    "carbon market": "Carbon Markets / Article 6 / CORSIA",
    "article 6": "Carbon Markets / Article 6 / CORSIA",
    "corsia": "Carbon Markets / Article 6 / CORSIA",
    "carbon credits": "Carbon Markets / Article 6 / CORSIA",
    "carbon credits / project developers / buyers": "Carbon Markets / Article 6 / CORSIA",
    "sustainability": "Sustainability / ESG / Climate",
    "esg": "Sustainability / ESG / Climate",
    "climate": "Sustainability / ESG / Climate",
    "sustainability / esg / carbon reporting": "Sustainability / ESG / Climate",
    "aviation": "Aviation / SAF / CORSIA",
    "saf": "Aviation / SAF / CORSIA",
    "aviation / corsia / saf": "Aviation / SAF / CORSIA",
    "buyers": "Buyers / Importers / Exporters",
    "importers": "Buyers / Importers / Exporters",
    "exporters": "Buyers / Importers / Exporters",
    "indian exporters / manufacturing / ccts readiness": "Buyers / Importers / Exporters",
    "consultants": "Consultants / Advisors",
    "advisors": "Consultants / Advisors",
    "consultants / advisors": "Consultants / Advisors",
    "policy": "Policy / Government / Think Tanks",
    "government": "Policy / Government / Think Tanks",
    "think tanks": "Policy / Government / Think Tanks",
    "policy / think tanks / industry associations": "Policy / Government / Think Tanks",
    "verification": "Verification / Audit / MRV",
    "audit": "Verification / Audit / MRV",
    "mrv": "Verification / Audit / MRV",
    "finance": "Finance / Insurance / Risk",
    "insurance": "Finance / Insurance / Risk",
    "risk": "Finance / Insurance / Risk",
    "banks / insurance / trade finance / climate risk": "Finance / Insurance / Risk",
}


def normalize_category(value: object, *, default: str = DEFAULT_CATEGORY) -> str:
    """Map messy input category text into one locked category."""
    text = "" if value is None else str(value).strip()
    if not text or text.lower() == "nan":
        return default

    if text in LOCKED_CATEGORIES:
        return text

    lowered = " ".join(text.lower().replace("&", "and").split())
    if lowered in _CATEGORY_ALIASES:
        return _CATEGORY_ALIASES[lowered]

    # Substring fallback. This intentionally maps into the locked list only.
    for needle, category in _CATEGORY_ALIASES.items():
        if needle in lowered:
            return category

    return default


def is_locked_category(value: object) -> bool:
    return str(value).strip() in LOCKED_CATEGORIES
