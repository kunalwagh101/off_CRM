# S-05.01.01 · Persistent public crawl frontier

Mode TASK; leading role senior engineer; implementer Codex /root.
Authorised continuation: next ready capability from the prior five-item list.
S-06.01.01 remains READY/unclaimed. Previous three stories remain IN_REVIEW
because browser fixture access is still unavailable (work/browser-recheck.log).

## Requirements and tasks

- T-05.01.01.a / AC3: persist a workspace-scoped public URL frontier, inspect it,
  deduplicate canonical URLs, reject credentials/private/social targets and
  current attended-only platform domains at insertion and consumption.
- T-05.01.01.b / AC1: reuse SafePublicFetcher/robots/parser; honour crawl delay
  without shortening it, recheck robots on redirect destinations, coordinate
  host pacing across worker processes and retry safely after interrupted claims.
- T-05.01.01.c / AC2: store observed content hashes, unchanged streaks, errors
  and next_due. Changed pages reset to the baseline revisit interval; unchanged
  pages back off to a bounded maximum. Use an injected clock in meaningful tests.
- T-05.01.01.d: complete CLI seed/inspect/run flow, bounded page attempts,
  same-policy link expansion, failure backoff, stale-claim recovery, docs,
  rollback exercise, acceptance/security/integration evidence and board update.

## Architecture and interfaces

Create crawl/frontier.py (SQLite via existing guarded SQLiteDatabase),
crawl/runner.py and crawl_cli.py; expose offsetx-crawl in pyproject.toml.
Frontier(path, policy, workspace_id='local') owns enqueue/inspect/claim/finish.
Claims have opaque tokens and leases; only the claim owner can finish. All
compound writes use transactions. Persist next host request times and lease
ownership in the same file, so separate processes share limits. Store only URL,
metadata and content hashes; parsed pages return to trusted host consumers.

FrontierRunner(frontier, fetcher=None) uses the existing
SafePublicFetcher by default. Extend it only where shared pacing, complete
robots delay and redirect checks need a seam. Preserve existing discovery API,
POI import and optional Crawl4AI behaviour. No model/provider calls, credentials,
logged-in sessions, automatic posting, or browser-policy changes.

CLI: offsetx-crawl --db PATH --workspace ID --allow DOMAIN [--allow DOMAIN]
seed URL...; inspect; remove URL; run --max-pages N; watch. JSON output; readable failures and
nonzero errors. No UI is required for this library/CLI story.

Defaults (implementation choices, not business rules): revisit 1 day to 30 days;
failure backoff bounded at 1 day; leases 10 minutes and heartbeat before requests.
Parameters are validated and configurable on the library boundary. Robots cache
and request pacing use bounded, local data; caching must not widen URL policy.

## Verification

Baseline: 15 existing discovery checks pass. Structural board check passes.
Full regression from the previous unchanged revision: 1994 passed, 21 existing
Chromium failures, 4 skipped. Recheck reproduces the environment failure.
Write acceptance tests before behaviour edits; run them RED, implement GREEN,
then run affected discovery, CLI, security-wall and storage checks. Exercise
robots refusal/long delays/redirects, changing vs unchanged pages, retries,
crashes, stale tokens, concurrent workers and blocked targets. Run full Python,
frontend tests/build and structural verifier; report known environment failures.
Self-review must be labelled; do not claim independent penetration testing.

## State and recovery

New, separate SQLite file; no changes to CRM schema. Back up with SQLite backup;
restore into an isolated file and verify queue state. Older versions ignore it.
Only promote DONE after the required project verifier gate passes. Otherwise
keep IN_REVIEW with exact missing evidence. Do not change managed browser policy.

Resumed 2026-11-19. Owner controls remain in the shared BOARD.md. The chosen
worker uses durable deferral rather than a sleep parameter, so long site delays
do not occupy a worker. The frontier owns the injected clock.


Certification update · 2026-11-19: GitHub Actions run 2291 passed full Python
(2060 passed, 4 skipped), all 55 historical evidence commands, frontend 116 and
the production build. S-03.02.05, S-02.02.02, S-04.01.01 and S-05.01.01 are now
DONE. Earlier IN_REVIEW statements describe the prior local-only evidence stage.
See work/REMOTE_VERIFICATION.md and work/ci-run-2291.log. PR #29 is unmerged;
no deployment or independent penetration assessment is claimed.
