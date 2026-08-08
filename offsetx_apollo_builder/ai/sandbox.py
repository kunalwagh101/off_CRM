"""Sandbox for running code the AI wrote (§4J).

Salvaged from ``agent/off-crm-v0-12-ai-studio``, an abandoned parallel design
that had solved this before the ``ai/`` module existed.  The container flags and
the ``--pull=never`` trick below are that branch's work; the rest is adapted to
this module's rules.

The one thing to understand about this file: **it is the campaign runner's
mirror image.**

===================  ==================  =========================
                     sandbox             campaign runner
===================  ==================  =========================
runs AI-written code yes                 never
network              **none**            SMTP only
real contact data    never               yes
credentials          never               yes
makes decisions      yes                 never
===================  ==================  =========================

Neither holds all three legs of the lethal trifecta — private data, untrusted
content, outbound network — and that is the entire security argument.  The
runner has credentials and no judgement; the sandbox has judgement and no way to
send anything anywhere.

**Python cannot sandbox Python.**  Restricted ``exec`` has dozens of documented
escapes and is not used here.  The isolation is the operating system's, via a
container, and if the container cannot be started the answer is a refusal rather
than a fallback to something weaker.

**Honest limits, stated rather than buried:**

* This does not run on hosts that already containerise the app (Render's
  standard plans among them), because nesting is not permitted.  Detected up
  front so the feature refuses with a sentence instead of failing obscurely.
* A bind mount cannot be size-capped by Docker.  off_CRM counts the bytes
  itself, which is a safety limit rather than a lock — see :func:`workspace_usage`.
* The isolation flags need verifying on real hardware with a Docker daemon.
  Everything around them is unit-tested; the flags themselves are asserted as
  *composition*, and the live network test skips unless an image is supplied.
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Sequence

from .errors import PolicyViolation
from .tiers import DataClass

#: An image reference must be explicitly pinned.  ``:latest`` is a moving target,
#: so a build that passed review can silently become a different image tomorrow.
_IMAGE_RE = re.compile(r"^[A-Za-z0-9./_-]+(?::[A-Za-z0-9._-]+|@sha256:[0-9a-f]{64})$")

#: A well-formed name carrying no tag and no digest. Matched first so "unpinned"
#: reports as unpinned rather than as malformed.
_NAME_ONLY_RE = re.compile(r"^[A-Za-z0-9./_-]+$")

#: Hard ceilings.  A tool that needs more than this is not a tool, it is a
#: deployment, and should be reviewed rather than waved through.
MAX_COMMAND_PARTS = 40
MAX_ARGUMENT_LENGTH = 1000

#: Default resource caps.  Deliberately small: a sandbox is for running a build
#: or a check, not for training something.
DEFAULT_MEMORY = "512m"
DEFAULT_CPUS = "1"
DEFAULT_PIDS = 128
DEFAULT_TMPFS_SIZE = "64m"

#: Default byte budget for the writable directory, counted by off_CRM because
#: Docker cannot cap a bind mount.
DEFAULT_WORKSPACE_BYTES = 10 * 1024 * 1024 * 1024  # 10 GB


class SandboxUnavailable(PolicyViolation):
    """The sandbox cannot run here, and running the code unsandboxed is not an
    alternative on offer."""


@dataclass(slots=True)
class SandboxWorkspace:
    """The three directories, and which of them the container can see.

    ``store`` is the important one: it is **not mounted at all**.  Not read-only
    — absent.  The context layer, the recall index, the egress log and the
    encrypted keys do not exist inside the container's view of the filesystem.
    """

    root: Path
    max_bytes: int = DEFAULT_WORKSPACE_BYTES

    @property
    def inbox(self) -> Path:
        """What off_CRM pushed in for this job.  Mounted read-only."""
        return self.root / "inbox"

    @property
    def work(self) -> Path:
        """The tool's desk.  The only writable mount."""
        return self.root / "work"

    @property
    def store(self) -> Path:
        """Databases and keys.  Never mounted."""
        return self.root / "store"

    def prepare(self) -> "SandboxWorkspace":
        self.inbox.mkdir(parents=True, exist_ok=True)
        self.work.mkdir(parents=True, exist_ok=True)
        return self

    def usage(self) -> int:
        return workspace_usage(self.work)

    def assert_within_budget(self) -> None:
        used = self.usage()
        if used > self.max_bytes:
            raise PolicyViolation(
                f"The sandbox workspace holds {used / 1e9:.2f} GB, over the "
                f"{self.max_bytes / 1e9:.2f} GB limit. Clear it, or raise the "
                "limit in Settings."
            )


def workspace_usage(path: Path) -> int:
    """Bytes on disk under ``path``.

    Docker cannot size-cap a bind mount, so this is how the limit is enforced:
    off_CRM counts before and after. That makes it a safety limit rather than a
    lock — code inside the container can still fill the disk mid-run. The real
    lock would be a sized volume, which is a deployment decision rather than a
    code one.
    """
    total = 0
    if not path.exists():
        return 0
    for entry in path.rglob("*"):
        try:
            if entry.is_file() and not entry.is_symlink():
                total += entry.stat().st_size
        except OSError:
            # A file that vanished mid-walk is not a reason to fail the count.
            continue
    return total


def sandbox_available(*, check_daemon: bool = True) -> tuple[bool, str]:
    """Whether a container can be started here, and if not, why.

    Returns a sentence rather than a boolean alone, because §4L says a blocked
    capability explains itself before the owner commits to it.

    ``check_daemon`` runs a real probe against the engine, which costs a
    subprocess. Pass ``False`` where the answer only needs to be advisory — a
    UI badge, say — and leave it on before actually running something.
    """
    if os.environ.get("RENDER"):
        return False, (
            "Sandboxed tools need to start a container, and Render already runs "
            "off_CRM inside one. Nesting is not available on the standard plans, "
            "so run off_CRM locally or on a VM to use them."
        )
    if os.path.exists("/.dockerenv") and not os.environ.get(
        "OFFSETX_SANDBOX_ALLOW_NESTED"
    ):
        return False, (
            "off_CRM appears to be running inside a container already, so it "
            "cannot start another. Set OFFSETX_SANDBOX_ALLOW_NESTED=1 if your "
            "host genuinely supports nesting."
        )
    if shutil.which("docker") is None:
        return False, (
            "Docker is not installed or not on PATH. The sandbox needs it: "
            "isolation comes from the operating system, and there is no weaker "
            "fallback worth offering."
        )
    if check_daemon and not _daemon_responds():
        # The binary being present is not the same as the engine running, and
        # answering "available" on the strength of a file on PATH sends the
        # owner into a failure several steps later with a worse message.
        return False, (
            "The docker command is installed but the daemon is not responding. "
            "Start Docker Desktop, or the docker service, and try again."
        )
    return True, ""


def _daemon_responds(timeout_seconds: int = 10) -> bool:
    """Whether the engine is actually up.

    ``docker version --format {{.Server.Version}}`` is the cheapest question
    that requires a live daemon to answer; ``docker info`` exits zero even when
    the server half fails, which makes it useless as a check.
    """
    try:
        completed = subprocess.run(
            ["docker", "version", "--format", "{{.Server.Version}}"],
            capture_output=True,
            text=True,
            check=False,
            timeout=timeout_seconds,
        )
    except (OSError, subprocess.SubprocessError):
        return False
    return completed.returncode == 0 and bool(completed.stdout.strip())


def assert_sandbox_available() -> None:
    ok, reason = sandbox_available()
    if not ok:
        raise SandboxUnavailable(reason)


def validate_image(value: str) -> str:
    """A pinned, injection-free image reference.

    Two separate rules, both from the salvaged design:

    * the reference must match a strict character set, so an image name cannot
      smuggle extra arguments into the docker command;
    * it must be pinned to a tag or a digest. ``:latest`` means the image you
      reviewed and the image you run are not necessarily the same one.
    """
    image = str(value or "").strip()
    if not image:
        raise ValueError("A sandbox image is required.")
    # Checked before the full pattern, so a name that is merely *unpinned* gets
    # the useful message rather than a generic "invalid reference".
    if _NAME_ONLY_RE.fullmatch(image):
        raise ValueError(
            f"{image!r} has no tag or digest. Pin it, so the image you reviewed "
            "is the image that runs."
        )
    if not _IMAGE_RE.fullmatch(image):
        raise ValueError(
            f"{image!r} is not a valid image reference. Use name:tag or "
            "name@sha256:<digest>."
        )
    if image.endswith(":latest"):
        raise ValueError(
            "Sandbox images must be version-pinned. ':latest' moves, so the "
            "image you reviewed is not necessarily the image that runs."
        )
    return image


def validate_command(command: Sequence[str]) -> list[str]:
    """Bounded, null-free arguments."""
    parts = [str(part) for part in command]
    if not parts:
        raise ValueError("A sandbox command needs at least one argument.")
    if len(parts) > MAX_COMMAND_PARTS:
        raise ValueError(
            f"A sandbox command may have at most {MAX_COMMAND_PARTS} arguments; "
            f"this one has {len(parts)}."
        )
    for part in parts:
        if not part:
            raise ValueError("A sandbox command argument cannot be empty.")
        if len(part) > MAX_ARGUMENT_LENGTH:
            raise ValueError(
                f"A sandbox command argument may be at most "
                f"{MAX_ARGUMENT_LENGTH} characters."
            )
        if "\x00" in part:
            raise ValueError("A sandbox command argument cannot contain a null byte.")
    return parts


def assert_public(data_class: DataClass) -> None:
    """A sandbox job is ``public`` work, and only ``public`` work.

    Source code, schemas and tests identify nobody. If a task genuinely needs
    contact data, it is not a sandbox task — it is an egress task, and it goes
    through the broker where the tier rules apply.
    """
    if data_class is not DataClass.PUBLIC:
        raise PolicyViolation(
            f"The sandbox runs public work only, not {data_class.value}. Code and "
            "schemas identify nobody; anything carrying a person belongs on the "
            "egress path where the trust tiers apply.",
            data_class=data_class.value,
        )


@dataclass(slots=True)
class SandboxPolicy:
    """Builds the container invocation, and guards any egress the owner designs.

    Network is denied by construction. ``allowed_hosts`` exists for a future
    feature where a tool is *deliberately* given a narrow allowlist; until then
    it is empty and :meth:`assert_host` refuses everything, which is the correct
    default.
    """

    allowed_hosts: frozenset[str] = field(default_factory=frozenset)
    memory: str = DEFAULT_MEMORY
    cpus: str = DEFAULT_CPUS
    pids_limit: int = DEFAULT_PIDS
    tmpfs_size: str = DEFAULT_TMPFS_SIZE

    @classmethod
    def with_hosts(cls, hosts: Iterable[str], **kwargs: Any) -> "SandboxPolicy":
        return cls(
            allowed_hosts=frozenset(
                str(host).strip().lower() for host in hosts if str(host).strip()
            ),
            **kwargs,
        )

    def assert_host(self, host: str) -> None:
        value = str(host or "").strip().lower().split(":", 1)[0]
        if value not in self.allowed_hosts:
            raise PolicyViolation(
                f"Sandbox egress to {host or 'an empty host'!r} is blocked. The "
                "sandbox has no network by default, and this host is not on the "
                "allowlist."
            )

    def docker_command(
        self,
        *,
        image: str,
        command: Sequence[str],
        workspace: SandboxWorkspace,
    ) -> list[str]:
        """The full ``docker run`` invocation.

        Each flag earns its place:

        ``--network=none``
            The one that matters most. It removes the third leg of the lethal
            trifecta: even hostile code that escapes its process has nowhere to
            send anything.
        ``--pull=never``
            The image must already be present locally. Without this, a crafted
            image name becomes a network fetch — which is a way to reach the
            internet from a feature whose whole point is that it cannot.
        ``--read-only`` and the tmpfs
            The root filesystem is immutable; scratch space is small, and mounted
            ``noexec,nosuid`` so it cannot be used to stage a new binary.
        ``--memory-swap`` equal to ``--memory``
            Without it, the memory cap is advisory: a container can exceed it by
            swapping. (The salvaged original omitted this.)
        ``--cap-drop=ALL``, ``--security-opt=no-new-privileges``, ``--user``
            No Linux capabilities, no way to gain any, and never root.
        """
        image = validate_image(image)
        parts = validate_command(command)
        workspace.prepare()

        return [
            "docker",
            "run",
            "--rm",
            "--pull=never",
            "--network=none",
            "--read-only",
            "--cap-drop=ALL",
            "--security-opt=no-new-privileges",
            "--user=65534:65534",
            f"--pids-limit={int(self.pids_limit)}",
            f"--memory={self.memory}",
            # Equal to --memory, so the cap cannot be exceeded via swap.
            f"--memory-swap={self.memory}",
            f"--cpus={self.cpus}",
            "--tmpfs",
            f"/tmp:rw,noexec,nosuid,size={self.tmpfs_size}",
            "-v",
            f"{workspace.inbox}:/inbox:ro",
            "-v",
            f"{workspace.work}:/work:rw",
            "-w",
            "/work",
            image,
            *parts,
        ]

    def describe(self) -> dict[str, Any]:
        """What the UI shows before the owner runs anything."""
        available, reason = sandbox_available()
        return {
            "available": available,
            "blocked_reason": reason,
            "network": "none",
            "writable_paths": ["/work"],
            "readonly_paths": ["/inbox"],
            "unmounted": ["store (databases, keys, logs)"],
            "memory": self.memory,
            "cpus": self.cpus,
            "pids_limit": self.pids_limit,
            "runs_as": "65534:65534 (nobody)",
            "allowed_hosts": sorted(self.allowed_hosts),
        }
