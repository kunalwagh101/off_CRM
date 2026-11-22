"""A30: active operator instructions must not confuse an isolated demo with a safe release.

This test guards live documentation; it does not establish that a production
database, offsite backup, worker or tenant boundary is actually deployed.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BRANCHING = ROOT / "docs" / "BRANCHING.md"


def _active_runbook() -> str:
    content = BRANCHING.read_text(encoding="utf-8")
    # Historical branch consolidation notes below this section are immutable
    # provenance, not a deployment recommendation.
    return content.split("## What happened to every branch", 1)[0]


def test_A30_active_runbook_does_not_claim_github_ci_has_no_runners():
    text = _active_runbook()
    assert "CI cannot start a runner on this repository today" not in text
    assert "GitHub CI" in text


def test_A30_disk_example_cannot_be_mistaken_for_complete_production_storage():
    text = _active_runbook()
    assert "### Historical single-disk example (not a production release recipe)" in text
    section = text.split("### Historical single-disk example (not a production release recipe)", 1)[1]
    assert "not sufficient" in section.lower()
    for required in ("dedicated PostgreSQL", "independent encrypted backup", "object storage", "durable worker", "recovery drill"):
        assert required.lower() in section.lower(), required


def test_A30_ephemeral_state_warning_does_not_equate_push_with_data_loss():
    text = _active_runbook().lower()
    assert "nothing typed into either survives the next push" not in text
    assert "restart or redeploy" in text
