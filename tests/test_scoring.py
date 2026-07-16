from offsetx_apollo_builder.scoring import score_candidate


def test_trade_compliance_scores_high():
    s = score_candidate({"title": "Global Trade Compliance Manager", "organization_name": "Exporter Co", "has_email": True}, "CBAM / Trade Compliance")
    assert s["problem_relevance_score"] >= 70
    assert s["reachability_score"] >= 80
    assert s["risk_level"] == "Safe"


def test_competitor_hold():
    s = score_candidate({"title": "Founder", "organization_name": "MRV Software Platform", "has_email": True}, "Sustainability")
    assert s["risk_level"] == "Hold"
    assert s["overall_score"] <= 55
