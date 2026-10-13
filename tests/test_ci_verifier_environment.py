"""Regression checks for the CI environment the repository verifier depends on.

S-06.02.15 exists because the verifier's own logic was correct while CI gave it
an intentionally incomplete checkout and ran it before frontend evidence could
execute. These tests pin the workflow ordering so that defect cannot quietly
return.
"""
from pathlib import Path

import yaml


CI = Path(".github/workflows/ci.yml")


def _workflow() -> str:
    return CI.read_text(encoding="utf-8")


def test_ci_syncs_locked_python_evidence_dependencies_before_the_verifier():
    text = _workflow()
    install = text.index("name: Install Python dependencies")
    sync = text.index("uv sync --extra dev --extra email --extra postgres --locked", install)
    verifier = text.index("name: Verify the board against the repository")
    assert install < sync < verifier


def test_clean_checkout_docs_prepare_both_evidence_environments_before_verification():
    readme = Path("README.md").read_text(encoding="utf-8")
    readme_sync = readme.index("uv sync --extra dev --extra email --extra postgres --locked")
    readme_npm = readme.index("npm ci --prefix frontend", readme_sync)
    readme_verify = readme.index("uv run python scripts/verify_board.py", readme_npm)
    assert readme_sync < readme_npm < readme_verify

    handoff = Path("CONTINUE.md").read_text(encoding="utf-8")
    handoff_sync = handoff.index("uv sync --extra dev --extra email --extra postgres --locked")
    handoff_npm = handoff.index("npm ci --prefix frontend", handoff_sync)
    handoff_verify = handoff.index("uv run python scripts/verify_board.py", handoff_npm)
    assert handoff_sync < handoff_npm < handoff_verify


def test_ci_fetches_history_needed_for_evidence_commit_ancestry():
    """S-06.02.20: no job may silently default to depth-1 checkout."""
    workflow = yaml.safe_load(_workflow())
    for name, job in workflow["jobs"].items():
        checkouts = [
            step for step in job["steps"]
            if str(step.get("uses", "")).startswith("actions/checkout@")
        ]
        assert checkouts, f"{name} has no checkout"
        for step in checkouts:
            assert step.get("with", {}).get("fetch-depth") == 0, (
                f"{name}: commit-ancestry verification needs full history"
            )


def test_ci_installs_frontend_evidence_dependencies_before_the_verifier():
    text = _workflow()
    install = text.index("name: Install frontend dependencies")
    npm_ci = text.index("run: npm ci", install)
    verifier = text.index("name: Verify the board against the repository")
    assert install < npm_ci < verifier


def test_frontend_production_and_dev_vulnerabilities_are_hard_ci_gates():
    workflow = yaml.safe_load(_workflow())
    steps = workflow["jobs"]["quality"]["steps"]
    names = [str(step.get("name", "")) for step in steps]
    install = names.index("Install frontend dependencies")
    production = names.index("Audit frontend production dependencies")
    development = names.index("Audit frontend development dependencies")
    build = names.index("Build frontend")
    assert install < production < development < build
    assert steps[production]["working-directory"] == "frontend"
    assert steps[production]["run"] == "npm audit --omit=dev --audit-level=low"
    assert steps[development]["working-directory"] == "frontend"
    assert steps[development]["run"] == "npm audit --audit-level=high"
    for step in (steps[production], steps[development]):
        assert not step.get("continue-on-error", False)
        assert "|| true" not in step["run"]
