# Where everything stands

**Current implementation snapshot: 2026-09-23, branch `develop`.**

This is a readable summary. `BOARD.md` is the source of truth and
`uv run python scripts/verify_board.py` is the independent delivery check.
Implementation in IN_REVIEW is not DONE evidence.

## Current flow

| State | Count | Meaning |
|---|---:|---|
| DONE | 61 | built, tested, evidence recorded and re-runnable |
| IN_PROGRESS | 0 | nothing is being built right now |
| IN_REVIEW | 16 | code and passing tests exist; an independent review (and for some, an owner pass) is pending |
| READY | 3 | work orders written; an implementer can pull them now |
| BACKLOG | 15 | written down, not started |
| BLOCKED | 6 | waiting on something only the owner or an outside party can do: the old branches' deletion (`S-06.02.19`), a decision (`Q-27`), CI runners, YouTube, platform reviews |

Recompute with `uv run python scripts/verify_board.py`.

## One branch now: `develop` (2026-09-23)

All built work is on `develop`; `main` is promoted from it after checking.
Both deploy to Render — `off-crm-develop` and `off-crm-demo` — on the free plan,
**so data on either is wiped at every restart and deploy** until the owner
decides to pay for a disk (`OPEN_QUESTIONS.md` Q-26). `docs/BRANCHING.md` has
the workflow and where every old branch went.

**One step is the owner's.** The 45 old branches are still on GitHub: this
session was refused (HTTP 403) when it tried to tag and delete them. From a
clone with push rights, `bash scripts/archive_old_branches.sh --delete` keeps
each as an `archive/<branch>` tag, checks it, then deletes the branch. Nothing
is lost meanwhile.

**A cold review of `develop` found ten defects, all fixed with tests**
(`D-124`–`D-133`). The worst: any workspace login could download the whole
install's backup — its admin token included — or restore over it; and one
workspace could read another's private product through drafts. Both are closed.
It also filed two: the CLIs ignore the restore lease (`S-06.02.24`), and CRM
rows belong to no workspace — whether they should is the owner's call
(`Q-27`).

The consolidation found that the newest line had never run its own tests: 33
failed and 5 test files could not load. All are fixed at their cause and logged
(`D-103`–`D-123`). Two older pieces of built work were missing from it and are
now in: **durable state and safe recovery** (`S-06.02.21` — whole-workspace
backup, a restore that rolls back on failure, readiness that tells the truth,
and a Docker image that builds, which it did not, on `main` either) and
**campaign selection** (`S-06.02.22` — a newly created campaign now stays
selected, so an import cannot land in the wrong one). Both are IN_REVIEW.

The owner explicitly authorised build-ahead under DD-22. That allows complete
implementation batches to accumulate in IN_REVIEW, but it does not allow the
repository to call them DONE ahead of their evidence/dependency chain.

## Newest DONE work: the GTM brain, Phase 1 and 2 (E-12)

| What it does | Story | Proof |
|---|---|---|
| You describe your product once; every writer uses it, and a forbidden claim is caught | S-12.01.01, S-12.01.02 | 53 tests |
| A goal (replies or views) becomes a plan that fits what is actually connected | S-12.02.01 | 50 tests |
| Applying a plan makes **paused** campaigns — nothing imported, spent or sent — and paused now stops posting too | S-12.02.02 | 78 tests |
| A review says what is wrong, in a fixed order: the pipe before the copy | S-12.02.03 | 64 tests |
| A review becomes the next version, which learns the real reply rate | S-12.02.04 | 24 tests |

Honest limits. With no model connected, the brain plans and reviews by rules
and says so. A plan's **posting** channel cannot yet post from the screens
(`D-82`, story `S-12.02.06`): Apply and the review both say this plainly. The
brain judges replies and views only, because nothing links a meeting or a
sign-up back to the campaign that earned it. Design:
`docs/architecture/GTM_ENGINE.md`.

## Build-ahead stories currently in review

### Public discovery and privacy

- S-05.01.01 — durable crawler frontier with shared host pacing;
- S-05.01.02 — declarative extraction packs;
- S-05.01.03 — structure-only competitor teardown;
- S-06.02.04 — inventory-driven subject access/deletion.

The privacy inventory now has **12 named stores**, including companions,
routines, workspace identities and derived meeting transcripts.

### Agent identity, steering and automation

- S-03.02.05 — one browser platform declaration drives identity/policy/budget;
- S-02.02.02 — one editable PLAN.md per run, read before every decision;
- S-04.01.01 — persisted companions with exact memory/tool grants;
- S-06.01.01 — workspace-bound logins, encrypted keys/sessions and immutable
  request-bound AI credentials;
- S-06.01.04 — durable interval/event routines with unattended-policy checks,
  dedupe, workspace browser leases and verified-finding-only notifications;
- S-06.02.01 — every model-visible text channel is secret-scanned before
  provider I/O.

### Security, accessibility and meetings

- S-06.02.02 — the API is private by default; runtime route enumeration proves
  protected routes refuse anonymous requests and validation does not echo
  sensitive bodies;
- S-06.02.05 — shared keyboard/focus/live-region/modal semantics plus recursive
  frontend accessibility contracts;
- S-07.01.03 — localhost browser captures microphone + shared system/tab audio
  without a bot, keeps raw chunks transient, freezes one declared
  transcription provider/model, and persists only derived transcript metadata.

## What is deliberately not claimed

On `develop` the build-ahead stories' tests now run and pass locally — they did
not on the branch they were built on (`D-115`). That is not DONE: each still
needs the review and evidence block the Definition of Done asks for, and CI
cannot yet run them (`D-75`). Meeting transcription also needs a real localhost
browser capture in the owner verification pass, and accessibility needs the
owner's keyboard and screen-reader pass.

Therefore their correct state is **IN_REVIEW**.

## Next work

**The remaining work is written down, not built** (the owner's instruction,
2026-09-23): each open item on `BOARD.md` carries a `work_order:` line naming
the plan to follow. Three are READY: `S-06.02.24`, `S-06.02.25` and
`S-06.02.23`. Three more are planned and can follow: `S-12.01.03`,
`S-12.02.06`, `S-12.02.05`.

First, three things only the owner can do:

- run `bash scripts/archive_old_branches.sh --delete` (above);
- answer `Q-27` — does each workspace get its own campaigns and contacts?
- answer `Q-26` — does `main` get a paid disk before real data goes in?

Then the next useful work, in order:

1. **Review the 16 IN_REVIEW stories** so they can become DONE. They pass their
   tests on `develop`; each still needs its review and evidence block.
   `S-06.02.21` and `S-06.02.22` have had one — its ten findings are fixed — and
   need their real-container and real-browser checks re-run on the fixed code.
2. **`S-06.02.23` — re-check the 7 September production audit on `develop`.**
   Two of its findings are known to be open: the sandbox's `/work` folder
   refuses writes (`D-121`) and a short valid video export is rejected
   (`D-122`). The rest were found on older code and have not been re-run.
3. **`S-06.02.18` — CI runners.** Until GitHub Actions can start a job, nothing
   checks a push automatically.

`S-07.01.04 — Reports and artifacts` (deck, sheet or PDF from verified run
findings) is built and IN_REVIEW.

## Externally blocked

- S-01.05.01 — Google Cloud project + YouTube Data API v3/channel OAuth;
- S-01.05.02 — Meta/TikTok/LinkedIn platform review/partner access;
- S-01.05.03 — engagement readback, downstream of the YouTube connection.

Engineering must not replace these official-platform requirements with browser
automation while calling the result a real publishing integration.

## Dedicated verification pass

```bash
uv sync --extra dev --extra email --locked
npm ci --prefix frontend

# Run the focused commands listed in DEMO.md.
uv run pytest tests/ -q
npm test --prefix frontend
npm run build --prefix frontend
uv run python scripts/verify_board.py
```

The commands and their exit codes are the authority, not historical prose.
