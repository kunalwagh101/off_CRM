"""One editable PLAN.md per browser run.  S-02.02.02.

The trace remains the immutable audit record. PLAN.md is the owner's mutable
steering surface: the model reads it fresh before every decision, so editing the
file changes the next decision without rewriting history or creating a second
checkpoint state.
"""
from __future__ import annotations

import os
import tempfile
from pathlib import Path

MAX_PLAN_CHARS = 64_000


class PlanError(ValueError):
    """The run plan is missing or unsafe to read."""


class RunPlan:
    def __init__(self, run_directory: Path | str) -> None:
        self.directory = Path(run_directory)
        self.path = self.directory / "PLAN.md"

    def ensure(self, goal: str) -> Path:
        """Create the one plan for a new run, never overwrite an owner edit."""
        self.directory.mkdir(parents=True, exist_ok=True)
        if self.path.exists():
            self.read()
            return self.path
        text = (
            "# PLAN\n\n"
            f"## Goal\n{str(goal).strip()}\n\n"
            "## Checklist\n"
            "- [ ] Work toward the owner goal using only the declared browser actions.\n"
            "- [ ] Record required evidence before leaving a page.\n"
            "- [ ] Stop when the goal is complete; do not create extra work.\n"
        )
        self._atomic_create(text)
        return self.path

    def _atomic_create(self, text: str) -> None:
        if len(text) > MAX_PLAN_CHARS:
            raise PlanError("Initial PLAN.md exceeds the allowed size")
        fd, temporary_name = tempfile.mkstemp(
            prefix=".PLAN.", suffix=".tmp", dir=self.directory
        )
        temporary = Path(temporary_name)
        try:
            with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
                handle.write(text)
                handle.flush()
                os.fsync(handle.fileno())
            try:
                os.chmod(temporary, 0o600)
            except OSError:
                pass
            # Do not overwrite a plan that appeared while the temporary file was
            # being written.  Link is an atomic "create if absent" operation.
            try:
                os.link(temporary, self.path)
            except FileExistsError:
                pass
            except OSError:
                # Filesystems without hard-link support still get an exclusive
                # create. It is slower but preserves "never overwrite".
                try:
                    target_fd = os.open(
                        self.path,
                        os.O_WRONLY | os.O_CREAT | os.O_EXCL,
                        0o600,
                    )
                except FileExistsError:
                    pass
                else:
                    with os.fdopen(target_fd, "w", encoding="utf-8", newline="\n") as handle:
                        handle.write(text)
                        handle.flush()
                        os.fsync(handle.fileno())
        finally:
            temporary.unlink(missing_ok=True)
        self.read()

    def read(self) -> str:
        """Read fresh from disk. There is deliberately no in-memory cache."""
        if not self.path.exists():
            raise PlanError(
                f"{self.path} is missing. The run will not continue without its PLAN.md."
            )
        if self.path.is_symlink() or not self.path.is_file():
            raise PlanError("PLAN.md must be a regular non-symlink file")
        try:
            size = self.path.stat().st_size
        except OSError as exc:
            raise PlanError("PLAN.md cannot be inspected safely") from exc
        if size > MAX_PLAN_CHARS * 4:
            raise PlanError("PLAN.md is too large to send to the planning model")
        try:
            text = self.path.read_text(encoding="utf-8")
        except (OSError, UnicodeError) as exc:
            raise PlanError("PLAN.md must be readable UTF-8 text") from exc
        if not text.strip():
            raise PlanError("PLAN.md is empty")
        if len(text) > MAX_PLAN_CHARS:
            raise PlanError(f"PLAN.md exceeds {MAX_PLAN_CHARS} characters")
        return text
