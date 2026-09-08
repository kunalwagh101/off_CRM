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
        self._unlock = None

    def __enter__(self):
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
