"""AI Copilot chat: persistent multi-turn conversations routed through the
configured provider chain.

Security note: messages are sanitised with the same data-policy redaction as
the email engine.  The AI never receives raw CRM data unless the prompt
explicitly includes it via a future context-injection feature.
"""
from __future__ import annotations

import uuid
from typing import Any

from .models import clean_text, to_utc_iso
from .store import OutreachStore


class AIChatService:
    def __init__(self, store: OutreachStore) -> None:
        self.store = store

    # ── projects ────────────────────────────────────────────────────────────

    def list_projects(self, workspace_id: str = "local") -> list[dict[str, Any]]:
        rows = self.store.connection.execute(
            "SELECT id, name, created_at FROM ai_chat_projects "
            "WHERE workspace_id = ? ORDER BY name ASC",
            (workspace_id,),
        ).fetchall()
        return [dict(r) for r in rows]

    def create_project(self, name: str, workspace_id: str = "local") -> dict[str, Any]:
        name = clean_text(name)[:120]
        if not name:
            raise ValueError("Project name is required")
        now = to_utc_iso()
        row_id = str(uuid.uuid4())
        with self.store.transaction(immediate=True):
            self.store.connection.execute(
                "INSERT INTO ai_chat_projects(id, workspace_id, name, created_at) VALUES(?,?,?,?)",
                (row_id, workspace_id, name, now),
            )
        return {"id": row_id, "name": name, "created_at": now}

    def delete_project(self, project_id: str, workspace_id: str = "local") -> None:
        with self.store.transaction(immediate=True):
            self.store.connection.execute(
                "DELETE FROM ai_chat_projects WHERE id = ? AND workspace_id = ?",
                (project_id, workspace_id),
            )

    # ── chats ────────────────────────────────────────────────────────────────

    def list_chats(
        self,
        workspace_id: str = "local",
        project_id: str | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        if project_id is not None:
            rows = self.store.connection.execute(
                "SELECT id, title, project_id, created_at, updated_at "
                "FROM ai_chats WHERE workspace_id = ? AND project_id = ? "
                "ORDER BY updated_at DESC LIMIT ?",
                (workspace_id, project_id, limit),
            ).fetchall()
        else:
            rows = self.store.connection.execute(
                "SELECT id, title, project_id, created_at, updated_at "
                "FROM ai_chats WHERE workspace_id = ? "
                "ORDER BY updated_at DESC LIMIT ?",
                (workspace_id, limit),
            ).fetchall()
        return [dict(r) for r in rows]

    def create_chat(
        self,
        title: str = "New chat",
        project_id: str | None = None,
        workspace_id: str = "local",
    ) -> dict[str, Any]:
        now = to_utc_iso()
        chat_id = str(uuid.uuid4())
        title = clean_text(title)[:200] or "New chat"
        with self.store.transaction(immediate=True):
            self.store.connection.execute(
                "INSERT INTO ai_chats(id, workspace_id, title, project_id, created_at, updated_at)"
                " VALUES(?,?,?,?,?,?)",
                (chat_id, workspace_id, title, project_id, now, now),
            )
        return {"id": chat_id, "title": title, "project_id": project_id,
                "created_at": now, "updated_at": now}

    def get_chat(self, chat_id: str, workspace_id: str = "local") -> dict[str, Any] | None:
        row = self.store.connection.execute(
            "SELECT id, title, project_id, created_at, updated_at "
            "FROM ai_chats WHERE id = ? AND workspace_id = ?",
            (chat_id, workspace_id),
        ).fetchone()
        return dict(row) if row else None

    def delete_chat(self, chat_id: str, workspace_id: str = "local") -> None:
        with self.store.transaction(immediate=True):
            self.store.connection.execute(
                "DELETE FROM ai_chats WHERE id = ? AND workspace_id = ?",
                (chat_id, workspace_id),
            )

    def move_chat(
        self,
        chat_id: str,
        project_id: str | None,
        workspace_id: str = "local",
    ) -> dict[str, Any] | None:
        now = to_utc_iso()
        with self.store.transaction(immediate=True):
            self.store.connection.execute(
                "UPDATE ai_chats SET project_id = ?, updated_at = ? "
                "WHERE id = ? AND workspace_id = ?",
                (project_id, now, chat_id, workspace_id),
            )
        return self.get_chat(chat_id, workspace_id)

    def rename_chat(
        self, chat_id: str, title: str, workspace_id: str = "local"
    ) -> dict[str, Any] | None:
        title = clean_text(title)[:200] or "New chat"
        now = to_utc_iso()
        with self.store.transaction(immediate=True):
            self.store.connection.execute(
                "UPDATE ai_chats SET title = ?, updated_at = ? "
                "WHERE id = ? AND workspace_id = ?",
                (title, now, chat_id, workspace_id),
            )
        return self.get_chat(chat_id, workspace_id)

    # ── messages ─────────────────────────────────────────────────────────────

    def list_messages(self, chat_id: str) -> list[dict[str, Any]]:
        rows = self.store.connection.execute(
            "SELECT id, role, content, provider, model, created_at "
            "FROM ai_messages WHERE chat_id = ? ORDER BY created_at ASC",
            (chat_id,),
        ).fetchall()
        return [dict(r) for r in rows]

    def add_message(
        self,
        chat_id: str,
        role: str,
        content: str,
        provider: str = "",
        model: str = "",
        workspace_id: str = "local",
    ) -> dict[str, Any]:
        now = to_utc_iso()
        msg_id = str(uuid.uuid4())
        with self.store.transaction(immediate=True):
            self.store.connection.execute(
                "INSERT INTO ai_messages(id, chat_id, role, content, provider, model, created_at)"
                " VALUES(?,?,?,?,?,?,?)",
                (msg_id, chat_id, role, content, provider, model, now),
            )
            self.store.connection.execute(
                "UPDATE ai_chats SET updated_at = ? WHERE id = ? AND workspace_id = ?",
                (now, chat_id, workspace_id),
            )
        return {"id": msg_id, "role": role, "content": content,
                "provider": provider, "model": model, "created_at": now}

    def send_message(
        self,
        *,
        chat_id: str,
        user_content: str,
        provider_fn: Any,
        workspace_id: str = "local",
        system_prompt: str = (
            "You are a helpful AI assistant embedded in off_CRM, "
            "a local-first B2B outreach CRM. Help the user with their "
            "sales strategy, email copy, lead research, and CRM questions. "
            "Be concise and direct."
        ),
    ) -> dict[str, Any]:
        """Store user message, call the provider, store and return the reply."""
        user_content = clean_text(user_content)
        if not user_content:
            raise ValueError("Message content is required")

        self.add_message(chat_id, "user", user_content, workspace_id=workspace_id)

        history = self.list_messages(chat_id)
        history_text = "\n\n".join(
            f"[{m['role'].upper()}]: {m['content']}"
            for m in history
            if m["role"] in ("user", "assistant")
        )

        result = provider_fn(system_prompt=system_prompt, user_prompt=history_text)
        reply_content = clean_text(str(result.get("text", result) if isinstance(result, dict) else result))
        provider_name = str(result.get("provider", "") if isinstance(result, dict) else "")
        model_name = str(result.get("model", "") if isinstance(result, dict) else "")

        # Auto-title from first user message
        chat = self.get_chat(chat_id, workspace_id)
        if chat and chat["title"] == "New chat":
            auto_title = user_content[:60].rstrip() + ("…" if len(user_content) > 60 else "")
            self.rename_chat(chat_id, auto_title, workspace_id)

        return self.add_message(
            chat_id, "assistant", reply_content, provider_name, model_name, workspace_id
        )
