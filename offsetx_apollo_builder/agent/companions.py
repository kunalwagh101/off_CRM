"""Persisted companion profiles with isolated memory and tool grants.

A companion is configuration around existing capabilities, not another agent
engine. Profiles live as rows beside the existing owner-pinned tool registry,
so profile updates and grants inherit SQLite's transactional/concurrent-writer
behaviour instead of creating another JSON persistence mechanism.
"""
from __future__ import annotations

import re
import sqlite3
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Sequence

from ..ai.errors import PolicyViolation
from ..ai.sandbox import SandboxPolicy, SandboxWorkspace
from ..ai.tiers import DataClass
from ..ai.tools import ToolRegistry, ToolRun
from ..outreach.models import to_utc_iso

_NAME = re.compile(r"^[^\x00\r\n]{1,100}$")
_SCOPE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9:_-]{0,159}$")
MAX_INSTRUCTIONS = 12_000
MAX_TOOLS = 100

SCHEMA = """
CREATE TABLE IF NOT EXISTS agent_companions (
    id TEXT PRIMARY KEY,
    workspace_id TEXT NOT NULL,
    name TEXT NOT NULL,
    instructions TEXT NOT NULL,
    memory_scope TEXT NOT NULL,
    granted_tool_ids TEXT NOT NULL DEFAULT '[]',
    enabled INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE UNIQUE INDEX IF NOT EXISTS ux_agent_companions_name
    ON agent_companions(workspace_id, lower(name));
CREATE UNIQUE INDEX IF NOT EXISTS ux_agent_companions_memory_scope
    ON agent_companions(workspace_id, memory_scope);
CREATE INDEX IF NOT EXISTS ix_agent_companions_workspace
    ON agent_companions(workspace_id, enabled, name);
"""


class CompanionError(ValueError):
    """A companion profile is missing, invalid or crosses a security boundary."""


@dataclass(frozen=True, slots=True)
class Companion:
    id: str
    workspace_id: str
    name: str
    instructions: str
    memory_scope: str
    granted_tool_ids: tuple[str, ...]
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
            "granted_tool_ids": list(self.granted_tool_ids),
            "enabled": self.enabled,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_row(cls, row: Any) -> "Companion":
        import json

        try:
            granted = json.loads(str(row["granted_tool_ids"] or "[]"))
        except (TypeError, ValueError, json.JSONDecodeError) as exc:
            raise CompanionError(
                f"Companion {row['id']!r} has corrupt granted_tool_ids"
            ) from exc
        if not isinstance(granted, list):
            raise CompanionError(
                f"Companion {row['id']!r} has corrupt granted_tool_ids"
            )
        return cls(
            id=str(row["id"]),
            workspace_id=str(row["workspace_id"]),
            name=str(row["name"]),
            instructions=str(row["instructions"]),
            memory_scope=str(row["memory_scope"]),
            granted_tool_ids=tuple(str(item) for item in granted),
            enabled=bool(row["enabled"]),
            created_at=str(row["created_at"]),
            updated_at=str(row["updated_at"]),
        )


@dataclass(frozen=True, slots=True)
class CompanionContext:
    profile: Companion
    tools: tuple[dict[str, Any], ...]
    memory: tuple[dict[str, Any], ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "companion": self.profile.to_dict(),
            "tools": list(self.tools),
            "memory": list(self.memory),
        }


class CompanionRegistry:
    """Workspace-scoped companion persistence and runtime enforcement."""

    def __init__(
        self,
        data_dir: Path | str,
        *,
        tools: ToolRegistry,
        memory_backend: Any,
    ) -> None:
        self.data_dir = Path(data_dir)
        self.tools = tools
        self.memory = memory_backend
        conn = self.tools.connection()
        conn.execute("PRAGMA busy_timeout=5000")
        conn.executescript(SCHEMA)
        try:
            self.tools.path.chmod(0o600)
        except OSError:
            pass

    def rebind_memory(self, memory_backend: Any) -> None:
        """Rebind after a CRM database restore without changing profile storage."""
        self.memory = memory_backend

    @staticmethod
    def _workspace(value: str) -> str:
        workspace = str(value or "").strip()
        if not workspace or len(workspace) > 120 or "\x00" in workspace:
            raise CompanionError("workspace_id must be a non-empty bounded string")
        return workspace

    @staticmethod
    def _name(value: str) -> str:
        name = str(value or "").strip()
        if not _NAME.fullmatch(name):
            raise CompanionError("Companion name must be 1-100 characters on one line")
        return name

    @staticmethod
    def _instructions(value: str) -> str:
        text = str(value or "").strip()
        if not text:
            raise CompanionError("Companion instructions must not be empty")
        if len(text) > MAX_INSTRUCTIONS or "\x00" in text:
            raise CompanionError(
                f"Companion instructions may be at most {MAX_INSTRUCTIONS} characters"
            )
        return text

    @staticmethod
    def _scope(value: str) -> str:
        scope = str(value or "").strip()
        if not _SCOPE.fullmatch(scope) or "*" in scope:
            raise CompanionError(
                "Companion memory_scope must be an exact bounded scope, not a wildcard"
            )
        return scope

    @staticmethod
    def _tool_ids(values: Iterable[str]) -> tuple[str, ...]:
        if not isinstance(values, (list, tuple)):
            raise CompanionError("granted_tool_ids must be a list of tool ids")
        result = tuple(
            dict.fromkeys(
                str(item or "").strip()
                for item in values
                if str(item or "").strip()
            )
        )
        if len(result) > MAX_TOOLS:
            raise CompanionError(f"A companion may grant at most {MAX_TOOLS} tools")
        return result

    def _validate_tools(self, workspace_id: str, tool_ids: Sequence[str]) -> None:
        for tool_id in tool_ids:
            if self.tools.get(tool_id, workspace_id=workspace_id) is None:
                raise CompanionError(
                    f"Tool {tool_id!r} is not registered in workspace {workspace_id!r}"
                )

    @staticmethod
    def _encode_tools(tool_ids: Sequence[str]) -> str:
        import json
        return json.dumps(list(tool_ids), separators=(",", ":"))

    def create(
        self,
        *,
        workspace_id: str,
        name: str,
        instructions: str,
        granted_tool_ids: Iterable[str] = (),
        memory_scope: str = "",
    ) -> Companion:
        workspace = self._workspace(workspace_id)
        identifier = uuid.uuid4().hex
        profile_name = self._name(name)
        profile_instructions = self._instructions(instructions)
        scope = self._scope(memory_scope or f"companion:{identifier}")
        tool_ids = self._tool_ids(granted_tool_ids)
        self._validate_tools(workspace, tool_ids)
        now = to_utc_iso()
        conn = self.tools.connection()
        try:
            with conn:
                conn.execute(
                    """
                    INSERT INTO agent_companions(
                        id, workspace_id, name, instructions, memory_scope,
                        granted_tool_ids, enabled, created_at, updated_at
                    ) VALUES(?,?,?,?,?,?,1,?,?)
                    """,
                    (
                        identifier,
                        workspace,
                        profile_name,
                        profile_instructions,
                        scope,
                        self._encode_tools(tool_ids),
                        now,
                        now,
                    ),
                )
        except sqlite3.IntegrityError as exc:
            message = str(exc).lower()
            if "memory_scope" in message:
                raise CompanionError(
                    f"Memory scope {scope!r} already belongs to another companion"
                ) from exc
            raise CompanionError(
                f"A companion named {profile_name!r} already exists"
            ) from exc
        return self.require(identifier, workspace_id=workspace)

    def get(self, companion_id: str, *, workspace_id: str) -> Companion | None:
        workspace = self._workspace(workspace_id)
        row = self.tools.connection().execute(
            """
            SELECT * FROM agent_companions
            WHERE id = ? AND workspace_id = ?
            """,
            (str(companion_id), workspace),
        ).fetchone()
        return Companion.from_row(row) if row is not None else None

    def require(self, companion_id: str, *, workspace_id: str) -> Companion:
        profile = self.get(companion_id, workspace_id=workspace_id)
        if profile is None:
            raise CompanionError(
                f"Companion {companion_id!r} does not exist in workspace {workspace_id!r}"
            )
        return profile

    def list(self, *, workspace_id: str) -> list[Companion]:
        workspace = self._workspace(workspace_id)
        rows = self.tools.connection().execute(
            """
            SELECT * FROM agent_companions
            WHERE workspace_id = ?
            ORDER BY lower(name), id
            """,
            (workspace,),
        ).fetchall()
        return [Companion.from_row(row) for row in rows]

    def update(
        self,
        companion_id: str,
        *,
        workspace_id: str,
        name: str | None = None,
        instructions: str | None = None,
        granted_tool_ids: Iterable[str] | None = None,
        memory_scope: str | None = None,
        enabled: bool | None = None,
    ) -> Companion:
        workspace = self._workspace(workspace_id)
        current = self.require(companion_id, workspace_id=workspace)
        next_name = current.name if name is None else self._name(name)
        next_instructions = (
            current.instructions
            if instructions is None
            else self._instructions(instructions)
        )
        next_scope = (
            current.memory_scope
            if memory_scope is None
            else self._scope(memory_scope)
        )
        next_tools = (
            current.granted_tool_ids
            if granted_tool_ids is None
            else self._tool_ids(granted_tool_ids)
        )
        self._validate_tools(workspace, next_tools)
        if enabled is not None and not isinstance(enabled, bool):
            raise CompanionError("enabled must be true or false")
        conn = self.tools.connection()
        try:
            with conn:
                cursor = conn.execute(
                    """
                    UPDATE agent_companions
                    SET name = ?, instructions = ?, memory_scope = ?,
                        granted_tool_ids = ?, enabled = ?, updated_at = ?
                    WHERE id = ? AND workspace_id = ?
                    """,
                    (
                        next_name,
                        next_instructions,
                        next_scope,
                        self._encode_tools(next_tools),
                        int(current.enabled if enabled is None else enabled),
                        to_utc_iso(),
                        current.id,
                        workspace,
                    ),
                )
                if cursor.rowcount != 1:
                    raise CompanionError(f"Companion {companion_id!r} does not exist")
        except sqlite3.IntegrityError as exc:
            message = str(exc).lower()
            if "memory_scope" in message:
                raise CompanionError(
                    f"Memory scope {next_scope!r} already belongs to another companion"
                ) from exc
            raise CompanionError(
                f"A companion named {next_name!r} already exists"
            ) from exc
        return self.require(current.id, workspace_id=workspace)

    def delete(self, companion_id: str, *, workspace_id: str) -> bool:
        workspace = self._workspace(workspace_id)
        conn = self.tools.connection()
        with conn:
            cursor = conn.execute(
                "DELETE FROM agent_companions WHERE id = ? AND workspace_id = ?",
                (str(companion_id), workspace),
            )
        return cursor.rowcount > 0

    def start(
        self,
        companion_id: str,
        *,
        workspace_id: str,
        memory_query: str = "",
        memory_limit: int = 8,
    ) -> CompanionContext:
        """Resolve exactly what one run under this companion is allowed to see."""
        profile = self.require(companion_id, workspace_id=workspace_id)
        if not profile.enabled:
            raise CompanionError(f"Companion {profile.name!r} is disabled")
        if isinstance(memory_limit, bool) or not isinstance(memory_limit, int):
            raise CompanionError("memory_limit must be an integer between 0 and 50")
        if memory_limit < 0 or memory_limit > 50:
            raise CompanionError("memory_limit must be between 0 and 50")

        tool_rows: list[dict[str, Any]] = []
        for tool_id in profile.granted_tool_ids:
            tool = self.tools.get(tool_id, workspace_id=workspace_id)
            if tool is not None and tool.enabled:
                tool_rows.append(tool.catalogue_entry())

        memory_rows: list[dict[str, Any]] = []
        if memory_limit:
            memory_rows, _ = self.memory.search_memory_items(
                str(memory_query or ""),
                workspace_id=workspace_id,
                scope=profile.memory_scope,
                approved_only=True,
                limit=memory_limit,
                offset=0,
            )
        return CompanionContext(
            profile=profile,
            tools=tuple(tool_rows),
            memory=tuple(memory_rows),
        )

    def remember(
        self,
        companion_id: str,
        *,
        workspace_id: str,
        content: str,
        kind: str = "companion_fact",
        tags: Iterable[str] = (),
        approved: bool = False,
    ) -> str:
        """Write only into this companion's exact memory scope."""
        profile = self.require(companion_id, workspace_id=workspace_id)
        return self.memory.add_memory_item(
            workspace_id=workspace_id,
            scope=profile.memory_scope,
            kind=str(kind or "companion_fact"),
            content=str(content or ""),
            tags=list(tags),
            metadata={"companion_id": profile.id},
            confidence=1.0 if approved else 0.7,
            approved=bool(approved),
            source_type="companion",
        )

    def run_tool(
        self,
        companion_id: str,
        tool_id: str,
        *,
        workspace_id: str,
        workspace: SandboxWorkspace,
        extra_arguments: Sequence[str] = (),
        data_class: DataClass = DataClass.PUBLIC,
        policy: SandboxPolicy | None = None,
        timeout_seconds: int = 600,
        fetch_source: bool = True,
    ) -> ToolRun:
        """Execution-time grant enforcement; hiding a tool from a prompt is not enough."""
        profile = self.require(companion_id, workspace_id=workspace_id)
        if not profile.enabled:
            raise CompanionError(f"Companion {profile.name!r} is disabled")
        if str(tool_id) not in profile.granted_tool_ids:
            raise PolicyViolation(
                f"Companion {profile.name!r} is not granted tool {tool_id!r}"
            )
        tool = self.tools.get(str(tool_id), workspace_id=workspace_id)
        if tool is None:
            raise PolicyViolation("The granted tool no longer exists in this workspace")
        if not tool.enabled:
            raise PolicyViolation(f"Tool {tool.name!r} is disabled")
        return self.tools.run(
            tool.id,
            workspace=workspace,
            extra_arguments=extra_arguments,
            data_class=data_class,
            policy=policy,
            workspace_id=workspace_id,
            timeout_seconds=timeout_seconds,
            fetch_source=fetch_source,
        )
