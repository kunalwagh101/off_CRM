# off_CRM — IN_REVIEW execution ledger (2026-10-15)

Branch `develop`. Review runner revision `6d5dce5404a1c84f1e5044e3519e95bf1b762cb2` adds **only** `Dockerfile.review`; feature code baseline `0d2e28d0065b2ce39d54abb911f848ba0ea529b8`.

Verification rules: PASS = actual completed test with evidence; FAIL = executed failing test with error and cause; NOT RUN = no executed test; BLOCKED = prerequisite unavailable. A build in progress is NOT RUN, not PASS. Each feature below is source implemented unless otherwise stated, and remains IN_REVIEW until its acceptance, end-to-end, isolation and recovery gates pass. Do not send live mail, call paid providers or alter customer records in QA.

## QA infrastructure results

| Check | Result | Evidence / limitation |
|---|---|---|
| QA Docker build | PASS | Render off-crm-qa-20261015 deploy dep-db86lq2j9qps73bs375g live at develop 0d2e28d |
| API startup | PASS | Render 2026-10-15 05:57:08Z startup complete, port 10000 |
| PostgreSQL network connections | PASS (connectivity only) | Render PG active_connections=3 at 05:58–05:59Z after QA startup; not schema or data correctness |
| Python SyntaxWarning | WARNING | browser/page.py:106 invalid escape sequence '\\s'; did not prevent startup; fix needed and retest |
| Python/React full regression | NOT RUN | QA deployment Dockerfile does not execute tests. Separate Render review runner `srv-db86p4u89jmc73cehns0` created, Dockerfile.review executes gated checks. Read current runner logs for results. |
| Migration, restart, backup/restore | NOT RUN | Needs isolated DB and real destructive/recovery harness; do not run against customer data |
| Chrome/browser end-to-end | NOT RUN | No trusted browser execution yet |
| Live provider / email delivery | NOT RUN | Would create external side effects; QA smoke tests must be side-effect-safe |

## Every IN_REVIEW item — individual execution status

| # | ID | Feature / story | Test result | Reason / next evidence |
|---:|---|---|---|---|
| 1 | F-06.19 | CRM Data Quality Centre | NOT RUN | Await executed regression and user-path acceptance; map associated work order and evidence in BOARD.md |
| 2 | F-06.20 | Campaign Comparison Dashboard | NOT RUN | Await executed regression and user-path acceptance; map associated work order and evidence in BOARD.md |
| 3 | F-06.21 | Follow-up Performance Centre | NOT RUN | Await executed regression and user-path acceptance; map associated work order and evidence in BOARD.md |
| 4 | F-06.16 | Unified CRM Search | NOT RUN | Await executed regression and user-path acceptance; map associated work order and evidence in BOARD.md |
| 5 | F-06.17 | Account Intelligence Workspace | NOT RUN | Await executed regression and user-path acceptance; map associated work order and evidence in BOARD.md |
| 6 | F-06.18 | Campaign-to-Revenue Attribution | NOT RUN | Await executed regression and user-path acceptance; map associated work order and evidence in BOARD.md |
| 7 | F-06.13 | Qualified Reply-to-Sales Conversion | NOT RUN | Await executed regression and user-path acceptance; map associated work order and evidence in BOARD.md |
| 8 | F-06.14 | Contact 360 Workspace | NOT RUN | Await executed regression and user-path acceptance; map associated work order and evidence in BOARD.md |
| 9 | F-06.15 | Daily Action Command Center | NOT RUN | Await executed regression and user-path acceptance; map associated work order and evidence in BOARD.md |
| 10 | F-06.10 | Reply Inbox & Human Triage | NOT RUN | Await executed regression and user-path acceptance; map associated work order and evidence in BOARD.md |
| 11 | F-06.11 | Contact Communication History | NOT RUN | Await executed regression and user-path acceptance; map associated work order and evidence in BOARD.md |
| 12 | F-06.12 | Human Follow-up Task Manager | NOT RUN | Await executed regression and user-path acceptance; map associated work order and evidence in BOARD.md |
| 13 | F-06.07 | Audience Management Workspace | NOT RUN | Await executed regression and user-path acceptance; map associated work order and evidence in BOARD.md |
| 14 | F-06.08 | Campaign Launch Readiness Center | NOT RUN | Await executed regression and user-path acceptance; map associated work order and evidence in BOARD.md |
| 15 | F-06.09 | Campaign Activity & Audit Timeline | NOT RUN | Await executed regression and user-path acceptance; map associated work order and evidence in BOARD.md |
| 16 | F-06.04 | Campaign Management | NOT RUN | Await executed regression and user-path acceptance; map associated work order and evidence in BOARD.md |
| 17 | F-06.05 | Campaign Blueprint Reuse | NOT RUN | Await executed regression and user-path acceptance; map associated work order and evidence in BOARD.md |
| 18 | F-06.06 | Campaign Performance Intelligence | NOT RUN | Await executed regression and user-path acceptance; map associated work order and evidence in BOARD.md |
| 19 | S-06.02.47 | Large send queues are paginated | NOT RUN | Await executed regression and user-path acceptance; map associated work order and evidence in BOARD.md |
| 20 | S-06.02.48 | Campaign-wide queue counters do not mislead | NOT RUN | Await executed regression and user-path acceptance; map associated work order and evidence in BOARD.md |
| 21 | S-06.02.49 | Queue views focus on actionable cohorts | NOT RUN | Await executed regression and user-path acceptance; map associated work order and evidence in BOARD.md |
| 22 | S-06.02.44 | Download all filtered Contacts rows | NOT RUN | Await executed regression and user-path acceptance; map associated work order and evidence in BOARD.md |
| 23 | S-06.02.45 | Category and variant filters for contacts | NOT RUN | Await executed regression and user-path acceptance; map associated work order and evidence in BOARD.md |
| 24 | S-06.02.46 | Marked-only contacts remain reachable | NOT RUN | Await executed regression and user-path acceptance; map associated work order and evidence in BOARD.md |
| 25 | S-06.02.41 | Contacts beyond row 500 are reachable | NOT RUN | Await executed regression and user-path acceptance; map associated work order and evidence in BOARD.md |
| 26 | S-06.02.42 | Enrichment exports cannot run spreadsheet formulas | NOT RUN | Await executed regression and user-path acceptance; map associated work order and evidence in BOARD.md |
| 27 | S-06.02.43 | Logout revokes the copied browser session | NOT RUN | Await executed regression and user-path acceptance; map associated work order and evidence in BOARD.md |
| 28 | S-12.02.05 | The brain drafts against the expert corpus and the owner's winners | NOT RUN | Await executed regression and user-path acceptance; map associated work order and evidence in BOARD.md |
| 29 | S-06.02.16 | Resolve frontend development dependency audit findings | NOT RUN | Await executed regression and user-path acceptance; map associated work order and evidence in BOARD.md |
| 30 | S-12.01.03 | The video director uses the product | NOT RUN | Await executed regression and user-path acceptance; map associated work order and evidence in BOARD.md |
| 31 | S-06.02.34 | Connectors show how much is left | NOT RUN | Await executed regression and user-path acceptance; map associated work order and evidence in BOARD.md |
| 32 | S-06.02.28 | A command-line tool locks the workspace it actually opens | NOT RUN | Await executed regression and user-path acceptance; map associated work order and evidence in BOARD.md |
| 33 | S-06.02.36 | A second owner login is made on purpose | NOT RUN | Await executed regression and user-path acceptance; map associated work order and evidence in BOARD.md |
| 34 | S-05.01.04 | Public-page fetches connect only to checked destinations | NOT RUN | Await executed regression and user-path acceptance; map associated work order and evidence in BOARD.md |
| 35 | S-03.01.03 | Browser blocks internal network access | NOT RUN | Await executed regression and user-path acceptance; map associated work order and evidence in BOARD.md |
| 36 | S-06.02.37 | Skip navigation keeps the current screen | NOT RUN | Await executed regression and user-path acceptance; map associated work order and evidence in BOARD.md |
| 37 | S-06.02.20 | The verifier tells a shallow clone apart from a missing commit | NOT RUN | Await executed regression and user-path acceptance; map associated work order and evidence in BOARD.md |
| 38 | S-06.02.39 | Valid low-bitrate WebM exports pass verification | NOT RUN | Await executed regression and user-path acceptance; map associated work order and evidence in BOARD.md |
| 39 | S-12.02.06 | A plan's posting channel runs from the screens | NOT RUN | Await executed regression and user-path acceptance; map associated work order and evidence in BOARD.md |
| 40 | S-06.02.38 | Any error can be traced back the next day | NOT RUN | Await executed regression and user-path acceptance; map associated work order and evidence in BOARD.md |
| 41 | S-06.02.25 | Every screen opens at its top, its warnings in view | NOT RUN | Await executed regression and user-path acceptance; map associated work order and evidence in BOARD.md |
| 42 | S-06.02.21 | Durable customer state and safe recovery (audit WP1) | NOT RUN | Await executed regression and user-path acceptance; map associated work order and evidence in BOARD.md |
| 43 | S-06.02.22 | A created or selected campaign stays the active workspace | NOT RUN | Await executed regression and user-path acceptance; map associated work order and evidence in BOARD.md |
| 44 | S-07.01.03 | Meeting transcription with no bot in the call | NOT RUN | Await executed regression and user-path acceptance; map associated work order and evidence in BOARD.md |
| 45 | S-06.02.05 | The UI is usable by keyboard and screen reader | NOT RUN | Await executed regression and user-path acceptance; map associated work order and evidence in BOARD.md |
| 46 | S-06.02.02 | Every endpoint authorises and validates | NOT RUN | Await executed regression and user-path acceptance; map associated work order and evidence in BOARD.md |
| 47 | S-06.02.01 | No secret may enter a model prompt | NOT RUN | Await executed regression and user-path acceptance; map associated work order and evidence in BOARD.md |
| 48 | S-06.01.04 | Routines that fire agent runs on a schedule or an event | NOT RUN | Await executed regression and user-path acceptance; map associated work order and evidence in BOARD.md |
| 49 | S-06.01.01 | Workspaces with their own keys and their own logins | NOT RUN | Await executed regression and user-path acceptance; map associated work order and evidence in BOARD.md |
| 50 | S-04.01.01 | Companions: persisted agent profiles | NOT RUN | Await executed regression and user-path acceptance; map associated work order and evidence in BOARD.md |
| 51 | S-02.02.02 | PLAN.md as the single source of truth | NOT RUN | Await executed regression and user-path acceptance; map associated work order and evidence in BOARD.md |
| 52 | S-03.02.05 | A platform is a row, not a code change | NOT RUN | Await executed regression and user-path acceptance; map associated work order and evidence in BOARD.md |
| 53 | S-06.02.04 | Data deletion and subject access | NOT RUN | Await executed regression and user-path acceptance; map associated work order and evidence in BOARD.md |
| 54 | S-05.01.03 | Take a competitor post apart and rebuild the shape | NOT RUN | Await executed regression and user-path acceptance; map associated work order and evidence in BOARD.md |
| 55 | S-05.01.02 | Extraction packs as declared data | NOT RUN | Await executed regression and user-path acceptance; map associated work order and evidence in BOARD.md |
| 56 | S-05.01.01 | A crawler with a frontier, not a loop | NOT RUN | Await executed regression and user-path acceptance; map associated work order and evidence in BOARD.md |
| 57 | S-07.01.04 | Reports and artifacts | NOT RUN | Await executed regression and user-path acceptance; map associated work order and evidence in BOARD.md |

## Executable QA gates

Review-only `Dockerfile.review`: `npm ci`, `npm test`, `npm run build`, `npm audit --omit=dev --audit-level=low`, `npm audit --audit-level=high`, `uv sync --locked --extra dev --extra email --extra postgres`, `uv run ruff check --select E9,F63,F7,F82 .`, and `uv run pytest -q` (in Docker stage). The review runner's build status and logs, not this ledger, establish whether each command actually completed. This runner tests code in a container; it does not certify PostgreSQL-backed integration or Chrome UI.

## Release restrictions

Unresolved customer tenancy/Q-27, persistence of non-PostgreSQL artifacts, hosted backups, browser egress isolation, independent review and CI runner failure remain release gates. No item was moved to DONE based on startup alone.
