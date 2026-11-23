"""A06: failed revocation must not show sign-out as completed."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_logout_failure_preserves_authenticated_ui_and_retry():
    src = (ROOT / "frontend/src/App.tsx").read_text()
    part = src.split("  async function logout() {", 1)[1].split("\n  if (error)", 1)[0]
    assert "catch {" in part
    assert "session may still be active" in part
    assert part.index("return;") < part.index('setToken("")')
    assert "finally" not in part
    assert 'role="alert"' in src
    assert "logoutError={logoutError}" in src


def test_mandatory_disposable_chromium_auth_gate():
    ci = (ROOT / ".github/workflows/ci.yml").read_text()
    script = (ROOT / "scripts/qa/a06_logout_browser.py").read_text()
    assert "uv run python -m scripts.qa.a06_logout_browser" in ci
    assert ci.index("name: Build frontend") < ci.index(
        "name: A06 real Chromium logout revocation and replay"
    ) < ci.index("name: Verify the board against the repository")
    assert "TemporaryDirectory" in script
    assert "child_environment" in script
    assert 'host="127.0.0.1"' in script
    assert "SESSION_COOKIE" in script
