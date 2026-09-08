"""Coordinate local workspace recovery with web requests and worker processes."""
from __future__ import annotations

import os
from pathlib import Path


class WorkspaceBusy(RuntimeError):
    pass


class WorkspaceLock:
    def __init__(self, data_dir: Path, *, exclusive: bool = False, instance: bool = False):
        suffix = "instance" if instance else "workspace"
        self.path = data_dir.parent / f".{data_dir.name}.{suffix}.lock"
        self.exclusive = exclusive or instance
        self.fd: int | None = None

    def __enter__(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.fd = os.open(self.path, os.O_CREAT | os.O_RDWR, 0o600)
        try:
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(self.fd, msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(self.fd, (fcntl.LOCK_EX if self.exclusive else fcntl.LOCK_SH) | fcntl.LOCK_NB)
        except OSError as exc:
            os.close(self.fd)
            self.fd = None
            raise WorkspaceBusy("Workspace is busy. Wait for active work to finish and retry.") from exc
        return self

    def __exit__(self, *args):
        if self.fd is not None:
            os.close(self.fd)
            self.fd = None
