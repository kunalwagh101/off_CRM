"""A33: run the same real-browser QA as an importable module in both hosts.

D-514: executing the file by path removed the repo root from sys.path on CI.
The live CI failure is the TDD RED; a passing static test does not replace
the real browser check.
"""
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_a33_qa_is_importable_from_both_ci_and_render() -> None:
    ci = (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")
    render = (ROOT / "Dockerfile.review").read_text(encoding="utf-8")
    assert "run: uv run python -m scripts.qa.a33_campaign_browser" in ci
    assert "RUN uv run --no-sync python -m scripts.qa.a33_campaign_browser" in render
    assert "python scripts/qa/a33_campaign_browser.py" not in ci
    assert "python scripts/qa/a33_campaign_browser.py" not in render
