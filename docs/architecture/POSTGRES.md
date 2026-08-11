# Postgres

off_CRM is SQLite-first and stays that way. Postgres is for the one case SQLite
genuinely cannot serve.

```
offsetx-db check                                       # what would be opened, and can it be reached
offsetx-db copy-log --from local_data/ai_egress.db --to postgresql://…
OFFSETX_DATABASE_URL=postgresql://…                    # switch over; unset to go back
```

---

## Scope, plainly

**One store is on Postgres: the egress log.** The CRM database, the context
layer, the recall index, the evals scoreboard, the response cache and the sales
tracker are all still SQLite-only. That is a real limit, not a phrasing of one.

The seam they will use exists and is tested; they have not been moved.

### Why the egress log went first

Not because it was easiest — though at 253 lines it was. Because it is the one
that is **broken in the deployed environment today**.

`BUILD_STATE` §6.4: on Render, `OFFSETX_DATA_DIR` points at `/tmp`, which is
wiped on every restart. The egress log lives there. That log is the record of
exactly what data left to which provider, and the entire security argument of
this system is that the guarantee is *verified* rather than trusted.

**A verification trail that resets on every restart verifies nothing.**

Everything else in `/tmp` is an inconvenience to lose. This one is a hole in the
argument. It also has no foreign keys into the CRM — the AI module was built to
be liftable — so it can move on its own.

The CRM database has the opposite profile: bigger, more entangled, and losing it
on Render is not a security problem because nobody runs their real CRM on a
disposable disk.

---

## The seam

`offsetx_apollo_builder/db/` — about 250 lines.

```python
database = open_database("postgresql://…")   # or a path
database.execute("SELECT * FROM t WHERE a = ?", [value]).fetchall()
```

Stores keep writing readable SQL with `?` placeholders. `open_database` returns
something that behaves like the `sqlite3.Connection` they already use — same
`execute`, `executescript`, `transaction`, same `row["column"]` and `dict(row)`.

**No ORM.** SQLAlchemy would have turned auditable SQL into expression trees, in
a codebase whose security argument depends on being able to *read the queries*.
It would also have been a far larger diff for the same result.

### `?` → `%s`, carefully

psycopg takes `%s`, not `?`, and `outreach/store.py` alone contains 449 `?`.
Rewriting them all would have been a huge diff that broke SQLite. So the
translation happens once, in `db/translate.py`.

It is a character walker, not a regex, because both `?` and `%` occur inside
string literals:

```sql
SELECT * FROM t WHERE note LIKE '50%' AND q = ?
```

A blind replace corrupts the literal, and the corruption is invisible until
someone reads the row back. The walker tracks quoting — including `'it''s'`,
where a doubled quote is an escape and not the end of the string — and is a
dozen lines that cannot be wrong in the way a pattern can.

`%` is doubled because psycopg treats it as a placeholder marker whenever
parameters are present. For the same reason, parameters are **always** passed as
a sequence, never `None`: otherwise the same translated SQL would mean two
different things depending on the call.

### Autocommit, to match

SQLite runs at `isolation_level=None`. The stores were written against that:
they open an explicit transaction when they need one, and otherwise expect a
statement to be durable when it returns. psycopg defaults to an open transaction
block, so the Postgres backend sets `autocommit=True` — leaving the default in
place would silently change the contract for every existing caller.

---

## A bug the migration found

`EgressLog.stats()` contained:

```sql
SELECT provider_id, provider_name, jurisdiction, COUNT(*) AS calls
FROM ai_egress_log GROUP BY provider_id
```

SQLite runs this and picks an **arbitrary row** for `provider_name` and
`jurisdiction`. Postgres refuses it outright:

> ERROR: column "provider_name" must appear in the GROUP BY clause

Grouping on all three is both portable and the answer that was actually meant.
This is the kind of thing that only surfaces when a second engine reads the same
SQL, and it is one of the reasons to have one.

---

## Moving an existing log across

```bash
$ offsetx-db copy-log --from local_data/ai_egress.db \
                      --to postgresql://off_crm@db.internal/off_crm
From : sqlite at local_data/ai_egress.db
To   : postgres at postgresql://off_crm:***@db.internal/off_crm
120 row(s) copied. Source now holds 120, destination 120.

The SQLite file was not modified. To switch over, set:
    OFFSETX_DATABASE_URL=postgresql://off_crm@db.internal/off_crm
and restart. To go back, unset it.
```

Four properties, each chosen against a specific way this goes wrong:

| Property | The failure it prevents |
|---|---|
| **Never deletes the source** | A failed cutover is an environment variable away from being undone, not a restore |
| **Idempotent** — skips rows already present by primary key | An interrupted copy leaves an operator guessing whether re-running duplicates everything |
| **Counts both sides and reports** | "It seemed to work" |
| **Explicit column list, not `SELECT *`** | Column order across two engines is not something to leave to chance; a new column would shift every value one place to the left. A test fails if the list and the schema drift apart |

Passwords are masked in every line it prints.

---

## Configuration

| Variable | Effect |
|---|---|
| `OFFSETX_DATABASE_URL` | Where the egress log goes. Unset → the SQLite file under `OFFSETX_DATA_DIR`, as before |
| `OFF_CRM_TEST_POSTGRES_URL` | Runs the Postgres half of the test suite. Unset → those tests skip |

Resolution order is **explicit argument → environment → default path**. The
middle rung lets a deployment set one variable without every call site learning
about it; the top rung keeps a test's scratch file safe from an environment
variable reaching in.

Only an explicit `postgresql://`, `postgres://` or `psql://` scheme means
Postgres. Everything else is a path — so a mistyped DSN fails loudly instead of
silently creating an empty SQLite file that looks like it worked.

Install with `uv pip install 'offsetx-apollo-builder[postgres]'`. Without
psycopg, a Postgres URL raises a message containing that command rather than
`No module named 'psycopg'`.

---

## Testing

The egress log's tests are **parametrised over both backends**. With
`OFF_CRM_TEST_POSTGRES_URL` set they run twice, against a real Postgres server;
without it the Postgres half skips and says so — the same rule as the live
Docker sandbox test. A test that silently passes because it did not run is worse
than one that reports being skipped.

```bash
export OFF_CRM_TEST_POSTGRES_URL='postgresql://postgres@/offcrm_test?host=/tmp&port=5433'
python -m pytest tests/test_db_backend.py -q     # 35 passed
python -m pytest tests/ -q                       # 663 passed
```

Verified end to end by booting the app with the log on Postgres: the table is
created in the server, `GET /ai/egress-log/stats` reports `"backend":
"postgres"`, no `ai_egress.db` appears in the data directory, and the CRM keeps
working on SQLite in the same process.

---

## What is not built

- **The other five stores.** CRM, context, recall, scoreboard, cache, sales —
  all SQLite-only. The seam is there; the work is not done.
- **Schema migrations for Postgres.** The log creates its table with
  `CREATE TABLE IF NOT EXISTS` and has never needed a migration.
  `outreach/store.py` has a real migration path (`PRAGMA table_info`,
  `PRAGMA user_version`) with no Postgres equivalent yet — `information_schema`
  and a settings row are the answer, and neither is written.
- **FTS.** `expert_chunks_fts` is a SQLite `fts5` virtual table. Postgres uses
  `tsvector`, which is a genuinely different implementation and not a
  translation.
- **Connection pooling.** One connection per store, as today. Fine for one
  process; a multi-worker deployment wants `psycopg_pool`.
- **Moving anything back.** `copy-log` goes SQLite → Postgres only.
