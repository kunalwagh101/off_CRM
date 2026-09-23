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

-- One product per campaign: the campaign is the key. A campaign id is not a
-- foreign key because campaigns live in a table this module does not own.
CREATE TABLE IF NOT EXISTS gtm_campaign_links (
    campaign_id TEXT PRIMARY KEY,
    product_id TEXT NOT NULL,
    workspace_id TEXT NOT NULL,
    plan_id TEXT NOT NULL DEFAULT '',
    channel TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_gtm_links_product
ON gtm_campaign_links(product_id, workspace_id);

-- A plan and every revision of it. `root_id` is the first version's id, so a
-- line of revisions is one query. The product is copied in, never looked up
-- later: a plan read next month must show what it was written against.
CREATE TABLE IF NOT EXISTS gtm_plans (
    id TEXT PRIMARY KEY,
    workspace_id TEXT NOT NULL,
    product_id TEXT NOT NULL,
    root_id TEXT NOT NULL,
    parent_id TEXT NOT NULL DEFAULT '',
    version INTEGER NOT NULL,
    status TEXT NOT NULL,
    request_json TEXT NOT NULL,
    product_snapshot_json TEXT NOT NULL,
    product_version INTEGER NOT NULL,
    envelope_json TEXT NOT NULL,
    plan_json TEXT NOT NULL,
    feasibility_json TEXT NOT NULL,
    notes_json TEXT NOT NULL,
    source TEXT NOT NULL,
    provider_id TEXT NOT NULL DEFAULT '',
    model_id TEXT NOT NULL DEFAULT '',
    policy TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    applied_at TEXT,
    -- What the line's campaigns had already done when this version was
    -- applied, so its review counts only its own sends (S-12.02.04).
    baseline_json TEXT NOT NULL DEFAULT '{}'
);
CREATE INDEX IF NOT EXISTS idx_gtm_plans_product
ON gtm_plans(workspace_id, product_id, created_at);
CREATE INDEX IF NOT EXISTS idx_gtm_plans_root ON gtm_plans(root_id, version);

-- Kept, never overwritten: what was planned, what was measured and what the
-- brain concluded is the first labelled data this product owns (§4).
CREATE TABLE IF NOT EXISTS gtm_reviews (
    id TEXT PRIMARY KEY,
    plan_id TEXT NOT NULL,
    workspace_id TEXT NOT NULL,
    measurements_json TEXT NOT NULL,
    findings_json TEXT NOT NULL,
    remedies_json TEXT NOT NULL,
    summary TEXT NOT NULL DEFAULT '',
    notes_json TEXT NOT NULL,
    source TEXT NOT NULL,
    provider_id TEXT NOT NULL DEFAULT '',
    model_id TEXT NOT NULL DEFAULT '',
    policy TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_gtm_reviews_plan ON gtm_reviews(plan_id, created_at);
"""

#: The text columns written before the JSON lists, in table order.
_LEAD_COLUMNS = ("name", "one_liner", "audience", "problem", "outcome", "offer")


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _now_precise() -> str:
    """Microseconds, so two reviews of one plan in the same second still order.

    Not ``rowid``: that is SQLite's, and this store runs on Postgres too.
    """
    return datetime.now(timezone.utc).isoformat(timespec="microseconds")


class ProductConflict(RuntimeError):
    """The product changed between reading it and writing the edit."""


class PlanStateError(RuntimeError):
    """A plan asked to do something its status does not allow."""


#: draft -> applied | discarded; applied -> superseded. Nothing leaves the
#: last two. Checked in the UPDATE itself, so two requests cannot both win.
PLAN_STATUSES = ("draft", "applied", "superseded", "discarded")

_PLAN_JSON = ("request", "product_snapshot", "envelope", "plan", "feasibility", "notes", "baseline")


class GtmStore:
    def __init__(self, database_path: Path | str | None = None) -> None:
        self.target = database_path
        self._connection: Database | None = None

    @property
    def connection(self) -> Database:
        if self._connection is None:
            database = open_database(self.target)
            database.executescript(SCHEMA)
            # A table made before revisions existed has no baseline column, and
            # `CREATE TABLE IF NOT EXISTS` does not add one.
            database.add_column_if_missing("gtm_plans", "baseline_json", "TEXT NOT NULL DEFAULT '{}'")
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
        """Delete the product and its links. Plans keep their own snapshot."""
        with self.connection.transaction() as db:
            self._read_product(db, product_id, workspace_id)
            db.execute(
                "DELETE FROM gtm_campaign_links WHERE product_id = ? AND workspace_id = ?",
                (product_id, workspace_id),
            )
            db.execute(
                "DELETE FROM gtm_products WHERE id = ? AND workspace_id = ?",
                (product_id, workspace_id),
            )

    # ── campaign links (S-12.01.02) ─────────────────────────────────────────

    def set_links(
        self, product_id: str, workspace_id: str, campaign_ids: list[str]
    ) -> list[str]:
        """Make ``campaign_ids`` exactly the campaigns this product speaks for.

        Replaces rather than adds, so the owner's checklist is the whole truth.
        A campaign linked to another product moves here: one campaign tells one
        story. The caller checks the campaigns exist — they are not this
        module's rows to look up.
        """
        wanted = list(dict.fromkeys(str(item).strip() for item in campaign_ids if str(item).strip()))
        now = _now()
        with self.connection.transaction() as db:
            self._read_product(db, product_id, workspace_id)
            # A campaign Apply created also records which plan and channel it
            # serves. Re-saving the checklist must not wipe that, or the plan's
            # review would stop finding its own campaigns.
            kept_meta = {
                str(dict(row)["campaign_id"]): (str(dict(row)["plan_id"]), str(dict(row)["channel"]))
                for row in db.execute(
                    "SELECT campaign_id, plan_id, channel FROM gtm_campaign_links "
                    "WHERE product_id = ? AND workspace_id = ?",
                    (product_id, workspace_id),
                ).fetchall()
            }
            db.execute(
                "DELETE FROM gtm_campaign_links WHERE product_id = ? AND workspace_id = ?",
                (product_id, workspace_id),
            )
            for campaign_id in wanted:
                owner = db.execute(
                    "SELECT workspace_id FROM gtm_campaign_links WHERE campaign_id = ?",
                    (campaign_id,),
                ).fetchone()
                if owner and dict(owner)["workspace_id"] != workspace_id:
                    # Another workspace's campaign is "not found" here, the same
                    # answer another workspace's product gets. The transaction
                    # rolls back, so this product's old links survive.
                    raise KeyError(f"Campaign not found: {campaign_id}")
                db.execute(
                    "DELETE FROM gtm_campaign_links WHERE campaign_id = ? AND workspace_id = ?",
                    (campaign_id, workspace_id),
                )
                plan_id, channel = kept_meta.get(campaign_id, ("", ""))
                db.execute(
                    "INSERT INTO gtm_campaign_links (campaign_id, product_id, workspace_id, "
                    "plan_id, channel, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                    (campaign_id, product_id, workspace_id, plan_id, channel, now),
                )
        return self.linked_campaigns(product_id, workspace_id)

    def link_campaign(
        self,
        campaign_id: str,
        product_id: str,
        workspace_id: str,
        *,
        plan_id: str = "",
        channel: str = "",
    ) -> None:
        """Link one campaign, recording the plan and channel Apply made it for."""
        with self.connection.transaction() as db:
            self._read_product(db, product_id, workspace_id)
            owner = db.execute(
                "SELECT workspace_id FROM gtm_campaign_links WHERE campaign_id = ?", (campaign_id,)
            ).fetchone()
            if owner and dict(owner)["workspace_id"] != workspace_id:
                raise KeyError(f"Campaign not found: {campaign_id}")
            db.execute(
                "DELETE FROM gtm_campaign_links WHERE campaign_id = ? AND workspace_id = ?",
                (campaign_id, workspace_id),
            )
            db.execute(
                "INSERT INTO gtm_campaign_links (campaign_id, product_id, workspace_id, plan_id, "
                "channel, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                (campaign_id, product_id, workspace_id, plan_id, channel, _now()),
            )

    def unlink_campaign(self, campaign_id: str, workspace_id: str) -> None:
        """Forget a link whose campaign is gone. The product and plans stay."""
        self.connection.execute(
            "DELETE FROM gtm_campaign_links WHERE campaign_id = ? AND workspace_id = ?",
            (campaign_id, workspace_id),
        )

    def plan_links(self, plan_id: str, workspace_id: str) -> list[dict[str, Any]]:
        """The campaigns Apply created for exactly this plan."""
        rows = self.connection.execute(
            "SELECT campaign_id, product_id, plan_id, channel, created_at FROM gtm_campaign_links "
            "WHERE plan_id = ? AND workspace_id = ? ORDER BY created_at, campaign_id",
            (plan_id, workspace_id),
        ).fetchall()
        return [dict(row) for row in rows]

    def line_links(self, root_id: str, workspace_id: str) -> dict[str, str]:
        """channel -> campaign for every version of one plan's line.

        What makes Apply idempotent (a half-finished apply resumes rather than
        duplicating) and what makes a revision update the campaigns its line
        already has instead of making new ones.
        """
        rows = self.connection.execute(
            "SELECT l.channel, l.campaign_id FROM gtm_campaign_links l "
            "JOIN gtm_plans p ON p.id = l.plan_id AND p.workspace_id = l.workspace_id "
            "WHERE p.root_id = ? AND l.workspace_id = ? AND l.channel <> '' "
            "ORDER BY l.created_at, l.campaign_id",
            (root_id, workspace_id),
        ).fetchall()
        found: dict[str, str] = {}
        for row in rows:
            item = dict(row)
            found.setdefault(str(item["channel"]), str(item["campaign_id"]))
        return found

    def linked_campaigns(self, product_id: str, workspace_id: str) -> list[str]:
        rows = self.connection.execute(
            "SELECT campaign_id FROM gtm_campaign_links WHERE product_id = ? "
            "AND workspace_id = ? ORDER BY created_at, campaign_id",
            (product_id, workspace_id),
        ).fetchall()
        return [str(dict(row)["campaign_id"]) for row in rows]

    def product_for_campaign(self, campaign_id: str, workspace_id: str) -> dict[str, Any] | None:
        """The product a campaign speaks for, or ``None``.

        With ``angle``: how this campaign pitches it — the applied plan's angle
        for its channel, or the one-liner when no plan made the campaign. It is
        what posts are written from and what `{product_angle}` fills, so a
        revision's new angle reaches what is sent.
        """
        row = self.connection.execute(
            "SELECT p.* FROM gtm_campaign_links l JOIN gtm_products p "
            "ON p.id = l.product_id AND p.workspace_id = l.workspace_id "
            "WHERE l.campaign_id = ? AND l.workspace_id = ?",
            (str(campaign_id or ""), workspace_id),
        ).fetchone()
        if not row:
            return None
        product = self._product(row)
        product["angle"] = self.plan_angle(campaign_id, workspace_id) or product["one_liner"]
        return product

    def linked_workspace(self, campaign_id: str) -> str:
        """The workspace whose product a campaign speaks for, or "" if unlinked.

        A campaign has at most one link (`campaign_id` is the key), so the link
        says whose product it is.
        """
        row = self.connection.execute(
            "SELECT workspace_id FROM gtm_campaign_links WHERE campaign_id = ?",
            (str(campaign_id or ""),),
        ).fetchone()
        return str(row[0]) if row else ""

    def product_for_linked_campaign(self, campaign_id: str) -> dict[str, Any] | None:
        """The product a campaign speaks for, read through the link's own workspace.

        For the timers, which act for the install rather than for a signed-in
        person, and so have no workspace of their own to ask with. Asking with
        the install's workspace found nothing for any campaign linked from a
        workspace login (D-109). A request must not use this: it would read
        another workspace's product (D-125).
        """
        workspace_id = self.linked_workspace(campaign_id)
        return self.product_for_campaign(campaign_id, workspace_id) if workspace_id else None

    def plan_angle(self, campaign_id: str, workspace_id: str) -> str:
        """The angle the applied version of a campaign's plan gives its channel, or "".

        The version, not the plan that created the campaign: a revision is
        applied onto the same campaigns, and its angle is the one that counts.
        """
        link = self.connection.execute(
            "SELECT l.channel, p.root_id FROM gtm_campaign_links l JOIN gtm_plans p "
            "ON p.id = l.plan_id AND p.workspace_id = l.workspace_id "
            "WHERE l.campaign_id = ? AND l.workspace_id = ?",
            (str(campaign_id or ""), workspace_id),
        ).fetchone()
        if not link:
            return ""
        found = dict(link)
        applied = self.connection.execute(
            "SELECT plan_json FROM gtm_plans WHERE root_id = ? AND workspace_id = ? "
            "AND status = 'applied' ORDER BY version DESC LIMIT 1",
            (found["root_id"], workspace_id),
        ).fetchone()
        if not applied:
            return ""
        for channel in json.loads(dict(applied)["plan_json"]).get("channels") or []:
            if channel.get("kind") == found["channel"]:
                return str(channel.get("angle") or "")
        return ""

    # ── plans (S-12.02.01) ──────────────────────────────────────────────────

    @staticmethod
    def _plan(row: Mapping[str, Any]) -> dict[str, Any]:
        item = dict(row)
        plan: dict[str, Any] = {
            key: item[key]
            for key in ("id", "workspace_id", "product_id", "root_id", "parent_id", "status",
                        "source", "provider_id", "model_id", "policy", "created_at", "applied_at")
        }
        plan["version"] = int(item["version"])
        plan["product_version"] = int(item["product_version"])
        for key in _PLAN_JSON:
            plan[key] = json.loads(item[f"{key}_json"])
        return plan

    def create_plan(
        self,
        workspace_id: str,
        *,
        product: Mapping[str, Any],
        request: Mapping[str, Any],
        envelope: Mapping[str, Any],
        plan: Mapping[str, Any],
        feasibility: Mapping[str, Any],
        notes: list[str],
        source: str,
        provider_id: str = "",
        model_id: str = "",
        policy: str = "",
        parent: Mapping[str, Any] | None = None,
        created_at: str = "",
    ) -> dict[str, Any]:
        """Store a draft. With ``parent`` it is the next version of that line.

        ``created_at`` is for a revision: its horizon is counted from the same
        moment, so its window ends exactly where its parent's does.
        """
        plan_id = str(uuid.uuid4())
        with self.connection.transaction() as db:
            if parent is None:
                root_id, parent_id, version = plan_id, "", 1
            else:
                root_id, parent_id = str(parent["root_id"]), str(parent["id"])
                row = db.execute(
                    "SELECT MAX(version) AS latest FROM gtm_plans WHERE root_id = ?", (root_id,)
                ).fetchone()
                version = int(dict(row)["latest"] or 0) + 1
            db.execute(
                "INSERT INTO gtm_plans (id, workspace_id, product_id, root_id, parent_id, "
                "version, status, request_json, product_snapshot_json, product_version, "
                "envelope_json, plan_json, feasibility_json, notes_json, source, provider_id, "
                "model_id, policy, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, 'draft', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    plan_id,
                    workspace_id,
                    str(product["id"]),
                    root_id,
                    parent_id,
                    version,
                    json.dumps(dict(request)),
                    json.dumps(dict(product)),
                    int(product["version"]),
                    json.dumps(dict(envelope)),
                    json.dumps(dict(plan)),
                    json.dumps(dict(feasibility)),
                    json.dumps(list(notes)),
                    source,
                    provider_id,
                    model_id,
                    policy,
                    created_at or _now(),
                ),
            )
        return self.get_plan(plan_id, workspace_id)

    def get_plan(self, plan_id: str, workspace_id: str) -> dict[str, Any]:
        row = self.connection.execute(
            "SELECT * FROM gtm_plans WHERE id = ? AND workspace_id = ?", (plan_id, workspace_id)
        ).fetchone()
        if not row:
            raise KeyError(f"Plan not found: {plan_id}")
        return self._plan(row)

    def list_plans(self, workspace_id: str, *, product_id: str = "") -> list[dict[str, Any]]:
        if product_id:
            rows = self.connection.execute(
                "SELECT * FROM gtm_plans WHERE workspace_id = ? AND product_id = ? "
                "ORDER BY created_at DESC, version DESC",
                (workspace_id, product_id),
            ).fetchall()
        else:
            rows = self.connection.execute(
                "SELECT * FROM gtm_plans WHERE workspace_id = ? ORDER BY created_at DESC, version DESC",
                (workspace_id,),
            ).fetchall()
        return [self._plan(row) for row in rows]

    def move_plan(
        self,
        plan_id: str,
        workspace_id: str,
        *,
        allowed_from: tuple[str, ...],
        to: str,
        db: Database | None = None,
    ) -> None:
        """Change a plan's status only from an allowed one, atomically.

        The condition is in the UPDATE, so of two requests racing to apply the
        same draft exactly one wins and the other is told why.
        """
        if to not in PLAN_STATUSES:
            raise ValueError(f"Unknown plan status {to!r}.")
        target = db or self.connection
        placeholders = ", ".join("?" for _ in allowed_from)
        applied = ", applied_at = ?" if to == "applied" else ""
        params: list[Any] = [to]
        if applied:
            params.append(_now())
        params += [plan_id, workspace_id, *allowed_from]
        cursor = target.execute(
            f"UPDATE gtm_plans SET status = ?{applied} WHERE id = ? AND workspace_id = ? "
            f"AND status IN ({placeholders})",
            params,
        )
        if getattr(cursor, "rowcount", 1) == 0:
            current = self._read_status(target, plan_id, workspace_id)
            raise PlanStateError(
                f"This plan is {current}, so it cannot become {to}. Only a plan that is "
                f"{' or '.join(allowed_from)} can."
            )

    def set_baseline(self, plan_id: str, workspace_id: str, baseline: Mapping[str, Any]) -> None:
        """Record what was already done when this version was applied — once.

        A resumed apply must not move it: sends between the two attempts
        belong to this version, not to the one before.
        """
        self.connection.execute(
            "UPDATE gtm_plans SET baseline_json = ? WHERE id = ? AND workspace_id = ? "
            "AND baseline_json = '{}'",
            (json.dumps(dict(baseline)), plan_id, workspace_id),
        )

    def _read_status(self, db: Database, plan_id: str, workspace_id: str) -> str:
        row = db.execute(
            "SELECT status FROM gtm_plans WHERE id = ? AND workspace_id = ?", (plan_id, workspace_id)
        ).fetchone()
        if not row:
            raise KeyError(f"Plan not found: {plan_id}")
        return str(dict(row)["status"])

    # ── reviews (S-12.02.03) ───────────────────────────────────────────────

    @staticmethod
    def _review(row: Mapping[str, Any]) -> dict[str, Any]:
        item = dict(row)
        review: dict[str, Any] = {
            key: item[key]
            for key in ("id", "plan_id", "workspace_id", "summary", "source", "provider_id",
                        "model_id", "policy", "created_at")
        }
        for key in ("measurements", "findings", "remedies", "notes"):
            review[key] = json.loads(item[f"{key}_json"])
        return review

    def create_review(
        self,
        plan_id: str,
        workspace_id: str,
        *,
        measurements: list[Mapping[str, Any]],
        findings: list[Mapping[str, Any]],
        remedies: list[Mapping[str, Any]],
        summary: str,
        notes: list[str],
        source: str,
        provider_id: str = "",
        model_id: str = "",
        policy: str = "",
    ) -> dict[str, Any]:
        self.get_plan(plan_id, workspace_id)  # KeyError for a plan that is not this workspace's
        review_id = str(uuid.uuid4())
        with self.connection.transaction() as db:
            db.execute(
                "INSERT INTO gtm_reviews (id, plan_id, workspace_id, measurements_json, "
                "findings_json, remedies_json, summary, notes_json, source, provider_id, "
                "model_id, policy, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    review_id,
                    plan_id,
                    workspace_id,
                    json.dumps([dict(item) for item in measurements]),
                    json.dumps([dict(item) for item in findings]),
                    json.dumps([dict(item) for item in remedies]),
                    summary,
                    json.dumps(list(notes)),
                    source,
                    provider_id,
                    model_id,
                    policy,
                    _now_precise(),
                ),
            )
        return self.get_review(review_id, workspace_id)

    def get_review(self, review_id: str, workspace_id: str) -> dict[str, Any]:
        row = self.connection.execute(
            "SELECT * FROM gtm_reviews WHERE id = ? AND workspace_id = ?", (review_id, workspace_id)
        ).fetchone()
        if not row:
            raise KeyError(f"Review not found: {review_id}")
        return self._review(row)

    def latest_review(self, plan_id: str, workspace_id: str) -> dict[str, Any] | None:
        row = self.connection.execute(
            "SELECT * FROM gtm_reviews WHERE plan_id = ? AND workspace_id = ? "
            "ORDER BY created_at DESC LIMIT 1",
            (plan_id, workspace_id),
        ).fetchone()
        return self._review(row) if row else None

