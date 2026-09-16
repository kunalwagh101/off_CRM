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


def test_ci_syncs_locked_python_evidence_dependencies_before_the_verifier():
    text = _workflow()
    install = text.index("name: Install Python dependencies")
    sync = text.index("uv sync --extra dev --extra email --locked", install)
    verifier = text.index("name: Verify the board against the repository")
    assert install < sync < verifier


def test_clean_checkout_docs_prepare_both_evidence_environments_before_verification():
    readme = Path("README.md").read_text(encoding="utf-8")
    readme_sync = readme.index("uv sync --extra dev --extra email --locked")
    readme_npm = readme.index("npm ci --prefix frontend", readme_sync)
    readme_verify = readme.index("uv run python scripts/verify_board.py", readme_npm)
    assert readme_sync < readme_npm < readme_verify

    handoff = Path("CONTINUE.md").read_text(encoding="utf-8")
    handoff_sync = handoff.index("uv sync --extra dev --extra email --locked")
    handoff_npm = handoff.index("npm ci --prefix frontend", handoff_sync)
    handoff_verify = handoff.index("uv run python scripts/verify_board.py", handoff_npm)
    assert handoff_sync < handoff_npm < handoff_verify


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
