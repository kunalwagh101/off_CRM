"""Bound video multipart upload bodies before the framework's multipart parser.

A bounded spooled body prevents unbounded RAM and temporary-disk use from
video uploads. The endpoint retains its separate per-file byte limit.
"""
from __future__ import annotations

import asyncio
import re
from tempfile import SpooledTemporaryFile
from typing import Any

from starlette.responses import JSONResponse


_VIDEO_BODY_ROUTES = (
    re.compile(r"^/api/v1/campaigns/[^/]+/video-media$"),
    re.compile(r"^/api/v1/video-projects/[^/]+/renders$"),
)
_BODY_OVERHEAD_BYTES = 16 * 1024  # Multipart form fields and boundaries.
_REPLAY_CHUNK_BYTES = 64 * 1024


class VideoUploadBodyGuard:
    """Per-worker concurrency and request size gate for video POST uploads.

    This runs before Starlette parses multipart files. A bounded spool avoids
    holding full media bodies in Python memory. Content-Length is a fast
    rejection hint only: each received chunk is counted independently.
    """

    def __init__(
        self, app: Any, *, max_file_bytes: int,
        max_concurrent: int = 2, idle_timeout_seconds: float = 30.0,
    ) -> None:
        if max_file_bytes < 1 or max_concurrent < 1 or idle_timeout_seconds <= 0:
            raise ValueError("Upload budgets and concurrency must be positive")
        self.app = app
        self.max_body_bytes = max_file_bytes + _BODY_OVERHEAD_BYTES
        self._slots = asyncio.Semaphore(max_concurrent)
        self._idle_timeout = idle_timeout_seconds

    async def __call__(self, scope: dict[str, Any], receive: Any, send: Any) -> None:
        if (
            scope["type"] != "http"
            or scope.get("method") != "POST"
            or not any(route.fullmatch(scope.get("path", "")) for route in _VIDEO_BODY_ROUTES)
        ):
            await self.app(scope, receive, send)
            return

        raw_sizes = [
            value.strip() for key, value in scope.get("headers", [])
            if key.lower() == b"content-length"
        ]
        if raw_sizes:
            if len(raw_sizes) != 1 or len(raw_sizes[0]) > 20 or not raw_sizes[0].isdigit():
                await self._refuse(scope, receive, send, 400, "Invalid upload Content-Length header")
                return
            if int(raw_sizes[0]) > self.max_body_bytes:
                await self._refuse(scope, receive, send, 413, "Video upload exceeds the request size limit")
                return

        try:
            await asyncio.wait_for(self._slots.acquire(), timeout=0.05)
        except TimeoutError:
            await self._refuse(scope, receive, send, 429, "Too many video uploads. Retry shortly.")
            return

        # SpooledTemporaryFile uses a private, auto-deleted temp file after
        # 256 KiB, including when a client disconnects or the task is cancelled.
        spool = None
        try:
            spool = SpooledTemporaryFile(max_size=256 * 1024, mode="w+b")
            total = 0
            while True:
                try:
                    message = await asyncio.wait_for(receive(), timeout=self._idle_timeout)
                except TimeoutError:
                    await self._refuse(
                        scope, receive, send, 408,
                        "Video upload stopped receiving data. Retry the upload.",
                    )
                    return
                if message["type"] == "http.disconnect":
                    return
                if message["type"] != "http.request":
                    continue
                content = message.get("body", b"")
                total += len(content)
                if total > self.max_body_bytes:
                    await self._refuse(scope, receive, send, 413, "Video upload exceeds the request size limit")
                    return
                spool.write(content)
                if not message.get("more_body", False):
                    break
            spool.seek(0)
            exhausted = False

            async def replay() -> dict[str, Any]:
                nonlocal exhausted
                if exhausted:
                    return {"type": "http.request", "body": b"", "more_body": False}
                body = spool.read(_REPLAY_CHUNK_BYTES)
                more = spool.tell() < total
                if not more:
                    exhausted = True
                return {"type": "http.request", "body": body, "more_body": more}

            await self.app(scope, replay, send)
        finally:
            if spool is not None:
                spool.close()
            self._slots.release()

    @staticmethod
    async def _refuse(
        scope: dict[str, Any], receive: Any, send: Any, status: int, detail: str,
    ) -> None:
        await JSONResponse({"detail": detail}, status_code=status)(scope, receive, send)
