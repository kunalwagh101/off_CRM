"""The package's supported interpreters must each execute the regression suite."""
from pathlib import Path
import re

try:
    import tomllib
except ModuleNotFoundError:
    import tomli as tomllib

import yaml


ROOT = Path(__file__).resolve().parents[1]


def test_ci_executes_the_suite_on_each_declared_python_and_the_container_python():
    project = tomllib.loads((ROOT / "pyproject.toml").read_text())["project"]
    declared = {
        item.rsplit(" :: ", 1)[-1]
        for item in project["classifiers"]
        if re.fullmatch(r"Programming Language :: Python :: 3\.\d+", item)
    }
    docker_versions = set(re.findall(
        r"^FROM python:(3\.\d+)", (ROOT / "Dockerfile").read_text(), re.MULTILINE,
    ))
    workflow = yaml.safe_load((ROOT / ".github/workflows/ci.yml").read_text())
    covered = set()
    for job in workflow["jobs"].values():
        versions = job.get("strategy", {}).get("matrix", {}).get("python-version", [])
        if not versions:
            continue
        assert not job.get("continue-on-error", False), "A failed version must fail CI"
        assert job["strategy"].get("fail-fast") is False, "Collect evidence for every version"
        commands = "\n".join(step.get("run", "") for step in job["steps"])
        assert "uv run pytest -q" in commands
        assert "uv sync --python ${{ matrix.python-version }}" in commands
        assert "--locked" in commands
        covered.update(str(version) for version in versions)
    assert declared | docker_versions <= covered, (
        f"Declared/container Python versions {sorted(declared | docker_versions)} "
        f"are not all tested by CI: {sorted(covered)}"
    )


def test_ci_pytest_gates_cannot_exit_after_printing_a_version():
    workflow = yaml.safe_load((ROOT / '.github/workflows/ci.yml').read_text())
    for job in workflow['jobs'].values():
        for step in job['steps']:
            for line in step.get('run', '').splitlines():
                if 'uv run pytest' in line:
                    assert '--version' not in line, 'A pytest gate must execute tests, not just print a version'
