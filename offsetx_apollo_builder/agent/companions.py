"""Persisted companion profiles for bounded agent runs.

A companion is policy, not a second runner. It names the owner instructions,
one memory scope, and the subset of the existing browser action vocabulary that
this agent may use. The browser runner remains the only executor.

S-04.01.01 intentionally does not make sandbox tools executable from AgentRun:
that contract does not exist today. Calling stored browser verbs "tools" here
matches the product language while preserving the runner's closed vocabulary.
"""
from __future__ import annotations

import hashlib
import json
import re
import sqlite3
import threading
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Iterable

from ..browser.page import ACTIONS
from ..outreach.models import to_utc_iso

MAX_NAME_CHARS = 80
MAX_INSTRUCTIONS_CHARS = 8_000
MAX_MEMORY_SCOPE_CHARS = 200
MAX_MEMORY_CONTEXT_CHARS = 12_000
_NAME_RE = re.compile(r"^[^\x00-\x1f\x7f]{2,80}$")
_SCOPE_RE = re.compile(r"^[^\x00-\x1f\x7f]{1,200}$")

SCHEMA = """
CREATE TABLE IF NOT EXISTS agent_companions (
    id TEXT PRIMARY KEY,
    workspace_id TEXT NOT NULL DEFAULT 'local',
    name TEXT NOT NULL,
    name_key TEXT NOT NULL,
    instructions TEXT NOT NULL DEFAULT '',
    memory_scope TEXT NOT NULL,
    granted_tools TEXT NOT NULL DEFAULT '[]',
    enabled INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE UNIQUE INDEX IF NOT EXISTS ux_agent_companions_name
    ON agent_companions(workspace_id, name_key);
CREATE INDEX IF NOT EXISTS ix_agent_companions_workspace
    ON agent_companions(workspace_id, enabled, updated_at DESC);
"""


class CompanionError(ValueError):
    """A companion definition or lookup is invalid."""


@dataclass(frozen=True, slots=True)
class CompanionProfile:
    id: str
    workspace_id: str
    name: str
    instructions: str
    memory_scope: str
    granted_tools: tuple[str, ...]
    enabled: bool
    created_at: str
    updated_at: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "workspace_id": self.workspace_id,
            "name": self.name,
            "instructions": self.instructions,
            "memory_scope": self.memory_scope,
            "granted_tools": list(self.granted_tools),
            "enabled": self.enabled,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


@dataclass(frozen=True, slots=True)
class CompanionRuntime:
    profile: CompanionProfile
    memory_context: str

    @property
    def granted_tools(self) -> frozenset[str]:
        return frozenset(self.profile.granted_tools)


MemoryLoader = Callable[[str, str], str]


def policy_fingerprint(profile: CompanionProfile) -> str:
    """Stable hash of the execution policy that must survive resume."""
    payload = json.dumps(
        {
            "id": profile.id,
            "workspace_id": profile.workspace_id,
            "instructions": profile.instructions,
            "memory_scope": profile.memory_scope,
            "granted_tools": list(profile.granted_tools),
            "enabled": profile.enabled,
        },
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _clean_name(value: str) -> str:
    name = " ".join(str(value or "").split())
    if not _NAME_RE.fullmatch(name):
        raise CompanionError(
            f"Companion name must be 2-{MAX_NAME_CHARS} printable characters."
        )
    return name


def _clean_scope(value: str) -> str:
    scope = str(value or "").strip()
    if not _SCOPE_RE.fullmatch(scope):
        raise CompanionError(
            f"Memory scope must be 1-{MAX_MEMORY_SCOPE_CHARS} printable characters."
        )
    return scope


def _clean_instructions(value: str) -> str:
    instructions = str(value or "").strip()
    if len(instructions) > MAX_INSTRUCTIONS_CHARS:
        raise CompanionError(
            f"Companion instructions exceed {MAX_INSTRUCTIONS_CHARS} characters."
        )
    return instructions


def _clean_tools(values: Iterable[str]) -> tuple[str, ...]:
    requested = [str(value or "").strip().lower() for value in values]
    unknown = sorted({value for value in requested if value not in ACTIONS})
    if unknown:
        raise CompanionError(
            "Companion grants unknown browser tool(s): " + ", ".join(unknown)
        )
    # Stable order follows the runner's declared vocabulary, not caller order.
    granted = set(requested)
    return tuple(action for action in ACTIONS if action in granted)


class CompanionStore:
    """Workspace-scoped persisted companion profiles."""

    def __init__(self, database_path: Path | str) -> None:
        self.path = Path(database_path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._conn = sqlite3.connect(self.path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        with self._lock, self._conn:
            self._conn.executescript(SCHEMA)

    def connection(self) -> sqlite3.Connection:
        """The one store connection; every operation is serialized by _lock."""
        return self._conn

    def close(self) -> None:
        with self._lock:
            self._conn.close()

    def create(
        self,
        *,
        workspace_id: str,
        name: str,
        instructions: str,
        memory_scope: str,
        granted_tools: Iterable[str],
        enabled: bool = True,
    ) -> CompanionProfile:
        workspace = str(workspace_id or "").strip()
        if not workspace:
            raise CompanionError("A companion requires a workspace id.")
        cleaned_name = _clean_name(name)
        cleaned_instructions = _clean_instructions(instructions)
        cleaned_scope = _clean_scope(memory_scope)
        cleaned_tools = _clean_tools(granted_tools)
        now = to_utc_iso()
        companion_id = uuid.uuid4().hex
        try:
            with self._lock, self.connection() as conn:
                conn.execute(
                    """
                    INSERT INTO agent_companions
                        (id, workspace_id, name, name_key, instructions,
                         memory_scope, granted_tools, enabled, created_at, updated_at)
                    VALUES (?,?,?,?,?,?,?,?,?,?)
                    """,
                    (
                        companion_id,
                        workspace,
                        cleaned_name,
                        cleaned_name.casefold(),
                        cleaned_instructions,
                        cleaned_scope,
                        json.dumps(list(cleaned_tools)),
                        int(bool(enabled)),
                        now,
                        now,
                    ),
                )
        except sqlite3.IntegrityError as exc:
            raise CompanionError(
                f"A companion named {cleaned_name!r} already exists in this workspace."
            ) from exc
        return self.require(companion_id, workspace_id=workspace)

    def update(
        self,
        companion_id: str,
        *,
        workspace_id: str,
        name: str | None = None,
        instructions: str | None = None,
        memory_scope: str | None = None,
        granted_tools: Iterable[str] | None = None,
        enabled: bool | None = None,
    ) -> CompanionProfile:
        current = self.require(companion_id, workspace_id=workspace_id)
        next_name = _clean_name(name) if name is not None else current.name
        next_instructions = (
            _clean_instructions(instructions)
            if instructions is not None
            else current.instructions
        )
        next_scope = (
            _clean_scope(memory_scope)
            if memory_scope is not None
            else current.memory_scope
        )
        next_tools = (
            _clean_tools(granted_tools)
            if granted_tools is not None
            else current.granted_tools
        )
        next_enabled = current.enabled if enabled is None else bool(enabled)
        try:
            with self._lock, self.connection() as conn:
                conn.execute(
                    """
                    UPDATE agent_companions
                    SET name = ?, name_key = ?, instructions = ?, memory_scope = ?,
                        granted_tools = ?, enabled = ?, updated_at = ?
                    WHERE id = ? AND workspace_id = ?
                    """,
                    (
                        next_name,
                        next_name.casefold(),
                        next_instructions,
                        next_scope,
                        json.dumps(list(next_tools)),
                        int(next_enabled),
                        to_utc_iso(),
                        companion_id,
                        workspace_id,
                    ),
                )
        except sqlite3.IntegrityError as exc:
            raise CompanionError(
                f"A companion named {next_name!r} already exists in this workspace."
            ) from exc
        return self.require(companion_id, workspace_id=workspace_id)

    def get(self, companion_id: str, *, workspace_id: str) -> CompanionProfile | None:
        with self._lock:
            row = self.connection().execute(
                "SELECT * FROM agent_companions WHERE id = ? AND workspace_id = ?",
                (str(companion_id), str(workspace_id)),
            ).fetchone()
        return _from_row(row) if row is not None else None

    def require(self, companion_id: str, *, workspace_id: str) -> CompanionProfile:
        profile = self.get(companion_id, workspace_id=workspace_id)
        if profile is None:
            raise CompanionError("Companion not found in this workspace.")
        return profile

    def list(
        self, *, workspace_id: str, include_disabled: bool = True
    ) -> list[CompanionProfile]:
        sql = "SELECT * FROM agent_companions WHERE workspace_id = ?"
        params: list[Any] = [str(workspace_id)]
        if not include_disabled:
            sql += " AND enabled = 1"
        sql += " ORDER BY name_key, id"
        with self._lock:
            rows = self.connection().execute(sql, params).fetchall()
        return [_from_row(row) for row in rows]

    def delete(self, companion_id: str, *, workspace_id: str) -> bool:
        with self._lock, self.connection() as conn:
            cursor = conn.execute(
                "DELETE FROM agent_companions WHERE id = ? AND workspace_id = ?",
                (str(companion_id), str(workspace_id)),
            )
        return cursor.rowcount > 0

    def runtime(
        self,
        companion_id: str,
        *,
        workspace_id: str,
        memory_loader: MemoryLoader | None = None,
    ) -> CompanionRuntime:
        profile = self.require(companion_id, workspace_id=workspace_id)
        if not profile.enabled:
            raise CompanionError(f"Companion {profile.name!r} is disabled.")
        memory = ""
        if memory_loader is not None:
            memory = str(memory_loader(workspace_id, profile.memory_scope) or "")
        return CompanionRuntime(
            profile=profile,
            memory_context=memory[:MAX_MEMORY_CONTEXT_CHARS],
        )


def approved_memory_loader(backend: Any, *, limit: int = 50) -> MemoryLoader:
    """Build a loader that can see only approved items in the declared scope."""

    bounded_limit = max(1, min(int(limit), 200))

    def load(workspace_id: str, scope: str) -> str:
        items, _ = backend.search_memory_items(
            "",
            workspace_id=workspace_id,
            scope=scope,
            approved_only=True,
            include_global=False,
            limit=bounded_limit,
            offset=0,
        )
        parts = [
            str(item.get("content") or "").strip()
            for item in items
            if str(item.get("content") or "").strip()
        ]
        return "\n".join(parts)[:MAX_MEMORY_CONTEXT_CHARS]

    return load


def _from_row(row: sqlite3.Row) -> CompanionProfile:
    raw_tools = json.loads(str(row["granted_tools"] or "[]"))
    return CompanionProfile(
        id=str(row["id"]),
        workspace_id=str(row["workspace_id"]),
        name=str(row["name"]),
        instructions=str(row["instructions"]),
        memory_scope=str(row["memory_scope"]),
        granted_tools=_clean_tools(raw_tools if isinstance(raw_tools, list) else []),
        enabled=bool(row["enabled"]),
        created_at=str(row["created_at"]),
        updated_at=str(row["updated_at"]),
    )
