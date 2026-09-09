# Main consolidation — 9 September 2026

The owner requested one integration branch before promotion to main.
`integration/main-consolidation` starts from main `37cf9b151200be42a6c1c31c8e9a05d6825ac1f5`.
Main and its deployment have not been changed by this work.

## Pending pull requests combined

| PR | Branch | Input commit |
|---|---|---|
| #13 | feature/audit-wp1-durable-state-safe-recovery | 0986070460ae51a926432609feba2fdf93b7f43b |
| #11 | agent/live-integration-audit-20260907 (included through #13) | f2b3000663edf29a21792d4c09f685c1b91b8bc4 |
| #4 | agent/production-contract | 67442bffc5eb2607c1c14634d28b36281ac58489 |
| #6 | feature/s-02-02-02-plan-md | 0c2a04a54694a8e30d8dd15c41a20b21aa44103e |
| #10 | feature/s-11-02-04-page-read-cache | 253449965c1f4313d90c08d10225e1de858e9f6c |

All five input tips are ancestors of the integration branch. The published
consolidation commit keeps main and the four feature tips as parents; the audit
tip is already an ancestor of WP1. This preserves the input histories.

## Conflict decisions

- Preserve main's authentication, serialized database access and failed-action
  recovery; combine WP1's complete backup/restore and persistent deployment.
- Keep the current board and both sets of historical evidence. Refresh stale
  handoff instructions instead of restoring September 5 branch/storage claims.
- PLAN.md is read before every decision. Its initial digest is recorded on the
  existing run-start event; owner edits add version events. Captured evidence
  remains the source of truth for structured facts.
- Keep one bounded page cache. Merge the conservative URL identity and durable
  text sidecars from #10 with main's maximum capture count and action recovery.
  Preserve fragments and raw query order because browser routes, duplicate
  query keys and signed URLs can depend on them. Update the two older tests
  that wrongly required these distinct URLs to collapse.
- Cache hits reuse the original capture, screenshot, truncation state and source
  ID without incrementing actual browser actions. Reloads, waits and partially
  failed mutations discard affected captures. A successful cache hit resets the
  failed-action streak. Seven integration cases cover these interactions.
- PLAN.md remains IN_REVIEW: its file and checklist projection are present, but
  this merge does not claim a completed customer checklist UI.

## Verification

Local commands:

```sh
uv sync --extra dev --extra email --locked
uv run --no-sync ruff check --select E9,F63,F7,F82 .
uv run --no-sync pytest tests -q -ra
uv run --no-sync python scripts/verify_board.py
(cd frontend && npm test && npm run build)
```

The WP1 workflow now runs on this integration branch. It provisions PostgreSQL,
real sandboxed Chromium, Docker and FFmpeg, builds the production container,
tests persistent-volume replacement and browser recovery, runs the complete
Python/frontend suites and the original production audit regressions, and rejects
skipped or missing evidence. The Windows job checks native process leases.
Workflow artifacts and the draft PR carry results for the exact pushed commit.

Local full suite: **1,678 passed, 25 skipped**, with no failures. The skips
require Chromium, a pre-pulled Docker image or PostgreSQL and must pass in the
real-service workflow. Frontend: **116 passed**, production build passed. Ruff
and board structure checks passed.

Focused local results: 58 passed and 5 browser-dependent skips across
PLAN.md, both caches, action recovery, structured results, provenance and claim
verification; all 7 added interaction tests passed. Full combined validation is
required before promotion. Historical green results from #13 do not substitute
for the combined run. Known open audit assertions remain enabled.

## Promotion and deployment

Keep this branch as the single place for integration fixes. Do not merge into
main until the combined results have been reviewed and remaining failures have
been resolved or explicitly scoped by the owner. Recheck main before promotion
and retest if its application code has moved. Use a merge commit to preserve the
included branch history. Existing PRs and source branches remain available.

The Blueprint still deploys only `main`, requires a mounted persistent disk,
and waits for passing checks. Creating or pushing this integration branch does
not change the customer service or provision paid infrastructure.

## Branch inventory

The older source lineage was imported as a new main history: the complete
application and frontend trees at `4f5d29a` equal main's root snapshot `1ba7513`.
Its ancestors do not need to be merged again with unrelated history enabled.
Older merged/draft snapshots are retained; pending work is represented by the
five open PRs above.

| Branch | Observed tip | Disposition |
|---|---|---|
| `agent/live-integration-audit-20260907` | `f2b3000663ed` | Included in integration ancestry |
| `agent/off-crm-v0-12-ai-studio` | `bf86db68054d` | Earlier merged PR (#1 / #3); evolved in main |
| `agent/production-contract` | `67442bffc5eb` | Included in integration ancestry |
| `agent/render-demo-login` | `2260afd2e3b2` | Earlier merged PR (#1 / #3); evolved in main |
| `agent/s-02-02-01-bounded-run-loop` | `6cd9d811b210` | Earlier Run Loop draft, superseded by merged PR #5 and later work |
| `agent/s-03-02-02-vault` | `e9dfb5ab6e4d` | Included in integration ancestry |
| `agent/s-03-02-03-revoke-forget` | `1e26a1f16212` | Included in integration ancestry |
| `claude/abacus-ai-app-idea-t1mnja` | `84fecfb2e4ca` | Historical pre-import development snapshot; retained, not merged over current code |
| `claude/ai-module-hardening` | `1fea2bda7405` | Historical source imported into main; application/frontend trees match main root |
| `claude/context-layer` | `fa1afb95e766` | Historical source imported into main; application/frontend trees match main root |
| `claude/orchestration-design` | `895ef444423b` | Historical source imported into main; application/frontend trees match main root |
| `claude/production-ai-system-design-6413s6` | `4f5d29ab0615` | Historical source imported into main; application/frontend trees match main root |
| `claude/recall-sent-mail` | `bd013ed8f715` | Historical source imported into main; application/frontend trees match main root |
| `codex/inspectable-outreach-v0-8` | `bf649e3dc948` | Historical pre-import development snapshot; retained, not merged over current code |
| `feature/audit-wp1-audit-baseline-merge` | `204cb74c1198` | Included in integration ancestry |
| `feature/audit-wp1-durable-state-safe-recovery` | `0986070460ae` | Included in integration ancestry |
| `feature/audit-wp1-with-live-audit-tests` | `f2b3000663ed` | Included in integration ancestry |
| `feature/s-02-02-01-run-loop` | `921298c41164` | Included in integration ancestry |
| `feature/s-02-02-02-plan-md` | `0c2a04a54694` | Included in integration ancestry |
| `feature/s-11-02-01-structured-run-results` | `48052e813261` | Included in integration ancestry |
| `feature/s-11-02-02-provenance` | `6750b014c94b` | Included in integration ancestry |
| `feature/s-11-02-03-claim-verification` | `71bb33371712` | Included in integration ancestry |
| `feature/s-11-02-04-page-read-cache` | `253449965c1f` | Included in integration ancestry |
| `main` | `37cf9b151200` | Included in integration ancestry |
