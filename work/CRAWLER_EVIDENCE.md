# S-05.01.01 evidence · 2026-11-19

Mode TASK; implementer Codex /root; review is a separate implementer self-review,
not independent review. Code is implemented; the story remains IN_REVIEW until
the existing browser/project verifier gate can pass. The work order is
CRAWLER_WORK_ORDER.md and the public guide is docs/architecture/CRAWL_FRONTIER.md.

## Acceptance coverage

| Criterion | Executed evidence |
|---|---|
| AC1: robots and host crawl delays honoured | test_crawl_fetch_safety.py; long-delay, persisted robots, redirect and private-DNS tests in test_crawl_runner.py; thread and actual-process claims in test_crawl_frontier.py |
| AC2: unchanged pages revisited less frequently | test_changed_pages_are_revisited_sooner_than_repeatedly_unchanged_pages; persisted metadata/backup cases |
| AC3: no session-gated platform in inspected frontier | invalid target cases, policy-change pruning, corrupt-registry preservation and redirected-platform refusal |
| Necessary lifecycle and integrity | canonical seed/dedup, atomic seed batches, scopes, stale claim refusal/recovery, bounded attempts, persistent retries, capacity/removal, depth changes, CLI and backup/restore |

## Commands and real results

Working directory /workspace/off_CRM. Managed environment variables:
UV_CACHE_DIR=/workspace/.uv-cache; UV_TOOL_DIR=/workspace/.uv-tools.

- `uv run pytest tests/test_crawl_cli.py tests/test_crawl_frontier.py tests/test_crawl_runner.py tests/test_crawl_fetch_safety.py -q`: 45 passed, 3 warnings in 7.71s; crawler-acceptance-final.log.
- `uv run pytest tests/test_crawl_cli.py tests/test_crawl_frontier.py tests/test_crawl_runner.py tests/test_crawl_fetch_safety.py tests/test_discovery.py tests/test_exclusion_discovery.py tests/test_parallel_discovery_and_notion.py tests/test_security_audit.py tests/test_ai_egress_wall.py -q`: 125 passed, 6 warnings in 14.55s; crawler-focused.log.
- `uv run pytest -q`: 2039 passed, 21 failed, 4 skipped, 6 warnings in 137.16s; crawler-full-python.log.
- `npm test --prefix frontend`: 8 files and 116 tests passed; crawler-frontend-tests.log.
- `npm run build --prefix frontend`: TypeScript and Vite build passed; crawler-frontend-build.log.
- `uv run ruff check --select E9,F63,F7,F82 .`: all checks passed.
- `git diff --check`: exit 0.
- `uv build --wheel --out-dir work/crawler-dist`: wheel built; inspected new modules and offsetx-crawl entry point in the zip; crawler-build.log.
- `uv run offsetx-crawl --db work/empty-crawl-demo.db --allow example.org inspect`: empty queue with a seed action, no network; crawler-cli-smoke.log.
- `uv run python scripts/verify_board.py --skip-tests`: structural check is saved in crawler-board-structure.log.
- `uv run python -u scripts/verify_board.py`: full replay is saved in crawler-board-full.log; existing Chromium commands fail in this environment.

The full verifier was started while the crawler was still IN_PROGRESS. Its
structural snapshot after closing the local slice records it IN_REVIEW. No
old DONE story's historical evidence was rewritten to appear green locally.
Compare failure node IDs against work/python-final.log: the same 21 browser
failures precede the crawler changes. No test or browser security policy was
disabled. Four unrelated environment-gated tests remain skipped.

## Test-first and review record

Before implementation, crawler-fetch-red.log reproduces three existing failures:
shortened crawl delay, unchecked redirect robots and cross-origin robots reuse.
Later RED logs reproduce fractional delay, paced redirect loops, blocking FIFO
opens and ignored depth changes. Their corresponding checks now pass. Frontier
and runner tests were defined before their implementation, then exercised once
the new module interfaces existed; an import error is not claimed as RED proof.
Additional lifecycle/security checks were added during self-review.

D-54 through D-59 record found/fixed defects. Reviewed SQL transaction ownership,
leased-worker recovery, deferred redirect state/counts, policy changes, shared
host timing, error propagation, queue bounds, origin/agent cache expiry, file
types/permissions, public transport guards and CLI exits. Tests include an actual
four-process race over one SQLite file. This is local security/integration
coverage, not an independent penetration test of an external service.

No real site was crawled and no live provider was called by these tests. No
application deployment has occurred. Workspace queue isolation is not a claim
that S-06.01.01's key/session isolation is implemented.

## Recovery and remaining gate

A test executes SQLite backup, restore and content/history inspection. Others
execute stale-lease recovery and explicit removal. Code rollback: stop workers,
keep the separate database/backup and restore the prior application version,
which ignores the new file. The CRM schema is unchanged.

D-51 remains the local release blocker: Chromium cannot launch with its sandbox
and managed policy blocks embedded test pages. The implementation is ready for
browser verification in a suitable environment; until then keep IN_REVIEW.


Certification update · 2026-11-19: GitHub Actions run 2291 passed full Python
(2060 passed, 4 skipped), all 55 historical evidence commands, frontend 116 and
the production build. S-03.02.05, S-02.02.02, S-04.01.01 and S-05.01.01 are now
DONE. Earlier IN_REVIEW statements describe the prior local-only evidence stage.
See work/REMOTE_VERIFICATION.md and work/ci-run-2291.log. PR #29 is unmerged;
no deployment or independent penetration assessment is claimed.
