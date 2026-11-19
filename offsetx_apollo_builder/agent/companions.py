"""Owner-created companion profiles and explicit, scoped memory snapshots.

Profiles grant a subset of the existing browser vocabulary. They never grant
filesystem access, retrieval, provider access or permission to bypass review.
"""
from __future__ import annotations

import json
import os
import re
import stat
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from ..ai.workspace import atomic_json
from ..browser.page import ACTIONS


class CompanionError(ValueError):
    """A profile or scoped snapshot cannot safely be used."""


def _identifier(value: object) -> str:
    if not isinstance(value, str) or not re.fullmatch(r'[a-zA-Z0-9][a-zA-Z0-9_-]{0,63}', value):
        raise CompanionError('Use an identifier of 1–64 letters, numbers, underscores or dashes.')
    return value


@dataclass(frozen=True)
class Companion:
    id: str
    name: str
    instructions: str = ''
    tools: tuple[str, ...] = ()
    memory_scopes: tuple[str, ...] = ()
    workspace_id: str = 'local'

    def __post_init__(self) -> None:
        _identifier(self.id)
        _identifier(self.workspace_id)
        if not isinstance(self.name, str) or not self.name.strip() or len(self.name) > 120:
            raise CompanionError('A companion needs a name of 1–120 characters.')
        if not isinstance(self.instructions, str) or len(self.instructions) > 1500:
            raise CompanionError('Companion instructions must contain at most 1500 characters.')
        for field in ('tools', 'memory_scopes'):
            values = getattr(self, field)
            if not isinstance(values, (list, tuple)) or len(values) > 32 or any(not isinstance(v, str) for v in values):
                raise CompanionError(f'{field} must be a list of declared names.')
            if len(values) != len(set(values)):
                raise CompanionError(f'{field} must not contain duplicate names.')
            object.__setattr__(self, field, tuple(values))
        if set(self.tools) - set(ACTIONS):
            raise CompanionError('Companions may grant only existing browser verbs.')
        for scope in self.memory_scopes:
            _identifier(scope)

    def to_dict(self) -> dict[str, Any]:
        return {**asdict(self), 'tools': list(self.tools), 'memory_scopes': list(self.memory_scopes)}

    @classmethod
    def from_dict(cls, value: object) -> 'Companion':
        try:
            if not isinstance(value, dict):
                raise TypeError('expected a profile object')
            return cls(**value)
        except (TypeError, ValueError) as exc:
            raise CompanionError('Invalid companion profile. Restore a valid owner profile.') from exc


@dataclass(frozen=True)
class MemorySnapshot:
    workspace_id: str
    scope: str
    text: str

    def __post_init__(self) -> None:
        _identifier(self.workspace_id)
        _identifier(self.scope)
        if not isinstance(self.text, str) or len(self.text) > 1500:
            raise CompanionError('A memory snapshot must be text of at most 1500 characters.')


class CompanionStore:
    """One atomic private JSON file per workspace/profile; unrelated writes do not race."""

    def __init__(self, data_dir: Path | str) -> None:
        self.root = Path(data_dir) / 'companions'

    def _path(self, workspace_id: str, profile_id: str) -> Path:
        workspace = _identifier(workspace_id)
        profile = _identifier(profile_id)
        directory = self.root / workspace
        if self.root.is_symlink() or directory.is_symlink():
            raise CompanionError('Companion directories must not be symbolic links.')
        path = directory / f'{profile}.json'
        if path.is_symlink():
            raise CompanionError('Companion profiles must not be symbolic links.')
        return path

    def save(self, profile: Companion) -> Companion:
        if not isinstance(profile, Companion):
            raise CompanionError('Save a validated Companion profile.')
        path = self._path(profile.workspace_id, profile.id)
        try:
            path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            self.root.chmod(0o700)
            path.parent.chmod(0o700)
            atomic_json(path, profile.to_dict())
        except OSError as exc:
            raise CompanionError('Cannot save the companion. Check directory permissions and disk space.') from exc
        return profile

    def get(self, workspace_id: str, profile_id: str) -> Companion:
        path = self._path(workspace_id, profile_id)
        try:
            fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
            with os.fdopen(fd, 'rb') as handle:
                if not stat.S_ISREG(os.fstat(handle.fileno()).st_mode):
                    raise ValueError('not a regular profile')
                raw = handle.read(32769)
            if len(raw) > 32768:
                raise ValueError('oversized profile')
            profile = Companion.from_dict(json.loads(raw))
        except (OSError, ValueError) as exc:
            raise CompanionError(f'Cannot read companion {profile_id!r}. Restore or create its profile.') from exc
        if profile.workspace_id != workspace_id or profile.id != profile_id:
            raise CompanionError('The companion file does not match its workspace and identifier.')
        return profile

    def list(self, workspace_id: str) -> list[Companion]:
        directory = self._path(workspace_id, 'index').parent
        return [self.get(workspace_id, p.stem) for p in sorted(directory.glob('*.json'))]

    def delete(self, workspace_id: str, profile_id: str) -> None:
        path = self._path(workspace_id, profile_id)
        try:
            path.unlink(missing_ok=True)
        except OSError as exc:
            raise CompanionError(f'Cannot delete companion {profile_id!r}. Check file permissions.') from exc
