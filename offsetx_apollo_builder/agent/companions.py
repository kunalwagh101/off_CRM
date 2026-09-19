"""Persisted companion profiles with isolated memory and tool grants.

A companion is configuration around existing capabilities, not another agent
engine. The profile stores its instructions, one exact memory scope and the IDs
of owner-pinned tools it may use. Runtime resolution re-checks every grant
against the current ToolRegistry, so disabling/removing a tool takes effect
immediately.
"""
from __future__ import annotations

import json
import re
import threading
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Sequence

from ..ai.errors import PolicyViolation
from ..ai.sandbox import SandboxPolicy, SandboxWorkspace
from ..ai.tiers import DataClass
from ..ai.tools import ToolRegistry, ToolRun
from ..ai.workspace import atomic_json
from ..outreach.models import to_utc_iso

_NAME = re.compile(r"^[^\x00\r\n]{1,100}$")
_SCOPE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9:_-]{0,159}$")
MAX_INSTRUCTIONS = 12_000
MAX_TOOLS = 100


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
    def from_dict(cls, raw: dict[str, Any]) -> "Companion":
        return cls(
            id=str(raw["id"]),
            workspace_id=str(raw["workspace_id"]),
            name=str(raw["name"]),
            instructions=str(raw["instructions"]),
            memory_scope=str(raw["memory_scope"]),
            granted_tool_ids=tuple(str(item) for item in raw.get("granted_tool_ids", [])),
            enabled=bool(raw.get("enabled", True)),
            created_at=str(raw.get("created_at") or ""),
            updated_at=str(raw.get("updated_at") or ""),
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

    _locks: dict[str, threading.RLock] = {}
    _locks_guard = threading.Lock()

    def __init__(
        self,
        data_dir: Path | str,
        *,
        tools: ToolRegistry,
        memory_backend: Any,
    ) -> None:
        self.path = Path(data_dir) / "companions.json"
        self.tools = tools
        self.memory = memory_backend
        self._lock = self._lock_for(self.path)

    def rebind_memory(self, memory_backend: Any) -> None:
        """Rebind after a CRM database restore without changing profile storage."""
        self.memory = memory_backend


    @classmethod
    def _lock_for(cls, path: Path) -> threading.RLock:
        key = str(path.resolve())
        with cls._locks_guard:
            return cls._locks.setdefault(key, threading.RLock())

    def _document(self) -> dict[str, Any]:
        if not self.path.exists():
            return {"version": 1, "workspaces": {}}
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise CompanionError(
                f"Companion registry at {self.path} cannot be read safely"
            ) from exc
        if not isinstance(raw, dict) or raw.get("version") != 1:
            raise CompanionError("Companion registry has an unsupported format")
        workspaces = raw.get("workspaces")
        if not isinstance(workspaces, dict):
            raise CompanionError("Companion registry workspaces must be an object")
        return raw

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
        if isinstance(values, (str, bytes)):
            raise CompanionError("granted_tool_ids must be a list of tool ids")
        result = tuple(dict.fromkeys(str(item or "").strip() for item in values if str(item or "").strip()))
        if len(result) > MAX_TOOLS:
            raise CompanionError(f"A companion may grant at most {MAX_TOOLS} tools")
        return result

    def _validate_tools(self, workspace_id: str, tool_ids: Sequence[str]) -> None:
        for tool_id in tool_ids:
            if self.tools.get(tool_id, workspace_id=workspace_id) is None:
                raise CompanionError(
                    f"Tool {tool_id!r} is not registered in workspace {workspace_id!r}"
                )

    def _rows(self, document: dict[str, Any], workspace_id: str) -> dict[str, Any]:
        workspaces = document["workspaces"]
        rows = workspaces.get(workspace_id)
        if rows is None:
            rows = {}
            workspaces[workspace_id] = rows
        if not isinstance(rows, dict):
            raise CompanionError(f"Companion workspace {workspace_id!r} is corrupt")
        return rows

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
        scope = self._scope(memory_scope or f"companion:{identifier}")
        tools = self._tool_ids(granted_tool_ids)
        self._validate_tools(workspace, tools)
        now = to_utc_iso()
        profile = Companion(
            id=identifier,
            workspace_id=workspace,
            name=self._name(name),
            instructions=self._instructions(instructions),
            memory_scope=scope,
            granted_tool_ids=tools,
            enabled=True,
            created_at=now,
            updated_at=now,
        )
        with self._lock:
            document = self._document()
            rows = self._rows(document, workspace)
            if any(str(row.get("name", "")).casefold() == profile.name.casefold() for row in rows.values() if isinstance(row, dict)):
                raise CompanionError(f"A companion named {profile.name!r} already exists")
            if any(str(row.get("memory_scope", "")) == scope for row in rows.values() if isinstance(row, dict)):
                raise CompanionError(f"Memory scope {scope!r} already belongs to another companion")
            rows[identifier] = profile.to_dict()
            atomic_json(self.path, document)
        return profile

    def get(self, companion_id: str, *, workspace_id: str) -> Companion | None:
        workspace = self._workspace(workspace_id)
        with self._lock:
            rows = self._rows(self._document(), workspace)
            raw = rows.get(str(companion_id))
        return Companion.from_dict(raw) if isinstance(raw, dict) else None

    def require(self, companion_id: str, *, workspace_id: str) -> Companion:
        profile = self.get(companion_id, workspace_id=workspace_id)
        if profile is None:
            raise CompanionError(
                f"Companion {companion_id!r} does not exist in workspace {workspace_id!r}"
            )
        return profile

    def list(self, *, workspace_id: str) -> list[Companion]:
        workspace = self._workspace(workspace_id)
        with self._lock:
            rows = self._rows(self._document(), workspace)
            values = [
                Companion.from_dict(raw)
                for raw in rows.values()
                if isinstance(raw, dict)
            ]
        return sorted(values, key=lambda item: (item.name.casefold(), item.id))

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
        with self._lock:
            document = self._document()
            rows = self._rows(document, workspace)
            raw = rows.get(str(companion_id))
            if not isinstance(raw, dict):
                raise CompanionError(f"Companion {companion_id!r} does not exist")
            current = Companion.from_dict(raw)
            next_name = current.name if name is None else self._name(name)
            next_instructions = (
                current.instructions if instructions is None else self._instructions(instructions)
            )
            next_scope = current.memory_scope if memory_scope is None else self._scope(memory_scope)
            next_tools = (
                current.granted_tool_ids
                if granted_tool_ids is None
                else self._tool_ids(granted_tool_ids)
            )
            self._validate_tools(workspace, next_tools)
            if any(
                key != current.id
                and isinstance(row, dict)
                and str(row.get("name", "")).casefold() == next_name.casefold()
                for key, row in rows.items()
            ):
                raise CompanionError(f"A companion named {next_name!r} already exists")
            if any(
                key != current.id
                and isinstance(row, dict)
                and str(row.get("memory_scope", "")) == next_scope
                for key, row in rows.items()
            ):
                raise CompanionError(
                    f"Memory scope {next_scope!r} already belongs to another companion"
                )
            if enabled is not None and not isinstance(enabled, bool):
                raise CompanionError("enabled must be true or false")
            profile = Companion(
                id=current.id,
                workspace_id=workspace,
                name=next_name,
                instructions=next_instructions,
                memory_scope=next_scope,
                granted_tool_ids=next_tools,
                enabled=current.enabled if enabled is None else bool(enabled),
                created_at=current.created_at,
                updated_at=to_utc_iso(),
            )
            rows[current.id] = profile.to_dict()
            atomic_json(self.path, document)
        return profile

    def delete(self, companion_id: str, *, workspace_id: str) -> bool:
        workspace = self._workspace(workspace_id)
        with self._lock:
            document = self._document()
            rows = self._rows(document, workspace)
            existed = rows.pop(str(companion_id), None) is not None
            if existed:
                atomic_json(self.path, document)
            return existed

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

        tools: list[dict[str, Any]] = []
        for tool_id in profile.granted_tool_ids:
            tool = self.tools.get(tool_id, workspace_id=workspace_id)
            if tool is not None and tool.enabled:
                tools.append(tool.catalogue_entry())

        memory: list[dict[str, Any]] = []
        if memory_limit:
            memory, _ = self.memory.search_memory_items(
                str(memory_query or ""),
                workspace_id=workspace_id,
                scope=profile.memory_scope,
                approved_only=True,
                limit=memory_limit,
                offset=0,
            )
        return CompanionContext(
            profile=profile,
            tools=tuple(tools),
            memory=tuple(memory),
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
