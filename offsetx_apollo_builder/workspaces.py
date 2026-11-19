"""Trusted startup identities and private local workspace storage boundaries."""
from __future__ import annotations

import hashlib
import os
import re
import stat
import threading
from contextlib import contextmanager
from pathlib import Path


class WorkspaceError(ValueError):
    """A workspace identity or storage boundary cannot safely be used."""


def workspace_id(value: str) -> str:
    if not isinstance(value, str) or not re.fullmatch(r'[a-z0-9][a-z0-9_-]{0,63}', value):
        raise WorkspaceError('Workspace IDs must be 1–64 lowercase letters, digits, dashes or underscores.')
    return value


def workspace_env(identity: str, name: str) -> str:
    identity = workspace_id(identity)
    if identity == 'local':
        return 'OFFSETX_' + name
    digest = hashlib.sha256(identity.encode()).hexdigest().upper()
    return f'OFFSETX_WORKSPACE_{digest}_{name}'


def provider_environment(identity: str) -> dict[str, str] | None:
    """Legacy local providers inherit the host; other workspaces get only their keys."""
    identity = workspace_id(identity)
    if identity == 'local':
        return None
    prefix = workspace_env(identity, 'AI_')
    return {name: value for name, value in os.environ.items()
            if name.startswith(prefix) and name.endswith('_KEY')}


def workspace_directory(root: Path | str, identity: str) -> Path:
    root, identity = Path(root), workspace_id(identity)
    path = root if identity == 'local' else root/'workspaces'/identity
    for component in (root, root/'workspaces', path):
        if component.is_symlink():
            raise WorkspaceError('Workspace directories must not be symbolic links.')
    return path


def private_read(path: Path, *, limit: int = 4*1024*1024) -> bytes:
    if path.is_symlink():
        raise WorkspaceError('Workspace state must not be a symbolic link.')
    fd = os.open(path, os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0) | getattr(os, 'O_NONBLOCK', 0))
    with os.fdopen(fd, 'rb') as handle:
        if not stat.S_ISREG(os.fstat(handle.fileno()).st_mode):
            raise WorkspaceError('Workspace state must be a regular file.')
        data = handle.read(limit+1)
    if len(data) > limit:
        raise WorkspaceError('Workspace state exceeds its size limit.')
    return data


_locks: dict[str, tuple[threading.RLock, list[int]]] = {}
_registry_lock = threading.Lock()


@contextmanager
def workspace_lock(directory: Path):
    """Serialize a workspace RMW across store instances, threads and processes."""
    if directory.is_symlink():
        raise WorkspaceError('Workspace directories must not be symbolic links.')
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    directory.chmod(0o700)
    key = str(directory.absolute())
    with _registry_lock:
        lock, depth = _locks.setdefault(key, (threading.RLock(), [0]))
    with lock:
        if depth[0]:
            yield
            return
        fd = os.open(directory/'.workspace.lock', os.O_RDWR | os.O_CREAT | getattr(os, 'O_NOFOLLOW', 0) | getattr(os, 'O_NONBLOCK', 0), 0o600)
        try:
            if not stat.S_ISREG(os.fstat(fd).st_mode):
                raise WorkspaceError('The workspace lock must be a regular file.')
            if os.name == 'nt':
                import msvcrt
                if os.fstat(fd).st_size == 0:
                    os.write(fd, b'0')
                os.lseek(fd, 0, os.SEEK_SET)
                msvcrt.locking(fd, msvcrt.LK_LOCK, 1)
            else:
                import fcntl
                fcntl.flock(fd, fcntl.LOCK_EX)
            depth[0] = 1
            try:
                yield
            finally:
                depth[0] = 0
        finally:
            os.close(fd)
