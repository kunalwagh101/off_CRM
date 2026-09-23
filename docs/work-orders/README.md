# Work orders — everything still open, and who does it

On 2026-09-23 the owner asked for the remaining work to be **written down, not
built**: each open piece is a story on the board with a work order an
implementer can follow without asking. `BOARD.md` is the state; this page is
the map. Read `AGENTS.md` and `BUILD_STATE.md` before any of it.

## Rules for whoever picks one up

1. Pull only a **READY** item, and keep `IN_PROGRESS` at two or fewer.
2. Read the work order to the end first. Its FILES section says what not to
   touch; its IF BLOCKED section says what to do instead of improvising.
3. **Red first.** Write the test, run it, watch it fail for the reason the work
   order gives. Then fix.
4. Run the gates: `uv run ruff check --select E9,F63,F7,F82 .`,
   `uv run pytest -q`, `cd frontend && npm test && npm run build`,
   `uv run python scripts/verify_board.py`.
5. Every defect you find goes in `DEFECT_LOG.md`; every design call that was not
   the obvious one goes in `DECISIONS.md`. Commit and push to `develop` only.
6. **DONE needs its evidence block** (`DEFINITION_OF_DONE.md`). A work order's
   DONE WHEN is not rewritten to match what was built; if it cannot be met,
   file a question and stop.

**Tags.** *Kind*: `build` (code), `review` (a second pair of eyes and the
evidence block), `owner` (a decision or an action only the owner can take),
`external` (waiting on someone outside). *Status* is the board column. *Size*:
S, M or L, from the story.

## 1. Ready to build now

| Story | Kind | Size | What | Work order |
|---|---|---|---|---|
| S-06.02.24 | build | S | Every CLI takes the restore lease; two default paths follow the data directory (`D-134`, `D-138`) | [S-06.02.24](S-06.02.24-workspace-lease-for-clis.md) |
| S-06.02.25 | build | S | Every screen opens at its top, warnings in view (`D-137`) | [S-06.02.25](S-06.02.25-screen-opens-at-top.md) |
| S-06.02.23 | build | L | Re-check the audit's 24 unchecked findings on `develop` | [S-06.02.23](S-06.02.23-audit-recheck.md) |

## 2. Planned, can be pulled next (BACKLOG, dependencies DONE)

| Story | Kind | Size | What | Work order |
|---|---|---|---|---|
| S-12.01.03 | build | M | The video director speaks the product's voice; owner text leaves only in classified fields, and the log shows the system prompt (`D-81`) | [S-12.01.03](S-12.01.03-video-director-uses-the-product.md) |
| S-12.02.06 | build | M | A plan's posting channel posts from the screens: pairing at Apply, approve or skip on Posting, the plan's rate (`D-82`, `D-97`) | [S-12.02.06](S-12.02.06-posting-channel-from-the-screens.md) |
| S-12.02.05 | build · owner | L | Plans drafted with the expert library and the winning template; the `gtm_plan` eval suite. Needs the owner's expert library for its verdict | [S-12.02.05](S-12.02.05-plans-with-expert-references.md) |

## 3. Needs a work order before anyone builds it (BACKLOG)

These are the longer-term backlog. Their stories are written; their design is
not. Write the work order first, in the shape of the ones above.

| Story | Size | Depends on | What |
|---|---|---|---|
| S-06.02.16 | S | — | Frontend development-dependency audit findings (audit A31) |
| S-06.02.20 | S | S-06.02.12 | The verifier tells a shallow clone from a missing commit (`D-80`) |
| S-02.02.03 | M | S-02.02.02 | Interrupt, steer, resume an agent run |
| S-04.01.02 | M | S-04.01.01 | Skills: procedures fetched on demand |
| S-04.01.03 | L | S-04.01.01 | Sub-agents for context isolation |
| S-04.01.04 | L | S-04.01.03 | The five roles, wired to what exists |
| S-06.01.02 | M | S-04.01.01 | Three-level permissions |
| S-06.01.05 | L | S-06.01.01 | Deployment, monitoring and rollback |
| S-07.01.01 | L | S-06.01.02 | An MCP client |
| S-07.01.02 | L | S-03.02.02, S-07.01.01 | Native OAuth integrations |

Several depend on stories still IN_REVIEW; they can be designed now, not built.

## 4. Waits for CI runners (BACKLOG, depends on S-06.02.18)

| Story | Kind | Size | What | Work order |
|---|---|---|---|---|
| S-06.02.26 | build | S | CI runs the suite on 3.10, 3.11 and 3.12 (`D-128`). Its static test can be written now | [S-06.02.26](S-06.02.26-python-matrix.md) |
| S-06.02.27 | build | M | The audit's live harness runs against `develop` | none yet — the harness is on `integration/main-consolidation` (after the owner's clean-up: `git fetch origin 'refs/tags/archive/*:refs/tags/archive/*'`, then `archive/integration/main-consolidation`; before it, pull request #14's ref) |

## 5. Review and evidence (IN_REVIEW — 16 stories)

Code complete and tested on `develop`. Each needs an independent review and its
evidence block. None may move to DONE on this page's say-so.

| Story | Kind | Note |
|---|---|---|
| S-06.02.21, S-06.02.22 | review | [close-out work order](S-06.02.21-S-06.02.22-close-out.md) — the fixes of 2026-09-23 need their second review |
| S-07.01.03 | review · owner | needs one real capture on the owner's own machine (browser microphone + tab audio) |
| S-06.02.05 | review · owner | needs the owner's keyboard and screen-reader pass |
| S-06.02.01, S-06.01.01, S-06.02.04, S-04.01.01, S-02.02.02, S-05.01.01, S-05.01.02, S-05.01.03 | review | their CHECK repairs are code-fixed — `D-71`–`D-74`, `D-76`–`D-79`, `D-100`, `D-101`; the repair work orders in this folder are the record; the evidence was only waiting on runnable tests, which `develop` now has |
| S-06.02.02, S-06.01.04, S-03.02.05, S-07.01.04 | review | review and evidence only |

## 6. Waits on the owner

| Item | Kind | What only the owner can do |
|---|---|---|
| S-06.02.19 | owner | Run `bash scripts/archive_old_branches.sh --delete` from a clone with push rights (`docs/BRANCHING.md`). GitHub refused this to the cloud session |
| S-06.01.06 · `Q-27` | owner | Decide whether each workspace gets its own campaigns and contacts. If yes, the design is ready: `docs/architecture/CRM_TENANCY.md` |
| `Q-26` | owner | Decide whether `main` on Render gets a paid disk before real records go in |
| Promotion | owner | After using `develop` on Render, merge it into `main` (`docs/BRANCHING.md`) |

## 7. External

| Story | Waiting on |
|---|---|
| S-06.02.18 | GitHub Actions cannot start a runner (`D-75`): billing, budget or policy on the account, else GitHub support |
| S-01.05.01, S-01.05.02, S-01.05.03 | Google Cloud and YouTube Data API access; Meta, TikTok and LinkedIn platform reviews |
