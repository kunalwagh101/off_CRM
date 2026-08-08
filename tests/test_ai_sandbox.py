"""The sandbox (§4J), and the §5.12(c) acceptance case.

§5.12(c) is *sandboxed code cannot reach an arbitrary external host*. Until now
`test_ai_egress_wall.py` said honestly in its own docstring that it could not
cover this, because the sandbox did not exist.

It is covered two ways here:

* **Composition** — the command is asserted to carry `--network=none` and the
  rest of the isolation flags. Runs everywhere, including CI with no Docker.
* **Live** — a container is actually started and told to open a socket. Skips
  unless a pre-pulled image is supplied, because `--pull=never` means the test
  cannot fetch one, and a test that silently downloads an image from the
  internet would be a strange thing to find inside a network-isolation suite.

Set `OFF_CRM_SANDBOX_TEST_IMAGE` to a pinned local Python image to run it.
"""
from __future__ import annotations

import ast
import os
import shutil
import subprocess
from pathlib import Path

import pytest

from offsetx_apollo_builder.ai import DataClass, PolicyViolation
from offsetx_apollo_builder.ai.sandbox import (
    DEFAULT_WORKSPACE_BYTES,
    MAX_ARGUMENT_LENGTH,
    MAX_COMMAND_PARTS,
    SandboxPolicy,
    SandboxUnavailable,
    SandboxWorkspace,
    assert_public,
    assert_sandbox_available,
    sandbox_available,
    validate_command,
    validate_image,
    workspace_usage,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
PACKAGE_ROOT = REPO_ROOT / "offsetx_apollo_builder"

PINNED = "python:3.12-slim"


@pytest.fixture()
def workspace(tmp_path) -> SandboxWorkspace:
    return SandboxWorkspace(root=tmp_path / "job").prepare()


# ── §5.12(c), part one: the command composition ────────────────────────────


def test_the_container_has_no_network(workspace):
    """The single most important flag. Everything else is depth."""
    command = SandboxPolicy().docker_command(
        image=PINNED, command=["python", "-c", "print(1)"], workspace=workspace
    )
    assert "--network=none" in command


@pytest.mark.parametrize(
    "flag",
    [
        "--rm",
        "--pull=never",
        "--network=none",
        "--read-only",
        "--cap-drop=ALL",
        "--security-opt=no-new-privileges",
        "--user=65534:65534",
    ],
)
def test_every_isolation_flag_is_present(workspace, flag):
    command = SandboxPolicy().docker_command(
        image=PINNED, command=["true"], workspace=workspace
    )
    assert flag in command, f"{flag} went missing from the sandbox invocation"


def test_resource_caps_are_applied(workspace):
    command = SandboxPolicy().docker_command(
        image=PINNED, command=["true"], workspace=workspace
    )
    joined = " ".join(command)
    assert "--memory=512m" in joined
    assert "--cpus=1" in joined
    assert "--pids-limit=128" in joined


def test_the_memory_cap_cannot_be_escaped_through_swap(workspace):
    """--memory alone is advisory: a container can exceed it by swapping. The
    salvaged original omitted this."""
    command = SandboxPolicy(memory="256m").docker_command(
        image=PINNED, command=["true"], workspace=workspace
    )
    assert "--memory=256m" in command
    assert "--memory-swap=256m" in command


def test_scratch_space_cannot_be_used_to_stage_a_binary(workspace):
    command = SandboxPolicy().docker_command(
        image=PINNED, command=["true"], workspace=workspace
    )
    tmpfs = command[command.index("--tmpfs") + 1]
    assert "noexec" in tmpfs
    assert "nosuid" in tmpfs


def test_pull_never_means_a_crafted_image_name_cannot_become_a_network_fetch(workspace):
    """Without --pull=never, naming an unknown image is a way to reach the
    internet from the one feature that must not."""
    command = SandboxPolicy().docker_command(
        image=PINNED, command=["true"], workspace=workspace
    )
    assert "--pull=never" in command


# ── the store is absent, not merely read-only ──────────────────────────────


def test_the_store_is_never_mounted(workspace):
    """Databases, keys and the egress log must not exist in the container's view
    of the filesystem at all."""
    workspace.store.mkdir(parents=True, exist_ok=True)
    (workspace.store / "ai_context.db").write_text("secret")

    command = SandboxPolicy().docker_command(
        image=PINNED, command=["true"], workspace=workspace
    )
    joined = " ".join(command)
    assert str(workspace.store) not in joined
    assert "store" not in [
        part.split(":")[-2] for part in command if part.count(":") >= 2
    ]


def test_inbox_is_read_only_and_work_is_writable(workspace):
    command = SandboxPolicy().docker_command(
        image=PINNED, command=["true"], workspace=workspace
    )
    mounts = [command[i + 1] for i, part in enumerate(command) if part == "-v"]
    assert any(m.endswith(":/inbox:ro") for m in mounts), mounts
    assert any(m.endswith(":/work:rw") for m in mounts), mounts
    assert not any(m.endswith(":/inbox:rw") for m in mounts)


# ── image and command validation ───────────────────────────────────────────


def test_an_unpinned_image_is_refused():
    with pytest.raises(ValueError, match="version-pinned"):
        validate_image("python:latest")
    with pytest.raises(ValueError, match="no tag or digest"):
        validate_image("python")


def test_a_digest_pinned_image_is_accepted():
    digest = "python@sha256:" + "a" * 64
    assert validate_image(digest) == digest


@pytest.mark.parametrize(
    "bad",
    [
        "python:3.12 --privileged",
        "python:3.12; rm -rf /",
        "--privileged",
        "python:3.12\n--network=host",
        "",
    ],
)
def test_an_image_name_cannot_smuggle_arguments(bad):
    """An image reference is concatenated into an argv list. A name that parses
    as a flag would be a way to turn the isolation off."""
    with pytest.raises(ValueError):
        validate_image(bad)


def test_command_bounds_are_enforced():
    with pytest.raises(ValueError, match="at least one"):
        validate_command([])
    with pytest.raises(ValueError, match="at most 40"):
        validate_command(["x"] * (MAX_COMMAND_PARTS + 1))
    with pytest.raises(ValueError, match="at most 1000"):
        validate_command(["x" * (MAX_ARGUMENT_LENGTH + 1)])
    with pytest.raises(ValueError, match="null byte"):
        validate_command(["ok", "bad\x00arg"])
    with pytest.raises(ValueError, match="cannot be empty"):
        validate_command(["ok", ""])


# ── data class ─────────────────────────────────────────────────────────────


def test_the_sandbox_runs_public_work_only():
    assert_public(DataClass.PUBLIC)  # does not raise
    for forbidden in (
        DataClass.PERSON_PUBLIC,
        DataClass.CAMPAIGN,
        DataClass.INTERNAL,
        DataClass.MAILBOX,
    ):
        with pytest.raises(PolicyViolation) as excinfo:
            assert_public(forbidden)
        assert forbidden.value in str(excinfo.value)


# ── availability, refusing rather than degrading ───────────────────────────


def test_render_is_detected_and_refused_with_a_readable_reason(monkeypatch):
    monkeypatch.setenv("RENDER", "true")
    ok, reason = sandbox_available()
    assert ok is False
    assert "Render" in reason
    assert "locally" in reason
    with pytest.raises(SandboxUnavailable):
        assert_sandbox_available()


def test_a_missing_docker_refuses_rather_than_falling_back(monkeypatch):
    """There is no weaker fallback worth offering. Python cannot sandbox
    Python, so 'no container' means 'no'."""
    monkeypatch.delenv("RENDER", raising=False)
    monkeypatch.setattr(
        "offsetx_apollo_builder.ai.sandbox.os.path.exists", lambda path: False
    )
    monkeypatch.setattr(
        "offsetx_apollo_builder.ai.sandbox.shutil.which", lambda name: None
    )
    ok, reason = sandbox_available()
    assert ok is False
    assert "Docker" in reason


def test_nesting_is_detected_but_can_be_overridden_deliberately(monkeypatch):
    monkeypatch.delenv("RENDER", raising=False)
    monkeypatch.setattr(
        "offsetx_apollo_builder.ai.sandbox.os.path.exists",
        lambda path: path == "/.dockerenv",
    )
    monkeypatch.delenv("OFFSETX_SANDBOX_ALLOW_NESTED", raising=False)
    assert sandbox_available()[0] is False

    monkeypatch.setenv("OFFSETX_SANDBOX_ALLOW_NESTED", "1")
    monkeypatch.setattr(
        "offsetx_apollo_builder.ai.sandbox.shutil.which", lambda name: "/usr/bin/docker"
    )
    # The override clears the nesting objection; a live daemon is still required.
    monkeypatch.setattr(
        "offsetx_apollo_builder.ai.sandbox._daemon_responds", lambda **kw: True
    )
    assert sandbox_available()[0] is True


# ── disk budget ────────────────────────────────────────────────────────────


def test_workspace_usage_counts_bytes_written(workspace):
    assert workspace.usage() == 0
    (workspace.work / "out.txt").write_bytes(b"x" * 2048)
    (workspace.work / "nested").mkdir()
    (workspace.work / "nested" / "more.bin").write_bytes(b"y" * 1024)
    assert workspace.usage() == 3072


def test_exceeding_the_budget_raises_with_the_numbers(workspace):
    workspace.max_bytes = 1000
    (workspace.work / "big.bin").write_bytes(b"x" * 5000)
    with pytest.raises(PolicyViolation, match="over the"):
        workspace.assert_within_budget()


def test_usage_survives_a_file_vanishing_mid_walk(tmp_path):
    """A partially-deleted tree is not a reason to fail the count."""
    assert workspace_usage(tmp_path / "does-not-exist") == 0


def test_the_default_budget_is_ten_gigabytes():
    assert DEFAULT_WORKSPACE_BYTES == 10 * 1024**3


# ── egress allowlist ───────────────────────────────────────────────────────


def test_by_default_every_host_is_refused():
    policy = SandboxPolicy()
    for host in ("example.com", "localhost", "169.254.169.254", ""):
        with pytest.raises(PolicyViolation, match="blocked"):
            policy.assert_host(host)


def test_an_allowlisted_host_passes_and_a_port_does_not_defeat_it():
    policy = SandboxPolicy.with_hosts(["pypi.org"])
    policy.assert_host("pypi.org")
    policy.assert_host("PyPI.org:443")
    with pytest.raises(PolicyViolation):
        policy.assert_host("evil.pypi.org")


# ── structural ─────────────────────────────────────────────────────────────


def test_the_sandbox_module_imports_no_transport_and_no_provider():
    source = (PACKAGE_ROOT / "ai" / "sandbox.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module)
            imported.update(f"{node.module}.{alias.name}" for alias in node.names)
        elif isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
    banned = {"requests", "httpx", "urllib", "urllib.request", "socket", "openai"}
    assert not (imported & banned)
    assert not any("create_provider" in name for name in imported)


def test_describe_tells_the_owner_what_the_container_can_reach():
    described = SandboxPolicy().describe()
    assert described["network"] == "none"
    assert described["writable_paths"] == ["/work"]
    assert described["readonly_paths"] == ["/inbox"]
    assert "store" in described["unmounted"][0]
    assert described["allowed_hosts"] == []


# ── §5.12(c), part two: the live wall ──────────────────────────────────────


def test_a_networkless_container_cannot_reach_an_external_host(tmp_path):
    """The real acceptance case. Starts a container and tries to open a socket.

    Skips unless a pre-pulled, pinned image is supplied: `--pull=never` means
    this cannot fetch one, and a network-isolation test that quietly downloads
    from the internet would be self-defeating.
    """
    image = os.getenv("OFF_CRM_SANDBOX_TEST_IMAGE", "").strip()
    if not image:
        pytest.skip(
            "Set OFF_CRM_SANDBOX_TEST_IMAGE to a pre-pulled, version-pinned "
            "Python image to run the live egress test"
        )
    if shutil.which("docker") is None:
        pytest.skip("Docker is not available")
    present = subprocess.run(
        ["docker", "image", "inspect", image],
        capture_output=True,
        text=True,
        check=False,
        timeout=15,
    )
    if present.returncode != 0:
        pytest.skip(f"{image} is not present locally, and --pull=never forbids fetching it")

    workspace = SandboxWorkspace(root=tmp_path / "job").prepare()
    command = SandboxPolicy().docker_command(
        image=image,
        workspace=workspace,
        command=[
            "python",
            "-c",
            (
                "import socket; "
                "socket.create_connection(('example.com', 443), timeout=3); "
                "raise SystemExit('NETWORK_SHOULD_NOT_BE_REACHABLE')"
            ),
        ],
    )
    completed = subprocess.run(
        command, capture_output=True, text=True, check=False, timeout=30
    )
    assert completed.returncode != 0, "the container reached the network"
    assert "NETWORK_SHOULD_NOT_BE_REACHABLE" not in completed.stdout
    assert "NETWORK_SHOULD_NOT_BE_REACHABLE" not in completed.stderr


# ── the binary is not the daemon ───────────────────────────────────────────


def test_an_installed_binary_with_a_dead_daemon_is_not_available(monkeypatch):
    """A file on PATH is not a running engine. Answering "available" on the
    strength of `which docker` sends the owner into a failure several steps
    later, with a worse message than this one."""
    monkeypatch.delenv("RENDER", raising=False)
    monkeypatch.setattr(
        "offsetx_apollo_builder.ai.sandbox.os.path.exists", lambda path: False
    )
    monkeypatch.setattr(
        "offsetx_apollo_builder.ai.sandbox.shutil.which", lambda name: "/usr/bin/docker"
    )
    monkeypatch.setattr(
        "offsetx_apollo_builder.ai.sandbox._daemon_responds", lambda **kw: False
    )
    ok, reason = sandbox_available()
    assert ok is False
    assert "daemon is not responding" in reason


def test_the_daemon_probe_can_be_skipped_for_an_advisory_answer(monkeypatch):
    """A UI badge does not need to pay for a subprocess on every render."""
    monkeypatch.delenv("RENDER", raising=False)
    monkeypatch.setattr(
        "offsetx_apollo_builder.ai.sandbox.os.path.exists", lambda path: False
    )
    monkeypatch.setattr(
        "offsetx_apollo_builder.ai.sandbox.shutil.which", lambda name: "/usr/bin/docker"
    )

    def explode(**kwargs):
        raise AssertionError("the probe must not run when check_daemon is False")

    monkeypatch.setattr("offsetx_apollo_builder.ai.sandbox._daemon_responds", explode)
    assert sandbox_available(check_daemon=False) == (True, "")


def test_a_live_daemon_reports_available(monkeypatch):
    monkeypatch.delenv("RENDER", raising=False)
    monkeypatch.setattr(
        "offsetx_apollo_builder.ai.sandbox.os.path.exists", lambda path: False
    )
    monkeypatch.setattr(
        "offsetx_apollo_builder.ai.sandbox.shutil.which", lambda name: "/usr/bin/docker"
    )
    monkeypatch.setattr(
        "offsetx_apollo_builder.ai.sandbox._daemon_responds", lambda **kw: True
    )
    assert sandbox_available() == (True, "")


@pytest.mark.parametrize(
    "returncode,stdout,expected",
    [
        (0, "27.0.1\n", True),
        (0, "", False),      # exits zero with no server half — the docker info trap
        (1, "", False),
        (1, "27.0.1", False),
    ],
)
def test_the_probe_needs_both_a_zero_exit_and_a_server_version(
    monkeypatch, returncode, stdout, expected
):
    """`docker info` exits zero even when the server half fails, which is why
    the probe asks for the server version specifically."""
    from offsetx_apollo_builder.ai import sandbox as sandbox_module

    class Completed:
        pass

    completed = Completed()
    completed.returncode = returncode
    completed.stdout = stdout
    monkeypatch.setattr(
        sandbox_module.subprocess, "run", lambda *a, **k: completed
    )
    assert sandbox_module._daemon_responds() is expected


def test_a_probe_that_cannot_even_start_reports_unavailable(monkeypatch):
    from offsetx_apollo_builder.ai import sandbox as sandbox_module

    def explode(*args, **kwargs):
        raise OSError("no such binary")

    monkeypatch.setattr(sandbox_module.subprocess, "run", explode)
    assert sandbox_module._daemon_responds() is False
