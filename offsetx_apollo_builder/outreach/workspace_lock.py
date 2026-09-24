"""Coordinate local workspace recovery with web requests and worker processes."""
from __future__ import annotations

import os
import time
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from .backup import restore_pending


class WorkspaceBusy(RuntimeError):
    pass


class WorkspaceLock:
    def __init__(
        self,
        data_dir: Path,
        *,
        exclusive: bool = False,
        instance: bool = False,
        wait_seconds: float = 0.0,
    ):
        suffix = "instance" if instance else "workspace"
        self.path = data_dir.parent / f".{data_dir.name}.{suffix}.lock"
        self.exclusive = exclusive or instance
        #: 0 fails at once, as a request must. Start-up waits instead, for a
        #: worker's cycle to end (D-129) — polled, because neither lock call
        #: below can block with a deadline.
        self.wait_seconds = wait_seconds
        self.fd: int | None = None
        self._unlock = None

    def __enter__(self):
        deadline = time.monotonic() + self.wait_seconds
        while True:
            try:
                return self._acquire()
            except WorkspaceBusy:
                if time.monotonic() >= deadline:
                    raise
                time.sleep(0.1)

    def _acquire(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.fd = os.open(self.path, os.O_CREAT | os.O_RDWR, 0o600)
        try:
            if os.name == "nt":
                import ctypes
                import msvcrt
                from ctypes import wintypes

                class Overlapped(ctypes.Structure):
                    _fields_ = [("internal", ctypes.c_size_t), ("internal_high", ctypes.c_size_t),
                                ("offset", wintypes.DWORD), ("offset_high", wintypes.DWORD),
                                ("event", wintypes.HANDLE)]

                # msvcrt.locking has no shared mode: using it here would reject
                # normal concurrent dashboard requests on Windows.
                kernel = ctypes.WinDLL("kernel32", use_last_error=True)
                lock = kernel.LockFileEx
                lock.argtypes = [wintypes.HANDLE, wintypes.DWORD, wintypes.DWORD,
                                 wintypes.DWORD, wintypes.DWORD, ctypes.POINTER(Overlapped)]
                lock.restype = wintypes.BOOL
                overlap = Overlapped()
                flags = 1 | (2 if self.exclusive else 0)  # fail immediately; optionally exclusive
                if not lock(msvcrt.get_osfhandle(self.fd), flags, 0, 1, 0, ctypes.byref(overlap)):
                    raise ctypes.WinError(ctypes.get_last_error())
                unlock = kernel.UnlockFileEx
                unlock.argtypes = [wintypes.HANDLE, wintypes.DWORD, wintypes.DWORD,
                                   wintypes.DWORD, ctypes.POINTER(Overlapped)]
                unlock.restype = wintypes.BOOL
                handle = msvcrt.get_osfhandle(self.fd)
                self._unlock = lambda: unlock(handle, 0, 1, 0, ctypes.byref(overlap))
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
            try:
                if self._unlock:
                    self._unlock()
            finally:
                os.close(self.fd)
                self.fd = None


@contextmanager
def cli_workspace_lease(data_dir: Path) -> Iterator[None]:
    """The shared lease for one command-line run, as a web request holds (D-134).

    A restore swaps the data directory under the exclusive lease, which a
    backup also takes; without this, a tool's write landed in the generation
    being swapped out and was lost with it. Refused rather than waited for: a
    restore can take minutes, and a person at a terminal should be told why now.
    """
    lease = WorkspaceLock(data_dir)
    try:
        lease.__enter__()
    except WorkspaceBusy as exc:
        raise SystemExit(
            "The web app is backing up or restoring the workspace. Retry once it finishes."
        ) from exc
    try:
        # Checked under the lease, as the email worker does (D-129): a crash
        # mid-restore leaves no process holding anything, only the journal.
        if restore_pending(data_dir):
            raise SystemExit(
                "A restore was interrupted and has not been rolled back yet. Start the "
                "web app, which rolls it back as it starts, then retry."
            )
        yield
    finally:
        lease.__exit__(None, None, None)
