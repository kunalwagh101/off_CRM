# Persistent public crawl frontier · S-05.01.01

The existing discovery crawler remains a bounded, one-off POI discovery path.
The new `crawl/` library and `offsetx-crawl` CLI retain a public crawl frontier
between runs. They reuse SafePublicFetcher and Scrapling without opening a
browser session, contacting a model, importing contacts or sending mail.

## Use

```bash
uv run offsetx-crawl --allow example.org seed https://example.org/
uv run offsetx-crawl --allow example.org inspect
uv run offsetx-crawl --allow example.org run --max-pages 20
uv run offsetx-crawl --allow example.org watch --max-pages 20 --poll-seconds 5
uv run offsetx-crawl --allow example.org remove https://example.org/
```

The default database is `local_data/crawl.db`. Use `--db PATH` for another
file and `--workspace ID` for a separate queue. Repeat `--allow DOMAIN` for each
permitted domain. Global options precede the command. `--help` lists them.
Seed and inspect do not fetch pages. Remove deletes a named, unclaimed URL and
is idempotent; an active claim must finish or expire first.

Run processes one bounded batch. Watch repeats batches until interrupted. A
batch budget counts claims, including failed or paced attempts, so broken sites
cannot evade the limit. Deferred work returns its next_due UTC epoch timestamp.
Workers do not sleep through a site's long crawl delay. With robots delay or
redirect pacing, an initial batch can fetch robots and leave the document due
later; watch continues it. Failed one-shot batches exit 1, invalid input exits 2,
and interruption exits 130. Output is JSON with counts, public metadata and
readable errors. Empty inspection tells the owner to seed a permitted URL.

## Public library

`Frontier(path, CrawlPolicy(...), workspace_id='local', clock=time.time,
revisit_seconds=86400, max_revisit_seconds=2592000, lease_seconds=600,
capacity=10000)` owns seed/enqueue, inspect, claim, finish, retry and remove.
`FrontierRunner(frontier).run_due(max_pages=20)` returns CrawlBatch. Its `pages`
contains ParsedPage values for trusted host consumers; `to_dict()` exposes
metadata and counts. Close both the runner and frontier when finished.

A custom injected fetcher is a trusted host dependency and must honour the
same public-navigation, robots and pacing contract. Production defaults use
FrontierFetcher, not an unguarded substitute. The new CLI uses static HTTP
fetching. Existing JavaScript discovery remains on the separate one-off path.

## Scheduling and state

The SQLite database uses the existing guarded SQLiteDatabase boundary. Every
compound claim/update uses a transaction. URLs are canonicalised and unique
within a workspace; fragment duplicates do not reset schedule/history. A batch
of seeds validates before insertion. Queue capacity, URL size, seed count,
depth and batch size are bounded. Lowering max-depth makes deeper stored URLs
ineligible without deleting them. Inspection reports eligibility.

First observations and changed content use the base revisit interval. Each
unchanged observation doubles that interval to the maximum. SHA-256 is computed
from the fetched HTML bytes by the existing parser. The queue stores the hash,
title, timestamps, counts, next_due and error, not page text or extracted people.
The actual parsed page returns to the trusted caller. The scheduler does not
claim that cosmetic HTML changes are meaningful business changes.

Fetch errors retry after 60 seconds, doubling to at most one day. Deferral does
not increase the error count. Successful observations clear failures. A stale
worker cannot overwrite a new claim's result. A stopped worker's lease expires,
after which another worker can reclaim the URL. This gives recoverable,
at-least-once public fetches; a process dying after receiving a response can
cause a later refetch. There is no claim of exactly-once network activity.

## Politeness and navigation boundaries

Public URLs must fit the explicit domain allow-list. Credentials, private or
reserved literal addresses, social crawl targets and configured attended-only
platform domains are refused. DNS answers and every redirect still pass the
existing public fetch checks. Redirect destinations are validated before being
persisted or requested. No new login, cookie, proxy, stealth or bypass path exists.
The existing fetcher checks DNS before transport; this is not a new guarantee
against a hostile DNS resolver changing answers between checks and connection.

Current platform rules are checked again before consumption and inspection.
Tightening them removes prohibited queued targets, including resumed redirect
URLs. Other workers must use the same database to share pacing. A corrupt
platform registry stops processing and cannot cause a policy-driven purge.

Host request times and active leases are shared across workspaces and processes:
they use one public bot identity. URL queues are workspace-scoped; public robots
rules and host pace are shared. The floor applies to every actual request,
including robots fetches and redirects. A long delay schedules a later attempt.
Document and robots redirect positions/counts survive deferral, so a worker
neither repeats the source forever nor resets the redirect limit at each pause.

Robots rules are cached by full origin and user agent for one hour. Pending
robots redirect positions also expire after one hour. Rules older than one day
are removed when loading fresh rules. Changing the user agent selects a separate
cache. A missing robots file (404) allows public crawling; other transport errors
stop the attempt. Fractional delays round up because RobotFileParser accepts
integers; delays are never capped at 30 seconds or silently ignored. Malformed
negative/nonfinite delays refuse the attempt. The one-off HTTP fetcher also gains
complete redirect robots checks and origin-scoped rules. No decision is made
from a model's reading of robots.txt.

## Storage and rollback

This is a new, separate database; CRM schema and discovery records are unchanged.
New files are 0600, existing frontier file permissions are tightened to 0600,
and symlink/nonregular database files are refused. Use a private parent directory.
For a consistent backup, use SQLite's backup API rather than copying a live WAL
file. `test_backup_restores_queue_and_observed_content_without_legacy_migration`
executes a backup, opens the restored file and verifies observed state.

To roll back application code: stop crawl workers, keep the database/backup,
then use the previous version. It ignores the separate file. The previous bounded
POI discovery path still works. Queue removal/restore and stale-claim recovery
are exercised in acceptance tests. No live shared-server migration or deployment
has been performed.

## Verification and limits

Tests are in test_crawl_frontier.py, test_crawl_runner.py, test_crawl_fetch_safety.py
and test_crawl_cli.py. They use the actual SQLite store, parser and HTTP guard
with an in-process transport fixture. They cover restart/leases/concurrency,
robots and redirects, revisit ordering, scopes, private DNS answers, malformed
input, SQL-like URL strings, queue capacity and nonregular file refusal. They
are local tests, not an independent penetration assessment of a remote site.
Current raw results and the known managed-Chromium gate are in
`work/CRAWLER_EVIDENCE.md` and BOARD.md.
