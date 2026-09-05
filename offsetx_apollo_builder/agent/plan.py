"""The one owner-editable plan file for an agent run.

PLAN.md is deliberately a file rather than a model-owned data structure. The
owner can open it with any editor, the run reads it immediately before every
model decision, and a UI can render its markdown/checklist without inventing a
second source of truth.

The security boundary matters more than the file format: the model never gets a
filesystem tool or a path argument. Host code names exactly ``PLAN.md`` inside
the run directory, refuses symlinks/non-regular files, caps its size, and reads
UTF-8 strictly. A page or model cannot turn this feature into "read some other
local file and put it in a prompt".
"""

from __future__ import annotations

import hashlib
import os
import re
import stat
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

PLAN_FILENAME = "PLAN.md"
MAX_PLAN_BYTES = 64 * 1024
_CHECKBOX = re.compile(r"^\s*-\s+\[([ xX])\]\s+(.+?)\s*$")


class PlanError(ValueError):
    """PLAN.md is missing, unsafe or cannot be represented by the contract."""


@dataclass(frozen=True, slots=True)
class PlanSnapshot:
    """One exact saved version of PLAN.md."""

    markdown: str
    digest: str
    checklist: tuple[dict[str, Any], ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "markdown": self.markdown,
            "digest": self.digest,
            "checklist": [dict(item) for item in self.checklist],
        }


@dataclass(frozen=True, slots=True)
class RunPlan:
    """The fixed PLAN.md belonging to one run directory."""

    directory: Path

    @classmethod
    def open(cls, directory: Path | str, *, goal: str) -> "RunPlan":
        run_directory = Path(directory)
        run_directory.mkdir(parents=True, exist_ok=True)
        plan = cls(run_directory)
        plan._create_if_missing(goal)
        # Validate now. A pre-existing symlink or oversized file must fail the
        # run before any model call, not only when the second decision happens.
        plan.snapshot()
        return plan

    @property
    def path(self) -> Path:
        return self.directory / PLAN_FILENAME

    @property
    def filename(self) -> str:
        return PLAN_FILENAME

    def snapshot(self) -> PlanSnapshot:
        """Read the exact current file, safely, every time this is called."""
        raw = self._read_bytes()
        try:
            markdown = raw.decode("utf-8", errors="strict")
        except UnicodeDecodeError as exc:
            raise PlanError("PLAN.md must be valid UTF-8 text.") from exc
        digest = hashlib.sha256(raw).hexdigest()
        return PlanSnapshot(
            markdown=markdown,
            digest=digest,
            checklist=tuple(_checklist(markdown)),
        )

    def replace(self, markdown: str) -> PlanSnapshot:
        """Atomically replace PLAN.md with an owner/API edit.

        The temporary file lives in the same run directory, so ``os.replace``
        is atomic on the same filesystem. A crash leaves either the old plan or
        the new plan, never half a markdown document.
        """
        text = str(markdown)
        raw = text.encode("utf-8")
        _validate_size(len(raw))
        self.directory.mkdir(parents=True, exist_ok=True)

        handle = tempfile.NamedTemporaryFile(
            mode="wb",
            prefix=".PLAN.",
            suffix=".tmp",
            dir=self.directory,
            delete=False,
        )
        temporary = Path(handle.name)
        try:
            with handle:
                handle.write(raw)
                handle.flush()
                os.fsync(handle.fileno())
            try:
                os.chmod(temporary, 0o600)
            except OSError:
                pass
            # Replace the directory entry itself. If somebody planted a symlink
            # at PLAN.md, os.replace replaces that link rather than following it.
            os.replace(temporary, self.path)
            try:
                os.chmod(self.path, 0o600)
            except OSError:
                pass
        finally:
            try:
                temporary.unlink(missing_ok=True)
            except OSError:
                pass
        return self.snapshot()

    def _create_if_missing(self, goal: str) -> None:
        initial = _initial_markdown(goal).encode("utf-8")
        _validate_size(len(initial))
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
        try:
            descriptor = os.open(self.path, flags, 0o600)
        except FileExistsError:
            return
        try:
            with os.fdopen(descriptor, "wb") as handle:
                handle.write(initial)
                handle.flush()
                os.fsync(handle.fileno())
        except Exception:
            try:
                self.path.unlink(missing_ok=True)
            except OSError:
                pass
            raise

    def _read_bytes(self) -> bytes:
        # lstat checks the directory entry itself rather than following it. It
        # is required on platforms without O_NOFOLLOW (notably Windows).
        try:
            path_information = os.lstat(self.path)
        except FileNotFoundError as exc:
            raise PlanError("PLAN.md is missing from this run.") from exc
        except OSError as exc:
            raise PlanError("PLAN.md cannot be inspected safely.") from exc
        if stat.S_ISLNK(path_information.st_mode) or not stat.S_ISREG(path_information.st_mode):
            raise PlanError("PLAN.md must be a regular file inside the run directory.")
        _validate_size(path_information.st_size)

        flags = os.O_RDONLY
        no_follow = getattr(os, "O_NOFOLLOW", 0)
        if no_follow:
            flags |= no_follow
        try:
            descriptor = os.open(self.path, flags)
        except FileNotFoundError as exc:
            raise PlanError("PLAN.md is missing from this run.") from exc
        except OSError as exc:
            # Linux raises ELOOP for O_NOFOLLOW on a symlink. Keep the message
            # stable instead of exposing a platform-specific errno to the owner.
            raise PlanError("PLAN.md must be a regular file inside the run directory.") from exc

        try:
            information = os.fstat(descriptor)
            if not stat.S_ISREG(information.st_mode):
                raise PlanError("PLAN.md must be a regular file inside the run directory.")
            _validate_size(information.st_size)
            with os.fdopen(descriptor, "rb", closefd=False) as handle:
                raw = handle.read(MAX_PLAN_BYTES + 1)
            _validate_size(len(raw))
            return raw
        finally:
            os.close(descriptor)


def _validate_size(size: int) -> None:
    if int(size) > MAX_PLAN_BYTES:
        raise PlanError(
            f"PLAN.md is too large; keep it at or below {MAX_PLAN_BYTES // 1024} KiB."
        )


def _initial_markdown(goal: str) -> str:
    cleaned = " ".join(str(goal or "").split()).strip()
    if not cleaned:
        raise PlanError("PLAN.md needs a non-empty run goal.")
    return (
        "# Goal\n\n"
        f"{cleaned}\n\n"
        "## Checklist\n\n"
        "- [ ] Work toward the goal within the run budget.\n"
        "- [ ] Verify the goal is complete before stopping.\n\n"
        "## Owner notes\n\n"
        "Edit this file while the run is active. The next model decision reads "
        "the latest saved version.\n"
    )


def _checklist(markdown: str) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for line in str(markdown).splitlines():
        match = _CHECKBOX.match(line)
        if not match:
            continue
        items.append(
            {
                "done": match.group(1).lower() == "x",
                "text": match.group(2).strip(),
            }
        )
    return items
