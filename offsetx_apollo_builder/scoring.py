"""Simple explainable scoring for OffsetX POIs."""
from __future__ import annotations

from .categories import COMPETITOR_RISK_TERMS
from .dedupe import norm_text

HIGH_VALUE_TITLE_TERMS = [
    "cbam", "trade compliance", "customs", "export compliance", "carbon", "climate",
    "sustainability", "esg", "corsia", "saf", "article 6", "jcm", "mrv",
    "net zero", "decarbonization", "climate risk", "sustainable finance", "ehs",
]

DECISION_TERMS = ["head", "director", "vp", "partner", "principal", "lead", "manager", "senior"]

REPLY_BONUS_ORGS = ["think tank", "association", "consult", "advisory", "research", "policy"]


def competitor_risk(candidate: dict) -> tuple[str, int, str]:
    blob = norm_text(" ".join(str(candidate.get(k, "")) for k in ["title", "organization_name", "industry", "keywords", "category"]))
    for term in COMPETITOR_RISK_TERMS:
        if term in blob:
            return "Hold", 80, f"competitor-adjacent term: {term}"
    return "Safe", 10, "no direct competitor terms found"


def score_candidate(candidate: dict, category_name: str) -> dict:
    title = norm_text(candidate.get("title"))
    org = norm_text(candidate.get("organization_name"))
    seniority = norm_text(candidate.get("seniority"))
    blob = f"{title} {org} {category_name.lower()}"

    problem = 55 + min(35, sum(8 for term in HIGH_VALUE_TITLE_TERMS if term in blob))
    influence = 45 + min(35, sum(8 for term in DECISION_TERMS if term in title or term in seniority))
    reachability = 70 if candidate.get("has_email") else 45
    if norm_text(candidate.get("email_status")) == "verified" or candidate.get("has_email") is True:
        reachability += 10
    reply = 45 + min(20, sum(5 for term in REPLY_BONUS_ORGS if term in org))
    source_conf = 80 if candidate.get("id") else 65

    risk_level, risk_score, risk_reason = competitor_risk(candidate)
    safety = 100 - risk_score

    scores = [problem, influence, reachability, reply, safety, source_conf]
    overall = round(sum(scores) / len(scores), 1)

    if risk_level == "Hold":
        overall = min(overall, 55)

    return {
        "problem_relevance_score": int(min(problem, 100)),
        "decision_influence_score": int(min(influence, 100)),
        "reachability_score": int(min(reachability, 100)),
        "reply_probability_score": int(min(reply, 100)),
        "non_competitor_safety_score": int(min(safety, 100)),
        "source_confidence_score": int(min(source_conf, 100)),
        "overall_score": overall,
        "risk_level": risk_level,
        "risk_score": risk_score,
        "risk_reason": risk_reason,
    }
