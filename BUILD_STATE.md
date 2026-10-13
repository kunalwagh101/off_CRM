# BUILD_STATE.md

Working record for the off_CRM AI orchestration module. Read **this file** to
recover context between sessions rather than re-reading the codebase.

Then read **`docs/architecture/CAMPAIGN_TYPES.md`** before designing anything
new. The product is a CRM *with an AI layer that runs the campaigns itself*, and
email is one campaign kind of several. Nothing built from here may assume email.

Last updated: 2026-10-09
Branch: `develop` — the one working branch. Every line of work was merged or
ported into it on 2026-09-23; `docs/BRANCHING.md` says what came from where.
The 45 old branches are still on GitHub until the owner runs
`scripts/archive_old_branches.sh` — this session was refused (HTTP 403).
Tests (2026-10-03, on `develop` at `S-06.03.03` DONE): with
`OFF_CRM_TEST_POSTGRES_URL` on a real PostgreSQL 16, **2681 Python passed,
0 failed**, 1 skipped (a sandbox image); without the URL the PostgreSQL-only
tests skip. With `OFF_CRM_TEST_CRM_ON_POSTGRES=1` as well, the **whole suite
runs with the CRM on PostgreSQL: 2612 passed, 0 failed**, 70 skipped — tests
about SQLite itself or about a CRM file, each with its reason, and one sandbox
image (`tests/conftest.py`). CI has a `postgres` job for both, not yet run:
the runners are down (`S-06.02.18`). The whole suite last ran on a real Python 3.10 on
2026-09-24 (2404 passed); it has not been re-run on 3.10 since. Ruff gate
clean. Frontend **175 passed** and a clean production build. Board verifier
OK with every DONE story's evidence command re-run (2026-09-28).

**Newest: screens open at their top** (`S-06.02.25`, IN_REVIEW; checks passed
below). The CRM in the hosted database (`S-06.03.03`, DONE; next in
`F-06.03`: `S-06.03.04` backups, `S-06.03.07` filed by its review). Before it, the GTM engine,
Phase 1 and 2 (`E-12`) — section 3's first entry.
Read `docs/architecture/GTM_ENGINE.md` before touching `offsetx_apollo_builder/gtm/`.

The video editor is built: `offsetx_apollo_builder/video/` plus
`frontend/src/video/` and the **Video editor** screen. Read
`docs/architecture/VIDEO_EDITOR.md` before touching either resolver — there are
two implementations of one rule and a conformance fixture holding them together.
`docs/architecture/CAPCUT_FEATURE_MAP.md` is the feature inventory it was cut
from, and it now carries a **status column and a scoreboard**: 61 of its 162
rows built, 18 partly, 52% of the reachable rows touched.
`tests/test_capcut_scoreboard.py` recomputes those counts from the table, so the
summary cannot drift from what it summarises. Auto-captions is the first AI row
wired: `docs/architecture/AUTO_CAPTIONS.md`, and read its section on audio
before adding any other feature that sends bytes rather than text.

The long-standing `test_discovery.py::test_scrapling_parser…` failure was never
a code defect: `scrapling` is declared in `pyproject.toml` but omitted from
`requirements.txt`, so any environment installed from the latter lacked it. The
session-start hook installs via `uv sync --extra dev` and the test passes.



## 2026-10-09 — Five-feature programme, develop only

Owner selected F-06.02 reliability, F-06.03 hosted recovery, F-04.01 agent team,
F-06.01 team operations and F-12.02 GTM strategy. The concrete story queue and
upstream/owner/access gates are in `docs/DEVELOP_NEXT_WORK.md`. No branches or
worktrees were created; the old main-based work remains archived/stashed and
was not applied. Current scan base is develop `4b80d7c`.

S-06.02.38 traceable errors was committed and pushed to develop as `d3099f1`.
It is IN_REVIEW, code review clear. API/CLI/job
references, safe lifecycle protocol messages, bounded local logs, fresh cycle
scopes, workspace metadata and visible Settings/Posting status are implemented.
D-243–D-253 record the review findings and resolutions. The independent reviewer
ended with no remaining code finding. The exact ledger is
`docs/evidence/S-06.02.38-validation.md`; this is not DONE or a deployed release.

Locked dev/email/postgres extras installed. Use UV_CACHE_DIR=/tmp/off-crm-uv-cache
and UV_TOOL_DIR=/tmp/off-crm-uv-tools (home directories read-only); frontend cache
/tmp/off-crm-npm-cache. Baseline: 2569 passed, 22 failed, 22 skipped (21 Chromium
sandbox, one uvx cache fixed by override). Broad final regression run: 2612 passed,
21 Chromium failures, 22 skipped. Subsequent final affected run: 314 passed,
14 PostgreSQL skips, covering the last routine/safe-summary fixes. Frontend:
175 passed; production build passed with its existing large-chunk advisory.
Ruff and structural board checks passed. Whole-board run: 70 commands, 42
passed; Chromium environment prevents a green full-board gate. No sandbox or
test was disabled. Raw logs are copied to /workspace/artifacts/S-06.02.38.

Current real HTTP-process injected failure: status 500, one matching safe
record, local workspace. Earlier installed offsetx-db failure: exit 2, one
matching reference, password absent. Actual previous-revision process rollback
had readiness 200 and preserved the disposable CRM row/log bytes. No live
provider, PostgreSQL database, Render retention, deployment or CI pass claimed.

Owner authorised commit/push only to develop. Preserve the main-based archive
and stash. Continue the selected programme from the queue and actual board;
prepare the next independent READY slice and keep upstream/owner/access gates
open. Ending a task or a usage reset does not automatically resume work.

### Current slice — S-12.02.06 posting, IN_REVIEW

Apply declares a disabled posting/image pair with the plan's own rate. Owner
Start, workspace-scoped review/skip, transactional next-slot scheduling,
authenticated image/video previews and safe per-pair pace decisions are built.
D-254–D-265 record independent review fixes; final review has no remaining
concrete finding. Baseline affected tests 79 passed; final affected tests
145 passed. Frontend 181 passed and build passed (existing chunk advisory).
Broad pre-legacy-fix run: 2641 passed, 21 baseline Chromium failures, 22 skips;
latest broad result: 2643 passed, 21 Chromium failures, 22 skips. See
docs/evidence/S-12.02.06-validation.md.
The final affected run covers quarantine-result visibility after broad started.
Ruff and structural board checks passed. Browser/generated-media/live-social
and green full-board gates remain open; this is not DONE or a deployed release.

The owner requested a local run. App runs in the **cloud workspace** using
/tmp/off-crm-progress-server.py on loopback port 8766, serving frontend/dist.
Isolated data: /workspace/runtime/off-crm-progress; auth-token is private and
must never be printed, copied into artifacts, or committed. Real HTTP readiness
and frontend returned 200; rules plan applied disabled, Start enabled its pair,
manual caption approved/scheduled/published to the real local outbox, skipped
row never published. No model/social service used. Current-process restart
preserved the plan and published/skipped statuses. Plain archived d3099f1 source
also read a stopped-data copy and served its rebuilt frontend. Its process is
stopped; current app stays running. Automation is disabled after verification.
Raw safe results/logs: /workspace/artifacts/S-12.02.06. No laptop installation,
public preview, real browser walk, hosted restore or deployment is claimed.

Continue the five-feature programme from docs/DEVELOP_NEXT_WORK.md. Only
reliability logging and this posting slice have implementation/review evidence
from this session; do not claim the remaining large features are completed.

## 2026-10-04 — Screen navigation keeps its top in view (`S-06.02.25`)

Frontend implementation and independent review complete.
Pushed to `develop` at `815c72bbc7affdef29b2c288e4d7494a836ea292`; no `main` promotion.
Navigation focuses main without browser scrolling, then explicitly opens the
screen at scroll 0.
The main area's scroll margin matches the 68px desktop / 60px phone top bar.
No campaign store, screen component, API, database schema or credential setting
changed. Late campaign warnings stayed in view without adding another scroll
on background failures (`DD-79`). `D-137` is fixed.

Evidence this session: baseline and final full Python suites both **2570
passed, 43 skipped**, no PostgreSQL server configured; frontend **175 passed**,
production build passed; accessibility **12 passed**; egress wall **42 passed**;
Ruff passed. Real Chromium 153 through `run_offsetx_web.py` and the actual API
passed **32 checks** on Settings, Contacts, AI and Product at 1280x900 and
390x900: healthy navigation, delayed/existing campaign warnings, initial
failure recovery and preserved campaign-load gates. The full warning and
screen title are visible; long forms/chat panels may extend below the viewport,
but their beginning and first header/action are visible. Browser output and
the reusable launcher are linked from the work order.

Independent review corrected the browser selectors, render waits and disposable
launcher's inherited hosted-key configuration. It found an older skip-link
route defect (`D-239`), reproduced and filed as `S-06.02.37`; no additional
feature was absorbed. Whole-board evidence verification re-ran all 70 existing
DONE commands: **70 passed**. Historical commit ancestry was not checked because
the exact source snapshot has no local Git history. The story remains IN_REVIEW
for the full-checkout history and develop CI gates.
The baseline GitHub quality job also fails three older tests because it omits
the PostgreSQL driver; its separate postgres job passes (`D-241`, filed against
`S-06.02.19`). This is
work for `develop`; it is not a `main` promotion or a verified hosted release.
Existing blocked work remains on the board.

## 2026-10-03 — `F-06.03` phase 2: the CRM outlives the disk (`S-06.03.03`)

**DONE** (2026-10-03). Tasks a–i built, walked in a browser, reviewed in a
fresh context and pushed to `develop`; not deployed. The work
order, `docs/work-orders/S-06.03.03-crm-hosted.md`, holds every task's numbers.

**What it does.** With `OFFSETX_DATABASE_URL` set, the CRM — every one of its
31 tables — is in that database, for the web app and every tool
(`data_paths.crm_target`: a `--db` given, then the URL, then
`OFFSETX_OUTREACH_DB`). `outreach/store.py` runs the same SQL on both backends
and knows which it has only at opening, in transactions, at its first schema
and for search's index. A local CRM file holding the owner's rows stops a
hosted start until `offsetx-db import-crm --yes` or `--skip` (`DD-74`).
`offsetx-db copy-crm` copies a whole CRM either way: empty destination only,
one transaction, the source read at one moment and never written.

**How it is proved.** `tests/conftest.py` runs the whole suite with every CRM
on PostgreSQL (`OFF_CRM_TEST_CRM_ON_POSTGRES=1`); a test about SQLite itself is
marked `crm_sqlite_only` with its reason, and where its property also holds on
PostgreSQL, `tests/test_crm_hosted.py` proves it on both. Live: the real server
on PostgreSQL 16 kept a campaign through its data folder being deleted; a CRM
the app's own engine wrote (9,442 rows) went to PostgreSQL and back with every
value equal.

**The fresh-context review** (task i) found 11 defects, `D-227` to `D-237`.
The worst: once any tool had started on the database, the owner's local CRM
could no longer be imported, and only the web app refused to start while it
was left behind. Ten fixed test-first; one filed as `S-06.03.07` (installs
sharing one database). Walking that worst one with the real commands found
`D-238`, fixed. New decisions `DD-75` to `DD-78`; `DD-75` corrects `DD-73`:
accented letters fold on PostgreSQL only.

**Found and fixed on the way:** the email worker failed on PostgreSQL at
every send-window deferral (`D-221`); a closed connection reopened itself
(`D-222`, older); `copy-log` printed its URL's password (`D-225`, older); a
PostgreSQL URL as the CRM's path became a file named after it (`D-217`). The
work order's list of modules touching the CRM was built by text search and
missed one (`D-220`); the exact list came from tracing every statement.

**Not done, and where it goes:** backups of the hosted database
(`S-06.03.04`); production refusing a half-hosted install (`S-06.03.05`); the
stores with no decided home (`S-06.03.06`); expert search on PostgreSQL is
unranked — no full-text index there. A copy over the network to a hosted
database, and the CRM's load on Neon's compute hours, are unmeasured.

## 2026-10-02 — `F-06.03` phases 0 and 1: keys, settings and logins outlive the disk

**DONE on 2026-10-02:** `S-06.03.01` (the inventory of every store,
`db/inventory.py`, `offsetx-db inventory`, the table in `HOSTED_STORAGE.md`)
and `S-06.03.02`. With `OFFSETX_DATABASE_URL` and `OFFSETX_SECRETS_KEY` set,
provider keys (encrypted with that key, never stored), each workspace's AI
settings, limits and trust, the usage counters, workspace logins and the egress
log live in the database. With neither set, nothing changed.

**The owner's word, 2026-10-02:** not only Neon — Render's PostgreSQL too — and
build so the install can move to a PostgreSQL on AWS or Azure later (`DD-66`
amended, `DD-70`). The code names no host. Checked that day: Render's free
database is deleted with its data after 30 days plus 14 days' grace and has no
backups, so the free recommendation is Neon.

**Proof, not just tests:** a real app process (`run_offsetx_web.py`) on a real
PostgreSQL 16 was configured in headless Chromium — a key with the 200-a-day
and $5 presets, a trust raise with its reason, a colleague's login, a logged
call — then stopped and its data folder deleted. A new process on an empty
folder with the same two settings showed all of it, and the colleague signed
in. A different key, and no key, each stopped the start with a sentence. The
database held no plain-text key.

**Found and fixed on the way:** a PostgreSQL store never reopened a dropped
connection, so every hosted store would have failed after Neon's first
five-minute sleep (`D-199`, high); daily limits restarted at every spin-down
(`D-198`, high); privacy requests could not reach hosted logins (`D-200`); the
eval tool split the egress log (`D-201`); "encrypted on this machine" stopped
being true (`D-202`); unsubscribe links died at every restart on Render
(`D-203`); `.env.example` still offered provider-key variables (`D-204`).

**The fresh-context review of `646c593`** found ten defects, six medium, none
critical — the key core was sound. All fixed test-first (`D-206` to `D-215`):
a non-URL connection string became a local file (now refused); a billed answer
could be lost to a counter read (counters are read before a call, and counting
never fails it); a silently dropped flow hung the store (network keepalives,
about 15 seconds); signed-in browsers got a bare 500 in an outage (the
middleware answers the sentence); switching on beside a folder with data hid
it (refused until `offsetx-db import-local --yes` or `--skip`); a database
error read as the provider failing (passed through untouched). One more, older,
turned up under load: two connections opening a new SQLite file together
(`D-216`). A live outage — PostgreSQL stopped under a signed-in browser, then
started — showed the sentence and recovered with no restart. The fixes were
checked by tests, the reviewer's own reproductions and browser walks, not by a
second review.

**Read before touching storage:** `db/hosted.py` (documents, the key check),
`db/schema.py` (a version per store, forward-only, under a lock),
`db/connection.py` (reopen before a statement, never re-send one, never swap
inside a transaction). `S-06.03.06` is filed for the stores the inventory found
with no phase.

## 2026-09-25 — live bugs fixed; the owner's keys, limits, trust and storage decisions; two reviews

**Fixed from the live app** (each test-first, walked in a real browser):
NVIDIA's reasoning model refused every call (`D-147`); Render deploys timed
out on a 421 health check (`D-148`); Connect refused the form's own 0 cap and
hid why (`D-149`, `D-150`).

**The owner's decisions, 2026-09-25** — recorded in `DECISIONS.md` and
`OPEN_QUESTIONS.md`:
- Provider keys come only from the app. The environment-variable fallback is
  gone: it handed the owner's key to every workspace login (`D-151`, `DD-64`).
- Trust is the owner's to raise or lower, per provider and per model (`DD-65`).
- `Q-26` answered: stay on Render's free plan with a free hosted PostgreSQL
  (`DD-66`, `docs/architecture/HOSTED_STORAGE.md`, feature `F-06.03`, five
  phases). **Not built.** Until phase 1 (`S-06.03.02`) lands, everything on
  Render — keys included — is still wiped on every deploy.

**Built, DONE on 2026-09-28:** `S-06.02.31` (keys only from the app),
`S-06.02.32` (limit presets), `S-06.02.33` (trust per provider and model; also
`D-152`, `D-153`). Six fresh-context checks ran. The first found `D-154` to
`D-164`, two critical, in older code: a draft request or a profile could send
any server environment variable to any URL, and a client login could re-point
the owner's profile to receive the owner's key. The second found `D-165` to
`D-170`: the owner's fallback drafts used every workspace's profiles (high),
profile ownership was a label the request typed, lowering a provider
re-applied the full-data grant, and the call log was unscoped. Fixing those
found `D-171` — the full-data grant never sent more, older than this session —
and `D-172` to `D-175`. The third and fourth reviews (2026-09-26) found
nothing critical or high: `D-176` to `D-189`, four medium; the fourth
reviewer's look at its own findings' fixes found `D-190` to `D-193`, one of
them a regression in those fixes. The sixth check (2026-09-28) looked at those
fixes and found `D-194`, medium: the list and the click each worked out where a
waiting profile would go, so a workspace created in between could receive the
owner's key; and `D-195`, a screen-reader label that hid the destination. Both
fixed test-first; those two fixes were checked by tests and a real browser walk,
not by a seventh review. It also found `D-196`, older than this work — filed.
Re-reading the `D-194` fix before pushing found `D-197`: Enter in the key box,
or a browser that does not report the pressed button, took the first button —
the client workspace. Fixed test-first and walked in real Chromium.

**How profiles and trust work now — read before touching either:**
- A provider profile's owner is recorded by the server from the login — the
  install owner's is `local`, never a typed label. A draft uses only the
  caller's own profiles. Profiles saved before this wait for the owner to
  confirm them (`DD-68`, `POST /api/v1/provider-profiles/<id>/confirm`).
- The full-data grant reaches only a known model trusted at its provider's
  default tier or higher, and while it stands it decides what those models
  are sent; lowering the provider pauses it (`DD-67`). The owner's own level
  is never overwritten: Connect stores it cut only to the provider's standing
  trust. The per-model rule is `ProviderRegistry.resolve` (`grant_applied`);
  the screen's `sends`, `grant_state` and `grant_offer` are that function's
  answer per switched-on model (`describe`, `_grant_refusal` in
  `ai/workspace.py`). Change the rule in one place.
- Old profiles are settled in Settings, "Provider profiles to confirm":
  confirming takes the API key the profile holds — its label proves nothing.
  The list offers each one's destinations (`confirm_options`: the owner
  always, plus the client workspace its label names) and the pressed button
  sends one as `confirm_to`, by its own click; Enter confirms only a profile
  with one place to go. The server takes only an offered one, worked out
  again at the click (`DD-68`, `D-194`, `D-197`). A grant only ever lifts what
  is sent (`DD-67`).

**Found, not fixed:** `D-173` — Drafts reach a model only through provider
profiles, and no screen adds one since providers moved to Connectors. `Q-28`
asks which way drafts should go; `S-06.02.35` is filed for either answer.
`D-196` — a login made in workspace `local` acts as the install owner, and
nothing asks whether that was meant; `S-06.02.36`.

**Planned, not built:** `S-06.02.34` — show what is left per provider. Checked
on 2026-09-25: NVIDIA reports nothing; OpenRouter and DeepSeek do. A model
cannot know an account's balance; only a provider's API can say.

## 2026-09-24 — `S-06.02.24`: the command-line tools hold the restore lease

Building resumed at the owner's word, with the next READY item. Every
command-line tool that opens the workspace now holds the same shared lease as a
web request, for the whole command: `offsetx-outreach`, `-notebook`, `-evals`,
`-tools`, `-db` and `-artifacts`. During a backup or restore, or while an
interrupted restore awaits rollback, each refuses to start and says which. A
running one makes a restore answer 409, as a busy worker does. The helper is
`cli_workspace_lease` in `outreach/workspace_lock.py`.

Decisions made while building, with their reasons in the code:

- `offsetx-db` and `offsetx-artifacts` lock only when their target is inside
  the data directory. A Postgres check, or a run copied elsewhere, is nothing a
  restore swaps — and checking Postgres is what an operator does while a
  restore is stuck.
- Two refusal sentences, not the work order's one. A backup export takes the
  same exclusive lease, so "a restore is in progress" would have been wrong
  half the time.
- `data_paths.gmail_token_path` is now the one Gmail-token rule, and the web
  app reads it too, so the two cannot drift a third time.

Found while building, all fixed here: `offsetx-artifacts` writes into the
workspace (`D-139`); `.env.example` pinned the CRM and Gmail token outside the
data directory (`D-140`); the notebook read the AI context from the wrong
folder (`D-141`). Verified in a real run: six installed tools refused while a
separate process held the lease; a real HTTP restore answered 409 while a real
`offsetx-outreach import-contacts` held its lease, and succeeded after it ended.

The fresh-context review found one high defect this change widened: a tool
run as root left a lock file the app's user could not open, and every API
request answered 500 with health green (`D-142`). Fixed, with `D-143` to
`D-145`, each test-first. Open, and not claimed: `D-146` — a tool pointed at
the app's files from another folder, or with `OFFSETX_DATA_DIR` only in `.env`,
locks the wrong workspace; `S-06.02.28` owns it.

## 2026-09-23 — the handoff: the remaining work is written down, not built

The owner asked to stop building and to leave the rest as planned features, for
an implementer to build from. `BOARD.md` stays the one list: each item that
has a build plan carries a `work_order:` line pointing into `docs/work-orders/`.

New from this handoff: work orders for `S-06.02.24`, `S-06.02.25`,
`S-06.02.23`, `S-06.02.26`, `S-12.01.03`, `S-12.02.05`, `S-12.02.06` and the
close-out of `S-06.02.21`/`S-06.02.22`; the tenancy design for `S-06.01.06`
(`docs/architecture/CRM_TENANCY.md`); new stories `S-06.02.25` (`D-137`),
`S-06.02.26` and `S-06.02.27` (split from `S-06.02.23`); defects `D-137` and
`D-138`, both open with their stories. No code changed in this step.

## 2026-09-23 — the cold review of `develop`: ten defects, fixed

A reviewer in a fresh context read the consolidation's own code — the WP1
port, the campaign-selection port and the merge's `app.py` — and reproduced six
of its ten findings. Each is fixed with a test that failed first, and so is one
found while checking the fixes in a real browser:

| | Defect | Fix |
|---|---|---|
| critical | `D-124` any login could export the whole install (its admin token inside) or restore over it | owner-only: the token or the `local` login (DD-59) |
| high | `D-125` a workspace read another's product through drafts; any login ran the owner's content timer | a per-request caller marker; refused, not drafted blank (DD-60, DD-61); timer owner-only |
| high | `D-126` an external CRM database's WAL replayed over the other generation | sidecars move with the file, before it |
| high | `D-127` compose mounted the old data path; CLIs opened a second CRM | new mount; one path rule, `data_paths.py` (DD-63) |
| medium | `D-128` backups 500 on Python 3.10 | `wait_for`; the suite now runs on 3.10 |
| medium | `D-129` app would not start beside a busy worker; worker ran on a half-restored workspace | lock only with a journal, bounded wait; worker checks under its lease |
| medium | `D-130` a failed campaign list hid every screen, Settings included | only campaign screens wait |
| low | `D-131` the tool registry kept other threads' connections across a restore | tracks and closes all |
| low | `D-132` `api_token=`-style secrets passed the scanner | any `…token` name |
| low | `D-133` a long scheduled run held every request at 503 during a backup | timers stopped first, bounded; refuse, don't wait (DD-62) |
| low | `D-136` a failing campaign list always said "API access needed" | only a 401/403 says so; found in real Chromium |

Filed, not fixed: `D-134` (the CLIs write without the restore lease,
`S-06.02.24`) and `D-135` (CRM rows belong to no workspace — `Q-27`, the
owner's, with `S-06.01.06` waiting on it).

**What stays open.** `S-06.02.21` and `S-06.02.22` stay IN_REVIEW: their fixes
have tests but no second review, and the real-container and real-browser checks
ran before them — the browser walks were re-run on the fixed build (a created
campaign stays selected through Contacts and a reload; with the list failing,
Settings and its backup still show). `S-06.02.19` is BLOCKED on the branch
deletion. The image with
these fixes was built and run in real Docker: in the compose
layout a fresh `./local_data` became writable, kept a campaign across container
replacement, and refused a workspace login's backup and restore (403) while the
owner's export worked; the production acceptance (unprivileged user, kill and
recreate, restore, refusal on `/tmp`) passed again.

## 2026-09-23 — the branch consolidation: one working branch, `develop`

**What `develop` is.** Every piece of built work, on one branch. It started
from `feature/next-three-batch-4` (which contained `main`), merged the GTM
engine (E-12), the reports feature (`S-07.01.04`), the competitor research and
the frontend-audit record, and ported from `integration/main-consolidation` the
durable-state work (`S-06.02.21`), the campaign-selection fix (`S-06.02.22`) and
the owner's production contract. Every other branch was either already
inside it or built the same stories another way; each is to be kept as a tag.
`docs/BRANCHING.md` has the full record, the workflow and the renumbered IDs.

**What the consolidation found.** The newest line had never run its own
suite — CI could not start a runner (`D-75`), and nothing else ran it. On its
own it had 33 failing tests and 5 test files that could not load (`D-115`).
Root causes, all fixed with tests (`S-06.02.19`): every privacy route raised
NameError (`D-103`); the strict request schemas pre-empted the older endpoints'
readable errors and some requests the screens send (`D-107`); timers crashed
reading a login from a request they do not have (`D-109`); a bare `token=` in a
prompt passed the scanner (`D-110`); workspace-login installs could not start
(`D-111`); and several tests checked nothing (`D-104`, `D-105`, `D-108`). Its
restore lost data — a stale WAL replayed over the restored database, and the
backup named only four stores (`D-114`) — which the durable-state port replaced.
The Docker image could not build, on `main` too (`D-116`).

**Proven here, not assumed.**
- Full Python suite green, ruff gate clean, frontend tests and build green (the
  numbers are on the `Tests:` line at the top of this file).
- The real image, built and run in Docker with `OFFSETX_PRODUCTION=1` on a
  named volume, read-only root and no capabilities: kept a record and an asset
  through kill and recreate, restored a backup, stayed ready, and refused to
  start on `/tmp`.
- In real Chromium, the old code kept "First campaign" selected after
  "Second campaign" was created; `develop` keeps the new one through Contacts
  and a reload.

**Still open, on purpose.** The thirteen build-ahead stories stay IN_REVIEW —
the consolidation made them pass their tests, it did not review them.
`S-06.02.23` re-checks the other findings of the 7 September audit on
`develop`; two are known to be open (`D-121`, `D-122`). Both Render services
are free, so their data does not survive a restart (`Q-26`). CI still cannot
start a runner (`D-75`).

## 2026-09-23 — CHECK review of S-06.02.01, S-06.01.01 and S-06.01.04

The governing README was re-read first. Mode stayed CHECK, methodology Kanban,
role captain/architect. These stories were already IN_REVIEW, so this pass
audited production consumers and failure paths instead of creating new scope.

- **S-06.02.01 / D-79:** the scanner covered vendor-specific credential shapes
  but not generic assignments/field names such as `api_key=opaque-value` or
  `client_secret`. A bounded assignment rule plus the structural secret-field
  deny-list now block those values before provider instantiation.
- **S-06.01.01 / D-100:** `WorkspaceAISettingsStore` used per-instance thread
  locks around shared JSON/encrypted-key files. Concurrent processes could lose
  another workspace's update. Complete write windows now serialize through a
  standard-library SQLite write lock while the existing atomic replace remains.
- **S-06.01.01 / D-101:** the username regex double-escaped NUL/CR/LF and rejected
  normal characters such as r/n/x/0. The intended control-character regex and
  regressions are committed.
- **S-06.01.04:** cold review traced declaration → scheduler/event match →
  workspace lease → AgentRun → verified `notification` record → persistence.
  The two acceptance criteria remain enforced at production boundaries; no new
  code change was justified.

Work orders:
- `docs/work-orders/S-06.02.01-generic-secret-scan.md`
- `docs/work-orders/S-06.01.01-cross-process-settings.md`
- `docs/work-orders/S-06.01.01-username-validation.md`

The new workspace lock file contains no customer/settings/key data and requires
no migration. Rollback can remove the lock file while the application is
stopped; the existing JSON/encrypted-key formats are unchanged.

Executable proof is still unavailable because S-06.02.18 / D-75 prevents
GitHub-hosted jobs from reaching workflow step 1. None of these stories moves to
DONE without focused tests, full regression and the board verifier.

---

## 2026-09-23 — CHECK review of S-06.02.04, S-04.01.01 and S-02.02.02

The three requested stories were already code-complete and IN_REVIEW, so CHECK
mode audited acceptance criteria against production consumers rather than
restarting discovery.

- **S-06.02.04 / D-76:** a partial privacy retry cached old successful stores.
  Retry now re-inventories prior successes and re-deletes if matching subject
  data reappeared. The unchanged-success case still avoids a redundant delete.
- **S-04.01.01 / D-77:** the companion fixture used exact memory scope, but the
  real CRM store merges `global` into scoped searches. The shared store keeps
  that historical default for existing callers; companions explicitly use
  exact scope only. The regression now uses the real `OutreachStore`.
- **S-02.02.02 / D-78:** resume could recreate a deleted managed PLAN.md and
  lose owner edits. An empty private `.PLAN.managed` marker distinguishes a
  genuinely legacy run from managed state; managed plan loss now refuses.

Work orders:
- `docs/work-orders/S-06.02.04-retry-revalidation.md`
- `docs/work-orders/S-04.01.01-exact-memory-scope.md`
- `docs/work-orders/S-02.02.02-plan-loss.md`

Executable proof is still unavailable because S-06.02.18 / D-75 prevents GitHub
Actions from acquiring a runner. No story is promoted to DONE without focused
tests, full regression and the board verifier.

---

## 2026-09-22 — API, accessibility and local meeting batch

Three READY stories were implemented sequentially and moved to IN_REVIEW:

- `S-06.02.02`: one default-deny API middleware boundary plus a closed public
  bootstrap/signed-callback allowlist; route-enumerating auth tests and
  secret-safe request-validation errors cover the registered API surface.
- `S-06.02.05`: shared skip/focus/live-region/modal behaviour plus keyboard
  alternatives on custom interactions and recursive TSX accessibility
  contracts.
- `S-07.01.03`: browser-local microphone + shared system/tab audio mixing,
  MediaRecorder chunks, loopback-only capture mutations, one immutable
  transcription provider/model per meeting, transcript-only persistence,
  privacy deletion and encrypted backup/restore.

Batch review found D-65 through D-70. Meeting hardening fixed provider/model
redirection, privacy/backup registration and capture cleanup/recovery. API
hardening replaced 54 raw JSON request bodies with strict contracts. Accessibility
hardening fixed page-change focus and a hover-only tooltip. Close-out also found
and removed a duplicated S-06.02.02 board row before handoff.

Owner/manual verification is still required for the real local meeting capture
and keyboard/screen-reader pass. No story in this section is DONE.

---

## 2026-09-20 — second next-three implementation batch

Three additional READY stories were implemented sequentially and moved to
IN_REVIEW under DD-22:

- `S-03.02.05`: `browser/platforms.json` + validator now drive identity,
  domain policy and default budgets from one declaration. Reddit demonstrates
  data-only onboarding. No browser verb or executable plugin surface was added.
- `S-02.02.02`: `agent/plan.py` gives each trace run exactly one PLAN.md,
  read fresh before every broker decision. Owner edits affect the next call;
  the exact consumed plan version is captured in that decision's trace artefact.
- `S-04.01.01`: `agent/companions.py` persists profiles as rows inside the
  existing ToolRegistry SQLite DB. Runtime uses only the companion's exact
  approved-memory scope and enabled granted tools; tool execution enforces the
  grant again. Authenticated CRUD/context/memory endpoints are wired.

Integration review found D-59 through D-64. The important corrections were:
replace process-local JSON companion storage with transactional SQLite; register
companion profile text with privacy deletion; and close/reconstruct tool and
companion stores around backup restore.

Remote Actions close-out evidence: run 971 (`35470919395`) on HEAD `dbe9d7fd2` created one `quality` job, failed in ~2 seconds with `steps: []`, `runner_id: 0` and no runner name. No repository command executed, so this is infrastructure evidence, not a failing product test.

Verification remains deferred by owner instruction. Focused commands are
recorded in DEMO.md and TRACEABILITY.md; do not promote these stories to DONE
without executing them, full regression and the board verifier.

---

## 2026-09-20 — next three implementations complete, verification deferred

The owner explicitly authorised build-ahead (DD-22): implementation may
continue across code-complete IN_REVIEW dependencies, but no downstream story
may be called DONE ahead of its evidence/dependency chain.

The requested batch is implemented and all three stories are IN_REVIEW:

- **S-05.01.02 — extraction packs.** Validated repository-controlled JSON
  declares domain, record selector and bounded text/attribute fields. It reuses
  Scrapling and the existing URL/robots/SSRF path; no executable plugin or AI
  extractor was introduced. Generic JSON-LD remains the fallback.
  CHECK-mode cold review on 2026-09-23 found D-72: malformed CSS selectors
  previously loaded successfully and could fail only during page parsing. The
  registry now validates selectors with Scrapling itself before installation,
  and pack selectors cannot supply text/attribute pseudo-elements.
- **S-05.01.03 — competitor teardown.** Normalized public structural/performance
  facts map deterministically to an existing video recipe. Copied media/caption/
  transcript fields are rejected. Projects use our own material and enter the
  existing human review queue.
  CHECK-mode cold review on 2026-09-23 found D-73: NaN/Infinity could pass the
  non-negative numeric validator and later crash tick conversion or contaminate
  performance evidence. All numeric facts now reject non-finite values before
  recipe selection or arithmetic.
  The same review found D-74: a removed/renamed declared recipe escaped as
  `UnknownRecipe` and would become an API 500. Recipe resolution now fails as a
  controlled `CompetitorTeardownError`, preserving the catalogue reason.
- **S-06.02.04 — subject access/deletion.** Authenticated, workspace-bound access
  and confirmed deletion use one eight-adapter inventory covering CRM/research/
  delivery data, recall, AI context/egress, tagged artifacts, CSV queues/exports,
  crawler state and trace runs. Partial failures stay partial and retry safely;
  CRM identity rows delete last.

Review found and fixed D-53 through D-58 before owner testing. Focused tests are
in `tests/test_extraction_packs.py`, `tests/test_competitor_teardown.py` and
`tests/test_privacy.py`.

Do not promote these stories from IN_REVIEW until the dedicated verification
pass runs the DEMO.md commands, the full regression and
`uv run python scripts/verify_board.py`.


---

---

## 0. Session setup

`.claude/hooks/session-start.sh` runs on every session. It prints the repository
name, branch, HEAD and commit count **first**, then installs Python and frontend
dependencies so tests and linters work immediately.

The identity banner exists because of a real incident: a session started against
the empty sibling repo `email_agent`, found no commits, and reported "your repo
is empty" instead of noticing it was in the wrong place. A repo that announces
itself makes that failure impossible rather than unlikely. `AGENTS.md` carries
the same warning for the same reason.

---

## 1. What this module is

An AI layer inside off_CRM that runs outreach cheaply across many providers,
where the owner's mailbox, CRM database and context layers are **structurally**
unable to reach any provider.

The governing rule: **models never pull, off_CRM pushes.** A model that can
*ask* for data has access. A model that can only *receive* a constructed payload
does not.

---

## 2. Architecture as built

```
offsetx_apollo_builder/ai/          ← self-contained, extractable (§4M)
├── tiers.py      trust tiers, data classes, policy levels, the rules between them
├── registry.py   reads config/providers.yaml; resolves provider + owner override
├── payload.py    builds outbound payloads from an ALLOWLIST, starting empty
├── scanner.py    pre-flight scan; a hit BLOCKS and raises, never redacts
├── quota.py      local RPM/RPD/spend accounting, file-backed
├── broker.py     THE single egress gate — the only code that calls a provider
├── modes.py      run modes: simple, verified, compare, orchestrated
├── verify.py     write -> check -> repair -> review
├── sandbox.py    container isolation for AI-written code (§4J)
├── abstraction.py widens the *shape* of a request: bands, stages, margins
├── bandit.py     Thompson allocation between approved template variants
├── cache.py      exact + lexical near-match response cache, keyed on the payload
├── tools.py      the registry of owner-pinned tools that may run in it
└── tool_cli.py   `offsetx-tools` — register, inspect, run
├── discovery.py  asks a provider what models its key reaches
├── log.py        egress log; own table, exact payload, SQLite or Postgres
├── workspace.py  per-workspace settings + Fernet-encrypted provider keys
├── errors.py     structured refusals the API turns into readable answers
└── failures.py   what kind of failure this was, and what to do about it

config/providers.yaml               ← the registry. Adding a provider is a
                                       config edit, never a code change (§4E)

offsetx_apollo_builder/distribution/ ← the content distribution runner
├── platforms.py  what each platform permits, and what off_CRM refuses
├── youtube.py    Data API v3 read client; the only transport in the package
├── trends.py     competitor watch list + what is actually rising
├── topics.py     what several channels are covering at once
├── pipeline.py   trend -> brief -> swipe -> caption -> draft post
├── publishers.py the adapter interface + the local outbox
├── store.py      accounts, posts, goals, engagement snapshots
└── engine.py     plan -> approve -> schedule -> publish -> measure

offsetx_apollo_builder/imagery/     ← the image campaign runner
├── gates.py      deterministic quality gates; header parsing, no image library
├── store.py      briefs, candidate assets, generator scores
└── engine.py     generate -> gate -> review queue -> swipe -> score

offsetx_apollo_builder/video/       ← the timeline editor (CapCut's shape)
├── timeline.py   the document, its invariants, and the frame resolver
├── edits.py      every edit as a pure function; a default-deny registry
├── gates.py      MP4 + WebM + WAV header parsing; gates on the exported file
├── presets.py    transitions, animations, text styles and speed curves, as data
├── recipes.py    whole-video shapes: beats, shares, which preset each beat uses
├── assembly.py   material + recipe -> a finished project, and the edit-diff
├── director.py   a topic -> a shape and the words; the model's reply, checked
├── mixdown.py    the audio mix as a gain-envelope plan the browser executes
├── captions.py   transcript -> readable cues -> text clips, deterministic
├── store.py      projects, version history (undo), media, transcripts, renders
└── engine.py     create -> edit -> undo -> caption -> render -> gate

frontend/src/video/                 ← the half that needs a GPU and a codec
├── resolve.ts    the frame resolver again, pinned to Python by one fixture
├── mixdown.ts    the gain-envelope planner again, pinned by the same fixture
├── audio.ts      OfflineAudioContext mix -> Opus chunks for the muxer
├── demux/        MP4 and WebM read for their frames, by hand
├── footage.ts    a decoder, a cursor and a frame cache, per video clip
├── render.ts     paints one resolved frame; the preview and export share it
├── webm.ts       the muxer; the only thing that writes the finished file
└── export.ts     load -> mix -> paint -> encode -> mux -> upload

offsetx_apollo_builder/             ← deliberately OUTSIDE ai/
├── intake.py     two-mode campaign intake; a contact list never meets a model
├── campaigns.py  the registry of campaign kinds; email is one of them
├── notebook.py   research-notebook export; the destination is a trust tier
├── notebook_cli.py  `offsetx-notebook` — targets, plan, export
├── codegraph.py  Graphify wrapper; keeps the semantic path switched off
├── codegraph_cli.py `offsetx-codegraph` — policy, build, status, verify
├── db/           backend seam: SQLite or Postgres behind one interface
└── db_cli.py     `offsetx-db` — check the backend, copy the egress log
```

The module depends on the CRM only through `outreach/models.py` (dataclasses)
and `outreach/providers.py` (HTTP adapters). Lifting it into its own repo means
taking those two seams with it.

### The call path

```
caller → EgressRequest (task_type, data_class, person, template…)
       → broker.plan()      1. tier filter   ← runs FIRST, cost cannot override
                            2. quota filter
                            3. same-tier-only chain
       → build_payload()    4. construct from empty, per resolved policy
       → scan_payload()     5. block + raise on any hit
       → provider.generate  6. call
       → log.record()       7. record provider, tier, exact payload, timestamp
```

### Trust tiers (owner's ordering, 2026-07-25)

| Tier | Who | Policy ceiling | May receive |
|---|---|---|---|
| A | Europe, self-hosted | full | public, person, campaign, CRM internal |
| B | USA, Canada, allied | standard | public, person, campaign |
| C | China, and anything demoted for weak data terms | pseudonymous | public, person's public profile **as tokens** |
| D | Routers/aggregators, anything unlisted | strict | nothing |

Tier is derived from **two axes** — jurisdiction *and* retention terms. Passing
one is not enough. Google's free tier sits at C despite being US-based, because
its terms allow training on submitted content.

### Data policies (least → most)

| Policy | Sends |
|---|---|
| `strict` | Category and question structure. Nobody identifiable. |
| `pseudonymous` | Job title, category and the public hook, with the person and company as `PERSON_1` / `COMPANY_1`. Free text is scrubbed of the name too. Nobody identifiable. **Tier C ceiling.** |
| `minimal` | The person's public name, company, title, hook + your positioning line. Addresses tokenised. |
| `standard` | Above + your template text and campaign notes. Addresses tokenised. |
| `full` | No field restrictions. Real addresses can leave. Explicit opt-in. |

**Note on `minimal`:** it deliberately permits the person's public name so
enrichment can personalise — the owner's instruction. It is now reachable only
by tiers A and B: tier C's ceiling was lowered to `pseudonymous` (owner's
decision 2026-07-31, reversing §5.2 below). The older `outreach/providers.py`
path keeps its own stricter meaning for `minimal`; the two are documented
separately so existing profiles never silently widen.

`full` stays available on any tier via a recorded override with a mandatory
reason. Credentials, mailbox headers and internal field names are blocked at
**every** policy level including `full`.

---

## 3. Done

### The GTM engine — Phase 1 and 2 (E-12, 2026-09-22)

The owner's end goal is an autonomous GTM engineer. Phase 1 gives the system one
source of truth about the product; Phase 2 is the brain that plans, applies,
reviews and revises. Design, data model, API and work orders:
`docs/architecture/GTM_ENGINE.md`. Decisions `DD-40`–`DD-54`; defects
`D-80`–`D-84`; open questions `Q-20`–`Q-24`.

- [x] **`offsetx_apollo_builder/gtm/`** — `products.py` (validation, forbidden
      claims), `store.py` (the only code touching `gtm_*` tables),
      `strategy.py` (plan request, envelope, parse, rules plan, feasibility),
      `review.py` (diagnosis, remedies, revision) and `service.py` (the one
      stateful orchestrator). **It imports nothing from `ai/` and no transport**;
      `tests/test_gtm_products.py` walks the package's AST to hold that.
- [x] **The model never builds structure.** It chooses from declared lists and
      writes short sentences; code decides volume from what is connected and
      always sends on `targeted_outreach`. Its reply is untrusted input, checked
      field by field (`DD-40`).
- [x] **The owner's words travel only in classified fields** — the one-liner as
      the positioning line, the rest as campaign notes — never in the system
      prompt or `instructions`, which the data policy does not govern (`DD-41`,
      `D-81`). Requests are `DataClass.CAMPAIGN`, so tiers C and D never see them.
- [x] **Apply creates paused campaigns**, imports nobody, spends nothing and
      sends nothing (`DD-42`); it is idempotent per channel (`DD-49`).
- [x] **Review in a fixed order** — delivery, running, contacts, approvals,
      volume, and only then the copy, by a 90% Wilson interval after 20 sends
      (`DD-45`, `DD-47`, `DD-50`). Every review is stored with exactly what it
      measured: the first labelled data this product owns, and what a fine-tune
      would train on when the owner builds it last.
- [x] **Revise** carries the measured rate forward, keeps the deadline, and
      judges each version on its own sends (`DD-53`, `DD-54`).
- [x] Screens: **Product** and **Go-to-market plan** (plan, apply, review,
      revise). No button leads nowhere: a step no screen can do yet is shown
      without a link and says so.
- [x] 184 GTM tests across six files, plus 4 UI tests; all six stories `DONE`
      after a cold review by a reviewer that never saw the code being written.
      It found 13 problems (`D-87`–`D-99`); 12 are fixed, each behind a test that
      failed first, and one is filed (`D-97` → `S-12.02.06`). The worst:
      pausing a posting campaign did not stop posting (`D-87`), and a revised
      angle reached nothing that is sent (`D-89`).
- [x] Walked in a real browser (headless Chromium against the running app):
      product → plan → apply → review → revise, and the Product screen's link
      checklist. The migration's rollback was executed once (`GTM_ENGINE.md` §4).

**Not built here, on purpose:** the video director reading the product
(`S-12.01.03`, blocked on `D-81`); drafting against the expert corpus
(`S-12.02.05`); running a plan's posting channel from the screens (`S-12.02.06`,
`D-82`); video in the email (`F-12.03`, Google Drive for now — `Q-20`); driving
Apollo, Hunter, Clay and Mailchimp as tools (`F-12.04`); compiling an audience
into an Apollo search (`F-12.05`); creating social accounts in bulk (`Q-21`,
open — it conflicts with the sock-puppet row and the FTC rule on fake
influence).

### Protected bulk email delivery (beta, F-08.01, 2026-08-24)
- [x] Added deterministic permission, relationship, global-suppression,
      frequency, send-window and unsubscribe preflight. AI is not part of any
      send-policy decision.
- [x] Added stream- and domain-isolated sending identities with SES verification,
      seven-day SPF/DKIM/DMARC/alignment freshness, configuration-set and signed
      SNS-topic requirements. AWS credentials stay in the normal SDK chain.
- [x] Added schema v9 durable jobs with immutable message snapshots, atomic
      SQLite claims, cross-path daily caps, per-lane rate/backoff state, bounded
      retries and `delivery_unknown` quarantine after ambiguous provider state.
- [x] Added public HMAC one-click unsubscribe, RFC 8058 headers for permission
      marketing, hard-bounce/complaint suppression, idempotent feedback,
      campaign health thresholds, auto-pause and explicit resume.
- [x] Reply sync now cancels already queued jobs. Temporary pauses and closed
      send windows defer without consuming a provider attempt; cancellations
      are conditional and cannot race a claimed job into an operator cancel.
- [x] Added SES v2 raw-MIME transport, a separate `offsetx-email-worker`, API
      surface, exact `QUEUE LIVE EMAILS` confirmation and a Deliverability UI
      with loading/error/empty states, identity checks, permission evidence,
      suppression, job cancellation and health resume.
- [x] Core evidence re-certified under S-08.01.01–04 on 2026-08-27: 16 focused
      delivery tests and the complete 1,461-test Python suite pass. The latest
      known frontend evidence remains 116 tests and a production build from the
      implementation session; S-08.01.05 stays in review until its dashboard
      test is re-run. Live AWS/domain/mailbox-cohort validation is still
      explicitly required; see `docs/architecture/EMAIL_DELIVERY.md`.

### Open-source release hardening (2026-08-20)
- [x] Replaced the stale public README with the current product boundary: CRM,
      public-page lead discovery, AI routing, image campaigns, video editing,
      content distribution and the Stage-1 browser agent, with stable/beta/alpha
      status and external-provider costs stated plainly.
- [x] Removed real professional contact details from the public sample exclusion
      CSV and from the unit-test fixture that repeated one of those identities.
- [x] Repaired the locked install. `websockets` is now represented as a direct
      dependency in `uv.lock`, and the exact CI command `uv sync --extra dev
      --locked` succeeds on a clean environment.
- [x] Fixed `POST /api/v1/ai/run` in verified mode: a non-empty `checks_suite`
      called an undefined `_evals_path()` and returned 500. Eval config now has
      one shared resolver, an environment override, a packaged fallback and a
      drift test, so both source checkouts and installed wheels load the same
      rules.
- [x] Raised `cryptography` to 50.0.0 and `pypdf` to 6.16.1, clearing the known
      Python dependency advisories found in the release audit.
- [x] Added a focused Ruff CI gate for syntax and undefined names plus smoke
      tests for every installed CLI entry point. The gate would have caught the
      verified-mode failure before release.
- [x] Verified the full result: 1,416 Python tests, 115 frontend tests, frontend
      production build, CLI smoke tests, lock check, package compatibility and
      dependency audit all clean.

### Security core (§5)
- [x] Single egress gate. `create_provider` is reachable only from `ai/broker.py`,
      `outreach/providers.py` and `outreach/provider_profiles.py`; enforced by
      an AST test that walks every module.
- [x] Two former bypasses fixed: `api/app.py` (request-supplied provider) and
      `outreach_cli.py` now go through `create_guarded_provider`, which cannot
      return an unwrapped provider.
- [x] Payload **construction** replaces filtering. `PersonPublic` has no email
      field, so an address cannot arrive through the person path at all.
- [x] Pre-flight scanner blocks and raises. Catches addresses, owner domains,
      credentials (12 shapes), mail headers, internal field names, env vars,
      local paths.
- [x] Trust tiers on both axes, with per-model provenance caps (a US host
      serving a Chinese-origin model is capped at C).
- [x] Default-deny: an unlisted provider raises rather than being assumed safe.
- [x] Fail-closed: unknown tier, empty candidate set and exhausted quota all
      stop the call.
- [x] Failover never crosses a tier boundary.
- [x] Mailbox is unreachable by default for every provider; unlock needs the
      exact phrase `ALLOW MAILBOX CONTENT TO LEAVE`, and even then tier C is
      still refused.
- [x] Egress log with the exact payload + inspector UI (`#egress`).
- [x] Credential isolation: Fernet, `0600`, per workspace, env fallback.
- [x] §5.12 acceptance tests — 30 cases in `tests/test_ai_egress_wall.py`.

### Run modes (owner's design, 2026-07-25)
- [x] **Simple** — one model, cheapest permitted. The everyday path.
- [x] **Compare** — every permitted model answers at once, side by side. Each
      runs under *its own* policy, so a tier C model can contribute without
      seeing more than it should. Capped at 8 branches so one question cannot
      burn every quota.
- [x] **Orchestrated** — a head model writes a plan, each step routes normally.
      **The head model must be tier A or B.** Planning means seeing the whole
      job, so restricted models get steps to do, never the job to split.
      A plan cannot widen its own reach: a step asking for `mailbox` or
      `internal` is clamped to what the caller already offered.
- [x] Model strip in the AI screen: every connected AI, its trust badge, and a
      meter showing how close it is to its daily limit.

### Per-model connectors (2026-07-26)
- [x] A connector is a **key**, and a key reaches many models. One NVIDIA key
      offers Llama, DeepSeek, Qwen, Phi, Gemma, Granite, Mistral, Nemotron.
- [x] **Tier belongs to the model, not the key.** NVIDIA+Llama is B,
      NVIDIA+DeepSeek is C — in the same run, on the same key.
- [x] `model_origin_rules` in config classify a model by name prefix. The
      provider supplies names; config decides trust. Unmatched name -> tier D.
- [x] "Find models" calls the provider's `/models` endpoint. Sends no owner
      data; still written to the egress log so the record stays complete.
      Degrades to the config list on any failure, with the reason shown.
- [x] Connecting a model off_CRM cannot place is refused with the fix in the
      message, rather than failing later at call time.
- [x] **Per-model `request_options` in config** — `max_tokens`, `temperature`,
      and provider-specific keys such as NVIDIA's `reasoning_budget`. A large
      reasoning model with no `max_tokens` gets truncated by the provider's
      own default, so this is correctness, not tuning. Options are opt-in per
      model; models that declare none send a plain payload.
- [x] Reasoning models handled: `reasoning_content` is returned when
      `content` is empty, and `finish_reason: length` produces an error that
      names `max_tokens` as the fix instead of "no message content".
- [x] Nemotron Ultra 550B and DeepSeek R1 seeded with working options.
- [x] **Image generation.** Models carry `kind: chat | image`; image models
      go to `/images/generations` and return pictures. Same key, same tier
      rules, same scanner, same log — a prompt is text, so a prompt naming a
      real person is still person data. FLUX (German) and Stable Diffusion
      (British) seeded on the NVIDIA key with origin rules for their makers.
      Pictures come back as base64 so they never sit behind a provider URL;
      the image itself is not written to the egress log, only the prompt and
      a count, since the log exists to show what *left*.

### Fixed in this round
- [x] **The chosen model was ignored.** `candidates_for` resolved each provider
      with no model id, so every call fell back to `default_model` — and the
      provenance cap was therefore unreachable from the UI: picking a Chinese
      model on NVIDIA was treated as tier B. Three call sites had the same gap
      (broker, compare, orchestrated planner); all now route per model, each
      with a regression test.

### Features
- [x] §4B Connectors: own screen; Gmail moved out of Settings; every provider
      card shows **country, trust tier, retention terms**, usage and cost.
- [x] §4C AI chat: model selector, task mode, Markdown/HTML export, dictation
      where the browser supports it (degrades silently where it does not).
- [x] §4E config-driven registry: 17 providers in YAML with jurisdiction,
      retention, RPM/RPD, context window, cost, `verified_on` date.
- [x] §4E local quota counting + usage display + same-tier failover.
- [x] §4L: structured refusals surface as readable sentences with a next step,
      never a raw status code. Every empty state has an action.

### Context layer (§4F/§4H) — built

- [x] `ai/context.py` — job state (steps, decisions, facts) plus a **rolling
      summary assembled by Python**, not written by a model. Same inputs, same
      summary; no per-update AI cost and no drift.
- [x] Decisions survive a model swap mid-job, which is the point of the layer:
      the head model can change without the choices being quietly undone.
- [x] Reply-rate counting per template and variant. A template is not judged
      until 20 sends, so one lucky reply out of two is never a "50% success".
- [x] Weak templates (judged, at or under 5%) can be rewritten. The request that
      leaves carries **the template wording and two numbers** — no recipient, no
      name, no address — so it runs as public work under any permitted model.
- [x] Nothing goes live automatically. A rewrite is shown for approval and saved
      as a new variant to run against the old one.
- [x] The winning template is offered to other models as a reference to follow
      or beat (owner's request).
- [x] **Wired into the real send path.** `OutreachEngine` counts a send when the
      message actually leaves and a reply against the template that was sent —
      not the contact's current stage, which has usually moved on. The unattended
      automation sender counts too. A counter failure can never lose a send.
- [x] Two safety rules with their own tests: **no model can query this store**
      (no tool, no function, no retrieval interface, no provider import), and
      **only code writes to it** — so the numbers stay facts.
- [x] `record_reply` takes no reply text. Detecting that a reply arrived is a
      fact; reading what it says would be mailbox content leaving. There is
      nowhere to put it.
- [x] Memory screen in the UI: reply rates, weak flags, the rewrite awaiting
      approval, and jobs in progress.
- [x] This is **not fine-tuning**. No data is shipped away to retrain anything.

### Eval harness — built (2026-07-31)

Answers what the run modes could not: does orchestration beat one good model?

- [x] `ai/evals.py` — twelve **deterministic** check kinds, pure functions of the
      output text. No model judges anything, for the same reason no model
      enforces policy: a grader that varies is not a measurement.
- [x] An unknown check kind **fails** rather than passing, so a typo in a check
      name cannot silently inflate every score that uses it.
- [x] `config/evals.yaml` — suites are config, like `providers.yaml`. Adding a
      case is a data edit.
- [x] `ai/scoreboard.py` — run history, leaderboard, and the champion per suite.
- [x] **Champion/challenger gate.** A mode is promoted only if it beats the best
      single model on the mean, **and** wins case-by-case beyond chance, **and**
      stays inside a cost ceiling. Every other path keeps the champion.
- [x] Significance by **exact binomial sign test**, not `>`. Both subjects run
      the same cases, so the comparison is paired. Comparing raw means on a
      thirty-case suite flips the winner on noise about half the time when the
      two are actually equal, and every flip costs money because the challenger
      runs several models per task.
- [x] `route_for()` returns `simple` when nothing has been measured. An
      unmeasured system routes to one model, never to an unchecked ensemble.
- [x] `offsetx-evals` CLI: `list`, `run --modes`, `champion`, plus `--dry-run`
      that prints the call count without spending tokens.
- [x] Same rules as the rest of the module: evals go through the broker with
      ordinary tier rules (verified against a tier D aggregator), and **no model
      can read or write the scoreboard** — asserted by an AST walk.

**First result, and the reason this was worth building.** On the shipped suite,
compare mode scored *identically* to the champion — not close, equal — because
`first_permitted_text` returns the highest-tier branch, which is the champion's
own answer. Compare mode paid for two calls and returned what one model would
have said alone. That is fine for its designed use (the owner reads every branch
and picks) but means calling it programmatically buys nothing. Nobody could have
known without measuring.

**Honest limitation:** seven cases ship. That is a skeleton, not a suite. Thirty
or more is the floor for trusting a close verdict, and the CLI warns on every
`list`. The cases worth adding are ones from real work that disappointed you.

### Two-mode intake — built (2026-07-31)

Two ways a campaign gets its people, kept apart because conflating them is how
mistakes happen. **Generate**: describe who you want, discovery finds them.
**Parse**: you already have the list — CSV, spreadsheet or PDF.

**Deliberately outside the `ai/` package.** A contact list is the densest
concentration of exactly what the system protects — real names, addresses,
companies. If a model parsed it, that one feature would leak more than every
other path combined. Parsing is deterministic and local; a test walks the module
and fails the build if it ever gains a route to a provider or an import from
`ai/`. Same rule as the campaign runner: the parts touching real contacts have
no AI, the parts with AI have no real contacts.

- [x] CSV and XLSX through the existing loader. A column is a column, so nothing
      is flagged and the result is immediately usable.
- [x] **PDF reading via `pypdf`, locally.** Addresses are found exactly — an
      email has a shape a pattern matches. Names are inferred from layout: the
      same line first, then the line above, which are the two arrangements a
      printed table actually uses.
- [x] **Every PDF row is flagged `needs_review` and can never be sent
      unreviewed.** Not a placeholder for better parsing later — guessing which
      name belongs to which address and being wrong means emailing a real person
      by the wrong name. `ready_to_send` is False whenever anything is flagged.
- [x] When no name is convincing, the row says "no name found near this address"
      rather than guessing. A wrong name is worse than a missing one.
- [x] Column headers are not mistaken for people; duplicate addresses read once;
      page numbers recorded so a row can be found again.
- [x] **No OCR.** A scan has no text layer, and pretending otherwise produces
      confident nonsense — the warning says to export the original as CSV.
- [x] Refusals are readable: missing file, unsupported type, a file that is not
      really a PDF.
- [x] Generate mode is a validated brief. No contact in a generated list is
      invented by a model; the data source produces them.

**Defect found while building.** The row builder read `full_name` and `company`,
but `normalize_input_rows` emits the CRM's own field names, `name` and
`organization_name`. Every parsed row came back with no name — which looked like
a parsing failure and was really a mapping one. Caught by exercising it against
a real CSV rather than trusting the field names. Regression-tested.

**Not built:** no UI screen, and wiring generate mode to discovery is separate
work. Tests build a real PDF by hand rather than mocking extraction, so the
genuine `pypdf` path is exercised without adding a test dependency.

### Response cache — built (2026-07-31)

**Named honestly.** The literature's "semantic cache" and its 60-90% hit rates
come from chat systems where users repeat questions. Personalised outreach gives
every payload a different token and hook, so those numbers do not transfer. It is
also not embedding-based — that would mean a network call from a module whose
point is avoiding calls, or a heavy dependency. It does exact match plus lexical
near-match, which fully covers where caching actually pays here: re-running eval
suites, retries, verify-loop repair rounds, and repeated public or code work.
The cache reports its own hit rate, because whether it earns its place is a
question for the owner's numbers rather than a published average.

- [x] **Keyed on the constructed payload**, not the question. Payloads are built
      per policy — verified, not assumed — so a response produced from a richer
      payload can never be served for a thinner one. That matters beyond the
      obvious: a response can travel back out as `prior_drafts`, so a cache that
      blurred policy boundaries would be a slow path for tier A material to
      reach a tier C provider.
- [x] Partitioned by workspace, data class, policy, task type and provider.
      Near-matching is confined to one partition, so fuzzy comparison cannot
      cross a boundary however similar two texts look.
- [x] **Consulted after construction and scanning, never before.** A lookup must
      not become a way around the checks that precede it — if the scanner
      blocks, nothing is served and nothing is stored.
- [x] **A hit is logged as `cache_exact`/`cache_near`, not `succeeded`.** Nothing
      left the machine, and the egress log is the one thing that must never lie.
- [x] Near match at 0.92 Jaccard over **word triples**. Single-word overlap would
      call two different questions similar; triples require the phrasing to line
      up. The threshold errs towards missing, because serving a stale answer to
      a different request is worse than missing a hit. Switchable off.
- [x] Never stores empty responses or failed calls — that would turn one
      transient outage into a week of them — and never stores `MAILBOX`.
- [x] 7-day TTL, 5,000-row cap with oldest-first eviction, manual purge and
      clear. A cache, not an archive; the egress log holds the record.
- [x] Exact and near hits counted separately, since they carry different risk.

### Traffic shifting — built (2026-07-31)

`context.py` counts sends and replies; this decides the split. Thompson sampling
over Beta posteriors, in `ai/bandit.py`, reached through
`context.traffic_split()`.

**Why not a threshold.** The arithmetic of low reply rates rules it out:
separating 2% from 4% needs ~1,140 sends per variant, 2% from 3% needs ~3,800,
and twenty sends with no replies has a 54% chance of occurring even at a healthy
3% true rate. A threshold rule fed that data does not become cautious — it
becomes confidently wrong.

- [x] Thompson allocation: the share a variant wins **is** its probability of
      being best. Near-even when posteriors overlap, shifting as they separate —
      correct at both ends with no cut-off to choose. That graceful degradation
      is the whole reason for the choice: a threshold has to be right, this does
      not.
- [x] `sends_needed()` tells the owner how far off an answer is. On two nearly
      identical rates it reports tens of thousands of sends, which is the useful
      answer: stop trying.
- [x] 5% floor per active variant. Without a holdout a winner that later
      degrades looks fine forever, and a variant unlucky in its first twenty
      sends could never recover.
- [x] Rates reported as posterior means, not raw fractions — one reply from two
      sends is not a 50% reply rate.
- [x] Seeded runs are reproducible, so a split can be re-derived later.
- [x] Retired variants excluded entirely. Structural test: `bandit.py` imports
      no database and no provider, so the maths can be tested exactly.
- [x] **Decides how much, never whether.** It allocates only between variants
      the owner already approved; an unapproved rewrite is not an active row for
      it to see, so it cannot promote one. §3 is unchanged.

**Defect caught while building.** The verdict read "traffic stays near even"
while allocating 80/20 — the sentence contradicted the numbers. Thompson does
shift below the confidence bar; the text was simply false. It now describes the
real split, with a parametrised regression test asserting the even-split wording
only appears when the leader is under 65%.

### Abstraction layer — built (2026-07-31)

Tokenisation hides *who*. This hides *how the business works*, which no PII rule
touches. Verified against the real builder first: a tier B provider was
receiving company size, funding stage, the stated ICP band, the **gross margin**,
the **close rate**, the sequence length and engagement counts — verbatim, with
every identifier already removed.

- [x] `ai/abstraction.py` + `config/abstraction.yaml` — 14 deterministic rules,
      three kinds (`bucket_number`, `replace_pattern`, `replace_terms`). Rules,
      not a model: a protection that varies is not a protection.
- [x] **Every rule only ever widens.** None can make text more revealing, which
      is why applying it twice is safe — asserted by an idempotence test.
- [x] Applied below `full` only; at `full` the owner has explicitly trusted one
      provider with everything. Off per workspace via `abstract_business_shape`,
      defaulting **on**, so a caller that forgets gets protection not a leak.
- [x] Loud config validation: unknown kind, missing `(?P<value>)` group, absent
      open-ended bucket and malformed pattern all raise at load. A rule that
      silently does nothing is worse than no rule, because it looks like
      protection.
- [x] A broken rules file does not stop a send — failing to widen must not
      become failing to send.

**Three defects found and fixed, each with a regression test.**

1. **The margin was leaking.** The percentage rule ended in `\b`, and `%` is not
   a word character, so that boundary can never match. The single most
   commercially sensitive number in a payload passed straight through the rule
   written to catch it.
2. **A rule was lying.** The sequence-position rule turned "a warm *first*
   email" into "a warm *a later message in the sequence*", inverting the
   meaning. Caught by an existing test failing. `first` is now left alone
   entirely: every sequence has a first message, so the word leaks nothing —
   it is the high ordinals that disclose how many steps exist.
3. **Rule order was wrong.** `headcount` preceded `headcount_ranges` and
   consumed the right-hand number of "100-250 staff", so the range rule never
   fired. The more specific pattern must run first.

Cost to quality is near zero: ordinary copy instructions pass through untouched,
and where the rules do fire they leave the useful signal intact.

### Tool registry — built (2026-07-31)

The list of who may enter the locked room. One sentence carries the design:
**a model names a tool that already exists; it cannot describe a new one.**

- [x] `ai/tools.py` — register, list, enable/disable, remove, run, run history.
- [x] **`run()` takes a `tool_id`, never an image or a command.** A test asserts
      this at the *signature* level: if the parameter list ever grows `image=`
      or `command=`, the build fails, because the registry would have stopped
      being a registry.
- [x] Three mandatory pins, none defaultable: a `github.com/owner/repo` URL, a
      **full 40-character commit SHA** (branches and tags refused — they move),
      and a version-pinned image (`:latest` refused).
- [x] **The catalogue withholds the recipe.** A model sees id, name, description
      and whether arguments are accepted. No image, no command, no repository —
      so a leaked catalogue is not a leaked attack surface. A disabled tool is
      *absent* rather than marked, so a model cannot tell it exists.
- [x] Extra arguments are **opt-in per tool**, capped at 8, values only —
      anything starting with `-` is refused so a caller cannot change how the
      tool behaves.
- [x] **Source is fetched on the host, not in the container.** The container has
      no network, so it cannot clone; off_CRM materialises the pinned commit
      first and then proves `rev-parse HEAD` equals what was registered. That
      puts the integrity check somewhere a compromised tool cannot reach. Source
      lands in `inbox/`, which mounts read-only, so a tool cannot rewrite its own
      source mid-run.
- [x] Every run is logged with **the commit and image it actually used**, not
      just the tool name. A timeout is recorded as a run, not raised away.
- [x] `offsetx-tools` CLI: `register`, `list`, `show`, `catalogue` (prints
      exactly what a model would see), `run`, `enable`/`disable`, `remove`,
      `runs`.

**Defect found and fixed while building this.** `sandbox_available()` checked
for the docker *binary* with `shutil.which`, which is not the same as a running
*daemon* — the dev machine has the binary and no engine, and the first CLI run
sailed past the check and failed several steps later inside a git fetch with a
much worse message. It now probes with `docker version --format
{{.Server.Version}}`; `docker info` is unusable here because **it exits zero
even when the server half fails**. Both a zero exit and a non-empty server
version are required, with a parametrised test over all four combinations.
`check_daemon=False` skips the subprocess where the answer is only advisory.

**Not built on purpose:** no model-facing path. Nothing yet hands the catalogue
to a model or lets an orchestrated plan call a tool. Storage and isolation
should be solid before anything automated can reach them.

### Sandbox isolation — built (2026-07-31), salvaged not written

`agent/off-crm-v0-12-ai-studio` — an abandoned parallel design from 24 July —
had already solved container isolation before the `ai/` module existed. Rather
than merge that branch (14 conflicts, and it carries a whole second AI module
with no `ai/` at all), the isolation layer was lifted into `ai/sandbox.py`.

- [x] `docker_command()` — `--network=none`, `--read-only`, `--cap-drop=ALL`,
      `--security-opt=no-new-privileges`, `--user=65534:65534`, pids/memory/cpu
      caps, and `noexec,nosuid` scratch space.
- [x] **`--pull=never`**, the sharpest idea in the original: the image must
      already be present. Without it, a crafted image name *is* a network fetch
      — a way to reach the internet from the one feature that must not.
- [x] **Improved on the original:** `--memory-swap` equal to `--memory`. Without
      it the memory cap is advisory, since a container can exceed it by
      swapping. The salvaged version omitted this.
- [x] Images must be **version-pinned**; `:latest` is refused, because the image
      you reviewed is then not necessarily the image that runs. Image names are
      validated against a strict character set so a name cannot smuggle extra
      arguments into the docker invocation.
- [x] Workspace is `inbox/` (read-only), `work/` (writable) and `store/` —
      which is **not mounted at all**. Not read-only: absent. The context layer,
      recall index, egress log and encrypted keys do not exist in the
      container's view of the filesystem.
- [x] Sandbox jobs are `DataClass.PUBLIC` only, enforced. Anything carrying a
      person belongs on the egress path where the tier rules apply.
- [x] Refuses rather than degrading: Render and other nesting hosts are detected
      up front, and a missing Docker is a refusal, not a fallback. Python cannot
      sandbox Python, so there is no weaker option worth offering.
- [x] Disk budget counted by off_CRM (10 GB default), because Docker cannot
      size-cap a bind mount. Documented as a safety limit rather than a lock.
- [x] **§5.12(c) now covered.** Composition is asserted on every invocation, and
      a live test starts a real container and tries to open a socket — skipped
      unless `OFF_CRM_SANDBOX_TEST_IMAGE` names a pre-pulled image, since
      `--pull=never` forbids fetching one and a network-isolation test that
      quietly downloads from the internet would be self-defeating.

**Still unverified:** the flags themselves need a real Docker daemon. Everything
around them is tested; run the live test on your machine to close that.

### Verify loop — built (2026-07-31)

Where the quality per credit actually comes from. Not models voting: a cheap
model writes, **code** judges, the specific failures go back, and a more trusted
model reads the result. Checking is easier than producing, and output tokens
cost several times what input tokens do, so the checking half is the cheap half.

- [x] `ai/verify.py` — `VerifyLoop`: generate, check, repair, optional review.
- [x] **Enforces the same checks the eval harness scores with.** `checks_for()`
      reads the suite's `default_checks` from `config/evals.yaml`, so what
      production enforces and what the harness measures cannot drift apart —
      one edit moves both.
- [x] **The best attempt wins, not the last.** A model told to fix a length
      problem will cheerfully break the subject line; returning the final
      attempt would ship that. Ties go to the earlier round, since a later round
      that only matched it cost money for nothing.
- [x] **Deterministic checks are the gate; a model review only advises.** A
      glowing review cannot turn a failing draft into a passing one — tested.
- [x] Round cap: default 3, hard cap 5 regardless of what a caller asks for.
      Rounds 1-2 capture most of the available gain, and a loop that can run
      twenty times is a way to spend twenty times the money on a task that is
      not converging.
- [x] A policy refusal **stops** the loop rather than retrying it. Retrying
      produces the identical refusal.
- [x] No checks supplied means nothing was verified, and it says so rather than
      reporting a pass.
- [x] The repair prompt carries the previous draft in `instructions`, not
      `prior_drafts` — so a tier C model can fix its own work without the
      payload widening to carry campaign material. Tested: a repair round to a
      restricted provider stays pseudonymous and never gains the template.
- [x] The reviewer prefers a **second opinion within the same tier**, never
      dropping a tier to find one. Self-review is labelled as such.
- [x] Shipped as a fourth run mode, `verified`, so the eval harness can score
      it against the champion. The API dispatches it explicitly rather than
      letting it fall through to `simple`.

### Recall over sent mail (RAG) — built

Retrieval where the access rules, not the search, were the work. A normal RAG
stack leaks in four places; each is closed by construction here.

- [x] `ai/recall.py` — local full-text search (SQLite FTS5) over the owner's own
      sent mail. **No embeddings, no API key, no network call.** Indexing the
      whole archive posts nothing to anyone and works offline.
- [x] **Redacted before it is stored, not on the way out.** Most stacks keep the
      raw text and clean it at query time, which makes the index the most
      dangerous file in the product. Here names, companies, addresses, phone
      numbers and links are removed before the write. A test reads the raw bytes
      of the database file and asserts no identity survives in it.
- [x] Redaction is **targeted, not guessed**: off_CRM knows exactly who its
      contacts are, so it deletes their names precisely. The vocabulary covers
      *every* contact, not just the recipient — an email to one person routinely
      names another. A pattern pass then catches what no contact list could know.
- [x] Over-redaction is the deliberate choice where the two disagree. A common
      first name is removed even though it costs a legitimate word sometimes.
      Dates are kept: a date identifies nobody and losing them makes the
      snippets useless.
- [x] **Sent mail only, enforced twice.** `index_message` refuses an inbound row,
      and `store.sent_messages` filters to outbound in the SQL with no parameter
      that could switch it.
- [x] **Quoted threads are cut off first.** A follow-up usually quotes the reply
      underneath it — that block is *their* mail inside *your* mail, and it never
      reaches the index.
- [x] **No model can search it.** No tool, no function, no retrieval interface,
      no provider import, no network import. off_CRM chooses the search, reads
      the result and pushes a payload. Asserted structurally.
- [x] Snippets leave as `DataClass.CAMPAIGN` — the honest label for the owner's
      own business writing. Calling it `public` would have smuggled it past the
      rule keeping campaign material from restricted providers. **Two
      independent barriers, neither special-cased for this feature:** tier C and
      D refuse the class outright, and the snippets travel as `prior_drafts`,
      which a `minimal` policy does not carry at all.
- [x] The payload is still scanned on the way out, so a regression in redaction
      blocks the call rather than leaking.
- [x] Wired into the live send path and the unattended sender. A reply sets a
      "this one worked" flag and is otherwise not stored, which makes
      "show me emails like this that actually earned replies" possible.
- [x] Deletion: forget one message, forget one person, or clear everything.
      Redaction is not an answer to a deletion request.
- [x] Past emails screen: search, and a preview that renders the **real**
      outbound payload rather than a description of it.

### Orchestration audit (2026-07-31)

Full design review in `docs/architecture/`. Two defects found and fixed; both
reproduced against the real code before changing anything.

- [x] **Simple mode never picked the cheap model.** `candidates_for` returns
      permitted pairs cheapest-first, then `broker.plan` discarded everything
      below the top tier — so with Mistral (A, cost 20.0) and DeepSeek (C, 3.57)
      connected, a `public` coding task ran on Mistral at **5.6x the cost**,
      while the free model that was fully permitted sat idle. The same-tier rule
      exists to stop *failover* demoting restricted data; it was also gating
      *initial selection*, which is a different thing — `candidates_for` has
      already checked `permits(data_class)` on every candidate, so picking a
      cheaper one is not a demotion. Narrowed to: `public` uses the full
      cost-sorted list across tiers, everything else keeps the old behaviour.
      Each candidate still builds its own payload under its own policy.
      Switchable per workspace via `cross_tier_public_routing` (default on).
- [x] **`best_text` did not mean best.** It returned `branches[0]` after a sort
      on `(tier, ok, duration_ms)` — the fastest reply from the highest tier, not
      the best answer. Nothing scores quality; no scorer exists. The docstrings
      were honest (compare mode says the *owner* picks) but the name promised a
      judgement, and it ships through `to_dict()` into `frontend/src/types.ts`.
      Renamed `first_permitted_text`; `best_text` kept as a deprecated alias so
      the API contract is unchanged. A real `best_text` can land with the evals.
- [x] The Simple mode UI description claimed "cheapest" unconditionally. Now
      states the actual rule: cheapest for public work, most-trusted for person
      and campaign data.

### Notebook export (§4G, 2026-08-10)
- [x] `notebook.py` + `offsetx-notebook` (`targets`, `plan`, `export`).
      Docs: `docs/architecture/NOTEBOOK_EXPORT.md`.
- [x] **NotebookLM has no public write API**, so this produces a bundle you
      upload by hand rather than an integration that would break the week
      Google moves a button. The same bundle suits a Claude Project, a ChatGPT
      Project, or a notebook you host.
- [x] **The destination is a trust tier.** An export you drag into NotebookLM
      is a push, and the rules do not care that the transport is a person.
      `notebooklm` is C (Google free tier, terms permit training on input),
      `hosted_notebook` B, `self_hosted` A. Raising a tier needs a written
      reason; lowering one does not.
- [x] Built from a declared allowlist of sections, each naming its data class.
      The tier decides which survive; a withheld section's data is never even
      fetched.
- [x] Scanned with `ai/scanner.py` before the first byte reaches disk. A hit
      blocks the whole export and leaves no folder behind — a partial bundle is
      worse than none, because it is uploadable.
- [x] Every withholding is written down with its reason and its fix, in the
      README and `MANIFEST.json`. Nothing is silently absent.
- [x] **Mailbox content is unreachable structurally**, not by a runtime check:
      no section carries the class, and a test pins the exact set of store
      methods this module may call. `sent_messages`, `last_outgoing` and
      `record_reply` are not in it.
- [x] Addresses never appear at any tier, including `full`.
- [x] Below `minimal`, people and companies are tokenised **per bundle**
      (`PERSON_1..PERSON_n`) — one shared token for 200 people is a list with
      the answers removed. Free text is scrubbed too, so a public hook reading
      "Ana Silva spoke at the EU trade summit" survives as "PERSON_1 spoke at
      the EU trade summit". The campaign's own name is withheld below `minimal`
      as well: it is usually the ICP written out.
- [x] The map back to real people is written **outside** the uploaded folder,
      at `0600` — not a warning inside it, because "select all and upload" is
      what people actually do.
- [x] **Does not assume email.** Sections declare campaign kinds; outcomes and
      templates are email-only and refuse by *kind*, not by tier, so the owner
      is not sent looking for a permission problem that does not exist.
      `campaign_kind()` reads a `kind` column that does not exist yet and falls
      back to `email`; a test asserts the column is still absent, so the day it
      lands the test points at the reader that needs checking.
- [x] No model touches a bundle. An AST test fails the build if this module
      ever gains a route to a transport.

### Browser agent, Stage 1 — off_CRM gets hands (2026-08-18)
- [x] **The blueprint first.** `docs/architecture/BROWSER_AGENT_BLUEPRINT.md`
      maps every Strawberry feature the owner listed onto eight stages, and says
      honestly which are already built here under other names — model routing,
      memory, credits, local-first, routines and the permission substrate all
      exist. The genuinely new work is the browser, the run loop, companions,
      skills, MCP and the crawler.
- [x] **No Chromium fork, and the reason is written down.** A fork buys one
      thing: the agent runs in your real session. The same property comes from
      launching *your* browser against *your* profile with a debugging port and
      driving it over CDP. What it does not buy is an app with your name on the
      icon — stated rather than glossed.
- [x] **A hand-written CDP client**, for the reason the WebM muxer is
      hand-written. Playwright's value is launching browsers and we are
      attaching to one that already exists; it would add ~300MB of browsers we
      would never run.
- [x] **The accessibility tree, not the markup.** A fiftieth the tokens, stable
      across restyling, and expressed in the vocabulary instructions are written
      in. Every actionable node gets an integer; **a model names a handle and
      cannot describe an element**, which is the same closed-vocabulary rule
      `ai/tools.py` applies to Docker.
- [x] **Ten verbs and no `evaluate`.** If a model could supply JavaScript to run
      in a logged-in session, the policy layer would be the only thing between a
      prompt injection on some page and the owner's Gmail — and the open web
      will eventually serve one.
- [x] **Real input, not JavaScript shortcuts.** `Input.dispatchMouseEvent` and
      real key events, because a synthetic click skips the hover, focus and
      pointer handlers many sites depend on, and an assigned field value looks
      filled and behaves empty.
- [x] **The policy layer is the honest part.** `discovery.py` blocks LinkedIn,
      Instagram and the rest for its *headless* engines and that stays. Driving
      your own logged-in session is a different act, so it gets a different
      policy — drawn at **volume and autonomy** rather than at domain: reading
      pace on session-gated platforms, and **attended-only**, so the agent goes
      there when asked and never on a schedule. localhost, `.internal` and the
      cloud metadata endpoint are refused outright.
- [x] **An append-only trace.** No delete, no edit, no truncate — an audit log
      with an eraser in it is not one. It is also what makes a run resumable and
      what drives the watch-it-think view: one artefact, so the thing you watch
      and the thing you audit cannot disagree.
- [x] **Three real bugs found by running it.** `select` was advertised and never
      implemented; CDP's node list is not document order, so the first snapshot
      read the page out of sequence; and thirteen Chromium processes leaked per
      run because `start_new_session=True` makes the browser its own
      process-group leader and `terminate()` never reached the renderers. The
      last one presented as flaky tests, which is what a resource leak usually
      presents as.
- [x] **Verified against Chromium 141**, not a mock: navigate, perceive, type
      with real keys, re-read the field from the browser, refuse an unconfirmed
      send, send, read the page's own output, screenshot with a real PNG header,
      choose a dropdown by its visible label with the `change` event firing, and
      refuse a handle nobody issued.
- [x] 32 browser tests, 3 of them live. **1,415 Python tests**, 0 leaked
      processes.

### Stage 7a — the posting-rate control: your cap, the engine's advice (2026-08-18)
- [x] **The owner's answer changed the design.** Asked for a daily posting
      ceiling, the owner said: *"it should be left up to the user, he will
      decide, although the AI will make him the ideal recommendation after
      looking at the data."* That is a better shape than a number, and it is
      what got built.
- [x] **A cap per handle.** `dist_accounts.daily_cap`, set by the owner, checked
      when a post is scheduled, counted **across every campaign** — the handle is
      what gets restricted and it does not care which campaign filled its day.
      It sits under the platform's published limit, under the pacing arithmetic
      and under any goal.
- [x] **Zero means no cap, not zero posts.** Nothing invents a default: a number
      this code made up would be a limit the owner never chose being enforced as
      though they had. With none set, the platform's own limit still binds.
      Reconnecting an account does not reset it either.
- [x] **A campaign's ceiling is the sum of its accounts' caps**, because the rate
      is one campaign-wide number and three handles capped at two can carry six
      between them. One uncapped account means the campaign has no cap — summing
      over a partly-capped set would invent a limit out of handles left open.
- [x] **The pacer recommends and waits.** `auto_pace` became `pace_mode` with
      three values: `off` (nothing runs), **`suggest`** (the number is worked out
      every cycle and applied by nobody — the new default), `auto` (it moves
      itself, still never past the cap). The same shape the video review queue
      has, for the same reason: a machine that makes things unattended must not
      also decide they go out.
- [x] **`accept` or `dismiss`, not a number.** `POST /content-automation/pace`
      takes a word, because setting the rate is a `PATCH` and this is a different
      act — a person answering something the machine asked. A suggestion is only
      stored when it differs from what is running; a screen that repeats itself
      hourly is one people stop reading.
- [x] **The old boolean still means what it meant.** `auto_pace: true` reads as
      `auto`, `false` as `off`, so no existing install changes behaviour because
      the default did. There is a test for exactly that.
- [x] **A UI, because a cap you can only set with curl is not the owner's.** New
      **Posting** screen: a cap box per handle, the three modes with their
      consequences in words, and the waiting suggestion with its reasoning and an
      Accept button.
- [x] **Verified on a live server.** A handle capped at 2 took two posts for one
      day and refused the third by name; the next day was fresh; with 20 real
      published posts at 1,000 views each against a million-view goal 100 days
      out, the engine wanted **9.80/day**, ramped its suggestion to **1.25/day**,
      and a cap of 1 pulled that to **1.00/day** with *"Capped at 1.00 a day by
      your own cap. Raise it if you want the goal met sooner."*
- [x] **What is still blocked on the owner, and only this:** no platform app
      approvals have been started. YouTube is the one reachable adapter and needs
      a Google Cloud project with the Data API enabled. Nothing else waits.
- [x] 19 pacing-cap tests, 6 rewritten automation tests. **1,383 Python tests,
      115 frontend**, build clean.

### Stage 6 — the effect engine: 48 primitives, 124 looks (2026-08-18)
- [x] **The largest part of an editor, made searchable.** CapCut's eight hundred
      filters written as eight hundred implementations are eight hundred things
      nothing can rank. `video/effects.py` declares **48 pixel operations** and
      **124 looks over them**; `frontend/src/video/shaders/` implements the
      operations in GLSL. A new look is one row. Feature map 54 → **61 built**,
      45% → **52%** of the reachable rows.
- [x] **A look is an ordered stack, not a knob.** `noir` is a desaturation, a
      contrast, a vignette and a grain — in that order, because they do not
      commute. So a preset is a list of `(primitive, params)` and the renderer
      runs it as a chain of full-screen passes, ping-ponged between two textures.
- [x] **Every look gets a strength slider for free.** Each parameter declares
      the value at which its primitive does *nothing*; applying at `amount`
      interpolates from there. Colours and structural choices — a mirror's axis,
      a kaleidoscope's segment count — declare no neutral and do not
      interpolate, because half a fold is a different picture and not a weaker
      one.
- [x] **The server resolves; the browser executes.** The manifest carries each
      clip's stack already flattened into passes. Deliberately the opposite of
      how a transition works, and for a reason worth writing down: a transition
      is one row, a look is a stack drawn from a hundred-odd of them, and nobody
      should download the catalogue to draw one clip. It also means **a look
      nobody declared cannot reach a shader**.
- [x] **Seven controls that were declared and never drawn.** `PROPERTY_SPEC` has
      carried `tint`, `sharpen`, `grain`, `vignette`, `corner_radius`,
      `border_width` and `shadow` since the timeline was written — stored,
      clamped, animated, and drawn by nothing, because a 2D canvas cannot. All
      seven are primitives now, and `temperature` stopped being a sepia wash
      plus a hue rotation and became the red/blue rebalance it always claimed.
- [x] **Nothing is random.** Grain and noise seed from the *frame index*, never
      the clock. A preview and an export that disagreed about the grain would be
      two different videos, and a re-export has to produce yesterday's file.
- [x] **A machine with no WebGL2 still exports**, falls back to CSS filters, and
      **names what it lost** per clip rather than handing back a picture that is
      quietly wrong.
- [x] **A test reads the other language.** Every primitive must have a shader and
      every shader a primitive, with parameter names matching in both
      directions — parsed out of the TypeScript, because nothing else would
      notice a rename on one side.
- [x] **Two real bugs, both found by running it.** `edge` took a parameter called
      `mix`, which shadows the GLSL builtin and compiles right until something
      below it calls `mix()` — there is a test for that class now. And
      `posterize` neutralised at 64 levels, so a preset containing one was not
      *quite* a no-op at strength zero; its neutral is 256 and the drift over the
      whole catalogue is now 0/255.
- [x] **Verified against real pixels, not assertions.** Headless Chromium on
      ANGLE/SwiftShader compiled all 48 programs; nineteen exact predictions
      computed in Python matched the GPU (invert, one stop of exposure, Rec.709
      luma, the sepia matrix, a 120° hue rotation, chroma and luma keys to alpha
      0, a blur turning a hard edge into 99/156/166); **all 124 looks at
      strength zero drifted 0/255**; and `paintFrame` itself put `mono` on a
      clip at `[119,119,119]` and darkened a vignette's corner from 255 to 110.
- [x] 49 effect tests and 19 frontend tests. **1,358 Python tests, 115
      frontend**, build clean.

### Stage 5e — the review queue: push, ignore, edit (2026-08-18)
- [x] **The gate between a machine that makes videos alone and an audience.**
      Every assembled or directed project now lands in a queue by itself, and
      nothing leaves it except through a person pressing push or ignore. The
      button the owner asked for early and video never had. Feature map 53 →
      **54 built** of 162; still 45% of the reachable rows.
- [x] **Two verdicts, three buttons.** Push and ignore are the answers; *edit*
      is what you do before answering. There is deliberately no stored `edited`
      flag — it is `project.version != baseline_version`, a question the
      document already answers. A flag written at edit time goes stale the
      moment somebody undoes back to the start.
- [x] **Push requires a passing export of *this* version.** What distribution
      publishes is bytes, not a document. Without the "of this version" half the
      common accident is fatal: export, keep editing, push, and publish a video
      the owner is no longer looking at. Three refusals, each a sentence the
      owner can act on: never exported / gates failed / edited since exported.
- [x] **The diff is measured on both verdicts and stored with them.**
      `assembly.difference(baseline, current)` — the learning signal starts
      collecting the day the queue exists. An owner who pushed something
      untouched approved of the assembler; one who rebuilt half of it first said
      something far more specific, and named the clips. An ignore after twenty
      minutes of editing is a different verdict from one on sight.
- [x] **The baseline is copied into the review, not looked up later.**
      `video_history` is capped at 300, so a project worked on for an afternoon
      loses the very version the machine produced. There is a test that edits
      past the cap and proves the diff still means what it says.
- [x] **A verdict is given once**, in the engine and again in the store beneath
      it. A number that moves when you click twice is not a score. One *open*
      review per project is a partial unique index in SQLite rather than a
      check-then-insert two requests can both pass; a project ignored and later
      re-cut can be sent back, and both verdicts are kept.
- [x] **The handoff is real, and cost one function.** `GET
      /campaigns/{id}/video-approved` answers what
      `/image-assets?status=approved` answers for pictures, with the same row
      shape. The API's asset resolver tries the image store then the render
      store, so a post carrying a render id publishes the video and the
      publisher learned nothing. A render that **failed its gates is not
      resolvable** — posting one would walk around the checks.
- [x] **A real bug fixed on the way.** `difference()` computed
      `kept = |old ∩ new| - moved - removed`, but removed clips are already
      outside the intersection, so every one was counted twice and `kept_share`
      understated what survived — the exact number this queue makes a headline.
      Four clips, one removed, one trimmed read 0.25 instead of 0.5.
- [x] **Verified on a live server, not only in tests.** Real uvicorn, real
      SQLite: an assembled project appeared in the queue by itself marked
      not-ready with its sentence; push before an export → 422 *"Nothing has
      been exported yet"*; an edit after one → *"This has been edited since it
      was last exported"*; re-export → push with `kept_share 1.0`; the render
      under `/video-approved`; a post pointing at it published with **the
      video's own bytes** in the outbox, compared byte for byte; a second
      verdict → 422.
- [x] 37 review tests and 1 assembly test. **1,309 Python tests, 96 frontend**,
      build clean.

### Stage 5d — the director: a topic in, a finished project out (2026-08-16)
- [x] **The model half.** `POST /campaigns/{id}/video-projects/direct` takes a
      topic and returns a stored, renderable project. The model chooses the
      shape and writes the words; the assembler does everything else. Feature
      map 52 → **53 built**; "Script → video, auto-assembled" is now ●.
- [x] **A model asked to emit a timeline emits invalid ones**, and nobody can
      review four hundred lines of JSON before they become a video. A model
      asked to pick one of eight declared ids and write three sentences is doing
      a job it is good at, and the answer is small enough to check completely.
      So `director.py` is almost entirely the checking.
- [x] **The reply is untrusted input.** A shape nobody declared is refused by
      name with the real list; prose is refused rather than guessed at; a fence
      is unwrapped (they all do it); a sentence before the JSON is read past; a
      length outside the bounds is clamped and said so; forty lines are cut to
      what the beats hold; a 400-character caption is trimmed; an invented field
      is ignored and named. Twenty of the thirty-one tests are that list.
- [x] **A hostile topic cannot do much, and that is architectural.** Topics come
      from scraping, so a trend title can say anything — including instructions
      aimed at whatever reads it next. The reply is validated against a closed
      set, so the worst it achieves is a video in a *different one of the eight
      declared shapes*. There is no field it can fill with an arbitrary edit and
      no path from the reply to a file. A test proves it with a real injection
      string.
- [x] **The prompt lists the real recipes**, read from the registry at call
      time. One naming a shape the assembler does not have produces a refusal
      nobody can act on; one missing a shape never offers it.
- [x] **Data class `public`, not `campaign`.** A topic is usually a trend title
      that was already on somebody else's website, and calling it campaign
      material would narrow the tier rules for something already public.
- [x] **Two real bugs found by running it.** `DirectionRefused` was a plain
      `ValueError`, so a model picking a bad recipe would have returned a 500
      instead of the sentence — it is a `TimelineError` now, like every other
      refusal. And the new endpoint did not catch `NoPermittedProvider`, so the
      very first thing anyone hits — no provider connected — was a stack trace
      instead of the 409 that says to open Connectors.
- [x] **Verified end to end.** Topic `"why nobody reads changelogs"` → the model
      picked `pattern_interrupt`, wrote three lines, asked for 12s → assembled
      over two real VP9 shots and a WAV bed → **`renderable: true`, no
      warnings**, one note about the music being shorter than the video.
- [x] 31 director tests and 6 engine tests. **1,266 Python tests, 96 frontend**,
      build clean.

### Stage 5c — the assembler: material in, finished timeline out (2026-08-16)
- [x] **The line the whole editor was cut from.** `POST /campaigns/{id}/video-
      projects/assemble` takes a recipe and a length and returns a whole project
      — cut, animated, captioned, scored — that the gates accept with nobody
      having touched a timeline. Blueprint Stage 5's centre; feature map 49 →
      **52 built**, 42% → **45%** of the reachable rows.
- [x] **A model picks the recipe and writes the words; it never builds the
      timeline.** The decision everything else follows from. A model that emits
      a document emits invalid ones — overlapping clips, transitions that do not
      fit, footage read past its end — and every invariant this project enforces
      becomes a suggestion. Choosing from a declared list is what a model is
      good at and what can be checked. Assembly is arithmetic and runs with no
      model at all.
- [x] **Nothing constructs a clip.** Every piece goes through the same `edits`
      functions a person's clicks do, so an assembled project is valid for the
      same reason a hand-made one is. If the assembler could produce an
      overlapping timeline, so could a user, and the invariant would already be
      broken.
- [x] `video/recipes.py` — **8 shapes over 5 families** (`hook`, `list`,
      `story`, `montage`, `demo`) as rows: beats with shares, and which
      animation, speed curve and text style each beat uses. Shares are fractions,
      so one recipe fits any length. A test resolves every preset id a recipe
      names — one pointing at an animation nobody declared is one that fails on
      the video somebody actually wanted.
- [x] **The duration is exact, at every recipe and every length.** The export
      gate compares a file against the project's own length, so a 30s target
      produces exactly 30s — snapped to a whole frame, the last beat absorbing
      what the shares round away. 48 parametrised cases assert it.
- [x] **The material decides the cuts, inside what the recipe asked for.** A beat
      longer than one clip can stretch to gets more cuts whatever the recipe
      wanted; ten times its own length is as far as one goes. 300s from 1s of
      footage cuts itself 31 times and still lands exactly.
- [x] **Short footage is slowed, not gapped** — 2s over a 6s beat plays at 0.37x,
      reading all its material and none past the end. The rate rounds *down* to
      four places: rounding the last one up makes a clip consume ticks the source
      does not have, which the assembler found by refusing itself.
- [x] **It says what it settled for.** Music shorter than the video, a curve a
      clip has no material to spare for, a line nobody could read in the time it
      is on screen — each a sentence in `notes`. The readability rule is the
      caption engine's own `READABLE_CPS`, not a second copy of it.
- [x] **`difference(before, after)` — the edit-diff.** What was added, removed,
      moved, retimed, restyled and rewritten, and what share of the assembly
      survived. Deliberately coarse. A person who accepts a cut says nothing; a
      person who moves it says something specific, and this is the only place
      that gets written down — the signal any later "learn from what gets edited"
      has to be built on, worth having before there is anything to learn.
- [x] **Verified end to end, for real.** The server assembled a project from
      `setup_turn_resolve` over two real VP9 shots and a WAV bed; its manifest
      came back `renderable: true` with no warnings; Chromium exported that exact
      document and the file went back through the server's gates: **all eight
      passed** — `1080x1920 video/webm, 8.00s`, six footage clips drawn, an Opus
      track. ffmpeg reads it as `vp9 30fps / opus 48000 Hz stereo`.
- [x] **A real gap that run found:** a bitstream the decoder rejects — a file
      that demuxes cleanly and names a supported codec but whose frames are not
      what its header says — used to take the whole render down with it. It now
      costs its own clip, draws the hole the painter already draws for a missing
      asset, and is reported once per file however many clips use it.
- [x] 93 assembly tests and 5 engine tests in Python, 1 regression test in the
      browser. **1,229 Python tests, 96 frontend**, build clean.

### Stage 5b — time remapping: curves, freeze, reverse (2026-08-16)
- [x] **Three menu items, one integral.** Freeze frame, reverse and speed curves
      are all the same question — how a clip's offset maps to a position in its
      material — so they are one function, `Clip.source_at`. At a constant rate
      it is `offset × speed`, which is why the conformance frames came out
      unchanged when it landed. Feature map 44 → **49 built**, 38% → **42%** of
      the reachable rows.
- [x] **`consumed(t)` is the area under the speed curve**, and the curve is
      straight between its points. CapCut's are bezier; these are not, on
      purpose. The resolver exists twice and the two copies have to agree *to
      the tick*, and a trapezoid — `(v₀+v₁)/2 × Δt` — is the same arithmetic on
      the same doubles in both languages where a cubic is not. An eased speed
      point is refused, and the message says to use more points instead.
- [x] **A speed of zero is a freeze, not a missing value.** That is what lets a
      frozen stretch live *inside* a curve, which is what every "bullet time"
      preset is. Two places had to stop writing `float(speed or 1.0)` — the
      third sighting of the falsy-zero bug that once restarted a paused campaign,
      and the first one caught by a test written before the code.
- [x] **`freeze_frame` is three edits in a coat**: split at the playhead, open a
      gap, drop in a clip at speed 0 reading the instant that was on screen. It
      inherits the *resolved* properties of that instant, so a clip caught
      mid-zoom holds the size it was at rather than snapping back to defaults.
- [x] **Reverse is a flag, not a negative speed.** A negative speed makes every
      other piece of arithmetic in the timeline signed for the sake of one clip.
- [x] **12 speed presets over 4 families** — `ramp`, `hero`, `impact`, `loop` —
      as rows, the same shape as transitions and animations. Each carries its
      `average`, which is the number that decides whether a clip still fits in
      its source: `hero` averages 1.10×, so a ten-second clip on one needs eleven
      seconds of material. `keep_duration=False` divides by that average to find
      the length at which the curve consumes what the clip consumed before.
- [x] **Retimed sound is left out and the manifest says which clips and why.**
      Resampling audio is not playing it faster, it is deciding about pitch.
      Playing a clip's audio at one rate under a picture doing something else
      drifts further apart the longer it runs, so `retimed_reason` names the clip
      and the mix goes on without it. Both languages carry the rule and the
      conformance fixture pins the answer.
- [x] **A bug only a real browser could find.** The exporter samples the middle
      of an output frame, and it did that by adding `half a frame × clip.speed`
      to the resolved source time. Wrong twice over once time is remapped: a
      reversed clip moves *backwards*, and a curved clip's local rate is not its
      `speed` field. It now resolves a second frame half a step later and takes
      source times from that — while still drawing the cast of the first,
      because at a cut the two hold different clips.
- [x] **Verified against the server's own prediction.** Python resolved a `hero`
      curve, a `bullet` freeze and a reverse and wrote down the source tick it
      says belongs on each of thirty output frames; Chromium ran the same
      documents through its resolver, decoder and painter over the 60-frame test
      video. **All ninety source ticks identical, every drawn frame matching** —
      `bullet` holding frame 15 for eight output frames, `reverse` counting 29
      down to 0 with nothing repeated. The first run is what found the off-by-one.
- [x] The conformance document now carries a clip that is both on a `hero` curve
      and reversed, with four sample ticks across it — time remapping is the one
      place a clip's source time stops being a multiple of its offset, so an even
      spread there would prove nothing.
- [x] 34 retime tests in Python, 11 in the browser, plus a regression test for
      the sampling bug. **1,130 Python tests, 95 frontend**, build clean.

### Stage 5a — video on the canvas (2026-08-16)
- [x] **Imported footage draws now**, in the preview and in the export. Until
      today a video clip's sound worked and its picture was a red hole, and the
      manifest refused to call any project with footage on it renderable.
      Blueprint Stage 5, first half; feature map 43 → **44 built**.
- [x] **`paintFrame` needed one line.** Its `AssetSource` is a
      `CanvasImageSource` and a `VideoFrame` is one, so the painter could always
      draw a frame — what was missing was anything that could produce *the frame
      at a given instant*. The one line is that a clip's own table entry wins
      over its asset's: a still is shared by every clip that places it, a piece
      of footage is at a different moment of itself in each.
- [x] **A demuxer, written by hand, for both containers.** `demux/matroska.ts`
      walks EBML into Clusters and reads SimpleBlocks; `demux/isobmff.ts`
      expands MP4's five parallel sample tables — `stts`, `ctts`, `stss`,
      `stsc`, `stsz`/`stco` — into one flat frame list. One level deeper than
      `video/gates.py`, which already walks both formats to read a file's shape.
- [x] **Not a `<video>` element**, which reads as simpler and is worse three
      ways: a seek costs tens of milliseconds and an export asks for every frame
      in order, so a sixty-second render pays a minute in seeks; it needs a
      document, so no worker and no `OffscreenCanvas`; and it gives no way to
      *hold* a decoded frame, which is what freeze frame and reverse are made of.
- [x] **Forward-only decoding with a cursor.** An export asks in increasing
      order, so the cursor never goes back and every frame is decoded exactly
      once. A backwards jump or a jump into another group of pictures restarts
      from that group's keyframe — what a seek costs in any editor. Twelve
      frames cached, and clips that leave the screen give their decoder back.
- [x] **Decode order is not presentation order.** The frame list stays in decode
      order because that is what a decoder must be fed, and a separate index
      sorted by presentation time answers "which frame is showing at T". The MP4
      fixture carries a signed `ctts` so the two genuinely differ.
- [x] **A real bug real Chromium found: a flushed decoder will not take a delta
      frame.** `decodeQueueSize` falls to zero when a chunk is *accepted*, long
      before its frame comes out, so treating that as "done" flushed on the
      first frame of every file and then refused the second. The pump now waits
      for output to stop arriving before it concludes anything.
- [x] **A second real bug, found by measuring: an output frame is an interval,
      not an instant.** A container stores times in its own units, so 30fps
      footage has frames at 33ms and 67ms while a 30fps timeline asks at 33.333
      and 66.667. Sampled at the leading edge that asks for frame 1 twice and
      never asks for frame 2 — a third of the footage silently replaced by
      duplicates. The exporter samples half an output frame ahead, at the middle
      of the interval the frame covers. The measurement read `0,1,1,3,4,4,6,7,7`
      before and `0,1,2,3,4,5,6,7,8` after.
- [x] **Verified in a real browser, and measured.** Chromium encoded a real
      60-frame VP9 file where frame *n* is a flat colour spelling *n* out as a
      three-digit base-4 number — levels 85 apart, so the dozen levels a lossy
      codec shifts a flat fill by cannot round a channel wrong. Demuxed,
      decoded, put on a timeline, painted, and the canvas's centre pixel read:
      **30 of 30 output frames matched their own source frame, in order, nothing
      duplicated and nothing dropped.** The export passed the gates and ffmpeg
      read it as `vp9 1080x1920 30fps, 2.00s`.
- [x] `scripts/build_mp4_fixture.py` — Python writes an MP4 from the spec with
      three different chunk sizes, sparse sync samples, a signed `ctts` and a
      version-1 `mdhd`, and the browser reads every frame's offset, length,
      keyframe flag and presentation time back exactly. The same cross-language
      check the WebM muxer already had, in the other direction.
- [x] **What the server cannot check, said plainly.** There is a gate for a
      missing audio track because a header says whether one exists. A clip that
      drew as a red hole produces a file whose header is perfect, so there is no
      equivalent — the browser reports per-file failures instead, and one
      unreadable import costs its own clip rather than the whole render.
- [x] 18 demux tests + 18 footage tests in the browser, 1 fixture guard in
      Python. **1,094 Python tests, 83 frontend**, build clean.

### Stage 4 — audio in the export (2026-08-16)
- [x] **Every file this project produced before today was silent.** The timeline
      had resolved gain per clip per instant since the day it was written and
      the exporter threw all of it away. Platforms bury silent video, so this
      was the difference between an export that can be posted and one that
      cannot. Blueprint Stage 4; feature map 40 → **43 built**, 38% of the
      reachable rows touched.
- [x] **A plan, not samples.** `video/mixdown.py` emits an *envelope* per clip —
      the points where its gain changes, in the clip's own time — and WebAudio
      applies exactly that shape with `setValueAtTime` /
      `linearRampToValueAtTime`. Asking the resolver per sample is 48,000 calls
      a second to produce a number that changes a few times across a clip, and
      would put a second mixer in Python that nothing ever runs.
- [x] **Dense only where the curve bends.** Between two keyframes the gain is a
      straight line. A fade is linear too — but it *multiplies* the volume
      curve, so a fade over a ramp is a parabola. Those stretches are sampled at
      100Hz and anything that turns out straight is collapsed back to its ends,
      each dropped point checked against the last *kept* one so a shallow curve
      cannot be walked away from one tolerance at a time. A constant clip is 2
      points; a one-second linear fade is 3; a two-second eased ramp is ~80.
- [x] **The gain rule now lives in one function per language** — `clip_gain()`
      in `timeline.py`, `clipGain()` in `resolve.ts` — called by both the frame
      resolver and the mixer. Two copies of it would be a preview that lies
      about the file it is previewing. The conformance frames came out
      byte-identical across that refactor, which is how we know it changed
      nothing.
- [x] **Footage is in the mix.** A video clip's sound travels in the same
      container as its picture and `decodeAudioData` reads it out. The picture
      still is not drawn; leaving the sound out because of that would be keeping
      the wrong half.
- [x] **Clipping is scaled, not clamped.** `headroom()` reports the worst-case
      sum at every envelope point — measured mid-crossfade, not at clip edges,
      because two clips fading through each other are loudest where neither
      starts nor ends. Over 1.0 the whole mix is scaled by the reciprocal, which
      keeps the balance between clips exactly, and the export reports that it
      happened. The manifest says it *before* the render, so it can be fixed
      properly instead.
- [x] **A new gate: `has_audio_track`**, asked for only when the server's own
      mix plan says the timeline makes a sound. A browser that cannot encode
      Opus hands back a perfect picture, and a silent video nobody noticed was
      silent is exactly this stage's failure mode.
- [x] `frontend/src/video/audio.ts` — the `OfflineAudioContext` graph, 20ms Opus
      frames, and a hand-written 19-byte `OpusHead` for when WebCodecs supplies
      no decoder description, because a WebM Opus track with no CodecPrivate is
      a file some demuxers refuse.
- [x] **Two muxer bugs found on the way in.** A cluster's Timecode is a whole
      millisecond, but block offsets were computed against the unrounded value —
      up to half a millisecond of error per block, which did not matter until
      there were two tracks to keep together. And a cluster only ended at a video
      keyframe, so a keyframe-sparse stretch could run past the 32,767ms a signed
      16-bit block offset can express; it now also cuts at 30s.
- [x] **Cross-language, both directions.** `npm run fixtures` now also writes
      `muxed_sample_audio.webm` carrying the real `opusHead()` bytes, and the
      Python gates read 48000Hz / 2 channels back out of it — the WebM prober
      learned `SamplingFrequency` and `Channels` to do it. The mix plan is in the
      conformance fixture's `mix` block and both planners are asserted to agree
      **point for point, including how many points**: the same curve described in
      a different number of points means one simplifier moved.
- [x] Deliberately not built: ducking, compression, EQ, normalisation, waveform
      display, beat detection. Each changes what the mix *sounds* like rather
      than what it *is*, and building them before the plain mix worked would mean
      debugging two things at once. The scoreboard guard asserts they are still
      marked not-built, in both directions.
- [x] **Verified in a real browser against a real tone, and measured.** A 3s WAV
      (440Hz left, 660Hz right) on a track with a one-second fade at each end,
      exported through headless Chromium and decoded back by Chromium's own
      demuxer and Opus decoder. ffmpeg reads the result as `vp9 1080x1920 30fps
      / opus 48000 Hz stereo, 3.00s`. Decoded RMS per quarter-second — 0.0623,
      0.1648, 0.2716, 0.3794, then 0.4310–0.4320 across the flat middle —
      against `A/√2·√((b³−a³)/3(b−a))` predicting 0.0623, 0.1648, 0.2715,
      0.3789, 0.4316. The fade came out of the file as the shape the planner
      described, and the channels did not swap on the way through.
- [x] 29 mixdown tests, 5 engine tests, 4 gate tests and 2 scoreboard guards
      in Python; 25 in the browser (11 mix conformance, 14 audio scheduling and
      OpusHead). **1,093 Python tests, 47 frontend**, build clean.

### Stage 2 — transitions, animations, the preset registry (2026-08-14)
- [x] `video/presets.py` + `frontend/src/video/transitions.ts`. **46 transitions
      over 9 families, 32 animations over 3, 12 text styles, 16 blend modes, 12
      more animatable properties.** Feature map: 29 → **40 built**, 37% of the
      reachable rows touched.
- [x] **Transitions without relaxing the invariant.** A dissolve needs both
      clips on screen and clips cannot overlap by a tick. The clips stay
      adjacent and a `Transition` on the track declares how far either side of
      the cut both are drawn — a bounded, declared property of the boundary
      instead of an accident of two clips' positions. Both sides share one
      `progress`; a clip drawn past its end is held at its last frame; one
      transition per cut; halves at both ends must fit inside the clip; an edit
      that destroys the cut removes the transition.
- [x] **Presets are rows, families are code.** A new transition is a line of
      YAML-shaped data, which is what makes the space searchable by the
      orchestrator later. `CAPCUT_TOOL_INVENTORY.md` argued this; this is it.
- [x] **An animation is ordinary keyframes**, so it survives a split, travels
      with a trim and resolves identically in both languages — none of which
      was rebuilt.
- [x] **A real bug found by the new tests: splitting inside a non-linear ease
      was not transparent.** The old resampler synthesised boundary keyframes
      from interpolated values, which is exact for a linear segment and wrong
      for every other kind — a sub-range of an ease-out curve is not an ease-out
      curve. The original split test passed only because it used a linear
      segment. Keyframes are now shifted rather than rebuilt: exact, and bounded
      by keeping only the nearest anchor either side.
- [x] Conformance fixture regenerated with a transition, a blend mode and an
      applied animation across it, and the TS test now asserts the transition
      field — the one place a clip is drawn outside its own bounds.
- [x] 36 new preset/transition tests, 3 regression tests for the eased split and
      trim, and the scoreboard guard now checks **both** directions: nothing
      claims to be built that is not, and nothing that shipped loses its mark.

### Goal-driven pacing (2026-08-14)
- [x] `distribution/pacing.py` — posting volume is adjustable **and the goal
      moves it**. `(target − measured views) ÷ views per post ÷ days left`, with
      every term checkable by hand. Blueprint §6.4.
- [x] **No data, no steering.** Below 5 measured posts there is no
      views-per-post figure, so it holds the declared rate and says why. A
      controller with nothing to measure is a random number generator, and that
      is the rule most likely to be broken by someone making it look clever.
- [x] **Raise slowly (+25%/cycle), lower immediately.** The errors are not
      symmetrical: a missed goal is recoverable next week and a banned account
      is not. An engine that notices it is behind and posts ten times more *is*
      a spam bot at that moment.
- [x] **10% deadband**, or the rate moves every cycle on noise and the schedule
      becomes unplannable. **Platform caps are hard** — Instagram's 25/day is a
      ceiling the arithmetic may approach and never cross, and the capping
      platform is named so a throttled campaign does not look like an
      under-performing one.
- [x] The new rate is stored, so the ramp compounds instead of restarting from
      the declared number every cycle and never arriving. `auto_pace` off by
      default.
- [x] A falsy-zero bug found by its own test: `float(x or 1.0)` turned a rate
      deliberately set to 0 — a paused campaign — back into 1/day.
- [x] 26 pacing tests + 8 in the automation cycle, including a live HTTP run
      against a real goal and 20 real metric rows: holds at zero data, then
      raises to a ramped 1.25 against a measured requirement of 9.8.

### Stage 1 — the content engine runs itself (2026-08-14)
- [x] `distribution/automation.py` — `ContentAutomationService`. Sweep → plan →
      draft → publish-due, on a timer, started and stopped with the app.
      Blueprint: `docs/architecture/CONTENT_ENGINE_BLUEPRINT.md` Stage 1.
- [x] **This was the highest-value missing line in the project.** Every piece of
      the content pipeline worked and none of them ran on their own; the Amul
      point in the brief is about time, and a trend acted on tomorrow is one
      somebody else already used.
- [x] **Which campaigns run is declared, not inferred.** The pipeline needs a
      distribution campaign *and* an image campaign, and nothing in the schema
      says which pairs with which. Guessing would post from the wrong brand, so
      the pairs live in the service's own config, a half-declared pair is
      dropped, and enabling with none declared is refused with a message.
- [x] **A failing step does not cost the cycle.** A YouTube quota error at the
      sweep must not stop posts a person already approved from going out. Each
      step is caught, recorded and reported; the next cycle tries again.
- [x] **The two human gates are untouched.** `publish_due` can only act on posts
      that already carry an approval. This service drives the machine either
      side of the swipe and the approval and stops at both.
- [x] The loop **waits before it runs**, so a restart loop cannot become a burst
      of sweeps against a quota. Interval clamped to 300s–24h.
- [x] Separate from the email `AutomationService` on purpose: that one is
      email-shaped, and nothing built from here may assume email.
- [x] `_TimerScope` — the four per-request engine factories read only
      `request.app.state`, so the timer passes an object with an `.app`. The
      alternative was changing thirty call sites to land in the same place.
- [x] 26 tests: declaration rules, corrupt-config safety, bounds, step order,
      per-step failure isolation, switch-off-by-name, no overlapping cycles,
      the wait-then-run loop, clean start/stop, and a live HTTP cycle through
      the app's real factories. Plus a structural test that this module imports
      no transport.

### Video projects on Postgres (2026-08-14)
- [x] `VideoStore` is opened through `resolve_target`, the same seam the egress
      log uses: explicit target, then `OFFSETX_DATABASE_URL`, then the local
      file. One variable moves timelines off a disposable disk.
- [x] The reason is not tidiness. `render.yaml` writes to `/tmp` on the free
      plan, and an instance that sleeps comes back empty — an hour of editing
      disappearing at that point is the work, not a storage detail.
- [x] **What it does not fix, stated rather than implied:** renders, uploaded
      recordings and generated pictures are bytes on a disk. The document is the
      part that took the work and the part that moves; files still need a real
      disk or object storage.
- [x] `tests/test_video_postgres.py` — 17 tests over **both backends**: schema
      creation, a whole edit session surviving a cold reopen with its undo
      history, undo/redo after a reopen, media and transcripts, the
      `ON CONFLICT ... DO UPDATE` upsert, the hash uniqueness that stops paying
      twice for one recording, and history trimming. Run against a real
      Postgres 16, not asserted.
- [x] A structural test parses `api/app.py` and fails if `VideoStore` is ever
      handed a bare path again — that mistake shows up only as work quietly lost
      on the next restart.

### Auto-captions (2026-08-14)
- [x] `video/captions.py`, `broker.call_transcript`, `OpenAITranscriptionProvider`,
      media import, and an **Auto captions** button. Docs:
      `docs/architecture/AUTO_CAPTIONS.md`.
- [x] **Half of it is a media import path, and that is not padding.** Nothing in
      off_CRM generates speech, so the caption button had nothing to listen to.
      `POST /campaigns/{id}/video-media` takes a voiceover or a clip, reads its
      header before storing anything, and refuses a file that does not declare
      its own length — a clip whose `source_duration` is a guess cannot be
      stopped from reading past its end. WAV is in for that reason and **MP3 is
      refused**: a WAV's length is in its header, an MP3's needs every frame
      walked. Uploading the same file twice returns the existing row.
- [x] **The scanner cannot read a waveform, and that changes the rules.** Every
      other egress path is protected by a pre-flight scan; a recording of
      somebody reading a customer list scans clean because there is nothing to
      read. So `TRANSCRIBE_FORBIDDEN_CLASSES` refuses `mailbox` and `internal`
      **by class, before a provider is looked up** — their protection *is* that
      scan. The tier filter still applies in full, the text part of the request
      is still built from the allowlist and still scanned, and the egress log
      records the size and word count but **never the audio or the transcript**.
- [x] **Word timings, not sentence timings.** A caption timed to a sentence
      appears in full before it is spoken. Three response shapes are read (flat
      words, words nested in segments, segments alone) and a segment-only answer
      is kept rather than refused.
- [x] **Where to break is deterministic, not a second model call.** Sentence end,
      then pause (>0.6s), then line length (42 chars), then maximum hold (5s). A
      comma only breaks once the line is over half full — breaking at every comma
      gives a stutter of two-word captions. A test asserts no word is lost
      between transcript and captions.
- [x] **The timeline's invariant is the specification.** Clips cannot overlap by
      one tick and speech does not respect that, so `lay_out` snaps to frames,
      holds each cue back from the next, stretches short cues only into the gap
      actually in front of them, and **merges a cue that cannot get one frame
      into its neighbour** rather than dropping a word.
- [x] Media time is mapped through the clip's start, `in_point` **and** speed, so
      captioning a trimmed clip captions what is left and a slowed clip stretches
      its captions with the speech. Both have tests.
- [x] **Captions are ordinary text clips** on a Captions track, so every existing
      edit works on them and a person reads them before publication — the same
      judgement the swipe and the post approval are. The whole set is one step of
      undo; running it twice replaces rather than stacks; new pictures never land
      on the caption track.
- [x] The transcript is stored per file and reused. Deliberately **not** the
      response cache, which refuses anything whose output is a message: a
      transcript is a fact about a file that cannot change unless the file does.
- [x] `whisper-large-v3` and `-turbo` on Groq (same key as its chat models) and
      `whisper-1` on OpenAI, in both copies of `providers.yaml`. The `kind`
      filter in `candidates_for` needed no change — it was already generic.
- [x] Verified against an independent implementation: WAV files written by
      Python's stdlib `wave` module parse to the exact sample rate, channel count
      and duration.
- Not built: karaoke highlighting (the word timings are stored, the renderer
  cannot colour part of a line), translation, speaker labels, browser recording.
  **Imported footage is audible but not drawable** — its sound captions fine, the
  picture is not painted, and the manifest says so and marks the project
  unrenderable rather than exporting a hole.

### Video editor — timeline core and browser render (2026-08-14)
- [x] `offsetx_apollo_builder/video/` + `frontend/src/video/` + the **Video
      editor** screen. Docs: `docs/architecture/VIDEO_EDITOR.md`; the feature
      inventory it was cut from is `docs/architecture/CAPCUT_FEATURE_MAP.md`.
- [x] **The server owns the document; the browser draws it.** Every edit is a
      named operation, validated server-side, returned as a new document. One
      round trip per edit, and one place that decides whether an edit is legal —
      the same place that checks the exported file.
- [x] **Time is an integer at 90kHz**, the MPEG timebase, because it is the
      smallest rate whose frames are whole numbers at 24/25/29.97/30/50/60. A
      split at frame 100 is the same integer however many times the project is
      saved and re-split. An unlisted frame rate is refused, not rounded.
- [x] **Clips on a track cannot overlap.** Made unrepresentable rather than
      handled: an overlap means the renderer picks one, and which one it picks
      can differ between the preview and the export — the worst bug class an
      editor has.
- [x] **Every edit copies before it changes anything**, through
      `to_dict`/`from_dict`. A refused edit cannot half-apply and does not
      consume a step of undo.
- [x] **A split is transparent.** Both halves carry a synthesised keyframe at
      the cut, so the resolved animation is identical either side of it. A test
      resolves every tick across a split and asserts the two lists are equal.
      Trimming the head moves keyframes with the material for the same reason.
- [x] **Two resolvers, one fixture.** The browser must resolve keyframes itself
      — a preview cannot make a request per frame — so `timeline.py` and
      `resolve.ts` implement one rule twice.
      `tests/fixtures/timeline_conformance.json` holds a deliberately awkward
      document and the frame Python resolves at fifteen *chosen* ticks (the tick
      before a cut, the cut, the tick after, one past the end). Both suites
      assert against it. It forced `roundHalfToEven` in TypeScript, because
      Python breaks rounding ties to even and JavaScript breaks them upward.
- [x] **WebCodecs, and deliberately no MediaRecorder fallback.** MediaRecorder
      records in real time, drops frames silently, and writes no Duration —
      which would make the export gate unable to do its job. A fallback whose
      output cannot be verified is a quieter failure, so an old browser is told
      what it needs instead.
- [x] **A WebM muxer written by hand** (`frontend/src/video/webm.ts`), the same
      call `imagery/gates.py` made about Pillow. It buys an exact Duration
      written from the timeline that produced it.
- [x] **MP4 and WebM headers parsed by hand** (`video/gates.py`). Handles the
      display matrix (a phone records sideways) and version-1 64-bit boxes — a
      test caught a twelve-byte offset error in the latter during the build.
- [x] Gates: decodes, not_empty, readable_header, has_video_track, aspect_ratio,
      duration_matches, not_duplicate — checked against the project the file
      claims to be a render of. A failing render is **stored anyway** with its
      report: a gate result nobody can check the file against is an assertion,
      not evidence.
- [x] **Undo is a pointer move over stored history**, so there is no "unsplit"
      reconstructing what a split destroyed, and it survives a reload. Editing
      after an undo drops the abandoned branch. Capped at 300 versions.
- [x] Verified outside this project, not only by unit tests: the committed
      `muxed_sample.webm` is written by the TypeScript muxer and parsed by the
      Python gates in CI; ffmpeg reads it as `matroska,webm 1080x1920 3.00s vp9`;
      a real headless Chromium export passes the gates; and frame 0 of that
      export decodes to a blue rectangle of exactly 432x768 at (324, 576) —
      precisely scale 0.4 of a 1080x1920 canvas, measured rather than eyeballed.
- [x] Owned by the **image** campaign, whose registry entry always named video
      as what it was missing. `missing` is narrowed rather than cleared.
- Not built, and said plainly in the docs: **no AI feature is wired** (captions,
  cutout, reframe, text-to-video — every M row in the feature map); nothing
  generates video or audio material yet; no transitions (a dissolve is an
  overlap, which the invariant forbids — it needs a real transition object);
  the export holds the whole file in memory.

### Trend to post (2026-08-10)
- [x] `distribution/pipeline.py` — the piece that joins the three campaign
      kinds. Everything it needed already existed; this is the wiring, and it is
      what "run this campaign" finally means end to end. Docs:
      `docs/architecture/TREND_TO_POST.md`.
- [x] **Where the automation stops is the whole design.** Two halves, and the
      boundary between them is a judgement that already existed. `plan` goes
      topic -> brief -> candidates and **stops at the review queue**; `draft`
      takes the pictures the owner kept, writes captions and creates **draft**
      posts, which still need the approval the distribution runner has always
      required. The machine fetches, composes, generates and does the scheduling
      arithmetic; a person decides *is this picture good* and *does this go
      out*. Removing either would let the system publish something nobody saw,
      under the owner's name.
- [x] Both campaign ids are kind-checked in one call — the first must be
      distribution, the second image. A swapped id would otherwise write image
      briefs against an email campaign.
- [x] **The same topic is not planned twice.** Recorded by a key built from
      sorted terms rather than the label, because the label is the first three
      and a topic can gain a term between sweeps without becoming a different
      subject. A week's cooldown, or the review queue fills with the same
      picture every sweep.
- [x] Composition is **deterministic by default**, with an optional writer. The
      brief describes the subject and not the composition — over-specifying
      produces the same picture from every generator, defeating both running
      several and the swipe that compares them.
- [x] **The data class is chosen by what is sent**: topic terms and competitor
      titles are `public`; adding the owner's angle makes it `campaign`. The
      module decides nothing about trust — it labels honestly and the broker
      applies the rules it already has.
- [x] A failing or empty writer **falls back to the deterministic version**
      rather than costing the sweep. Tested both ways.
- [x] 21 new tests, all passing first run. Verified over HTTP, including the
      kind gate refusing a swapped campaign id.

#### Still not built
- Nothing calls it on a timer; that belongs in `AutomationService`.
- No UI for the plan/draft calls (the swipe half has one).
- One picture to three accounts carries the same caption to all three.
- The angle is a string the owner supplies — nothing derives it from their
  positioning or from what performed before, though `generator_performance` and
  the context layer both hold material that could.

### Topic clustering across channels (2026-08-10)
- [x] `distribution/topics.py`, surfaced at `GET /trends/topics` and inside the
      trends report. One channel running hot is a good week; several on one
      subject is an event, and the stronger signal.
- [x] **Distinct channels, not videos.** A channel posting five times about its
      own product has a content calendar, not a trend, so a term one channel
      uses scores one however often it repeats.
- [x] **A topic is a term common now and not before** — the same shape as the
      outlier multiple, one level down: share of channels inside the window
      against share outside, needing 2x lift. A term with no history at all is
      the strongest case, not a division by zero.
- [x] **Adaptive stopwords fall out of that for free.** Watch twenty logistics
      channels and "logistics" has a high baseline by definition, so the same
      arithmetic that finds a spike removes it. No per-industry list to
      maintain, and a hand-written one would still miss the words that matter to
      one owner and not another.
- [x] **Merging is on shared videos, not shared terms.** Term chaining is how
      clustering turns everything into one blob — A shares a word with B, B with
      C, and three unrelated stories become one topic. Tested with two
      simultaneous unrelated stories that must stay apart.
- [x] **Lexical, not semantic, and there is a test that says so.** "Rotterdam
      port strike" and "Dutch dockworkers walk out" share no word and will not
      group. Deliberate: semantic grouping means an embedding or a model call
      per sweep — a cost, a provider dependency, and a feature that dies with a
      key. The limitation is pinned by a named test so it is found here rather
      than by someone trusting the output.
- [x] 14 new tests, all passing first run.

### Trend detection on YouTube (2026-08-10)
- [x] `distribution/youtube.py` + `distribution/trends.py`. Docs:
      `docs/architecture/TREND_DETECTION.md`.
- [x] **YouTube because it is the only one of the four whose terms allow reading
      public data at scale** — no research application, no scraping. Instagram's
      Business Discovery is thin, TikTok's Research API needs approval, Facebook
      offers competitors almost nothing.
- [x] **The quota decides the design.** 10,000 units/day, and
      `search.list` costs **100** while a channel's uploads playlist costs **1
      for 50 videos**. A 1,000-channel sweep via playlists is ~1,100 units —
      daily. The same coverage via search is impossible: the whole budget buys
      100 searches. So `search` **exists only to refuse**, with the arithmetic
      in the message, and statistics are fetched batched 50 at a time.
- [x] Quota counted locally from documented per-call costs (Google exposes no
      live balance). A sweep that would exceed it **stops cleanly with a note**
      rather than raising halfway and leaving the day's picture half-updated.
- [x] **Raw view count is the wrong signal** — it returns the biggest channels'
      oldest videos every week, both already known. Two measures instead:
      velocity (views/hour, correcting for age) and **outlier multiple** (times
      the channel's *own* median). The multiple is the one that finds a subject
      rather than a channel, and there is a test where a small channel's
      20,000-view video outranks a big one's 520,000-view video because the
      first is 20x its baseline and the second is 1.04x.
- [x] A channel needs **5 observations** before its multiples are ranked; below
      that the video is listed and flagged rather than hidden, because hiding it
      would make the list depend on how long each channel had been watched. A
      20x multiple from two videos looks like insight and is arithmetic on noise.
- [x] Read-only, so **not** through the broker — same reasoning as
      `ai/discovery.py`: no owner data, only a channel id and a region code.
      Still written to the egress log so the record stays complete, and a test
      asserts the API key never appears in what is logged.
- [x] One module in `distribution/` has a transport and it is this one. The
      publishing path has none, and browser automation is refused across the
      whole package with no exception. The old blanket test was replaced by two
      precise ones rather than deleted.
- [x] 20 new tests, all passing first run. `/trends` works without a key from
      already-collected data; watching without one says so plainly.

#### Found while wiring it
- [x] `api/app.py` used `os.getenv` without importing `os`. It imported fine —
      the failure would have been a runtime `NameError` the first time anyone
      opened the trends screen.

#### Still not built
- Turning a trend into a post: `/trends` reports, nothing composes a caption
  from it. That is where this and the image campaign meet.
- Scheduled sweeps (nothing calls `/trends/sweep` on a timer).
- Topic clustering across channels — "six competitors posted about the same
  thing today" is a stronger signal than any one of them, and is not computed.

### Content distribution runner (2026-08-10)
- [x] `distribution/` — the third campaign kind, and the one that composes the
      others. All three kinds now have runners. Docs:
      `docs/architecture/DISTRIBUTION_CAMPAIGNS.md`.
- [x] **The hard part here is not code.** Each platform allows far less
      automated posting than it appears to, and the tools that seem to offer
      more are what get accounts banned. off_CRM publishes through **official
      APIs only**, and `platforms.py` declares every platform with its API, its
      preconditions, its quotas and what off_CRM refuses. Connecting an account
      it cannot post to is refused **at connection**, not at send time.
- [x] **One working adapter today: the local outbox** — not a stub, the same
      device `LocalOutboxProvider` is for email. The whole pipeline runs and is
      reviewable without touching a real account.
- [x] Quota facts recorded rather than assumed. YouTube's is **per API project,
      not per channel** (~6 uploads/day across every channel you own);
      Instagram's 25/day genuinely is per account. A planner assuming both were
      per-account would over-promise on YouTube by however many channels exist.
      Instagram's ceiling is checked **when a post is scheduled**, because a
      schedule that cannot be delivered looks like a plan.
- [x] Instagram's personal-account impossibility is refused by name; TikTok's
      unaudited private-only posting is refused rather than counted as reach.
- [x] **Goal-shaped**: "a million views", with progress against it.
- [x] **This closes the benchmark.** Gates and swipe were layers one and two
      from the image runner; engagement is layer three, and
      `generator_performance` joins it back — views grouped by the generator
      that drew the picture, so the owner's taste and the audience's can be
      compared and can disagree.
- [x] 20 new tests, and the whole loop verified over HTTP: campaign, account,
      goal, post, approve, schedule, publish, measure, progress (250,000 of
      1,000,000 views, 25%).

#### A real bug the tests caught
- [x] **Engagement snapshots were being summed.** `latest_metrics` picked rows
      by `MAX(measured_at)`, but timestamps were second-precision, so two
      readings a moment apart *both* matched the maximum and were added —
      reporting 100 views where there were 60, and a goal met when it was not.
      Now ordered by time then id, with microsecond precision on measurements.
      The test that caught it was written before the bug was known to exist.

#### Not built, recorded on the spec
- Adapters for the real platforms — each declared with the route that would
  serve it; each needs OAuth per account and, for Meta and TikTok, app review.
- Competitor watching and trend detection: the `read` column is the groundwork,
  the collector is not written, and it must be built on what terms permit.
- Automatic caption generation, scheduled publishing on a timer, and a UI.

### Image campaign runner (2026-08-10)
- [x] `imagery/` — the second campaign kind, and the first that produces
      something other than a message. `image` is now `implemented=True` with a
      runner. Docs: `docs/architecture/IMAGE_CAMPAIGNS.md`.
- [x] **The swipe is the label**, which is the answer to the owner's benchmark
      question. Not a model rating its own output — the owner's own decisions,
      collected free as a side effect of use. Every decision scores the
      generator that made the picture, and `ai/bandit.py` allocates the next
      batch on those scores using the same Thompson sampler that shifts traffic
      between email templates. The allocator does not know its arms are image
      models.
- [x] Three consequences, each tested: **a decision is made once** (or a score
      moves by clicking twice); **refresh counts as a rejection** (dropping the
      no would bias scores towards whatever got refreshed most); **rejection
      deletes the bytes and keeps the verdict** (the record of rejecting is what
      the benchmark is made of).
- [x] **It waits before steering.** Under 12 decisions per generator the
      allocator stays out of the way — a lopsided result from four swipes is
      noise, and acting on it would starve a generator that never had a fair run.
- [x] **Gates are layer one and are not about taste**: decodes, not_blank,
      readable_header, aspect_ratio (5% tolerance so a generator rounding to
      1152x648 still satisfies 16:9), not_duplicate. A gate failure is a
      separate status from a rejection — mixing "this came back broken" with
      "I do not like it" would poison the only real signal this kind has.
- [x] Failed candidates are **stored, not dropped**: "this generator returns the
      wrong ratio four times in five" is worth knowing, and a discarded
      candidate cannot say it.
- [x] **No image library.** Reading a width and a height is a header parse —
      PNG IHDR, JPEG start-of-frame walk, GIF, three WebP variants — so Pillow
      was not added to decode two integers. Fails closed on an unknown format,
      because a zero would silently pass a dimension check.
- [x] **Everything protective is inherited.** Generation goes through
      `EgressBroker.call_image`: same tier filter, same allowlist payload, same
      blocking scanner, same egress log. A structural test asserts `imagery/`
      imports no transport.
- [x] The kind gate now runs from **both sides** — `OutreachEngine` refuses an
      image campaign and `ImageCampaignEngine` refuses an email one.
- [x] Own database (`imagery.db`), three tables, and **pictures are files** at
      `0600` with the row holding a path and a hash. Same decision the egress log
      made when it chose to record the prompt and never the picture.
- [x] Seven API endpoints, and an **Image review** screen: one candidate at a
      time, three buttons, arrow-key shortcuts. One at a time rather than a grid
      because a grid invites picking a favourite and ignoring the rest, and
      "ignored" is not a label.
- [x] 22 new tests. Verified over HTTP end to end: an image campaign can now be
      created, the email runner refuses it by name, and generation with no image
      model connected fails with "Open Connectors and add one".

#### Still missing on this kind (recorded on the spec, not hidden)
- Video — the gates read image headers; duration, frame rate and audio are a
  different piece of work, and claiming video without them would claim a
  benchmark that does not exist.
- Publishing — an approved picture is an asset; posting it is the distribution
  campaign, which has its own credentials and per-platform rules.
- Layer three of the benchmark (views, watch time) needs distribution to exist.
- Brief authoring in the UI, and prompt improvement between rounds.

### Error classification (2026-08-10)
- [x] `ai/failures.py` + wiring in `ai/broker.py`. Docs:
      `docs/architecture/FAILURES.md`. The item deferred pending reading; the
      reading was of the codebase, and it changed the design twice.
- [x] **What it did before:** every provider failure treated identically —
      record, fail over, cool the model off after two. Right for a provider
      having a bad day, wrong for most of the rest.
- [x] **Three failures that cost money.** A rejected key failed over silently to
      a model that worked, so nobody found out while every call ran on a model
      the owner had not chosen. A payload *we* built wrong was tried against
      every provider in the tier and opened the circuit breaker on each. A 429
      fell through to a second provider's quota instead of waiting.
- [x] Four actions, and the classes exist only to choose between them:
      `RETRY_SAME`, `FAILOVER`, `STOP_REQUEST`, `STOP_CONFIG`. Both stops refuse
      to fail over, which is the point of them.
- [x] **Only provider-health failures open the circuit breaker.** A 400 says
      nothing about their service; letting it trip the breaker is how one
      malformed payload takes a whole tier offline.
- [x] **`unknown` fails over once and never retries** — default-deny applied to
      spending, and it lands in the log so the gap shows up there not in a bill.
- [x] **Reading the code changed the plan.** `outreach/providers.py` already
      retries three times for connection errors, 429 and 5xx, so no second retry
      loop was added: nine attempts at one model is a stuck request, not
      resilience. `RETRY_SAME` covers only what the transport does not, bounded
      by 2 retries and a **120s wall clock over the whole chain** — attempts,
      retries and failover share one deadline, and exceeding it is reported as
      `deadline_exceeded` rather than hidden.
- [x] `Retry-After` honoured when sent, capped at 300s.
- [x] `ProviderFailure` -> **502** carrying the kind, action and owner action.
      502 not 503: the upstream answered definitely and off_CRM chose not to
      route around it, so "try again later" would be the wrong advice.
- [x] `failure_kind` recorded in the egress log and grouped by
      `GET /ai/egress-log/stats`. This is the payoff: "NVIDIA has been returning
      auth errors for a week" is answerable with a kind column and not with a
      pile of 500-character strings.
- [x] **The log's first migration**, additive on both backends via the new
      `Database.add_column_if_missing` — which also closes one of the gaps the
      Postgres doc listed. Verified against a log built without the column:
      rows survive, the column appears.
- [x] `GET /ai/failure-kinds` serves the taxonomy so the inspector need not
      hard-code it.
- [x] 34 new tests.

#### Bugs found while building it
- [x] **`refus` matched "Connection refused".** The first content-filter pattern
      filed a dead network as a content filter, so off_CRM would have failed
      over politely instead of reporting nothing could be reached. Patterns on
      an error path are exercised by text nobody chose. A test pins the pair.
- [x] **A stray backspace character was written into that regex** by a patch
      script whose replacement string was not raw, so the word-boundary escape
      became a literal control character and the alternative could never match.
      Found by tracing which pattern fired, not by reading the file — the
      character is invisible. The package and test tree were scanned; it was the
      only occurrence.
- [x] `quota.record(rate_limited=...)` was a substring search for `"429"` over
      the message, which also fired on a body that merely contained those
      digits. Now driven by the classification.
- [x] A test of mine asserted failover between `mistral` (tier A) and `nvidia`
      (tier B) and got one candidate. That was the **failover-never-crosses-a-
      tier rule working**; the test was wrong and now uses two US providers.

### Response cache wired (2026-08-10)
- [x] The gap the rebuild-guide audit found is closed: `ResponseCache` is now
      constructed in `api/app.py` and passed to `EgressBroker`. Before this it
      was implemented, tested and exported with **no caller**, so no request had
      ever reached it.
- [x] **Switching it on surfaced a real defect first.** At `pseudonymous`
      policy a payload carries no name — everyone is `PERSON_1` — so two
      different prospects with the same title, category and an equivalent public
      hook build a **byte-identical** payload. Measured: two logistics directors
      who both "opened a new depot" score **1.000**, an exact hit. Wiring the
      cache as it stood would have sent both of them the same email body, which
      is the opposite of the product and exactly what spam filters cluster on.
      The 0.92 near-match threshold is no defence, because this is not a near
      match.
- [x] Fixed with an allowlist rather than a patch: **cache work whose output is
      a fact, never work whose output is a message.** `CACHEABLE_TASK_TYPES`
      holds `classify_reply`, `summarise`, `extract`, `enrich`,
      `orchestrator_plan`, `ai_chat`. An unlisted task type is not cached —
      default-deny, as everywhere else.
- [x] `NEVER_CACHE_TASK_TYPES` names `draft_email`, `template_rewrite` and
      `image_generation` **with the reason for each**, so the refusals are
      documented rather than merely absent. A test asserts every one carries a
      reason; refusals without reasons get "fixed" by the next reader.
- [x] Both axes checked independently: a never-cache data class wins even for an
      allowlisted task type.
- [x] **Evals never use the cache**, now explicitly `cache=None` with the reason
      in the source. An eval exists to measure a model; a cached answer makes it
      measure the cache, and those numbers feed a promotion decision. A test
      asserts the source still says so — the risk is someone "fixing" the
      missing cache later as an oversight.
- [x] `GET /ai/cache/stats` reports the hit rate **with** the allowlist and the
      named refusals; `POST /ai/cache/clear` empties a workspace. The published
      60–90% figures come from chat systems and do not apply to personalised
      outreach, so the only honest answer is a measured one.
- [x] Verified live: the app boots, `ai_cache.db` is created, and the stats
      endpoint serves the allowlist.
- [x] 14 new tests (48 in `test_ai_cache.py`). The existing suite had been
      written against "cache everything" and used `draft_email` throughout; it
      now uses a cacheable task type, and drafting has its own test that asserts
      the two-prospect payload collision and that nothing is stored or served.

### Rebuild guide, §10 (2026-08-10)
- [x] `docs/architecture/REBUILD_GUIDE.md`. Written **after** the system,
      describing what exists rather than specifying what should. Says so at the
      top: where the code and the guide disagree, the guide has the bug.
- [x] The abandoned `agent/off-crm-v0-12-ai-studio` branch had a 1,015-line
      rebuild guide. It was **not** reused: it describes `off_ai/`, a parallel
      module that was never merged. A rebuild guide for a system that is not
      there is the worst version of this document.
- [x] The content that lives nowhere else: **stage order with the reason each
      stage must come before the next**. Three orderings carry the security
      properties — scanner before any provider adapter (or the direct call site
      you made to test it survives as a second door); construction before
      everything (filtering is a one-way door); eval harness before the verify
      loop (or the loop invents weaker checks and measurement quietly disagrees
      with enforcement).
- [x] **15 traps**, each a real mistake, most of them made and fixed here. They
      share a shape: every one looks like a simplification and silently removes
      a guarantee.
- [x] The architecture rules that are enforced by AST tests rather than by
      discipline, listed with what enforces each. Includes the doubled-test
      pattern from campaign kinds: a list that must stay exhaustive needs a
      second test that checks the list itself.

#### Facts corrected while writing it
Every number in the guide was measured rather than recalled, and four claims
written from memory were wrong:
- [x] `ai/` is 24 modules / 10,303 lines; the package root has 24 more, not 15.
- [x] The single-gate test does not assert "three call sites". It parses every
      file in the package and fails if any module outside a **three-file
      allowlist** imports a provider constructor. Different rule, stronger.
- [x] Six named SQLite databases, not seven — and only four are opened by the
      web app; `ai_evals.db` and `ai_tools.db` belong to their CLIs.
- [x] **The response cache is not wired into anything.** `ResponseCache` is
      implemented, tested (34 cases) and exported, and `EgressBroker` accepts
      one as an optional argument — but no caller constructs one, so no request
      has ever hit it. Recorded in the guide so a rebuilder does not hunt for
      wiring that does not exist. Left unwired rather than switched on in the
      same change as a documentation task.

#### Fixed while writing it
- [x] `db/copy.py` imported `ai/log.py` for its schema — the generic backend
      layer knowing about one specific store, and the reverse of the dependency
      rule the guide states. Writing the rule down is what exposed it. `db/`
      now has a table-agnostic `copy_table(table, columns, schema, key)`, and
      the egress-log wrapper lives in `ai/log.py` where its schema is defined.

### Postgres backend, egress log first (2026-08-10)
- [x] `offsetx_apollo_builder/db/` — ~250 lines. `open_database()` returns
      something that behaves like the `sqlite3.Connection` the stores already
      use: same `execute` / `executescript` / `transaction`, same `row["col"]`
      and `dict(row)`. Docs: `docs/architecture/POSTGRES.md`.
- [x] **No ORM.** SQLAlchemy would have replaced auditable SQL with expression
      trees in a codebase whose security argument depends on reading the
      queries, for a much larger diff and the same result.
- [x] `?` → `%s` translation in `db/translate.py`, as a **character walker, not
      a regex**: both `?` and `%` occur inside string literals, and a blind
      replace corrupts data invisibly until someone reads the row back. Handles
      `'it''s'` (a doubled quote is an escape, not the end of the string) and
      doubles literal `%`, which psycopg treats as a placeholder marker.
      `outreach/store.py` alone has 449 `?`, so rewriting them was never the
      option.
- [x] Postgres runs in **autocommit** to match SQLite's `isolation_level=None`.
      The stores expect a statement to be durable when it returns; psycopg's
      default open transaction block would have changed that contract silently.
- [x] **The egress log is the store that moved, because it is the one broken in
      the deployed environment today.** §6.4: on Render `OFFSETX_DATA_DIR` is
      `/tmp`, wiped every restart. Everything else there is an inconvenience to
      lose; the audit trail is a hole in the argument — a verification trail
      that resets verifies nothing. It also has no foreign keys into the CRM.
- [x] **A bug the second engine found.** `EgressLog.stats()` selected
      `provider_name` and `jurisdiction` while grouping only by `provider_id`.
      SQLite runs that and picks an arbitrary row; Postgres refuses it. Now
      grouped on all three, which is also the answer that was meant.
- [x] `offsetx-db check` and `offsetx-db copy-log`. The copy never deletes the
      source, is idempotent by primary key, counts both sides and reports, uses
      an explicit column list (a test fails if it drifts from the schema), and
      masks passwords in everything it prints.
- [x] Only an explicit `postgresql://` / `postgres://` / `psql://` scheme means
      Postgres; everything else is a path, so a mistyped DSN fails loudly rather
      than silently creating an empty SQLite file that looks like it worked.
- [x] Resolution order is explicit → `OFFSETX_DATABASE_URL` → default path. The
      middle rung lets a deployment set one variable; the top rung keeps a
      test's scratch file safe from the environment reaching in.
- [x] Missing psycopg raises a sentence containing the install command, not
      `No module named 'psycopg'`.
- [x] Log tests are **parametrised over both backends**, 35 of them. The
      Postgres half skips with a reason unless `OFF_CRM_TEST_POSTGRES_URL` is
      set — same rule as the live Docker test.
- [x] Verified end to end against a real Postgres 16: the app boots with the log
      on the server, `GET /ai/egress-log/stats` reports `"backend": "postgres"`,
      no `ai_egress.db` appears in the data directory, and the CRM keeps working
      on SQLite in the same process.

### Campaign kinds (2026-08-10)
- [x] `campaigns` gained `kind TEXT NOT NULL DEFAULT 'email'`, schema v8.
      Registry in `offsetx_apollo_builder/campaigns.py` — **package root, not
      inside `outreach/`**, because the registry is above the email runner
      rather than part of it. Docs: `docs/architecture/CAMPAIGN_KINDS.md`.
- [x] **The migration was the easy half.** Every pre-existing row was an email
      campaign because nothing else existed, so the column default backfills
      them and there is no data migration to get wrong. The hard half is the
      code written when email was the only possibility.
- [x] **The gate.** `OutreachEngine._require_own_kind` refuses a campaign of
      another kind at all nine entry points that act on one: `import_contacts`,
      `generate_drafts`, `edit_draft`, `bulk_replace_drafts`, `schedule_drafts`,
      `approve_drafts`, `sync_replies`, `run_due`, `export_crm`. Without it the
      first image campaign would be handed to the mail sender.
- [x] Two tests keep that list honest: one asserts each listed method contains
      the check, and one walks every public method taking a `campaign_id` and
      fails if any is missing from the list. Without the second, the first
      quietly stops being exhaustive the day someone adds a method.
- [x] `run_due` is checked **before** it syncs replies, with a test whose mail
      provider raises if touched — a refusal after the mailbox has been read has
      already done the thing it was meant to prevent.
- [x] Three kinds declared, one implemented. `image` and `distribution` refuse
      at creation with **what is missing**, rather than being omitted. The
      failure mode of a bare `kind` column is a database of campaigns nothing
      will ever run; a refusal at creation is the alternative to discovering
      that a week later.
- [x] **Absent means email, wrong means stop.** A missing value is a row written
      before the column; a present unrecognised value raises. Falling back to
      email there would hand an unknown campaign to the mail sender.
- [x] `kind` is fixed at creation — `update_campaign` refuses a change rather
      than dropping it through the allowlist, because the campaign's contacts,
      drafts and messages were all made under the original kind.
- [x] The index over the new column is applied **after** the migration
      (`POST_MIGRATION_SQL`): on an existing database `CREATE TABLE IF NOT
      EXISTS` is a no-op, so an index over a brand-new column in `SCHEMA_SQL`
      would be asked for before `ALTER TABLE` added it and every upgrade would
      fail on startup.
- [x] Surfaced end to end: `GET /api/v1/campaign-kinds`, `kind` on create and as
      a list filter, `offsetx-outreach campaign-kinds`, and a picker in the
      Campaigns screen that shows unbuilt kinds greyed with their reason and
      hides the email-shaped fields when one is selected.
- [x] **Settings blob deliberately not built.** Email's settings are real
      validated columns and no other kind can be created, so `settings_json`
      today would be an unvalidated blob with no writer. The column is additive
      and costs the same later; the validator is what has to come first.

### Code graph (§4K, 2026-08-10)
- [x] `codegraph.py` + `offsetx-codegraph` (`policy`, `build`, `status`,
      `verify`, `ignore`). Docs: `docs/architecture/CODE_GRAPH.md`.
- [x] Wraps Graphify (`graphifyy==0.9.39`, pinned, run via `uvx` so it never
      enters the project venv). 7 seconds for this repo: 3,047 nodes, 7,935
      edges.
- [x] **The reason it is a module and not a shell command:** `graphify extract`
      is, in its own help, "AST + **semantic LLM**" — it finds an API key and
      posts chunks of source to gemini/openai/deepseek/claude/kimi/ollama.
      `--code-only` makes it "local AST, no API key". Two flags separate a build
      step from an egress event. The previous attempt put them in
      `scripts/build_code_graph.ps1`: PowerShell only, and editable.
- [x] `--code-only` is not a parameter of `extract_command()`. A keyword
      argument would put the unsafe call one keystroke away.
- [x] Seven refusals, each with its reason: the semantic path, `label`,
      `add <url>`, `--global` (merges into a shared file in `$HOME`), the
      `install` subcommands (they write to AGENTS.md and install git hooks),
      `--no-gitignore`, `--postgres`.
- [x] **Verified, not asserted.** After every build the graph is read back and
      **deleted** if any indexed file lives under a runtime-data path. Kept-with-
      a-warning is not an option: someone queries it anyway because the file is
      there.
- [x] `.graphifyignore` is generated from `RUNTIME_DATA_PATHS` in code,
      overwriting hand edits, and a test cross-references that list against
      `api/config.py` so the two cannot drift.
- [x] **Live probe run, three ways** (recorded in the doc): a planted
      `local_data/leak_probe.py` is excluded by `.gitignore` alone (0 nodes) and
      by `.graphifyignore` alone (0 nodes); with **both** bypassed it leaks 2
      nodes and the verifier rejects the graph by name. Each layer holds
      independently and the backstop fires when both are cut.
- [x] Staleness: `graph.json` records `built_at_commit`; `status` compares it to
      HEAD. A graph recording no commit is treated as stale.
- [x] `graphify-out/` gitignored — build artefact plus a 4.6 MB cache, rebuilt
      in seconds.

### Fixed defects found during the audit
- [x] **AI chat leaked.** It passed the raw conversation to a provider with no
      policy applied, while its own docstring claimed the opposite. Chat now
      goes through the broker. `ai_chat.py` no longer imports any transport, and
      a test asserts it never will again.
- [x] **Scanner newline bug.** Patterns ran against a JSON dump, which escapes
      `\n` and silently disabled every `^`-anchored mail-header rule — the
      payload looked clean exactly when it held a pasted email. Patterns now run
      against raw string values.
- [x] Removed `frontend/src/providerCatalog.ts`, which hardcoded providers in
      TypeScript and recommended DeepSeek for "bulk email generation".

---

### Public discovery frontier — S-05.01.01 (2026-09-18, IN_REVIEW)

- [x] The old per-run `deque` is gone from the production discovery path.
- [x] `crawler_frontier.sqlite3` persists URL, depth, content hash, last
      crawl/change, next due time, counters, last error and a short claim lease.
- [x] Changed pages are due after one day; unchanged pages back off by observed
      stability up to 30 days; failures back off separately up to one day.
- [x] Claims are transactional and leased, so two processes sharing the file do
      not intentionally take the same due URL. A dead worker's lease expires.
- [x] Every seed/link still goes through the existing public URL policy before
      persistence. Session-gated social domains lose even if mistakenly present
      in an allow-list.
- [x] Existing SafePublicFetcher/Crawl4AI robots, crawl-delay, SSRF, redirect and
      size controls are reused rather than copied.
- [x] Seven focused tests cover robots + crawl delay, adaptive revisit cadence,
      restart/budget persistence, concurrent claim exclusion, stale-policy
      revalidation without queue starvation, the social boundary and shared
      cross-process host pacing.
- [x] CHECK-mode cold review on 2026-09-23 found and fixed D-71:
      a persisted URL rejected by the current policy could repeatedly consume
      the claim limit and starve valid due work behind it. The regression test
      is committed; no public interface or schema changed.
- [ ] Locked repository test evidence is still missing. GitHub Actions runs 584
      and 590 failed before creating a workflow step and expose no job log.
      Under the Definition of Done this is IN_REVIEW, not DONE.


### CI evidence infrastructure — S-06.02.18 (2026-09-23, BLOCKED)

- [x] Workflow source reviewed: the `quality` job targets standard
      `ubuntu-latest`; step 1 is `actions/checkout@v4`.
- [x] Current head re-run attempted. Run 1205 / 35779093017, attempt 2,
      created job 106939339831 and failed before runner allocation.
- [x] Jobs API evidence: `steps = null`, `logs_url = null`; no repository
      command executed.
- [x] Application/test changes are not a valid fix for a failure that occurs
      before step 1.
- [ ] Owner-side Actions billing/budget/payment and repository Actions policy
      must be checked. If clean, GitHub Support must investigate hosted-runner
      provisioning.
- [ ] After runner capacity is restored, execute the locked closure chain:
      S-05.01.01 → S-05.01.02 → S-05.01.03.

### Reports and artifacts — S-07.01.04 (2026-09-18, IN_REVIEW)

- [x] Existing verified trace findings are the only content source. Artifact
      generation has no broker/provider/model route.
- [x] XLSX uses the installed openpyxl dependency, includes Findings + Trace
      sheets and internally hyperlinks every claim to its exact trace-step row.
- [x] Spreadsheet formula prefixes from hostile page text are forced to literal
      strings; invalid XML control characters are normalised before writing.
- [x] PPTX is a small standard-library OOXML package: title slide plus one slide
      per finding, with value, quote, source URL, capture time and trace step.
      No macros or external relationships.
- [x] PDF reuses the already-hardened offline HTML report and prints it through
      installed Chromium with a temporary empty profile and background networking
      disabled. No second PDF renderer or dependency.
- [x] Broken provenance fails closed before an artifact is written.
- [x] `offsetx-artifacts` exposes XLSX, PPTX, PDF and all locally.
- [x] Ten focused tests cover format structure, trace linkage, hostile text,
      output privacy, PDF browser contract, CLI behaviour and the no-AI rule.
- [ ] Locked executable evidence is pending. GitHub Actions is still creating
      failed quality jobs with zero workflow steps, so this story cannot be
      called DONE until the test command and board verifier actually run.
- [x] D-102 (D-51 on its branch) was caught before review: a scripted metadata edit wrote a literal
      `\\n` into `pyproject.toml`; the committed file was re-read and fixed.
- [x] Supplemental format probe: the exact PPTX package shape opened in
      LibreOffice Impress and converted to PDF successfully.
- [ ] Live PDF rendering is not certified in this container. Root Chromium
      correctly refuses to run with its sandbox; a non-root probe did not
      complete here. No `--no-sandbox` weakening was added to make the probe
      pass.

## 4. Not built yet

Listed honestly. Nothing below is silently assumed done.

| § | Item | Note |
|---|---|---|
| 4D | Two-mode campaign intake | **Built** (`intake.py`). Generate/Parse split, plus PDF reading. Deliberately outside `ai/` — a contact list must never reach a model. Remaining: no UI screen, and generate mode is the brief object only; wiring it to discovery is separate. |
| 4G | NotebookLM export | **Built** (`notebook.py`, `offsetx-notebook`). Remaining: no API endpoint and no UI screen — and the web shape has a real problem to solve first, since a zip download would put the identity key back inside the folder the owner uploads. Two separate downloads is probably the answer and needs deciding, not defaulting. No scheduled re-export. |
| 4H | Bandit / automatic traffic shifting | **Built** (`ai/bandit.py`, `context.traffic_split`). Decides *how much* traffic each approved variant gets; still never decides *whether* a rewrite goes live — that stays with the owner per §3. |
| 4J | Bring-your-own tools, sandboxed | **Built.** Isolation in `ai/sandbox.py`, registry in `ai/tools.py`, CLI `offsetx-tools`. §5.12(c) covered. Remaining: no model-facing path yet (nothing hands the catalogue to a model or lets a plan call a tool — deliberate), no UI screen, and the container flags still need one live run against a real daemon. |
| 4K | Graphify code graph | **Built** (`codegraph.py`, `offsetx-codegraph`). Remaining: no CI job, no automatic rebuild on commit (Graphify's git hooks are on the refused list), and nothing inside off_CRM reads the graph — handing a model a map of the codebase is a separate decision. |
| — | Campaign `kind` column | **Built** (`campaigns.py`, schema v8). Remaining: no `settings_json` blob — deliberately deferred until there is a kind whose settings are known, since a validator has to exist before the blob does. |
| — | Postgres | **Partly done.** The seam is built and tested (`db/`). On either backend now: the egress log, video, GTM, keys, settings and logins (`S-06.03.02`), and the **CRM with its sales tables** (`S-06.03.03`). Still SQLite-only: context, recall, scoreboard, cache — `S-06.03.06` decides each. Migrations: a schema version per store in `offcrm_schema` (`db/schema.py`), the CRM's under `crm`. Still missing: FTS (`fts5` → `tsvector` is a reimplementation; expert search is unranked on PostgreSQL) and connection pooling. |
| E-12 | GTM engine, the rest | Phase 1 and 2 are built (section 3). Remaining, each with a backlog id: the video director reading the product (`S-12.01.03`), the expert corpus (`S-12.02.05`), posting from the screens (`S-12.02.06`), video in the email (`F-12.03`), driving external GTM tools (`F-12.04`), audience → Apollo search (`F-12.05`). |
| 10 | Rebuild guide | **Written** — `docs/architecture/REBUILD_GUIDE.md`. Stage order with the reason each stage must precede the next, the 15 traps, the invariants that are enforced by AST tests, and what is deliberately absent. |

---

## 5. Decisions and why

1. **`full` policy kept as a user choice.** The brief said addresses never leave;
   the owner overrode that and asked to keep the freedom. Implemented as: full
   is available on any tier, but above a tier's ceiling it needs an override
   with a written reason, stored with who decided and when. Never silent, never
   a default, never reached by failover.
2. **Chinese providers stay enabled and useful — but pseudonymously.**
   *Superseded 2026-07-31.* The original decision gave tier C the person's real
   public name, company and title. The owner then identified client and POI
   identity as the business secret, which contradicts it. Resolved by adding a
   `pseudonymous` policy between `strict` and `minimal` and lowering tier C's
   ceiling to it: a restricted provider still receives the job title, category
   and public hook — enough to write something specific — but the person and
   company arrive as `PERSON_1` and `COMPANY_1`, and owner-typed free text is
   scrubbed of the name as well. off_CRM re-attaches the real values locally,
   the same way it already does for addresses. `minimal` is unchanged for tiers
   A and B. Tier C is still useful for public and coding work at full detail.
3. **Google demoted to C.** Acceptable jurisdiction, but free-tier terms permit
   training on input. If billing moves to paid, re-verify and pin `trust_tier: B`
   with a note.
4. **SQLite kept.** Swapping the 2,221-line store to Postgres mid-hardening
   would have risked 88 passing tests for no security gain. Flagged above.
5. **Per-workspace, not global.** Multi-user from the start: one colleague
   raising a provider cannot change what another's calls send.
6. **Log payloads on by default.** The older audit defaulted to off, which meant
   it could only report "42 characters were sent" — useless for the question the
   owner actually has. Bounded at 20k rows.

---

## 6. Open questions for the owner

1. **Recall coverage** — the index covers sent mail. Whether attachments and
   older archives outside off_CRM should be pulled in is an owner decision.
2. **Orchestrator** — confirm the §7 reversal, and which model is the head.
2b. **Tier C and person identity — resolved 2026-07-31.** Pseudonymised; see
   §5.2. Open sub-question: whether `PERSON_1` / `COMPANY_1` should become
   stable *across* jobs for the same contact, so a model could in principle
   recognise a returning prospect. Today they are constant per payload, which
   means no mapping table exists and there is nothing to leak. Making them
   durable would need a stored mapping and is a real trade — flagged, not built.
   *Partly answered 2026-08-10:* the notebook export needs distinct tokens
   within one bundle or the export says nothing, so it numbers `PERSON_1..n`
   **per bundle** and writes the mapping to a file outside the uploaded folder.
   That is a stored mapping, but a local one with a single obvious owner. If
   cross-job stability is ever wanted, that file is the shape it should take —
   not a column on `contacts`.
3. **Positioning line** — set per workspace in Connectors; no default shipped.
4. **Render deployment** — `render.yaml` deploys `branch: main` with
   `autoDeploy: true`, so nothing ships until this branch is merged there.
   Two things to set up before the first deploy:
   - *(Superseded 2026-09-25, `DD-64`: keys are typed in the app only. The
     environment fallback this line described handed the owner's key to every
     workspace login (`D-151`) and is gone; keys surviving a deploy is
     `F-06.03`.)*
   - **The egress log lives in the same disposable `/tmp` directory.** It is
     the audit trail, and on Render it resets on every restart. Fine for a
     demo; a real shared deployment needs a Render disk or Postgres.
5. **Postgres** — needed before "millions of users"; say when.

---

## 7. How to verify the wall yourself

```bash
python -m pytest tests/test_ai_egress_wall.py -v   # 30 security cases
python -m pytest tests/test_ai_api.py -v           # 15 API cases
```

Then in the app: **Connectors** → connect a provider → **What was sent** →
Inspect any row. The payload shown is byte-for-byte what left the machine.


---

### Workspace isolation — S-06.01.01 (2026-09-20, IN_REVIEW)

- [x] Replaced the single hard-coded `local` browser-login identity with a
      persistent workspace account store. Passwords are scrypt hashes; signed
      cookies bind username + workspace + expiry + session version.
- [x] Provider keys and browser session vaults remain encrypted and keyed by
      workspace. Password rotation/disable increments session version so old
      cookies stop working.
- [x] Workspace administration requires the install API token. Ordinary
      workspace sessions cannot create or alter another workspace.
- [x] Removed the shared mutable `ai_broker.credential_resolver`. Every request
      now gets a credential-bound broker view; shared quota/cache/log/circuit
      state remains shared without sharing credentials.
- [x] Backup/privacy coverage now includes workspace auth and encrypted workspace
      AI state.
- [x] Focused regression tests are committed in
      `tests/test_workspace_isolation.py`, including concurrent credential
      isolation.
- [ ] Executable locked test/full-regression/verifier evidence is not available
      on this branch head yet, so the story stays IN_REVIEW.

### Agent routines — S-06.01.04 (2026-09-20, IN_REVIEW)

- [x] Durable interval and event declarations persist in
      `agent_routines.db`; duplicate scheduler/event deliveries are claimed
      transactionally.
- [x] Creation checks `check_navigation(..., unattended=True)`, so an
      attended-only target is refused before it can be scheduled.
- [x] Routine browser use is serialized per workspace with a renewable
      cross-process lease and named Docker containers are explicitly removed.
- [x] A routine notification requires the existing AgentRun provenance system
      to return a verified `notification` finding. Plain model prose such as
      “No updates found” cannot create a notification.
- [x] Routine state participates in encrypted backup and subject-access/deletion.
- [x] Focused acceptance tests are committed in `tests/test_agent_routines.py`.
- [ ] Executable locked test/full-regression/verifier evidence is still missing;
      story stays IN_REVIEW.

### Prompt secret boundary — S-06.02.01 (2026-09-20, IN_REVIEW)

- [x] Audit found a real bypass: `system_prompt` was provider-visible but was
      outside `scan_payload`. Transcription filename/media type/language were
      also outside the scanned payload object.
- [x] Added `scan_model_input`, which scans the constructed payload plus every
      separately transmitted model/provider-visible text field.
- [x] Text, image and transcription broker paths all scan before provider
      instantiation/I/O. Transport API keys remain transport credentials and are
      never inserted into model-visible input.
- [x] Adversarial tests plant credential material in payload, system prompt,
      image prompt and transcription metadata and assert the provider is never
      instantiated.
- [ ] Executable locked test/full-regression/verifier evidence is still missing;
      story stays IN_REVIEW.


## 2026-10-13 continuation on develop

Next three areas requested by owner: reliable Git board verification (S-06.02.20), hosted PostgreSQL backups (S-06.03.04), and companion playbooks loaded on demand (S-04.01.02). S-06.02.20 implementation and Git-based tests are in IN_REVIEW after an isolated 3-case test pass; complete repository suite and CI jobs have not executed. S-06.03.04 and S-04.01.02 have scoped work orders and remain BACKLOG, blocked from READY by Q-29/Q-30 and upstream companion review respectively. S-06.02.23 audit stays the only IN_PROGRESS item. All pushes to develop only. See `docs/DEVELOP_NEXT_WORK.md` and `docs/evidence/S-06.02.20-validation.md`.

## 2026-10-13 latest owner-authorised three-story batch
Implemented and pushed on develop: S-06.02.37 skip-link click handler + two route regression cases; S-03.01.03 deny internal literal hosts and noncanonical aliases in browser policy + guard tests; S-05.01.04 Requests DNS-IP-pinned HTTP/HTTPS transport + regression cases. Each is IN_REVIEW; see `docs/evidence/S-06.02.37-validation.md`, `docs/evidence/S-03.01.03-validation.md`, `docs/evidence/S-05.01.04-validation.md`. Full repo tests, real Chromium, Docker firewall and Crawl4AI protections remain open. S-06.02.23 continues IN_PROGRESS. Main unaffected.

## 2026-10-13 owner-selected latest three stories

Active branch: `develop` only. Newly selected: `S-06.02.36` (explicit install-owner login confirmation), `S-06.02.28` (path-aware CLI restore leases with shared local dotenv defaults), `S-06.02.34` (local AI provider usage, classified reporting support, OpenRouter/DeepSeek on-demand balance). Code, tests and work orders were committed for all three. They are **IN_REVIEW, NOT DONE**: full Python/front-end tests, CI, real restore contention and live vendor endpoints were not executed in this environment. Provider response-header quota capture remains unimplemented and must not be described as available. See individual evidence files. The production-audit S-06.02.23 stays the only IN_PROGRESS story; main untouched.
