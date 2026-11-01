from __future__ import annotations

import asyncio
import json
import os
import threading
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any, Callable

from ..db.hosted import HostedStorage
from .models import to_utc_iso
from .workspace_lock import WorkspaceLock
from ..observability import ReportedFailure, failure_boundary, failure_message, failure_summary, report_failure


DEFAULT_AUTOMATION = {
    "enabled": False,
    "mode": "local",
    "interval_seconds": 300,
    "max_messages_per_campaign": 25,
    "sync_replies_first": True,
    "gmail_live_authorized": False,
}


class AutomationService:
    """Durable local scheduler for reply sync and due follow-ups."""

    def __init__(
        self,
        path: Path | str,
        *,
        engine_factory: Callable[[], Any],
        mail_provider_factory: Callable[[str, bool], Any],
        own_email_factory: Callable[[], str],
        hosted_storage: HostedStorage | None = None,
    ):
        self.path = Path(path)
        self.hosted_storage = hosted_storage
        if hosted_storage is not None and self.path.is_file():
            raise ValueError(
                "Existing local timer settings require an explicit migration before hosted storage starts. "
                "Keep the local file and resolve it with the install owner."
            )
        self.engine_factory = engine_factory
        self.mail_provider_factory = mail_provider_factory
        self.own_email_factory = own_email_factory
        self._task: asyncio.Task[None] | None = None
        self._stop = asyncio.Event()
        self._run_lock = threading.Lock()
        self.last_run_at = ""
        self.last_error = ""
        self.last_results: list[dict[str, Any]] = []

    def config(self) -> dict[str, Any]:
        payload = dict(DEFAULT_AUTOMATION)
        try:
            if self.hosted_storage is not None:
                body = self.hosted_storage.read("timer.email")
            else:
                body = self.path.read_text(encoding="utf-8") if self.path.exists() else None
            if body is not None:
                stored = json.loads(body)
                if isinstance(stored, dict):
                    payload.update(stored)
        except (OSError, json.JSONDecodeError) as exc:
            self.last_error = "Automation settings are invalid; safe defaults are active. " + failure_message(exc, operation="email.automation.settings", data_dir=self.path.parent)
        payload["enabled"] = bool(payload.get("enabled"))
        payload["mode"] = "gmail" if payload.get("mode") == "gmail" else "local"
        payload["interval_seconds"] = max(60, min(int(payload.get("interval_seconds", 300)), 86400))
        payload["max_messages_per_campaign"] = max(1, min(int(payload.get("max_messages_per_campaign", 25)), 500))
        payload["sync_replies_first"] = bool(payload.get("sync_replies_first", True))
        payload["gmail_live_authorized"] = bool(payload.get("gmail_live_authorized", False))
        return payload

    def update(self, values: dict[str, Any], *, gmail_confirmation: str = "") -> dict[str, Any]:
        if self.hosted_storage is not None:
            with self.hosted_storage.exclusive():
                return self._update(values, gmail_confirmation=gmail_confirmation)
        return self._update(values, gmail_confirmation=gmail_confirmation)

    def _update(self, values: dict[str, Any], *, gmail_confirmation: str) -> dict[str, Any]:
        config = self.config()
        for key in {"enabled", "mode", "interval_seconds", "max_messages_per_campaign", "sync_replies_first"}:
            if key in values:
                config[key] = values[key]
        if config.get("mode") == "gmail":
            if gmail_confirmation == "ENABLE AUTOMATED GMAIL":
                config["gmail_live_authorized"] = True
            elif not config.get("gmail_live_authorized"):
                raise ValueError("Automated Gmail requires confirmation: ENABLE AUTOMATED GMAIL")
        else:
            config["gmail_live_authorized"] = False
        normalized = dict(DEFAULT_AUTOMATION)
        normalized.update(config)
        normalized["enabled"] = bool(normalized["enabled"])
        normalized["mode"] = "gmail" if normalized["mode"] == "gmail" else "local"
        normalized["interval_seconds"] = max(60, min(int(normalized["interval_seconds"]), 86400))
        normalized["max_messages_per_campaign"] = max(1, min(int(normalized["max_messages_per_campaign"]), 500))
        if self.hosted_storage is not None:
            self.hosted_storage.write("timer.email", json.dumps(normalized, indent=2))
        else:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with NamedTemporaryFile("w", encoding="utf-8", dir=self.path.parent, delete=False) as handle:
                json.dump(normalized, handle, indent=2)
                temporary = Path(handle.name)
            os.replace(temporary, self.path)
        return self.status()

    def status(self) -> dict[str, Any]:
        return {**self.config(), "running": bool(self._task and not self._task.done()), "last_run_at": self.last_run_at, "last_error": self.last_error, "last_results": self.last_results}

    @failure_boundary
    def run_once(self) -> list[dict[str, Any]]:
        # A shared lease on the workspace for the whole cycle: a restore takes
        # it exclusively, so it cannot swap the files out from under a run
        # that is half way through writing them (S-06.02.21).
        with WorkspaceLock(self.path.parent):
            return self._run_once()

    def _run_once(self) -> list[dict[str, Any]]:
        if not self._run_lock.acquire(blocking=False):
            raise RuntimeError("An automation cycle is already running")
        engine = None
        try:
            config = self.config()
            engine = self.engine_factory()
            campaigns, _ = engine.store.list_campaigns(limit=200, status="active")
            results: list[dict[str, Any]] = []
            if not campaigns:
                self.last_run_at = to_utc_iso()
                self.last_results = results
                self.last_error = ""
                return results
            provider = self.mail_provider_factory(
                str(config["mode"]), bool(config["gmail_live_authorized"])
            )
            for campaign in campaigns:
                try:
                    result = engine.run_due(
                        str(campaign["id"]),
                        mail_provider=provider,
                        own_email=self.own_email_factory(),
                        sync_replies_first=bool(config["sync_replies_first"]),
                        max_messages=int(config["max_messages_per_campaign"]),
                    )
                    results.append({"campaign_id": campaign["id"], "campaign_name": campaign["name"], "sent_count": result["sent_count"], "replies_matched": result["replies"]["matched"], "failed_count": len(result["failed"]), "failed": result["failed"], "warnings": result.get("warnings", []) + result["replies"].get("warnings", [])})
                except Exception as exc:
                    results.append({"campaign_id": campaign["id"], "campaign_name": campaign["name"], "error": failure_message(exc, operation="email.automation.campaign", data_dir=self.path.parent)})
            self.last_run_at = to_utc_iso()
            self.last_results = results
            self.last_error = failure_summary(results)
            return results
        except Exception as exc:
            self.last_run_at = to_utc_iso()
            self.last_error = failure_message(exc, operation="email.automation.cycle", data_dir=self.path.parent)
            raise
        finally:
            if engine is not None:
                engine.close()
            self._run_lock.release()

    async def start(self) -> None:
        if self._task and not self._task.done():
            # Still finishing a run a stop asked it to end: a backup that could
            # not wait for it restarts us, and must get a running timer back,
            # not one that ends after this run (D-133).
            self._stop.clear()
            return
        self._stop.clear()
        self._task = asyncio.create_task(self._loop(), name="offsetx-automation")

    async def stop(self) -> None:
        self._stop.set()
        task = self._task
        if task is not None:
            await task
            if self._task is task:
                self._task = None

    async def _loop(self) -> None:
        while not self._stop.is_set():
            try:
                config = self.config()
            except Exception as exc:
                reference = report_failure(exc, operation="email.automation.timer", data_dir=self.path.parent)
                self.last_error = failure_message(ReportedFailure(reference), operation="email.automation.timer")
                raise ReportedFailure(reference) from None
            try:
                await asyncio.wait_for(self._stop.wait(), timeout=int(config["interval_seconds"]))
                continue
            except asyncio.TimeoutError:
                pass
            if config["enabled"]:
                try:
                    await asyncio.to_thread(self.run_once)
                except Exception:
                    pass
