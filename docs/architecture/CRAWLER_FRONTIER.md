# S-05.01.01 — Durable crawl frontier

## Problem

The public-web crawler already had strong request safety — robots.txt,
crawl-delay handling, domain allow-lists, redirect validation, response-size
limits, SSRF protection and a hard block on session-gated social platforms.
What it did not have was memory. Every run rebuilt an in-memory `deque`, so the
same seed could consume crawl budget again even when it had not changed.

The success measure for this story is **useful pages per crawl-hour**: changed
pages should become eligible quickly, stable pages should back off, and no page
may enter scheduling state unless the existing public-URL policy accepts it.

## Why this is not an AI problem

No model is used. Revisit scheduling is deterministic state management, not a
prediction problem with labelled training data. An ML model would add cost,
latency, evaluation burden and a new failure mode without evidence that it can
beat a simple observed-change baseline.

The baseline is therefore the production implementation:

- changed content: revisit after 1 day
- unchanged content: exponential/age-based backoff, capped at 30 days
- failed fetch: 15-minute exponential retry backoff, capped at 1 day

The scheduling rule can be replaced later only if measured crawl data shows a
better policy materially improves useful pages per crawl-hour.

## Data and flow

```text
seed URL / discovered link
        |
        v
existing validate_public_url()
  - http/https only
  - allow-list
  - no credentials
  - no local/private/reserved target
  - LinkedIn/Instagram/Facebook/Threads/TikTok/X blocked
        |
        v
crawl_frontier.sqlite3
  url + host + depth
  last content hash
  last crawl / last change
  next due time
  failure counters
  expiring claim lease
  per-host next request slot
        |
        v
claim only due rows within current run's allowed domains + depth
        |
        v
existing SafePublicFetcher / Crawl4AIPageFetcher
  robots.txt + crawl delay + SSRF/redirect/size controls
        |
        +--> success: hash content, update change history, schedule revisit
        |
        +--> failure: release lease, record bounded error, back off retry
        |
        +--> links: pass through the same URL admission policy before persistence
```

The frontier lives at `<OFFSETX_DATA_DIR>/crawler_frontier.sqlite3`. It stores
URLs and scheduling metadata only; it does not store raw HTML, cookies,
credentials or authenticated browser state.

## Concurrency

A due URL is claimed inside `BEGIN IMMEDIATE` and receives a short expiring
lease. A second process pointed at the same SQLite file cannot claim that row
until the lease expires. Success and failure both clear the lease. If a worker
dies, the lease expires and the URL becomes recoverable rather than remaining
stuck forever.

URL leases are not enough for politeness: two processes can claim two different
URLs on one host. The same SQLite file therefore also owns
`crawl_host_pace`. Before a request starts, the fetcher transactionally
reserves that host's next request slot, commits the new deadline, then sleeps
outside the transaction if needed. Two processes arriving together cannot both
observe the same free slot. A crashed worker can waste one delay interval, but
cannot make the crawler run faster than the configured/robots floor.

SQLite is deliberate here because off_CRM is still local-first and already uses
SQLite for its local operational stores. A distributed queue would add an
external service without solving a present requirement. If this crawler becomes
a multi-host service, the frontier is the boundary to move to Postgres or a
dedicated scheduler.

## Politeness and security

The frontier does **not** copy request policy. It injects every URL through the
existing `validate_public_url()` path. The existing fetchers still parse
robots.txt and decide the applicable crawl delay; they now reserve that delay
through the frontier's shared per-host clock. This keeps one security/politeness
policy rather than two versions that can drift.

Session-gated platforms are therefore rejected before insertion. Links to them
may remain as reference data on a parsed public page, but they are never crawl
targets.

## Persistence, migration and rollback

There is no migration of the main CRM database. The frontier database and its
URL/frontier plus host-pacing tables are created lazily on first crawl with
`CREATE TABLE IF NOT EXISTS`.

Rollback is safe: older code ignores `crawler_frontier.sqlite3`. Keeping the
file preserves scheduling history for a later re-upgrade. Deleting it is also
safe for CRM data, but intentionally resets crawl history and makes every seed
eligible again.

S-06.02.04 (data deletion / subject access) must include this file in its store
inventory because it now contains persisted source URLs.

## Observability

Each row records crawl count, change count, unchanged streak, failure count,
last error, last crawl, last observed change, next due time and lease expiry.
This is enough to explain why a URL is or is not eligible without model
introspection.

## Known limits

- Revisit cadence is a deterministic baseline, not learned prediction.
- The maximum revisit interval is 30 days.
- The frontier schedules only URLs already supplied or discovered inside the
  current public-domain policy; it is not a search engine.
- Authenticated/session-gated crawling is intentionally forbidden.
- Extraction packs and competitor-post structure analysis remain S-05.01.02
  and S-05.01.03 respectively.
