"""GtmStore — the only code that touches the ``gtm_*`` tables.

The seam rule from ``docs/architecture/GTM_ENGINE.md`` §3: this module owns its
tables and reads nobody else's. Campaigns, delivery health and post metrics
arrive through callables the API injects into the service, never through a
join here.

Opened through ``open_database`` like the distribution and video stores, so
``OFFSETX_DATABASE_URL`` moves it onto Postgres with no code change.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from ..db import Database, open_database
from .products import FIELDS, LIST_FIELDS, ProductInvalid, validate_product

SCHEMA = """
CREATE TABLE IF NOT EXISTS gtm_products (
    id TEXT PRIMARY KEY,
    workspace_id TEXT NOT NULL,
    name TEXT NOT NULL,
    one_liner TEXT NOT NULL,
    audience TEXT NOT NULL,
    problem TEXT NOT NULL,
    outcome TEXT NOT NULL DEFAULT '',
    offer TEXT NOT NULL,
    proof_json TEXT NOT NULL DEFAULT '[]',
    differentiators_json TEXT NOT NULL DEFAULT '[]',
    forbidden_claims_json TEXT NOT NULL DEFAULT '[]',
    voice TEXT NOT NULL DEFAULT '',
    website TEXT NOT NULL DEFAULT '',
    version INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_gtm_products_workspace
ON gtm_products(workspace_id, created_at);
"""

#: The text columns written before the JSON lists, in table order.
_LEAD_COLUMNS = ("name", "one_liner", "audience", "problem", "outcome", "offer")


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


class ProductConflict(RuntimeError):
    """The product changed between reading it and writing the edit."""


class GtmStore:
    def __init__(self, database_path: Path | str | None = None) -> None:
        self.target = database_path
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

    # ── products ────────────────────────────────────────────────────────────

    @staticmethod
    def _product(row: Mapping[str, Any]) -> dict[str, Any]:
        item = dict(row)
        product: dict[str, Any] = {"id": item["id"], "workspace_id": item["workspace_id"]}
        for field in FIELDS:
            if field in LIST_FIELDS:
                product[field] = json.loads(item.get(f"{field}_json") or "[]")
            else:
                product[field] = item.get(field) or ""
        product["version"] = int(item["version"])
        product["created_at"] = item["created_at"]
        product["updated_at"] = item["updated_at"]
        return product

    def _read_product(self, db: Database, product_id: str, workspace_id: str) -> dict[str, Any]:
        row = db.execute(
            "SELECT * FROM gtm_products WHERE id = ? AND workspace_id = ?",
            (product_id, workspace_id),
        ).fetchone()
        if not row:
            # Another workspace's product is "not found", not "forbidden": the
            # answer must not confirm that the id exists somewhere else.
            raise KeyError(f"Product not found: {product_id}")
        return self._product(row)

    def create_product(self, workspace_id: str, values: Mapping[str, Any]) -> dict[str, Any]:
        cleaned = validate_product(values)
        product_id = str(uuid.uuid4())
        now = _now()
        self.connection.execute(
            "INSERT INTO gtm_products (id, workspace_id, name, one_liner, audience, "
            "problem, outcome, offer, proof_json, differentiators_json, "
            "forbidden_claims_json, voice, website, version, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?)",
            (
                product_id,
                workspace_id,
                *(cleaned[column] for column in _LEAD_COLUMNS),
                json.dumps(cleaned["proof"]),
                json.dumps(cleaned["differentiators"]),
                json.dumps(cleaned["forbidden_claims"]),
                cleaned["voice"],
                cleaned["website"],
                now,
                now,
            ),
        )
        return self.get_product(product_id, workspace_id)

    def get_product(self, product_id: str, workspace_id: str) -> dict[str, Any]:
        return self._read_product(self.connection, product_id, workspace_id)

    def list_products(self, workspace_id: str) -> list[dict[str, Any]]:
        rows = self.connection.execute(
            "SELECT * FROM gtm_products WHERE workspace_id = ? ORDER BY created_at, id",
            (workspace_id,),
        ).fetchall()
        return [self._product(row) for row in rows]

    def update_product(
        self, product_id: str, workspace_id: str, changes: Mapping[str, Any]
    ) -> dict[str, Any]:
        """Apply an edit and raise the version by exactly one.

        Validated as a partial edit first, then re-validated as a whole product
        once merged: an edit that empties a required field must be refused even
        though every field it names is individually well-formed.
        """
        cleaned = validate_product(changes, partial=True)
        if not cleaned:
            raise ProductInvalid(
                "product", "Nothing to change — name at least one field to edit."
            )
        with self.connection.transaction() as db:
            current = self._read_product(db, product_id, workspace_id)
            merged = validate_product({field: current[field] for field in FIELDS} | cleaned)
            self._write(db, product_id, workspace_id, merged, current["version"])
        return self.get_product(product_id, workspace_id)

    def _write(
        self,
        db: Database,
        product_id: str,
        workspace_id: str,
        merged: Mapping[str, Any],
        expected_version: int,
    ) -> None:
        # `AND version = ?` is what turns a concurrent edit into a refusal
        # instead of a lost update. SQLite's `BEGIN IMMEDIATE` already
        # serialises writers; Postgres at READ COMMITTED does not, and there the
        # second writer's WHERE no longer matches the row the first one wrote.
        cursor = db.execute(
            "UPDATE gtm_products SET name = ?, one_liner = ?, audience = ?, problem = ?, "
            "outcome = ?, offer = ?, proof_json = ?, differentiators_json = ?, "
            "forbidden_claims_json = ?, voice = ?, website = ?, "
            "version = version + 1, updated_at = ? "
            "WHERE id = ? AND workspace_id = ? AND version = ?",
            (
                *(merged[column] for column in _LEAD_COLUMNS),
                json.dumps(merged["proof"]),
                json.dumps(merged["differentiators"]),
                json.dumps(merged["forbidden_claims"]),
                merged["voice"],
                merged["website"],
                _now(),
                product_id,
                workspace_id,
                int(expected_version),
            ),
        )
        if getattr(cursor, "rowcount", 1) == 0:
            raise ProductConflict(
                "The product was changed by someone else while this edit was being "
                "saved. Reload it and make the edit again."
            )

    def delete_product(self, product_id: str, workspace_id: str) -> None:
        with self.connection.transaction() as db:
            self._read_product(db, product_id, workspace_id)
            db.execute(
                "DELETE FROM gtm_products WHERE id = ? AND workspace_id = ?",
                (product_id, workspace_id),
            )
