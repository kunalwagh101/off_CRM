"""Process-local owner cancellation for bounded chat browser runs.

A run is tied to one chat in one workspace. No durable record is implied.
The existing durable workspace browser lease remains the cross-process guard.
"""
from __future__ import annotations

import asyncio
import threading
import uuid
from dataclasses import dataclass


@dataclass(frozen=True)
class _Active:
    run_id: str
    task: asyncio.Task
    loop: asyncio.AbstractEventLoop


class ChatBrowserRuns:
    """In-flight tasks only; cancellation is a request, never a success claim."""

    def __init__(self) -> None:
        self._guard = threading.RLock()
        self._runs: dict[tuple[str, str], _Active] = {}

    def register(self, workspace_id: str, chat_id: str, task: asyncio.Task) -> str:
        with self._guard:
            key = (workspace_id, chat_id)
            previous = self._runs.get(key)
            if previous is not None and not previous.task.done():
                raise ValueError("Chat already has a browser run")
            run_id = uuid.uuid4().hex
            self._runs[key] = _Active(run_id, task, task.get_loop())
            return run_id

    def active(self, workspace_id: str, chat_id: str) -> dict[str, object] | None:
        with self._guard:
            record = self._runs.get((workspace_id, chat_id))
            if record is None or record.task.done():
                return None
            return {"run_id": record.run_id, "active": True}

    def cancel(self, workspace_id: str, chat_id: str, run_id: str) -> bool:
        with self._guard:
            record = self._runs.get((workspace_id, chat_id))
            if record is None or record.run_id != run_id or record.task.done():
                return False
            record.loop.call_soon_threadsafe(record.task.cancel)
            return True

    def finish(self, workspace_id: str, chat_id: str, run_id: str) -> None:
        with self._guard:
            key = (workspace_id, chat_id)
            record = self._runs.get(key)
            if record is not None and record.run_id == run_id:
                self._runs.pop(key, None)

    def revoke_chat(self, workspace_id: str, chat_id: str) -> None:
        with self._guard:
            record = self._runs.pop((workspace_id, chat_id), None)
            if record is not None and not record.task.done():
                record.loop.call_soon_threadsafe(record.task.cancel)

    def close(self) -> None:
        """On shutdown/restore, cancel all references before closing stores."""
        with self._guard:
            records = list(self._runs.values())
            self._runs.clear()
        for record in records:
            if not record.task.done():
                record.loop.call_soon_threadsafe(record.task.cancel)
