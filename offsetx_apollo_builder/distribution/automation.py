"""The timer that makes the content engine run without anybody pressing anything.

Every piece of the content pipeline worked before this file existed and none of
them ran on their own. `/trends/sweep` was a button, `pipeline/plan` was a
button, `publish-due` was a button. A campaign that only advances when somebody
remembers to advance it is a set of buttons, not an engine — and the Amul point
from the brief is precisely about *time*: a trend acted on tomorrow is a trend
somebody else already used.

So this is the smallest amount of code that turns the parts into a system.

---

**Which campaigns run is declared, not inferred.**

The pipeline needs two campaigns at once: a distribution campaign to post from
and an image campaign to draw from. Nothing in the schema says which pairs with
which, and guessing — "the most recent image campaign", "the one with a similar
name" — would silently produce posts from the wrong brand.

So the pairs live in this service's own config as a list the owner writes down.
Default-deny, the same rule as the provider registry: **an undeclared pair does
not run.** An empty list means nothing happens, which is the correct behaviour
for a machine that posts under your name.

---

**A failing step does not cost the cycle.**

Four things happen per cycle and they are independent. A YouTube quota error at
the sweep must not stop the posts that were already approved from going out.
Each step is caught, recorded, and the cycle continues — the run report says
what worked and what did not, and the next cycle tries again.

**Nothing here publishes anything that was not approved.** `publish_due` only
touches posts a person already approved and scheduled. The two human gates —
the swipe and the approval — are exactly where they were; this service drives
the machine either side of them and stops at both.
"""

from __future__ import annotations

import asyncio
import json
import os
import threading
from datetime import datetime, timezone
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any, Callable

#: An hour. Trends do not move in minutes, and a sweep costs quota — the
#: default is chosen to be useful on a free YouTube key rather than to feel
#: responsive. `plan` also has a per-topic cooldown of a week, so a faster
#: interval mostly buys repeated no-ops.
DEFAULT_INTERVAL_SECONDS = 3600

DEFAULT_CONTENT_AUTOMATION: dict[str, Any] = {
    "enabled": False,
    "interval_seconds": DEFAULT_INTERVAL_SECONDS,
    # Each step can be switched off alone. Somebody who wants the machine to
    # find topics but not to draft anything is asking a reasonable question.
    "sweep": True,
    "plan": True,
    "draft": True,
    "publish_due": True,
    "per_channel": 10,
    "max_topics": 2,
    "candidates": 3,
    #: [{distribution_campaign_id, image_campaign_id, angle, account_ids}]
    "pipelines": [],
}

STEPS = ("sweep", "plan", "draft", "publish_due")


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


class ContentAutomationService:
    """Runs the content pipeline on a timer, and reports what it did.

    Every collaborator is injected. This module knows the *order* of the work
    and nothing about trends, images, posting or providers — which is what lets
    it be tested without a network, a key or a database.
    """

    def __init__(
        self,
        path: Path | str,
        *,
        trends_factory: Callable[[], Any],
        pipeline_factory: Callable[[str], Any],
        distribution_factory: Callable[[], Any],
    ) -> None:
        self.path = Path(path)
        self.trends_factory = trends_factory
        #: Called with the angle, because the pipeline chooses its data class
        #: from whether an angle is present — an owner's positioning is not
        #: public and narrows which models may see it.
        self.pipeline_factory = pipeline_factory
        self.distribution_factory = distribution_factory
        self._task: asyncio.Task[None] | None = None
        self._stop = asyncio.Event()
        self._run_lock = threading.Lock()
        self.last_run_at = ""
        self.last_error = ""
        self.last_results: list[dict[str, Any]] = []

    # ── configuration ───────────────────────────────────────────────────────

    def config(self) -> dict[str, Any]:
        payload = dict(DEFAULT_CONTENT_AUTOMATION)
        if self.path.exists():
            try:
                stored = json.loads(self.path.read_text(encoding="utf-8"))
                if isinstance(stored, dict):
                    payload.update(stored)
            except (OSError, json.JSONDecodeError):
                # A corrupt settings file must not start an unattended poster
                # with whatever half-parsed values survived.
                self.last_error = (
                    "Content automation settings are invalid; safe defaults are active "
                    "and nothing is enabled."
                )
                payload = dict(DEFAULT_CONTENT_AUTOMATION)
        return self._normalise(payload)

    @staticmethod
    def _normalise(values: dict[str, Any]) -> dict[str, Any]:
        payload = dict(DEFAULT_CONTENT_AUTOMATION)
        payload.update(values)
        payload["enabled"] = bool(payload.get("enabled"))
        for step in STEPS:
            payload[step] = bool(payload.get(step, True))
        payload["interval_seconds"] = max(
            300, min(int(payload.get("interval_seconds") or DEFAULT_INTERVAL_SECONDS), 86400)
        )
        payload["per_channel"] = max(1, min(int(payload.get("per_channel") or 10), 50))
        payload["max_topics"] = max(1, min(int(payload.get("max_topics") or 2), 10))
        payload["candidates"] = max(1, min(int(payload.get("candidates") or 3), 8))
        payload["pipelines"] = [
            item
            for item in (
                ContentAutomationService._normalise_pipeline(entry)
                for entry in payload.get("pipelines") or []
            )
            if item is not None
        ]
        return payload

    @staticmethod
    def _normalise_pipeline(entry: Any) -> dict[str, Any] | None:
        if not isinstance(entry, dict):
            return None
        distribution_id = str(entry.get("distribution_campaign_id") or "").strip()
        image_id = str(entry.get("image_campaign_id") or "").strip()
        # A half-declared pair is not a pair. Running it would mean guessing the
        # missing half, which is the thing this design exists to refuse.
        if not distribution_id or not image_id:
            return None
        accounts = [str(item).strip() for item in entry.get("account_ids") or [] if str(item).strip()]
        return {
            "distribution_campaign_id": distribution_id,
            "image_campaign_id": image_id,
            "angle": str(entry.get("angle") or "")[:500],
            "account_ids": accounts,
        }

    def update(self, values: dict[str, Any]) -> dict[str, Any]:
        merged = dict(self.config())
        for key in ("enabled", "interval_seconds", "per_channel", "max_topics", "candidates", "pipelines"):
            if key in values:
                merged[key] = values[key]
        for step in STEPS:
            if step in values:
                merged[step] = values[step]
        normalised = self._normalise(merged)
        if normalised["enabled"] and not normalised["pipelines"]:
            raise ValueError(
                "Nothing is declared to run. Add at least one pipeline — a "
                "distribution campaign to post from and an image campaign to "
                "draw from — before enabling unattended runs."
            )
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with NamedTemporaryFile("w", encoding="utf-8", dir=self.path.parent, delete=False) as handle:
            json.dump(normalised, handle, indent=2)
            temporary = Path(handle.name)
        os.replace(temporary, self.path)
        self.last_error = ""
        return self.status()

    def status(self) -> dict[str, Any]:
        return {
            **self.config(),
            "running": bool(self._task and not self._task.done()),
            "last_run_at": self.last_run_at,
            "last_error": self.last_error,
            "last_results": self.last_results,
        }

    # ── one cycle ───────────────────────────────────────────────────────────

    def run_once(self) -> list[dict[str, Any]]:
        """Sweep, plan, draft, publish — in that order, each independently.

        The order is the pipeline's own: you cannot plan against topics you have
        not swept, and you cannot draft from pictures nobody has kept. Steps
        that are switched off are skipped by name so the report says so, rather
        than silently doing less than it appears to.
        """
        if not self._run_lock.acquire(blocking=False):
            raise RuntimeError("A content automation cycle is already running")
        try:
            config = self.config()
            results: list[dict[str, Any]] = []

            if config["sweep"]:
                results.append(self._sweep(config))
            else:
                results.append({"step": "sweep", "status": "skipped"})

            for pipeline in config["pipelines"]:
                if config["plan"]:
                    results.append(self._plan(config, pipeline))
                if config["draft"]:
                    results.append(self._draft(config, pipeline))

            if config["publish_due"]:
                results.append(self._publish_due())
            else:
                results.append({"step": "publish_due", "status": "skipped"})

            self.last_run_at = _now()
            self.last_results = results
            self.last_error = ""
            return results
        except Exception as exc:  # noqa: BLE001 - recorded for the status panel
            self.last_run_at = _now()
            self.last_error = str(exc)[:1000]
            raise
        finally:
            self._run_lock.release()

    # Each step returns a row rather than raising, so one bad provider does not
    # cost the whole cycle. The row carries the error where there was one.

    def _sweep(self, config: dict[str, Any]) -> dict[str, Any]:
        watcher = None
        try:
            watcher = self.trends_factory()
            report = watcher.sweep(per_channel=int(config["per_channel"])).to_dict()
            return {
                "step": "sweep",
                "status": "ok",
                "channels_swept": report.get("channels_swept"),
                "videos_seen": report.get("videos_seen"),
                "videos_new": report.get("videos_new"),
                "units_spent": report.get("units_spent"),
                "skipped": len(report.get("skipped") or []),
            }
        except Exception as exc:  # noqa: BLE001
            return {"step": "sweep", "status": "failed", "error": str(exc)[:500]}
        finally:
            if watcher is not None:
                try:
                    watcher.close()
                except Exception:  # noqa: BLE001 - closing is best effort
                    pass

    def _plan(self, config: dict[str, Any], pipeline: dict[str, Any]) -> dict[str, Any]:
        row = {
            "step": "plan",
            "distribution_campaign_id": pipeline["distribution_campaign_id"],
            "image_campaign_id": pipeline["image_campaign_id"],
        }
        try:
            runner = self.pipeline_factory(pipeline["angle"])
            planned = runner.plan(
                distribution_campaign_id=pipeline["distribution_campaign_id"],
                image_campaign_id=pipeline["image_campaign_id"],
                max_topics=int(config["max_topics"]),
                candidates=int(config["candidates"]),
                angle=pipeline["angle"],
            ).to_dict()
            return {
                **row,
                "status": "ok",
                "topics_found": planned.get("topics_found"),
                "topics_planned": planned.get("topics_planned"),
                "topics_skipped": planned.get("topics_skipped"),
                "candidates": planned.get("candidates"),
            }
        except Exception as exc:  # noqa: BLE001
            return {**row, "status": "failed", "error": str(exc)[:500]}

    def _draft(self, config: dict[str, Any], pipeline: dict[str, Any]) -> dict[str, Any]:
        row = {
            "step": "draft",
            "distribution_campaign_id": pipeline["distribution_campaign_id"],
            "image_campaign_id": pipeline["image_campaign_id"],
        }
        try:
            runner = self.pipeline_factory(pipeline["angle"])
            drafted = runner.draft(
                distribution_campaign_id=pipeline["distribution_campaign_id"],
                image_campaign_id=pipeline["image_campaign_id"],
                account_ids=pipeline["account_ids"],
                angle=pipeline["angle"],
            ).to_dict()
            return {
                **row,
                "status": "ok",
                "assets_considered": drafted.get("assets_considered"),
                "posts_created": drafted.get("posts_created"),
                "skipped": len(drafted.get("skipped") or []),
            }
        except Exception as exc:  # noqa: BLE001
            return {**row, "status": "failed", "error": str(exc)[:500]}

    def _publish_due(self) -> dict[str, Any]:
        """Send what a person already approved and scheduled.

        This is the only step that reaches the outside world, and it can only
        act on posts that already carry an approval. The gate is in the
        distribution engine, not here — this service must never be the thing
        that decides something may go out.
        """
        try:
            engine = self.distribution_factory()
            round_ = engine.publish_due().to_dict()
            return {
                "step": "publish_due",
                "status": "ok",
                "published": round_.get("published"),
                "failed": round_.get("failed"),
                "skipped": round_.get("skipped"),
            }
        except Exception as exc:  # noqa: BLE001
            return {"step": "publish_due", "status": "failed", "error": str(exc)[:500]}

    # ── the timer ───────────────────────────────────────────────────────────

    async def start(self) -> None:
        if self._task and not self._task.done():
            return
        self._stop.clear()
        self._task = asyncio.create_task(self._loop(), name="offsetx-content-automation")

    async def stop(self) -> None:
        self._stop.set()
        if self._task:
            await self._task
            self._task = None

    async def _loop(self) -> None:
        """Wait, then run — never run, then wait.

        Waiting first means a restart loop cannot turn into a burst of sweeps
        against a quota, and it means enabling the setting does not fire
        immediately from whatever state the app happened to boot in.
        """
        while not self._stop.is_set():
            config = self.config()
            try:
                await asyncio.wait_for(
                    self._stop.wait(), timeout=int(config["interval_seconds"])
                )
                continue
            except asyncio.TimeoutError:
                pass
            if config["enabled"] and config["pipelines"]:
                try:
                    await asyncio.to_thread(self.run_once)
                except Exception:  # noqa: BLE001 - already recorded in status
                    pass
