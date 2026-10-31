"""Workspace and per-browser-tool policy, with non-durable chat permissions."""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from threading import RLock
from typing import Any, Mapping
from ..browser.page import ACTIONS

TOOLS = frozenset(ACTIONS)
MODES = frozenset(("allow", "ask", "deny"))


class PermissionErrorRule(ValueError):
    """A malformed permission must never widen access."""


@dataclass(frozen=True, slots=True)
class AgentPermissionPolicy:
    global_mode: str = "allow"
    tool_rules: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if type(self.global_mode) is not str or self.global_mode not in MODES:
            raise PermissionErrorRule("global_mode must be allow, ask or deny")
        if not isinstance(self.tool_rules, Mapping) or len(self.tool_rules) > len(TOOLS):
            raise PermissionErrorRule("tool_rules must be a bounded object")
        for tool, mode in self.tool_rules.items():
            if tool not in TOOLS:
                raise PermissionErrorRule("Unknown browser tool")
            if type(mode) is not str or mode not in MODES:
                raise PermissionErrorRule("Tool mode must be allow, ask or deny")

    @classmethod
    def from_mapping(cls, value: Any) -> "AgentPermissionPolicy":
        if not isinstance(value, Mapping) or set(value) - {"global_mode", "tool_rules"}:
            raise PermissionErrorRule("Unknown agent permission policy fields")
        return cls(value.get("global_mode", "allow"), value.get("tool_rules", {}))

    def to_dict(self) -> dict[str, Any]:
        return {"global_mode": self.global_mode, "tool_rules": dict(self.tool_rules)}

    def decide(self, tool: str, *, grants: "ChatPermissionGrants | None" = None) -> str:
        if tool not in TOOLS or self.global_mode == "deny":
            return "deny"
        mode = self.tool_rules.get(tool, self.global_mode)
        if mode == "ask" and grants and grants.permitted(tool):
            return "allow"
        return mode


class ChatPermissionGrants:
    """A live attended conversation's bounded, local-only grants."""
    def __init__(self, *, chat_id: str, lifetime_seconds: float = 3600.0):
        if not isinstance(chat_id, str) or not (1 <= len(chat_id) <= 128) or not chat_id.strip():
            raise PermissionErrorRule("Invalid chat identifier")
        if not (0 < lifetime_seconds <= 3600):
            raise PermissionErrorRule("Chat grant lifetime must be at most one hour")
        self.chat_id = chat_id
        self._deadline = time.monotonic() + lifetime_seconds
        self._closed = False
        self._tools: set[str] = set()

    def grant(self, tool: str) -> None:
        if self._closed or time.monotonic() >= self._deadline:
            raise PermissionErrorRule("Chat permission has expired")
        if tool not in TOOLS:
            raise PermissionErrorRule("Unknown browser tool")
        self._tools.add(tool)

    def permitted(self, tool: str) -> bool:
        return not self._closed and time.monotonic() < self._deadline and tool in self._tools

    @property
    def active(self) -> bool:
        return not self._closed and time.monotonic() < self._deadline

    @property
    def granted_tools(self) -> list[str]:
        return sorted(self._tools) if self.active else []

    def close(self) -> None:
        self._closed = True
        self._tools.clear()


class ChatPermissionRegistry:
    """Per-process, workspace-scoped approval records; never stored or restored."""

    MAX_ACTIVE = 256

    def __init__(self) -> None:
        self._lock = RLock()
        self._grants: dict[tuple[str, str], ChatPermissionGrants] = {}

    def get(self, workspace_id: str, chat_id: str) -> ChatPermissionGrants | None:
        with self._lock:
            key = (workspace_id, chat_id)
            value = self._grants.get(key)
            if value is not None and not value.active:
                value.close()
                self._grants.pop(key, None)
                return None
            return value

    def grant(self, workspace_id: str, chat_id: str, tool: str) -> ChatPermissionGrants:
        with self._lock:
            current = self.get(workspace_id, chat_id)
            if current is None:
                if len(self._grants) >= self.MAX_ACTIVE:
                    for key, value in list(self._grants.items()):
                        if not value.active:
                            value.close()
                            del self._grants[key]
                if len(self._grants) >= self.MAX_ACTIVE:
                    raise PermissionErrorRule("Too many active attended chats; close a chat first")
                current = ChatPermissionGrants(chat_id=chat_id)
                self._grants[(workspace_id, chat_id)] = current
            current.grant(tool)
            return current

    def close(self, workspace_id: str, chat_id: str) -> None:
        with self._lock:
            grant = self._grants.pop((workspace_id, chat_id), None)
            if grant is not None:
                grant.close()

    def close_all(self) -> None:
        with self._lock:
            for grant in self._grants.values():
                grant.close()
            self._grants.clear()
