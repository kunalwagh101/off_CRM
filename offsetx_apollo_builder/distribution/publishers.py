"""Publishing adapters.

One interface, and today one implementation. Every real platform is declared in
``platforms.py`` with the official API that would serve it; none has an adapter
yet, and scheduling to one is refused rather than queued.

``LocalOutboxPublisher`` is not a stub. It is the same device
``LocalOutboxProvider`` is for email: a real destination that writes to disk, so
the whole pipeline — plan, approve, schedule, publish, measure — runs and is
reviewable without touching an account. It is what makes the rest of this module
testable, and it is a genuinely useful way to see exactly what would go out.
"""

from __future__ import annotations

import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Protocol


class Publisher(Protocol):
    """What a platform adapter has to answer.

    Deliberately narrow. An adapter receives a caption, a handle and optionally
    a picture, and returns a receipt. It is given no campaign, no store and no
    way to ask for more — the same reasoning as the provider adapters: a
    component that can only receive what it was handed cannot reach for
    anything else.
    """

    def publish(
        self,
        *,
        platform: str,
        handle: str,
        caption: str,
        asset: dict[str, Any] | None,
        post_id: str,
    ) -> dict[str, Any]: ...


class LocalOutboxPublisher:
    """Writes what would have been posted to a folder."""

    def __init__(self, root: Path | str) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def publish(
        self,
        *,
        platform: str,
        handle: str,
        caption: str,
        asset: dict[str, Any] | None,
        post_id: str,
    ) -> dict[str, Any]:
        folder = self.root / platform
        folder.mkdir(parents=True, exist_ok=True)
        record = {
            "post_id": post_id,
            "platform": platform,
            "handle": handle,
            "caption": caption,
            "published_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        }

        if asset and asset.get("path"):
            source = Path(str(asset["path"]))
            if source.exists():
                target = folder / f"{post_id}{source.suffix}"
                shutil.copy2(source, target)
                record["asset"] = str(target)
            else:
                # Reported rather than silently dropped: a post that was meant to
                # carry a picture and did not is a different thing from a text
                # post, and the receipt should say which one went out.
                record["asset_missing"] = str(source)

        (folder / f"{post_id}.json").write_text(
            json.dumps(record, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        record["external_id"] = f"local:{post_id}"
        return record
