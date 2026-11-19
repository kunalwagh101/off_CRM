"""One owner-editable Markdown file per run; no model write path."""
from __future__ import annotations

import os
import stat
from pathlib import Path

MAX_PLAN_CHARS = 4500
MAX_PLAN_BYTES = MAX_PLAN_CHARS * 4


class PlanError(ValueError):
    """The owner plan is unavailable; continuing would ignore owner intent."""


class RunPlan:
    def __init__(self, directory: Path | str) -> None:
        self.path = Path(directory) / 'PLAN.md'

    def ensure(self, goal: str) -> str:
        """Exclusive creation preserves an existing owner edit, including on resume."""
        text = f'# Run plan\n\n{goal}\n\n- [ ] Complete the owner goal\n'
        try:
            fd = os.open(self.path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        except FileExistsError:
            return self.read()
        except OSError as exc:
            raise PlanError('Cannot create PLAN.md. Check the run directory permissions.') from exc
        with os.fdopen(fd, 'w', encoding='utf-8') as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        return self.read()

    def read(self) -> str:
        try:
            fd = os.open(self.path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
            with os.fdopen(fd, 'rb') as handle:
                if not stat.S_ISREG(os.fstat(handle.fileno()).st_mode):
                    raise ValueError('not a regular file')
                raw = handle.read(MAX_PLAN_BYTES + 1)
            if len(raw) > MAX_PLAN_BYTES:
                raise ValueError('too large')
            text = raw.decode('utf-8')
            if not text.strip() or len(text) > MAX_PLAN_CHARS:
                raise ValueError('empty or too large')
            return text
        except (OSError, ValueError) as exc:
            raise PlanError(
                f'Cannot read PLAN.md. Restore a regular UTF-8 plan of 1–{MAX_PLAN_CHARS} characters before continuing.'
            ) from exc
