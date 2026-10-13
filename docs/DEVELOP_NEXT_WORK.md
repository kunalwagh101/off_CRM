# Next work on develop — 2026-10-09

## Owner-selected feature programme

The owner's latest instruction expands the queue from five individual stories
to these five existing multi-story features. This supersedes the earlier
story-priority table as the programme's scope; that table remains useful as
an initial set of slices, not five complete features.

| Order | Existing feature | Remaining delivery and gates |
|---|---|---|
| 1 | F-06.02 — Production reliability and verification | Error references S-06.02.38; production audit S-06.02.23; dependency audit S-06.02.16; keyboard navigation S-06.02.37; CLI locks S-06.02.28; verifier history S-06.02.20; explicit second-owner login S-06.02.36. CI matrix/live harness S-06.02.26/.27 await runner capacity; draft routing S-06.02.35 awaits Q-28. |
| 2 | F-06.03 — Hosted data and recovery | S-06.03.04 encrypted backups and restore, S-06.03.06 homes for remaining stores, S-06.03.05 half-hosted startup refusal, S-06.03.07 per-install decisions. Existing hosted settings and CRM are preserved. Backup destination and shared-database policy require actual configuration/owner decisions. |
| 3 | F-04.01 — The agent team | S-04.01.02 on-demand skills, S-04.01.03 bounded children, S-04.01.04 five functional roles. Existing companion implementation S-04.01.01 needs its IN_REVIEW gate before dependent stories can be DONE. Product child agents are application functionality, not permission to spawn development assistants. |
| 4 | F-06.01 — Team permissions and operations | S-06.01.02 global/per-tool/chat permissions and S-06.01.05 health, monitoring and tested release recovery. Preserve built workspace credentials, cost ledger and routines. S-06.01.06 CRM tenancy waits for the owner's Q-27 answer; no tenant migration before it. |
| 5 | F-12.02 — The GTM strategy brain | S-12.02.06 posting pairs, approval/skip UI and plan pacing; S-12.02.05 expert references and a real evaluation corpus. Existing planning/apply/review/revise stories are DONE. Reference material is missing; live social publishing retains platform-access blockers. |

Start the independent traceable-errors slice of F-06.02 now, test-first and
on develop. Implement complete slices sequentially; keep review and external
gates open. No claim that these five feature areas can finish in one task,
before the owner returns, or automatically after a usage reset.

## Branch and scan scope

Work, commit and push only on `develop`, as reaffirmed by the owner. No new
branches, worktrees, force-pushes or automatic `main` promotion. Scan base:
`4b80d7c1f262911916810e9cbb63823ca90e2bb4` from `origin/develop`.

This scan used the attached dev-prompt skill in CHECK mode and senior-engineer
responsibility. It inspected the board, backlog, work orders, working record,
branch instructions and the relevant code paths. It is not a complete security
audit or a fresh application test run.

The original cloud checkout was based on older `main`. Its uncommitted platform
implementation was preserved in a verified external archive and a Git stash
before switching. It was not applied over `develop`: this branch already has
`browser/platforms.py`, packaged `platforms.json` and its own tests and contract.
That earlier work is historical evidence for the older checkout, not release
evidence for this branch.

## Existing implementation to validate, not rebuild

The board has 70 DONE stories and 17 IN_REVIEW stories. Editable agent plans,
persisted companions, scheduled routines, browser platform declarations,
frontier crawling, extraction packs, reports/artifacts, meeting transcription
and several accessibility/security capabilities already have implementations.
Their IN_REVIEW status must not be turned into a release claim from this scan.
Hosted provider settings/logins and the hosted CRM are recorded DONE. Media,
outboxes and several other stores still need a durable-storage decision.

`S-06.02.23` is the one current READY item: re-check the September production
audit against `develop`, following its existing work order. This verification
comes before new production claims; unresolved findings get their own tracked
fixes. Do not rebuild capabilities just because they appeared absent on `main`.

## Proposed feature sequence

The owner selected these five capabilities in the follow-up conversation.
They form one ordered queue on `develop`, not five new branches or five
simultaneous implementations. First preparation: the traceable-errors work
order linked from `BOARD.md`. Selection authorises delivery preparation; it
does not establish readiness, executed tests, completion or deployment.

| Priority | Story | User-visible result | Preparation or release constraint |
|---|---|---|---|
| 1 | S-06.02.38 — Any error can be traced back the next day | A failed request, job or command shows a reference ID matched to one secret-safe JSON log entry; local installs retain a rotating log | Write the work order, map API/worker/CLI failure paths, and prove redaction and duplicate-log prevention. Existing owner requirement; no dependency |
| 2 | S-12.01.03 — The video director uses the product | A campaign's videos use its product positioning and house style, with owner text governed by the AI policy and the complete sent request auditable | Existing work order; fix D-81 without weakening trust tiers or putting owner text in an unclassified system prompt |
| 3 | S-06.02.34 — Connectors show how much is left | Each provider shows off_CRM's daily call count and cap, plus provider-reported remaining quota/balance where supported | Confirm each provider's documented reporting. Unsupported providers say they do not report it. Live acceptance needs one connected provider, entered through the app |
| 4 | S-12.02.06 — A plan's posting channel runs from the screens | An approved plan's posting/image pair can be started from the UI; drafted posts offer Approve/Skip; the configured daily pace is honoured | Existing work order. Keep human approval, workspace access checks and pause guards. A local outbox does not prove live social publishing; official adapters retain their external blockers |
| 5 | S-06.03.04 — The hosted database is backed up outside itself | An encrypted scheduled database export can be downloaded and restored into an empty database with reconciled counts | Prepare the work order and backup destination/access requirements; verify a real PostgreSQL restore. Keep file-storage gaps and the dependent half-hosted production guard visible |

These items are still BACKLOG at the scan date; this plan does not silently
promote them. Refine each against its acceptance criteria and known contracts,
then move it to READY before implementation. Keep one feature in flight and use
its existing ID. Existing unrelated external blockers remain on the board.
Do not add MCP, social-adapter or account-permission assumptions to these slices.

## Interruption and resumption

Keep the active story, changed files, executed commands, remaining checks and
blockers in its work order and `BUILD_STATE.md` as work proceeds. A later task
must inspect the actual checkout and board before resuming. Preserve existing
changes and continue on `develop`; do not restart by creating another branch.

This queue is a development plan, not an unattended scheduler. Ending a task,
running out of usage or resetting a usage allowance does not establish that a
new task has started. Do not promise automatic resumption. After an interrupted
task the owner can request: "Resume the selected five-feature queue on develop;
read the board and work orders, and continue from the recorded checkpoint."
Local documentation is not a remote backup; distinguish saved workspace work
from a verified Git commit and successful push.

Draft-model routing (`S-06.02.35`) and workspace-owned CRM (`S-06.01.06`) are not
chosen here: they require the owner's unresolved Q-28/Q-27 decisions. Expert
corpus planning (`S-12.02.05`) also awaits actual reference material; no corpus
or benchmark is invented.

## Scan evidence

`python scripts/verify_board.py --skip-tests` passed on this checkout. Counts:
25 BACKLOG, 1 READY, 0 IN_PROGRESS, 17 IN_REVIEW, 6 BLOCKED, 70 DONE, 0 DEFERRED;
119 board items. All 70 recorded evidence commits exist on this branch. The
runner explicitly executed zero evidence commands in this structural check.

No current full Python/frontend, PostgreSQL, provider or hosted release pass is
claimed. Before implementing a selected feature, prepare the locked environment
including the PostgreSQL extra from AGENTS.md and run the applicable baseline
and release gates. Earlier test counts from the main-based checkout must not be
reused as develop's results.


## 2026-10-13 owner-selected next three priorities — develop

The user requested three feature areas. Keep them ordered and do not exceed two simultaneous IN_PROGRESS stories (S-06.02.23 audit remains active):

1. **F-06.02 production reliability — S-06.02.20**: real Git history check and CI full-depth checkout implemented, evidence tracked; now IN_REVIEW pending full suite and a functioning Actions runner.
2. **F-06.03 hosted backup/recovery — S-06.03.04**: acceptance work order `docs/work-orders/S-06.03.04-hosted-backup-and-restore.md` prepared. BACKLOG, not READY: Q-29 requires an authorised off-database durable destination and backup-key custody. Existing local backup is not a hosted backup.
3. **F-04.01 on-demand agent skills — S-04.01.02**: acceptance work order `docs/work-orders/S-04.01.02-on-demand-agent-skills.md` prepared. BACKLOG, not READY: S-04.01.01 is IN_REVIEW and Q-30 must settle the exact trusted skill-selection contract.

No code for items 2–3 has been implemented yet and no release or hosted integration has been certified. Do not interpret this selected order as permission to bypass dependencies or invent new storage/agent policy.

## 2026-10-13 subsequent batch — skip navigation and network audit security
The owner authorised selecting three additional stories from `develop`: `S-06.02.37` (skip link preserves screen), `S-03.01.03` (browser private-network isolation), and `S-05.01.04` (public fetch DNS rebinding). All three received source changes, red-first regression tests and review evidence files. All three are IN_REVIEW, **not DONE**. Browser isolation remains incomplete because bridge egress is not filtered. The Requests crawler path is pinned; Crawl4AI remains exposed to a second DNS resolution. CI jobs currently fail before allocation. S-05.01.04 also cannot be DONE before its upstream S-05.01.01 is DONE. Audit S-06.02.23 stays the only IN_PROGRESS item. `main` unchanged.


## 2026-10-13 owner-authorised newest three features

1. **S-06.02.36 — second owner login on purpose**: authenticated workspace-creation API requires a strict explicit owner-confirmation Boolean only for the reserved `local` workspace. Existing accounts and bootstrap unaffected. Test cases committed; status IN_REVIEW, live API and full suites unrun.
2. **S-06.02.28 — path-aware CLI workspace leases**: canonical target paths and existing restore lock/journal sidecars decide what workspace is locked. Shared project .env loader covers CLI entry points; target/cross-folder tests committed. Status IN_REVIEW; real multi-process restore proof and full suites unrun.
3. **S-06.02.34 — provider usage and what is left**: Connectors always shows locally counted usage; reporting capabilities classified for all providers in both registries; OpenRouter per-key remaining limit and DeepSeek account balance checked on explicit click with current workspace credentials, no model call. Rate-limit response-header capture is not built, and no real provider/account was queried. Status IN_REVIEW; full suites and live checks unrun.

All changes and evidence were committed to `develop` only. Audit S-06.02.23 is still IN_PROGRESS. GitHub Actions runner has historically failed to allocate (zero steps); do not call these feature areas DONE or deployed.


## 2026-10-13 — Latest next-three selection and implementation

The requested three were chosen from `develop` and tracked under WIP ≤2. Selected S-12.01.03 (video director product confidentiality), S-06.02.16 (frontend npm audit CI enforcement), and S-12.02.05 (expert/winner-informed GTM plans and evals). S-02.02.03 was initially considered but rejected under DoR because S-02.02.02 remains IN_REVIEW. Each of the final three has code changes, named regression tests, a linked work order and an evidence file; each remains IN_REVIEW, not DONE. Key limitations: no live video/egress/provider check; no npm registry audit or dependency upgrades; no 30 judged real GTM cases or owner corpus; no runnable full repository checkout or GitHub runner capacity. See evidence files and Build State. Only develop was pushed. The production audit S-06.02.23 remains sole IN_PROGRESS item.

## 2026-10-13 — Current three security/reliability slices

The owner selected three more areas, and the current develop branch and WIP gate were checked. No new WIP items were pulled; `S-06.02.23` is the one `IN_PROGRESS` audit and two existing `IN_REVIEW` security stories were amended in place:

1. `S-03.01.03` — BrowserBox now refuses unsafe unrestricted Docker bridge under declared production mode (DD-91). It still requires a verified, usable IP-level egress firewall for public browsing; nonproduction bridge remains unsafe.
2. `S-05.01.04` — SafePublicFetcher retains its pinned HTTP/HTTPS path; the JavaScript Crawl4AI path now refuses to start without proven destination-level isolation (DD-92). Safe HTTP remains available; JS feature requires reactivation behind controlled egress and real integration tests.
3. `S-06.02.23` — Audited A07/A08 containment status and A25, which is still open because `render.yaml` declares no independent durable email worker. Track deployment remediation as new BACKLOG `S-06.02.40` / D-270 with a worker launch/restart/recovery work order; host authorisation and durable outboxes remain open.

GitHub-only modifications and regression test source were committed without disabling valid tests. CI runners were previously failing with zero executed steps. Python, JS, Docker, Chrome, the board verifier, real egress controls and real deployment were not run in this environment. Stories do not move to DONE; next action is executing gates on a trusted checkout and implementing the network-level policy and deployment worker. New JavaScript crawling must not be enabled by simply removing the fail-closed guard.
