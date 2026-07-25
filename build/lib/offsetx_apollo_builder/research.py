"""Prompt planning and normalized research-graph helpers.

The objective prompt is compiled into bounded, inspectable controls. It is never
executed as browser JavaScript, SQL, a shell command, or an unrestricted agent
instruction. Social interactions enter through official APIs or manual imports;
the public crawler does not log in to social networks.
"""
from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from typing import Any, Iterable
from urllib.parse import urlsplit

from .outreach.models import clean_text


DEFAULT_DISCOVERY_OBJECTIVE = "Find relevant decision-makers from the supplied public pages."

ROLE_GROUPS: dict[str, tuple[str, ...]] = {
    "sales": (
        "sales",
        "business development",
        "account executive",
        "commercial",
        "revenue",
        "partnerships",
    ),
    "sustainability": (
        "sustainability",
        "climate",
        "carbon",
        "esg",
        "environment",
    ),
    "leadership": (
        "founder",
        "chief executive",
        "ceo",
        "president",
        "director",
        "head of",
        "vice president",
        "vp",
    ),
    "marketing": (
        "marketing",
        "growth",
        "content",
        "communications",
        "brand",
    ),
    "procurement": ("procurement", "purchasing", "sourcing", "supply chain"),
}


@dataclass(frozen=True, slots=True)
class DiscoveryPlan:
    objective: str
    target_count: int
    role_groups: tuple[str, ...] = ()
    role_keywords: tuple[str, ...] = ()
    company_mode: str = "supplied_sources"
    collect_social_handles: bool = False
    collect_interactions: bool = False
    source_adapters: tuple[str, ...] = ("public_web",)
    blocked_requirements: tuple[str, ...] = ()
    query_terms: tuple[str, ...] = ()
    safeguards: tuple[str, ...] = (
        "domain_allow_list",
        "robots_txt",
        "ssrf_protection",
        "no_social_login",
        "no_anti_bot_bypass",
    )
    version: int = 1

    def to_dict(self) -> dict[str, Any]:
        result = asdict(self)
        for key, value in list(result.items()):
            if isinstance(value, tuple):
                result[key] = list(value)
        return result


def _target_count(text: str, fallback: int) -> int:
    patterns = (
        r"\b(?:find|identify|discover|research|list)\s+(\d{1,4})\b",
        r"\b(\d{1,4})\s+(?:companies|people|persons|leads|pois|employees|prospects)\b",
    )
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.I)
        if match:
            return max(1, min(1000, int(match.group(1))))
    return max(1, min(1000, int(fallback)))


def _query_terms(text: str) -> tuple[str, ...]:
    stop = {
        "about", "after", "also", "and", "are", "check", "companies", "company",
        "employees", "find", "for", "from", "have", "interacted", "into", "our",
        "people", "person", "social", "team", "their", "them", "that", "the", "to",
        "want", "who", "with",
    }
    words = re.findall(r"[a-z][a-z0-9+.-]{2,}", text.lower())
    return tuple(dict.fromkeys(word for word in words if word not in stop))[:30]


def compile_discovery_plan(
    objective_prompt: str,
    *,
    default_target_count: int = 100,
) -> DiscoveryPlan:
    objective = clean_text(objective_prompt) or DEFAULT_DISCOVERY_OBJECTIVE
    lowered = objective.lower()
    groups: list[str] = []
    keywords: list[str] = []
    for group, terms in ROLE_GROUPS.items():
        if any(term in lowered for term in terms):
            groups.append(group)
            keywords.extend(terms)

    competitor_mode = any(term in lowered for term in ("competitor", "competing", "rival"))
    social_handles = any(
        term in lowered
        for term in ("social media", "social handle", "linkedin", "instagram", "profile handle")
    )
    interactions = any(
        term in lowered
        for term in ("interacted", "interaction", "commented", "liked", "reposted", "engaged")
    )

    adapters = ["public_web"]
    blocked: list[str] = []
    if competitor_mode:
        adapters.append("search_api")
        blocked.append(
            "Competitor expansion needs an operator-configured search API or supplied competitor URLs."
        )
    if social_handles or interactions:
        adapters.append("official_social_api_or_manual_import")
    if interactions:
        blocked.append(
            "Social interaction checks need an approved platform API or a manual evidence import."
        )

    return DiscoveryPlan(
        objective=objective,
        target_count=_target_count(objective, default_target_count),
        role_groups=tuple(groups),
        role_keywords=tuple(dict.fromkeys(keywords)),
        company_mode="competitor_expansion" if competitor_mode else "supplied_sources",
        collect_social_handles=social_handles,
        collect_interactions=interactions,
        source_adapters=tuple(dict.fromkeys(adapters)),
        blocked_requirements=tuple(blocked),
        query_terms=_query_terms(objective),
    )


def objective_match(title: str, company: str, plan: DiscoveryPlan) -> dict[str, Any]:
    """Score a candidate against the plan without silently removing evidence."""
    haystack = f"{clean_text(title)} {clean_text(company)}".lower()
    role_hits = [term for term in plan.role_keywords if term in haystack]
    query_hits = [term for term in plan.query_terms if term in haystack]
    if plan.role_keywords:
        score = min(1.0, 0.2 + 0.6 * min(1.0, len(role_hits) / 2) + 0.2 * min(1.0, len(query_hits) / 3))
    else:
        score = min(1.0, 0.65 + 0.1 * min(3, len(query_hits)))
    return {
        "score": round(score, 2),
        "role_hits": role_hits,
        "query_hits": query_hits,
        "role_match": bool(role_hits) if plan.role_keywords else True,
    }


def social_platform(url: str) -> str:
    host = (urlsplit(clean_text(url)).hostname or "").lower().removeprefix("www.")
    domains = {
        "linkedin.com": "linkedin",
        "instagram.com": "instagram",
        "facebook.com": "facebook",
        "threads.net": "threads",
        "tiktok.com": "tiktok",
        "twitter.com": "x",
        "x.com": "x",
        "youtube.com": "youtube",
        "github.com": "github",
    }
    for domain, platform in domains.items():
        if host == domain or host.endswith("." + domain):
            return platform
    return "web"


def normalized_social_handles(values: Iterable[Any]) -> dict[str, list[str]]:
    result: dict[str, list[str]] = {}
    for value in values:
        url = clean_text(value.get("url") if isinstance(value, dict) else value)
        if not url.startswith(("https://", "http://")):
            continue
        platform = social_platform(url)
        if platform == "web":
            continue
        result.setdefault(platform, [])
        if url not in result[platform]:
            result[platform].append(url)
    return result
