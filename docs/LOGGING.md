# Finding a failure

Copy the `Reference: E-...` shown by the screen, command or job history.
Search Render's Logs for that exact reference. On a local install search
`OFFSETX_DATA_DIR/logs/failures.jsonl` and its numbered rotated files.
Records include UTC time, the operation/route, workspace identifier, exception
type and safe traceback locations. They exclude messages, source lines, locals,
request bodies, query strings, cookies, keys, database credentials and prompts.
The trace identifies where code failed; it is not a copy of customer data.

API failures retain their status and expose `error_id`, `X-Error-ID`, and a
readable reference. Successful requests have a bounded access record and
`X-Request-ID`; they never log bodies. `offsetx-web` disables uvicorn's separate
access log so query strings do not escape through another channel. Run through
the documented launcher. External reverse proxies and independently configured
server loggers have their own logging policies and need separate inspection.

Each local file is capped at 1 MiB, with three backups (at most 4 MiB total).
Rotation is serialised between threads and processes. Files are opened per
record and closed immediately; restarting the app keeps the retained files.
The log has no database schema and does not share a provider egress log.

The local writer respects the restore lease and pending journal. During
recovery, or when the local file cannot be written, the record goes to stdout
only. A broken stdout sink cannot prevent the local-file attempt. If both
sinks are unavailable, diagnostic retention is not guaranteed; logging does
not mask or repeat the underlying operation. Capture stdout in the local
service manager if records from a disk/recovery failure must survive a restart.

On Render (`RENDER` supplied by the platform), no local log is written. A
published Codex environment does not configure Render retention. Confirm the
hosting plan's actual log retention before promising next-day lookup; long-term
retention requires a configured external destination. This implementation has
not been deployed to Render or verified against its live retention policy.

Existing authenticated API routes and approvals stay in effect. Unexpected
errors return a safe 500; they are never converted into a successful model
fallback. Known database/profile guidance retains its next step. Commands keep
existing nonzero results and numeric SystemExit codes; an unexpected command
exception is reported and returns 1. Job errors retain retry/unknown-delivery
semantics; an uncertain delivery must be checked before a person resends it.

Rollback: stop the application and workers, run the preceding application
revision with the same data directory and database settings, and verify live
and readiness checks plus representative CRM reads. Leave the logs in place:
the previous revision ignores them, and no customer-table migration is added.
Restore the preceding `offsetx-web` logger configuration with that revision.
Record an actual rollback run in the work order; this procedure alone is not
evidence that it succeeded.

Email and content cycle failures also appear in Settings and Posting status,
including errors caught inside individual sends, sweeps, publishing and writer
fallbacks. A later successful cycle clears its previous summary. The owner can
read GET /api/v1/agent-routine-status without querying the failing run-history
store. A successful send with a counter/archive warning stays successful and
is never resent to repair bookkeeping; its result carries the warning ID.
