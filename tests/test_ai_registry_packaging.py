"""Deployment safety for the provider registry.

The registry is the one file the whole AI module depends on. A deploy that
cannot find it, or finds a stale copy, has no working AI at all — so these
checks exist to fail the build rather than fail in production.
"""
from __future__ import annotations

import tomllib
from pathlib import Path

import pytest

from offsetx_apollo_builder.ai.registry import (
    PACKAGED_REGISTRY_PATH,
    SOURCE_REGISTRY_PATH,
    ProviderRegistry,
    default_registry_path,
)

REPO_ROOT = Path(__file__).resolve().parents[1]


def test_the_editable_registry_and_the_packaged_copy_do_not_drift():
    """``config/providers.yaml`` is the file humans edit. The copy inside the
    package is what a pip-installed deploy reads. If they differ, a server would
    silently run different trust rules to a laptop.

    To fix a failure here: copy config/providers.yaml over
    offsetx_apollo_builder/ai/providers.yaml.
    """
    assert SOURCE_REGISTRY_PATH.exists(), "config/providers.yaml is missing"
    assert PACKAGED_REGISTRY_PATH.exists(), "packaged providers.yaml is missing"
    assert SOURCE_REGISTRY_PATH.read_text(encoding="utf-8") == PACKAGED_REGISTRY_PATH.read_text(
        encoding="utf-8"
    ), (
        "config/providers.yaml and offsetx_apollo_builder/ai/providers.yaml have "
        "drifted. Copy the config one over the packaged one."
    )


def test_pyyaml_is_a_real_install_dependency():
    """The Docker image builds with `pip install .`, which reads pyproject.toml
    and ignores requirements.txt. PyYAML being listed only in requirements.txt
    would break every deployed build while every local test still passed.
    """
    payload = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    dependencies = [item.lower() for item in payload["project"]["dependencies"]]
    assert any(item.startswith("pyyaml") for item in dependencies), (
        "PyYAML must be in pyproject.toml dependencies, not only requirements.txt"
    )


def test_every_requirement_needed_at_runtime_is_also_in_pyproject():
    """Guards the same gap generally: anything imported at runtime has to be
    installable by the Docker build."""
    payload = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    installed = {
        item.split(">=")[0].split("==")[0].split("[")[0].strip().lower()
        for item in payload["project"]["dependencies"]
    }
    requirements = (REPO_ROOT / "requirements.txt").read_text(encoding="utf-8").splitlines()
    runtime_only = {"pytest"}  # dev tooling lives in the optional extra
    missing = []
    for line in requirements:
        name = line.split(">=")[0].split("==")[0].split("[")[0].strip().lower()
        if not name or name.startswith("#") or name in runtime_only:
            continue
        if name not in installed:
            missing.append(name)
    assert not missing, (
        "These are in requirements.txt but not pyproject.toml, so the Docker "
        f"build would not install them: {', '.join(sorted(missing))}"
    )


def test_registry_resolves_without_a_source_tree(tmp_path, monkeypatch):
    """A deployed container runs from a working directory with no config/ dir.
    The packaged copy has to carry it."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("OFFSETX_PROVIDER_REGISTRY", raising=False)
    resolved = default_registry_path()
    assert resolved.exists()
    assert ProviderRegistry(resolved).all()


def test_environment_override_wins(tmp_path, monkeypatch):
    """On a server the registry can be mounted anywhere."""
    custom = tmp_path / "custom.yaml"
    custom.write_text(SOURCE_REGISTRY_PATH.read_text(encoding="utf-8"), encoding="utf-8")
    monkeypatch.setenv("OFFSETX_PROVIDER_REGISTRY", str(custom))
    assert default_registry_path() == custom


def test_a_missing_registry_fails_with_a_readable_message(tmp_path):
    registry = ProviderRegistry(tmp_path / "nope.yaml")
    with pytest.raises(Exception) as excinfo:
        registry.all()
    assert "not readable" in str(excinfo.value) or "not found" in str(excinfo.value)


def test_render_blueprint_deploys_the_default_branch():
    """render.yaml pins a branch. If that branch is not the repository default,
    merged work would never reach the deployment."""
    text = (REPO_ROOT / "render.yaml").read_text(encoding="utf-8")
    assert "branch: main" in text
    assert "healthCheckPath: /health/ready" in text
