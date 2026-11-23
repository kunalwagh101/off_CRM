"""S-06.02.16: a vulnerable frontend dependency rollback must fail closed."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.qa.s16_frontend_lock_recovery import (
    _locked_vitest,
    allowed_vitest_version,
)


def _fixture(version: str = "4.1.12") -> tuple[dict, dict]:
    manifest = {"devDependencies": {"vitest": version}}
    lock = {"packages": {
        "": {"devDependencies": {"vitest": version}},
        "node_modules/@vitest/mocker": {"version": version},
    }}
    return manifest, lock


def test_old_known_vulnerable_vitest_fails_closed() -> None:
    assert not allowed_vitest_version("4.1.11")


def test_patched_and_newer_releases_are_allowed() -> None:
    assert allowed_vitest_version("4.1.12")
    assert allowed_vitest_version("4.2.0")


@pytest.mark.parametrize("bad", ["4.1", "4.1.11-rc", "", "4.one.12"])
def test_invalid_versions_fail_closed(bad: str) -> None:
    assert not allowed_vitest_version(bad)


def test_pair_accepts_secure_exact_pin() -> None:
    pkg, lock = _fixture()
    assert _locked_vitest(
        json.dumps(pkg).encode(), json.dumps(lock).encode()
    ) == "4.1.12"


def test_pair_refuses_unsafe_older_pin() -> None:
    pkg, lock = _fixture("4.1.11")
    with pytest.raises(ValueError, match="known-unsafe"):
        _locked_vitest(json.dumps(pkg).encode(), json.dumps(lock).encode())


def test_pair_refuses_different_lock_version() -> None:
    pkg, lock = _fixture()
    lock["packages"][""]["devDependencies"]["vitest"] = "4.1.11"
    with pytest.raises(ValueError, match="inconsistent"):
        _locked_vitest(json.dumps(pkg).encode(), json.dumps(lock).encode())


def test_pair_refuses_vulnerable_transitive_mocker() -> None:
    pkg, lock = _fixture()
    lock["packages"]["node_modules/@vitest/mocker"]["version"] = "4.1.11"
    with pytest.raises(ValueError, match="mocker"):
        _locked_vitest(json.dumps(pkg).encode(), json.dumps(lock).encode())


def test_quality_gate_runs_disposable_recovery_after_npm_audits() -> None:
    ci = (Path(__file__).resolve().parents[1] / ".github/workflows/ci.yml").read_text()
    production = ci.index("name: Audit frontend production dependencies")
    development = ci.index("name: Audit frontend development dependencies")
    recovery = ci.index("name: Verify safe frontend dependency rollback and recovery")
    build = ci.index("name: Build frontend")
    assert production < development < recovery < build
    assert "run: uv run python -m scripts.qa.s16_frontend_lock_recovery" in ci


def test_npm_failure_never_escapes_secret_in_process_output(monkeypatch, tmp_path) -> None:
    """D-517: npm stderr must not leak a private registry credential in CI."""
    from subprocess import CompletedProcess
    import scripts.qa.s16_frontend_lock_recovery as recovery

    canary = "npm-private-registry-key-should-not-be-logged"

    def fake_run(*args, **kwargs):
        return CompletedProcess(args[0], 1, stdout=canary, stderr=canary)

    monkeypatch.setattr(recovery.subprocess, "run", fake_run)
    with pytest.raises(RuntimeError) as exc:
        recovery._run(["npm", "ci"], tmp_path, timeout=10)
    assert canary not in str(exc.value)
    assert "npm ci failed" in str(exc.value)
