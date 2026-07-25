"""off_CRM Apollo search plans mapped exactly to the nine locked CRM categories."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .locked_categories import LOCKED_CATEGORIES

TARGET_COUNTRIES = [
    "India",
    "Germany",
    "Netherlands",
    "France",
    "United Kingdom",
    "Japan",
    "Singapore",
    "United Arab Emirates",
    "Australia",
    "Belgium",
    "Italy",
    "Spain",
    "Switzerland",
]

SENIORITIES = ["manager", "senior", "head", "director", "vp", "partner", "c_suite"]

COMPETITOR_RISK_TERMS = [
    "carbon registry",
    "registry platform",
    "mrv software",
    "carbon accounting software",
    "carbon data platform",
    "carbon credit marketplace",
    "offset marketplace",
    "climate software",
    "emissions management software",
    "esg software",
    "carbon management platform",
]


@dataclass(frozen=True)
class SearchCategory:
    name: str
    person_titles: list[str]
    keywords: str | None = None
    person_locations: list[str] | None = None
    organization_locations: list[str] | None = None
    max_accept: int = 40
    weight: int = 1

    def payload(self, page: int, per_page: int) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "page": page,
            "per_page": per_page,
            "person_titles": self.person_titles,
            "person_seniorities": SENIORITIES,
            "contact_email_status": ["verified"],
            "include_similar_titles": True,
        }
        # q_keywords is deliberately not sent. Combining it with title,
        # seniority, verified-email and location filters made Apollo too narrow.
        if self.person_locations:
            payload["person_locations"] = self.person_locations
        if self.organization_locations:
            payload["organization_locations"] = self.organization_locations
        elif "person_locations" not in payload:
            payload["person_locations"] = TARGET_COUNTRIES
        return payload


CATEGORIES: list[SearchCategory] = [
    SearchCategory(
        name="CBAM / Trade Compliance",
        person_titles=[
            "CBAM manager", "trade compliance manager", "global trade compliance manager",
            "customs compliance manager", "export compliance manager", "customs manager",
            "trade compliance lead", "head of trade compliance",
        ],
        keywords="CBAM customs trade compliance export import embedded emissions",
        max_accept=40,
    ),
    SearchCategory(
        name="Carbon Markets / Article 6 / CORSIA",
        person_titles=[
            "carbon markets manager", "article 6 lead", "carbon procurement manager",
            "carbon offsets manager", "carbon project manager", "climate finance manager",
            "head of carbon markets", "VP carbon markets",
        ],
        keywords="carbon markets Article 6 CORSIA credits offsets project development",
        max_accept=35,
    ),
    SearchCategory(
        name="Sustainability / ESG / Climate",
        person_titles=[
            "sustainability manager", "ESG manager", "climate manager", "net zero manager",
            "carbon accounting manager", "sustainability lead", "head of sustainability",
            "chief sustainability officer",
        ],
        keywords="sustainability ESG climate reporting net zero emissions",
        max_accept=40,
    ),
    SearchCategory(
        name="Aviation / SAF / CORSIA",
        person_titles=[
            "aviation sustainability manager", "SAF manager", "CORSIA manager",
            "airport sustainability manager", "airline sustainability manager",
            "fuel sustainability manager", "head of aviation sustainability",
        ],
        keywords="aviation SAF CORSIA airline airport emissions",
        max_accept=25,
    ),
    SearchCategory(
        name="Buyers / Importers / Exporters",
        person_titles=[
            "carbon buyer", "carbon procurement manager", "import manager", "export manager",
            "trade compliance manager", "supply chain sustainability manager",
            "procurement sustainability manager", "head of exports",
        ],
        keywords="buyers importers exporters carbon procurement CBAM CCTS",
        max_accept=35,
    ),
    SearchCategory(
        name="Consultants / Advisors",
        person_titles=[
            "carbon markets consultant", "CBAM consultant", "sustainability consultant",
            "climate advisor", "ESG advisor", "decarbonization consultant",
            "partner sustainability", "principal climate advisory",
        ],
        keywords="CBAM carbon markets sustainability climate advisory consulting",
        max_accept=25,
    ),
    SearchCategory(
        name="Policy / Government / Think Tanks",
        person_titles=[
            "climate policy lead", "carbon markets policy lead", "research fellow",
            "senior research analyst", "director climate policy", "programme lead climate",
            "government affairs climate", "industry association director",
        ],
        keywords="CBAM CCTS Article 6 carbon policy government think tank association",
        max_accept=25,
    ),
    SearchCategory(
        name="Verification / Audit / MRV",
        person_titles=[
            "MRV manager", "carbon verification manager", "GHG verification lead",
            "environmental auditor", "assurance director", "carbon assurance manager",
            "validation verification manager", "head of climate assurance",
        ],
        keywords="MRV verification audit assurance GHG validation carbon",
        max_accept=25,
    ),
    SearchCategory(
        name="Finance / Insurance / Risk",
        person_titles=[
            "climate risk manager", "sustainable finance manager", "ESG risk manager",
            "trade finance manager", "carbon finance manager", "insurance sustainability manager",
            "head of climate risk", "environmental markets risk manager",
        ],
        keywords="climate risk sustainable finance insurance trade finance carbon price risk",
        max_accept=25,
    ),
]

if tuple(category.name for category in CATEGORIES) != LOCKED_CATEGORIES:
    raise RuntimeError("Apollo search categories must exactly match LOCKED_CATEGORIES and preserve their order.")
