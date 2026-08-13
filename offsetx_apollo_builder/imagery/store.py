"""Storage for image campaigns: briefs, candidate assets, generator scores.

Its own database, for the same reason the AI module has one: an image campaign
shares no foreign key with the CRM, so keeping it separate means neither has to
know about the other and either can move backends alone.

**Three tables, and the third is the interesting one.**

``image_briefs`` is the ask. ``image_assets`` is what came back. And
``image_generator_stats`` is the running record of how often each generator's
work survived the owner's swipe — which is the quality benchmark, accumulated
free as a side effect of ordinary use.

**Pictures are files, not rows.** The bytes go to disk and the row keeps a path
and a hash. A base64 blob in a database column bloats every backup and every
query that did not want it, and the egress log already made the same decision
for the same reason: it records the prompt and a count, never the picture.
"""

from __future__ import annotations

import hashlib
import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from ..db import Database, open_database

SCHEMA = """
CREATE TABLE IF NOT EXISTS image_briefs (
    id TEXT PRIMARY KEY,
    campaign_id TEXT NOT NULL,
    workspace_id TEXT NOT NULL DEFAULT 'local',
    brief TEXT NOT NULL,
    width INTEGER NOT NULL DEFAULT 0,
    height INTEGER NOT NULL DEFAULT 0,
    wanted INTEGER NOT NULL DEFAULT 1,
    status TEXT NOT NULL DEFAULT 'open',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_image_briefs_campaign
    ON image_briefs(campaign_id, status);

CREATE TABLE IF NOT EXISTS image_assets (
    id TEXT PRIMARY KEY,
    brief_id TEXT NOT NULL,
    campaign_id TEXT NOT NULL,
    workspace_id TEXT NOT NULL DEFAULT 'local',
    provider_id TEXT NOT NULL DEFAULT '',
    model_id TEXT NOT NULL DEFAULT '',
    path TEXT NOT NULL DEFAULT '',
    sha256 TEXT NOT NULL DEFAULT '',
    media_type TEXT NOT NULL DEFAULT '',
    width INTEGER NOT NULL DEFAULT 0,
    height INTEGER NOT NULL DEFAULT 0,
    bytes INTEGER NOT NULL DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'pending',
    gate_json TEXT NOT NULL DEFAULT '{}',
    log_id TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    decided_at TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS ix_image_assets_review
    ON image_assets(campaign_id, status, created_at);
CREATE INDEX IF NOT EXISTS ix_image_assets_brief
    ON image_assets(brief_id, status);

CREATE TABLE IF NOT EXISTS image_generator_stats (
    id TEXT PRIMARY KEY,
    workspace_id TEXT NOT NULL DEFAULT 'local',
    provider_id TEXT NOT NULL,
    model_id TEXT NOT NULL,
    shown INTEGER NOT NULL DEFAULT 0,
    approved INTEGER NOT NULL DEFAULT 0,
    rejected INTEGER NOT NULL DEFAULT 0,
    gate_failed INTEGER NOT NULL DEFAULT 0,
    updated_at TEXT NOT NULL
);
CREATE UNIQUE INDEX IF NOT EXISTS ux_image_generator
    ON image_generator_stats(workspace_id, provider_id, model_id);
"""

#: Statuses an asset can hold. ``gate_failed`` is separate from ``rejected`` on
#: purpose: the owner rejecting a picture is a statement about taste and feeds
#: the benchmark, while a gate failure is a statement about the file and must
#: not be mistaken for one.
ASSET_STATUSES = ("pending", "approved", "rejected", "gate_failed")


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


class ImageStore:
    """Briefs, assets and generator scores."""

    def __init__(self, database_path: Path | str | None = None, *, assets_dir: Path | str) -> None:
        self.target = database_path
        self.assets_dir = Path(assets_dir)
        self.assets_dir.mkdir(parents=True, exist_ok=True)
        self._connection: Database | None = None

    @property
    def connection(self) -> Database:
        if self._connection is None:
            database = open_database(self.target)
            database.executescript(SCHEMA)
            self._connection = database
        return self._connection

    def close(self) -> None:
        if self._connection is not None:
            self._connection.close()
            self._connection = None

    # ── briefs ──────────────────────────────────────────────────────────────

    def create_brief(
        self,
        *,
        campaign_id: str,
        brief: str,
        width: int = 0,
        height: int = 0,
        wanted: int = 1,
        workspace_id: str = "local",
    ) -> str:
        text = str(brief or "").strip()
        if not text:
            raise ValueError("A brief needs a description of the picture you want.")
        brief_id = str(uuid.uuid4())
        now = _now()
        self.connection.execute(
            "INSERT INTO image_briefs(id, campaign_id, workspace_id, brief, width,"
            " height, wanted, status, created_at, updated_at)"
            " VALUES(?,?,?,?,?,?,?,'open',?,?)",
            (
                brief_id,
                campaign_id,
                workspace_id,
                text[:4000],
                max(0, int(width)),
                max(0, int(height)),
                max(1, int(wanted)),
                now,
                now,
            ),
        )
        return brief_id

    def get_brief(self, brief_id: str) -> dict[str, Any]:
        row = self.connection.execute(
            "SELECT * FROM image_briefs WHERE id = ?", (brief_id,)
        ).fetchone()
        if not row:
            raise KeyError(f"Brief not found: {brief_id}")
        return dict(row)

    def list_briefs(self, campaign_id: str, *, status: str = "") -> list[dict[str, Any]]:
        sql = "SELECT * FROM image_briefs WHERE campaign_id = ?"
        params: list[Any] = [campaign_id]
        if status:
            sql += " AND status = ?"
            params.append(status)
        rows = self.connection.execute(sql + " ORDER BY created_at", params).fetchall()
        return [dict(row) for row in rows]

    def set_brief_status(self, brief_id: str, status: str) -> None:
        self.connection.execute(
            "UPDATE image_briefs SET status = ?, updated_at = ? WHERE id = ?",
            (status, _now(), brief_id),
        )

    # ── assets ──────────────────────────────────────────────────────────────

    def store_asset(
        self,
        *,
        brief_id: str,
        campaign_id: str,
        payload: bytes,
        provider_id: str,
        model_id: str,
        gate_report: Any,
        status: str,
        log_id: str = "",
        workspace_id: str = "local",
    ) -> str:
        """Write the picture to disk and the record to the database.

        The file is written first. A row pointing at a file that does not exist
        is a broken review queue; a file with no row is a stray byte on disk that
        the next sweep can clean up, which is the cheaper of the two failures.
        """
        if status not in ASSET_STATUSES:
            raise ValueError(f"Unknown asset status: {status}")
        asset_id = str(uuid.uuid4())
        digest = hashlib.sha256(payload).hexdigest()
        suffix = {
            "image/png": ".png",
            "image/jpeg": ".jpg",
            "image/webp": ".webp",
            "image/gif": ".gif",
        }.get(getattr(gate_report, "media_type", ""), ".bin")

        folder = self.assets_dir / campaign_id
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / f"{asset_id}{suffix}"
        path.write_bytes(payload)
        try:
            os.chmod(path, 0o600)
        except OSError:
            pass

        self.connection.execute(
            "INSERT INTO image_assets(id, brief_id, campaign_id, workspace_id,"
            " provider_id, model_id, path, sha256, media_type, width, height,"
            " bytes, status, gate_json, log_id, created_at, decided_at)"
            " VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,'')",
            (
                asset_id,
                brief_id,
                campaign_id,
                workspace_id,
                provider_id,
                model_id,
                str(path),
                digest,
                getattr(gate_report, "media_type", ""),
                int(getattr(gate_report, "width", 0)),
                int(getattr(gate_report, "height", 0)),
                len(payload),
                status,
                json.dumps(gate_report.to_dict() if gate_report else {}),
                log_id,
                _now(),
            ),
        )
        return asset_id

    def get_asset(self, asset_id: str) -> dict[str, Any]:
        row = self.connection.execute(
            "SELECT * FROM image_assets WHERE id = ?", (asset_id,)
        ).fetchone()
        if not row:
            raise KeyError(f"Asset not found: {asset_id}")
        item = dict(row)
        item["gates"] = _safe_json(item.pop("gate_json", "{}"))
        return item

    def list_assets(
        self,
        campaign_id: str,
        *,
        status: str = "",
        brief_id: str = "",
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        sql = "SELECT * FROM image_assets WHERE campaign_id = ?"
        params: list[Any] = [campaign_id]
        if status:
            sql += " AND status = ?"
            params.append(status)
        if brief_id:
            sql += " AND brief_id = ?"
            params.append(brief_id)
        sql += " ORDER BY created_at LIMIT ?"
        params.append(max(1, int(limit)))
        items = []
        for row in self.connection.execute(sql, params).fetchall():
            item = dict(row)
            item["gates"] = _safe_json(item.pop("gate_json", "{}"))
            items.append(item)
        return items

    def hashes_for_brief(self, brief_id: str) -> set[str]:
        rows = self.connection.execute(
            "SELECT sha256 FROM image_assets WHERE brief_id = ?", (brief_id,)
        ).fetchall()
        return {str(row["sha256"]) for row in rows if row["sha256"]}

    def set_asset_status(self, asset_id: str, status: str) -> dict[str, Any]:
        if status not in ASSET_STATUSES:
            raise ValueError(f"Unknown asset status: {status}")
        self.connection.execute(
            "UPDATE image_assets SET status = ?, decided_at = ? WHERE id = ?",
            (status, _now(), asset_id),
        )
        return self.get_asset(asset_id)

    def delete_asset_file(self, asset_id: str) -> bool:
        """Remove the picture from disk, keeping the row.

        A left swipe means the owner does not want the picture. The *record* of
        having rejected it is what the benchmark is made of, so the row stays and
        only the bytes go.
        """
        asset = self.get_asset(asset_id)
        path = Path(str(asset.get("path") or ""))
        if path.exists():
            path.unlink()
            self.connection.execute(
                "UPDATE image_assets SET path = '' WHERE id = ?", (asset_id,)
            )
            return True
        return False

    # ── generator scores: the swipe record ──────────────────────────────────

    def record_shown(self, *, provider_id: str, model_id: str, workspace_id: str = "local") -> None:
        self._bump(provider_id, model_id, workspace_id, "shown")

    def record_decision(
        self,
        *,
        provider_id: str,
        model_id: str,
        approved: bool,
        workspace_id: str = "local",
    ) -> None:
        self._bump(provider_id, model_id, workspace_id, "approved" if approved else "rejected")

    def record_gate_failure(
        self, *, provider_id: str, model_id: str, workspace_id: str = "local"
    ) -> None:
        self._bump(provider_id, model_id, workspace_id, "gate_failed")

    def _bump(self, provider_id: str, model_id: str, workspace_id: str, column: str) -> None:
        self.connection.execute(
            f"INSERT INTO image_generator_stats(id, workspace_id, provider_id, model_id,"
            f" {column}, updated_at) VALUES(?,?,?,?,1,?)"
            f" ON CONFLICT(workspace_id, provider_id, model_id) DO UPDATE SET"
            f" {column} = image_generator_stats.{column} + 1, updated_at = excluded.updated_at",
            (str(uuid.uuid4()), workspace_id, provider_id, model_id, _now()),
        )

    def generator_stats(self, *, workspace_id: str = "local") -> list[dict[str, Any]]:
        rows = self.connection.execute(
            "SELECT * FROM image_generator_stats WHERE workspace_id = ?"
            " ORDER BY approved DESC, shown DESC",
            (workspace_id,),
        ).fetchall()
        items = []
        for row in rows:
            item = dict(row)
            decided = int(item["approved"]) + int(item["rejected"])
            item["decided"] = decided
            item["approval_rate"] = (
                round(int(item["approved"]) / decided * 100, 1) if decided else 0.0
            )
            items.append(item)
        return items


def _safe_json(value: Any) -> Any:
    try:
        return json.loads(str(value))
    except (TypeError, ValueError):
        return {}
