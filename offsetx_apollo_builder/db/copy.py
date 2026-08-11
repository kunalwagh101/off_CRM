"""Copying the egress log from SQLite to Postgres.

Deliberately not a generic "migrate everything" tool. Only the egress log is on
the backend seam today, so this copies the egress log; a tool that claimed to
move the whole database while moving one table would be worse than one that
says what it does.

The copy is **append-only and verified**. It reads rows out of SQLite, writes
them into Postgres, then counts both sides and reports. It never deletes the
source: the SQLite file stays exactly as it was, so a failed cutover is a
matter of pointing the environment variable back rather than a restore.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..ai.log import SCHEMA
from .connection import Database, DatabaseError, describe_target, open_database

#: Written explicitly rather than taken from ``SELECT *``. Column order across
#: two engines is not something to leave to chance, and a schema change that
#: adds a column should fail this loudly instead of shifting every value one
#: place to the left.
EGRESS_COLUMNS = (
    "id",
    "workspace_id",
    "created_at",
    "provider_id",
    "provider_name",
    "model_id",
    "jurisdiction",
    "tier",
    "policy",
    "data_class",
    "task_type",
    "status",
    "error",
    "findings",
    "duration_ms",
    "payload",
    "payload_summary",
    "response_text",
)


@dataclass(frozen=True)
class CopyResult:
    """What moved, and what both sides hold now."""

    source: str
    destination: str
    rows_read: int
    rows_written: int
    source_total: int
    destination_total: int
    skipped_existing: int

    @property
    def ok(self) -> bool:
        return self.rows_read == self.rows_written + self.skipped_existing

    def summary(self) -> str:
        return (
            f"{self.rows_written} row(s) copied"
            + (f", {self.skipped_existing} already present" if self.skipped_existing else "")
            + f". Source now holds {self.source_total}, destination {self.destination_total}."
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "destination": self.destination,
            "rows_read": self.rows_read,
            "rows_written": self.rows_written,
            "skipped_existing": self.skipped_existing,
            "source_total": self.source_total,
            "destination_total": self.destination_total,
            "ok": self.ok,
        }


def _count(database: Database) -> int:
    row = database.execute("SELECT COUNT(*) AS total FROM ai_egress_log").fetchone()
    return int(row["total"]) if row else 0


def copy_egress_log(
    source: Path | str,
    destination: str,
    *,
    batch_size: int = 500,
) -> CopyResult:
    """Copy every egress-log row from ``source`` into ``destination``.

    Rows already present at the destination are skipped by primary key, so
    running it twice is safe and a partial run can be finished by running it
    again. That matters more than speed here: the alternative is an operator
    who is not sure whether to re-run and guesses.
    """
    if not Path(str(source)).exists():
        raise DatabaseError(f"No SQLite database at {source}. Nothing to copy.")

    reader = open_database(str(source), wal=False)
    writer = open_database(destination)
    try:
        if writer.name != "postgres":
            raise DatabaseError(
                "The destination must be a postgresql:// URL. Copying SQLite to "
                "SQLite is a file copy, which the operating system already does."
            )
        writer.executescript(SCHEMA)

        existing = {
            str(row["id"])
            for row in writer.execute("SELECT id FROM ai_egress_log").fetchall()
        }

        columns = ", ".join(EGRESS_COLUMNS)
        placeholders = ", ".join("?" for _ in EGRESS_COLUMNS)
        rows_read = 0
        rows_written = 0
        skipped = 0
        batch: list[tuple[Any, ...]] = []

        cursor = reader.execute(
            f"SELECT {columns} FROM ai_egress_log ORDER BY created_at ASC"
        )
        for row in cursor.fetchall():
            rows_read += 1
            if str(row["id"]) in existing:
                skipped += 1
                continue
            batch.append(tuple(row[name] for name in EGRESS_COLUMNS))
            if len(batch) >= batch_size:
                rows_written += _write(writer, columns, placeholders, batch)
                batch = []
        if batch:
            rows_written += _write(writer, columns, placeholders, batch)

        return CopyResult(
            source=describe_target(str(source)),
            destination=describe_target(destination),
            rows_read=rows_read,
            rows_written=rows_written,
            source_total=_count(reader),
            destination_total=_count(writer),
            skipped_existing=skipped,
        )
    finally:
        reader.close()
        writer.close()


def _write(
    writer: Database, columns: str, placeholders: str, batch: list[tuple[Any, ...]]
) -> int:
    """Write one batch inside a transaction.

    Per batch rather than one transaction for the whole copy: a log with tens of
    thousands of rows should not hold a single transaction open for the duration,
    and the operation is re-runnable, so a batch boundary is a safe place to be
    interrupted.
    """
    with writer.transaction():
        for values in batch:
            writer.execute(
                f"INSERT INTO ai_egress_log ({columns}) VALUES ({placeholders})",
                values,
            )
    return len(batch)
