"""The tool registry (§4J), and the property that makes it safe.

The property, stated once so every test below can be read against it:

    **A model names a tool that already exists. It cannot describe a new one.**

If a caller could supply an image and a command at run time, the sandbox flags
would be the only thing between a prompt injection and arbitrary code execution.
Flags are a last line. The registry is the first one.
"""
from __future__ import annotations

import ast
import json
import subprocess
from pathlib import Path

import pytest

from offsetx_apollo_builder.ai import DataClass, PolicyViolation
from offsetx_apollo_builder.ai.sandbox import SandboxPolicy, SandboxWorkspace
from offsetx_apollo_builder.ai.tools import (
    MAX_EXTRA_ARGS,
    RegisteredTool,
    ToolError,
    ToolRegistry,
    validate_commit_sha,
    validate_extra_arguments,
    validate_repository_url,
    validate_tool_name,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
PACKAGE_ROOT = REPO_ROOT / "offsetx_apollo_builder"

SHA = "a" * 40
REPO = "https://github.com/kunalwagh101/off_CRM"
IMAGE = "python:3.12-slim"


@pytest.fixture()
def registry(tmp_path) -> ToolRegistry:
    return ToolRegistry(tmp_path / "tools.sqlite3")


def _register(registry: ToolRegistry, **overrides) -> RegisteredTool:
    kwargs = {
        "name": "run-tests",
        "repository_url": REPO,
        "commit_sha": SHA,
        "image": IMAGE,
        "command": ["pytest", "-q"],
        "description": "Runs the project test suite.",
    }
    kwargs.update(overrides)
    return registry.register(**kwargs)


# ── everything must be pinned ──────────────────────────────────────────────


def test_a_branch_or_tag_is_refused_because_names_move():
    for moving in ("main", "v1.0", "HEAD", "a" * 7, "a" * 41):
        with pytest.raises(ToolError, match="40-character commit SHA"):
            validate_commit_sha(moving)


def test_a_full_sha_is_accepted_and_normalised():
    assert validate_commit_sha("  " + "AB" * 20 + " ") == "ab" * 20


def test_only_github_repository_urls_are_accepted():
    assert validate_repository_url(REPO + ".git") == REPO
    for bad in (
        "https://evil.example.com/owner/repo",
        "http://github.com/owner/repo",
        "git@github.com:owner/repo",
        "https://github.com/owner",
        "https://github.com/owner/repo/tree/main",
        "",
    ):
        with pytest.raises(ToolError, match="GitHub repository URL"):
            validate_repository_url(bad)


def test_an_unpinned_image_cannot_be_registered(registry):
    with pytest.raises(ValueError, match="version-pinned"):
        _register(registry, image="python:latest")
    with pytest.raises(ValueError, match="no tag or digest"):
        _register(registry, image="python")


def test_a_tool_name_must_be_a_plain_identifier():
    assert validate_tool_name("  Run-Tests  ") == "run-tests"
    for bad in ("x", "-leading", "has space", "has/slash", "A" * 60, ""):
        with pytest.raises(ToolError, match="usable tool name"):
            validate_tool_name(bad)


def test_an_image_name_cannot_smuggle_docker_flags(registry):
    with pytest.raises(ValueError):
        _register(registry, image="python:3.12 --privileged")


# ── registration is the owner's act ────────────────────────────────────────


def test_a_registered_tool_records_who_pinned_it(registry):
    tool = _register(registry)
    assert tool.registered_by == "owner"
    assert tool.commit_sha == SHA
    assert tool.command == ("pytest", "-q")
    assert tool.enabled is True
    assert tool.allows_arguments is False, "arguments must be opt-in"


def test_two_tools_cannot_share_a_name(registry):
    _register(registry)
    with pytest.raises(ToolError, match="already registered"):
        _register(registry)


def test_a_tool_can_be_disabled_and_removed(registry):
    tool = _register(registry)
    assert registry.set_enabled(tool.id, False) is True
    assert registry.get(tool.id).enabled is False
    assert registry.remove(tool.id) is True
    assert registry.get(tool.id) is None
    assert registry.remove(tool.id) is False


def test_workspaces_do_not_see_each_others_tools(registry):
    _register(registry, workspace_id="alice")
    assert registry.list(workspace_id="alice")
    assert registry.list(workspace_id="bob") == []


# ── what a model may see ───────────────────────────────────────────────────


def test_the_catalogue_withholds_the_recipe(registry):
    """A model choosing a tool needs to know what it does, not how to rebuild
    it. A leaked catalogue must not be a leaked attack surface."""
    _register(registry)
    entry = registry.catalogue()[0]
    assert set(entry) == {"id", "name", "description", "accepts_arguments"}
    blob = json.dumps(registry.catalogue())
    assert IMAGE not in blob
    assert SHA not in blob
    assert REPO not in blob
    assert "pytest" not in blob


def test_a_disabled_tool_is_absent_from_the_catalogue_not_marked(registry):
    """Absent rather than flagged, so a model cannot notice it exists at all."""
    tool = _register(registry)
    registry.set_enabled(tool.id, False)
    assert registry.catalogue() == []
    # The owner still sees it.
    assert len(registry.list()) == 1


def test_the_owner_view_does_carry_the_full_record(registry):
    tool = _register(registry)
    full = tool.to_dict()
    assert full["image"] == IMAGE
    assert full["commit_sha"] == SHA
    assert full["command"] == ["pytest", "-q"]


# ── arguments are opt-in and bounded ───────────────────────────────────────


def test_a_tool_refuses_arguments_unless_it_opted_in(registry):
    tool = _register(registry)
    assert validate_extra_arguments(tool, []) == []
    with pytest.raises(PolicyViolation, match="does not accept arguments"):
        validate_extra_arguments(tool, ["tests/"])


def test_an_opted_in_tool_accepts_bounded_values(registry):
    tool = _register(registry, allows_arguments=True)
    assert validate_extra_arguments(tool, ["tests/", "unit"]) == ["tests/", "unit"]
    with pytest.raises(PolicyViolation, match=f"At most {MAX_EXTRA_ARGS}"):
        validate_extra_arguments(tool, ["x"] * (MAX_EXTRA_ARGS + 1))


def test_extra_arguments_may_not_look_like_flags(registry):
    """Values only. A caller supplying `--network=host` style arguments would be
    changing how the tool behaves, which is what pinning exists to prevent."""
    tool = _register(registry, allows_arguments=True)
    for flag in ("--privileged", "-v", "--network=host"):
        with pytest.raises(PolicyViolation, match="looks like a flag"):
            validate_extra_arguments(tool, [flag])


def test_extra_arguments_inherit_the_command_shape_rules(registry):
    tool = _register(registry, allows_arguments=True)
    with pytest.raises(ValueError, match="null byte"):
        validate_extra_arguments(tool, ["bad\x00value"])


# ── running: a tool_id, never an image and a command ───────────────────────


def test_running_an_unknown_tool_is_refused(registry, tmp_path):
    workspace = SandboxWorkspace(root=tmp_path / "job")
    with pytest.raises(ToolError, match="No tool with id"):
        registry.run("does-not-exist", workspace=workspace)


def test_running_a_disabled_tool_is_refused(registry, tmp_path):
    tool = _register(registry)
    registry.set_enabled(tool.id, False)
    workspace = SandboxWorkspace(root=tmp_path / "job")
    with pytest.raises(PolicyViolation, match="is disabled"):
        registry.run(tool.id, workspace=workspace)


def test_a_non_public_data_class_is_refused_before_anything_starts(registry, tmp_path):
    tool = _register(registry)
    workspace = SandboxWorkspace(root=tmp_path / "job")
    for forbidden in (DataClass.PERSON_PUBLIC, DataClass.CAMPAIGN, DataClass.INTERNAL):
        with pytest.raises(PolicyViolation, match="public work only"):
            registry.run(tool.id, workspace=workspace, data_class=forbidden)


def test_run_builds_the_argv_from_the_pinned_record_not_the_caller(
    registry, tmp_path, monkeypatch
):
    """The heart of it. Whatever a caller passes, the image and the command come
    from the stored registration."""
    tool = _register(registry, allows_arguments=True)
    workspace = SandboxWorkspace(root=tmp_path / "job")
    captured: dict = {}

    monkeypatch.setattr(
        "offsetx_apollo_builder.ai.tools.assert_sandbox_available", lambda: None
    )

    class Completed:
        returncode = 0
        stdout = "ok"
        stderr = ""

    def fake_run(argv, **kwargs):
        captured["argv"] = argv
        return Completed()

    monkeypatch.setattr("offsetx_apollo_builder.ai.tools.subprocess.run", fake_run)

    run = registry.run(
        tool.id,
        workspace=workspace,
        extra_arguments=["tests/"],
        fetch_source=False,
    )
    argv = captured["argv"]
    assert argv[0] == "docker"
    assert "--network=none" in argv
    # The image, then the pinned command, then the caller's value — in that
    # order and nothing else after it.
    assert argv[-4:] == [IMAGE, "pytest", "-q", "tests/"]
    assert run.ok is True
    assert run.argv == ["pytest", "-q", "tests/"]

    # And the decisive one: a caller cannot substitute either half.
    assert argv.count(IMAGE) == 1
    assert "--privileged" not in argv


def test_a_run_is_recorded_with_the_commit_it_ran(registry, tmp_path, monkeypatch):
    """The audit trail must say which commit produced the output, not just which
    tool name."""
    tool = _register(registry)
    workspace = SandboxWorkspace(root=tmp_path / "job")
    monkeypatch.setattr(
        "offsetx_apollo_builder.ai.tools.assert_sandbox_available", lambda: None
    )

    class Completed:
        returncode = 3
        stdout = "some output"
        stderr = "some error"

    monkeypatch.setattr(
        "offsetx_apollo_builder.ai.tools.subprocess.run", lambda argv, **k: Completed()
    )
    registry.run(tool.id, workspace=workspace, fetch_source=False)

    rows = registry.runs()
    assert len(rows) == 1
    assert rows[0]["commit_sha"] == SHA
    assert rows[0]["image"] == IMAGE
    assert rows[0]["exit_code"] == 3
    assert registry.stats()["runs"] == 1


def test_a_timeout_is_recorded_rather_than_raised(registry, tmp_path, monkeypatch):
    tool = _register(registry)
    workspace = SandboxWorkspace(root=tmp_path / "job")
    monkeypatch.setattr(
        "offsetx_apollo_builder.ai.tools.assert_sandbox_available", lambda: None
    )

    def timeout(argv, **kwargs):
        raise subprocess.TimeoutExpired(cmd=argv, timeout=1)

    monkeypatch.setattr("offsetx_apollo_builder.ai.tools.subprocess.run", timeout)
    run = registry.run(
        tool.id, workspace=workspace, fetch_source=False, timeout_seconds=1
    )
    assert run.status == "timeout"
    assert run.ok is False
    assert registry.runs()[0]["status"] == "timeout"


def test_the_disk_budget_is_checked_before_running(registry, tmp_path, monkeypatch):
    tool = _register(registry)
    workspace = SandboxWorkspace(root=tmp_path / "job", max_bytes=100).prepare()
    (workspace.work / "big.bin").write_bytes(b"x" * 5000)
    monkeypatch.setattr(
        "offsetx_apollo_builder.ai.tools.assert_sandbox_available", lambda: None
    )
    with pytest.raises(PolicyViolation, match="over the"):
        registry.run(tool.id, workspace=workspace, fetch_source=False)


# ── source integrity ───────────────────────────────────────────────────────


def test_the_fetched_commit_must_match_the_pinned_one(registry, tmp_path, monkeypatch):
    """The whole value of pinning is that this is checked rather than assumed."""
    tool = _register(registry)
    monkeypatch.setattr(
        "offsetx_apollo_builder.ai.tools.shutil.which", lambda name: "/usr/bin/git"
    )

    class Ok:
        returncode = 0
        stdout = "b" * 40  # a different commit than the pinned one
        stderr = ""

    monkeypatch.setattr(
        "offsetx_apollo_builder.ai.tools.subprocess.run", lambda *a, **k: Ok()
    )
    with pytest.raises(ToolError, match="Integrity check failed"):
        registry.prepare_source(tool, tmp_path / "src")


def test_a_fetch_failure_names_the_repository_and_runs_nothing(
    registry, tmp_path, monkeypatch
):
    tool = _register(registry)
    monkeypatch.setattr(
        "offsetx_apollo_builder.ai.tools.shutil.which", lambda name: "/usr/bin/git"
    )

    def explode(argv, **kwargs):
        raise subprocess.CalledProcessError(
            returncode=128, cmd=argv, stderr=b"fatal: could not read from remote"
        )

    monkeypatch.setattr("offsetx_apollo_builder.ai.tools.subprocess.run", explode)
    with pytest.raises(ToolError, match="Could not fetch"):
        registry.prepare_source(tool, tmp_path / "src")


def test_missing_git_is_reported_rather_than_silently_skipped(
    registry, tmp_path, monkeypatch
):
    tool = _register(registry)
    monkeypatch.setattr(
        "offsetx_apollo_builder.ai.tools.shutil.which", lambda name: None
    )
    with pytest.raises(ToolError, match="git is not installed"):
        registry.prepare_source(tool, tmp_path / "src")


def test_source_is_fetched_into_the_read_only_inbox(registry, tmp_path, monkeypatch):
    """It lands in inbox/, which the container mounts read-only, so a tool
    cannot rewrite its own source mid-run."""
    tool = _register(registry)
    workspace = SandboxWorkspace(root=tmp_path / "job")
    monkeypatch.setattr(
        "offsetx_apollo_builder.ai.tools.assert_sandbox_available", lambda: None
    )
    seen: dict = {}

    def fake_prepare(self, tool_arg, destination):
        seen["destination"] = destination
        return destination

    monkeypatch.setattr(ToolRegistry, "prepare_source", fake_prepare)

    class Completed:
        returncode = 0
        stdout = ""
        stderr = ""

    monkeypatch.setattr(
        "offsetx_apollo_builder.ai.tools.subprocess.run", lambda *a, **k: Completed()
    )
    registry.run(tool.id, workspace=workspace, fetch_source=True)
    assert seen["destination"] == workspace.inbox / "source"
    assert workspace.inbox in seen["destination"].parents


# ── structural: no model path to registration ──────────────────────────────


def test_the_registry_exposes_no_way_for_a_model_to_register_a_tool():
    """`register` is the owner's act. It must not be reachable from anything a
    provider can influence — no tool schema, no function-calling surface."""
    source = (PACKAGE_ROOT / "ai" / "tools.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module)
            imported.update(f"{node.module}.{alias.name}" for alias in node.names)
        elif isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
    banned = {"requests", "httpx", "openai", "socket"}
    assert not (imported & banned), f"tools.py imports transport: {imported & banned}"
    assert not any("create_provider" in name for name in imported)


def test_run_takes_a_tool_id_and_never_an_image_or_command():
    """Signature-level guarantee. If `run` ever grows an `image=` or `command=`
    parameter, the registry has stopped being a registry."""
    import inspect

    parameters = set(inspect.signature(ToolRegistry.run).parameters)
    assert "tool_id" in parameters
    for forbidden in ("image", "command", "argv", "docker_command", "entrypoint"):
        assert forbidden not in parameters, (
            f"ToolRegistry.run accepts {forbidden!r}, which lets a caller "
            "describe a new tool instead of naming a registered one"
        )


def test_the_catalogue_returns_plain_data_not_callables(registry):
    """A catalogue entry must be inert. Anything callable in it would be a way
    for a model-facing surface to invoke something directly."""
    _register(registry)
    for entry in registry.catalogue():
        for value in entry.values():
            assert isinstance(value, (str, bool, int)), type(value)
