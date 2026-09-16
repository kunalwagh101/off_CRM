"""Regression checks for the CI environment the repository verifier depends on.

S-06.02.15 exists because the verifier's own logic was correct while CI gave it
an intentionally incomplete checkout and ran it before frontend evidence could
execute. These tests pin the workflow ordering so that defect cannot quietly
return.
"""
from pathlib import Path


CI = Path(".github/workflows/ci.yml")


def _workflow() -> str:
    return CI.read_text(encoding="utf-8")


def test_ci_fetches_history_needed_for_evidence_commit_ancestry():
    text = _workflow()
    checkout = text.index("uses: actions/checkout@v4")
    fetch_all = text.index("fetch-depth: 0", checkout)
    verifier = text.index("Verify the board against the repository")
    assert checkout < fetch_all < verifier


def test_ci_installs_frontend_evidence_dependencies_before_the_verifier():
    text = _workflow()
    install = text.index("name: Install frontend dependencies")
    npm_ci = text.index("run: npm ci", install)
    verifier = text.index("name: Verify the board against the repository")
    assert install < npm_ci < verifier
