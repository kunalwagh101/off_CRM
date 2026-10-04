# off_CRM — notes for any coding agent

This file is vendor-neutral on purpose. `AGENTS.md` is the convention several
tools now read; nothing in this repository is tied to one AI vendor, and the
product's whole premise is that no single provider is trusted by default.

Nothing here is secret. No application code reads this file, it never enters a
payload, and it can never reach a model provider — it is developer tooling, in
the same category as `.editorconfig`.

---

**You are in `kunalwagh101/off_CRM`.** If you expected a different repository —
say so and stop. Do not report on this one as if it were another.

There is a sibling repo named `email_agent` that is **empty and unused**. If a
session lands there and finds no commits, that is the wrong repo, not a missing
project. The work is here.

**Two branches: `develop` and `main`.** Commit and push to `develop`; `main` is
promoted from it after checking. Do not create other branches.
`docs/BRANCHING.md` has the workflow, the Render services, and where every older
branch went (each is kept as a tag `archive/<branch>` once the owner has run
`scripts/archive_old_branches.sh`, which a cloud session is not allowed to).

---

## Production contract — standing owner instruction (2026-09-05)

off_CRM is a production application for real users. Apply this requirement to
every plan, architecture decision, prompt, implementation, test, deployment,
data flow and user experience. The owner must not need to repeat it.

- Build real capabilities with validated inputs, permission checks, protected
  secrets and accurate user-visible results. No demo-only shortcuts, fake
  success states, placeholder runtime logic or mock integrations presented as
  working features. Test doubles belong in tests and do not prove a live
  integration.
- Protect customer data and audit records across process crashes, restarts and
  deployments. Verify persistence, backup and restoration for the storage the
  feature uses. Temporary storage is only for disposable work.
- Cover the relevant failure, concurrency and recovery paths. Bound retries,
  time and spend where applicable; an uncertain external action must not be
  repeated automatically. Preserve human approval for consequential actions.
- Include actionable errors, secret-safe logs, health checks and a tested
  rollback appropriate to the change. Record unresolved release blockers.
- A feature is complete only when its real supported user path is wired and
  the applicable Definition of Done evidence passes. Distinguish implemented,
  verified, merged and deployed; passing isolated tests is not a release claim.
- Use the simplest maintainable design that meets actual user, data and
  deployment needs. Production quality does not require unnecessary services
  or abstractions.

This instruction supersedes historical demo assumptions in this repository.
Legacy filenames or service names do not permit weaker release standards.
Read `DEFINITION_OF_DONE.md` for the evidence required before calling work done.
*(Written on `agent/production-contract` on 2026-09-05; it reached `develop` at
the branch consolidation of 2026-09-23.)*

---

## Read this before reading code

**`BUILD_STATE.md` is the working record.** It is kept current deliberately so a
new session can recover context without re-reading 47,000 lines. Read it first.
It lists what is built, what is explicitly *not* built, the decisions made and
why, and the open questions for the owner.

Design documents live in `docs/architecture/`.

**What to work on next: `BOARD.md`.** Pull only a READY item; each carries a
`work_order:` line naming the plan to follow, in `docs/work-orders/`.

**Two logs are kept, and both are enforced by `scripts/verify_board.py`:**

- **`DEFECT_LOG.md`** — every bug, security hole and broken connection found,
  in plain English, with the date. Read it before starting: it says what this
  codebase keeps getting wrong, which is usually where the next one is. Add a
  row for anything you find, including in old code, including things you file
  rather than fix.
- **`DECISIONS.md`** — design calls where the obvious thing was *not* done, and
  what that cost. Check it before deciding something; the answer may already be
  there. `OPEN_QUESTIONS.md` is the owner's decisions, which is a different
  file for a different reason.

---

## What this is

A local-first outreach CRM with an AI layer whose governing rule is:

> **Models never pull. off_CRM pushes.**

A model that can *ask* for data has access. A model that can only *receive* a
constructed payload does not.

The AI module is `offsetx_apollo_builder/ai/` — self-contained and extractable.
`ai/broker.py` is the single egress gate: it is the only code in the repository
that may call a provider, and `tests/test_ai_egress_wall.py` fails the build if
that stops being true.

---

## Rules that must not be broken

These are enforced by tests, not by convention. Breaking one fails CI.

1. **One egress gate.** Nothing outside `ai/broker.py`,
   `outreach/providers.py` and `outreach/provider_profiles.py` may import
   `create_provider`. An AST walk over every module checks this.
2. **Build payloads, never strip them.** `ai/payload.py` starts from an empty
   dict and adds only what the resolved policy permits. A field you forget to
   strip is a leak; a field you forget to add is merely missing.
3. **The scanner blocks, it does not redact.** A hit means the builder has a
   bug. Silently cleaning it up would hide that bug forever.
4. **Tier filter runs before cost.** A cheap model must never win a task it is
   not allowed to see.
5. **The mailbox is unreachable.** Received mail never reaches a provider.
   `DataClass.MAILBOX` is in no tier's permitted set by default.
6. **No model may query the context store or the recall index.** No tool, no
   function, no retrieval interface, no provider import.
7. **The sender has no AI.** `outreach/engine.py` and `outreach/automation.py`
   must never import from `ai/`. The runner holds credentials and no judgement;
   the models hold judgement and no credentials.

---

## Commands

Dependencies are installed by the session-start hook in `.claude/hooks/`
(the directory name is the hook runner's, not a statement about which agent is
welcome — any tool can read this file).

```bash
uv sync --extra dev --extra email --extra postgres --locked # what the Docker image ships
uv run ruff check --select E9,F63,F7,F82 .  # broken names and syntax
uv run pytest -q             # 1,400+ tests
uv run pytest tests/test_ai_egress_wall.py -v   # the 34 security cases

cd frontend && npm ci
npm test                     # 115 tests
npm run build                # tsc -b && vite build
```

`requirements.txt` is a **subset** of `pyproject.toml` — it omits `scrapling`.
Install from `pyproject.toml` via `uv sync`, or `tests/test_discovery.py` fails
with a misleading "Scrapling is not installed".

---

## Storage

SQLite is used by the CRM store and most others. The Postgres boundary covers
selected stores; it is not a completed migration of the whole application.
Choose storage from the actual deployment, concurrency, isolation and recovery
requirements.

Everything durable lives under one root, `OFFSETX_DATA_DIR`. A backup is that
whole root plus the CRM database; a restore swaps it under a journal and
reopens every service (`docs/architecture/WP1_OPERATIONS.md`). A new store
belongs under that root, and must be opened in `_open_runtime` and closed in
`RUNTIME_CLOSE_ORDER` — `tests/test_audit_wp1.py` fails if it is not.

**Both Render services run on the free plan with data under `/tmp`, which is
wiped on every restart, deploy and spin-down.** That loses CRM data, encrypted
keys and audit records, and it is a production release blocker until the owner
moves `main` to a paid service with a disk (`OPEN_QUESTIONS.md` Q-26). With
`OFFSETX_PRODUCTION=1` the app refuses to start on `/tmp` at all. The owner's
answer is a hosted PostgreSQL — any host, Render or Neon now, AWS or Azure
later (`DD-66`, `DD-70`): `docs/architecture/HOSTED_STORAGE.md`, feature
`F-06.03`. Phase 1 is built (`S-06.03.02`): with `OFFSETX_DATABASE_URL` and
`OFFSETX_SECRETS_KEY` set, provider keys, AI settings, usage counters, logins
and the egress log live in that database; with `S-06.03.03`, so does the CRM,
for the web app and every command-line tool alike (`data_paths.crm_target`).
Files — media, renders, outboxes, exports — are still on the wiped disk.
`OFFSETX_SECRETS_KEY` is the install's master key, not a provider key.
Provider keys come only from the app — there is no environment-variable
fallback any more (`DD-64`, `D-151`); never tell a user to set one.

---

## Conventions

- Errors are readable sentences with a next step, never a raw status code.
  Every empty state has an action (§4L).
- Adding a provider is a **config edit** in `config/providers.yaml`, never a
  code change.
- Comments explain *why*, especially where a simpler-looking approach was
  rejected for a reason. Match that density — do not add narration.

## Logging — standing owner instruction (2026-10-04)

Every error must be traceable the next day from what the user saw. The owner
should be able to take the words on a screen, or a time, and find the cause.

- **One log line per failure, with an error id.** Any request that fails with
  a 5xx, and every background job, worker cycle or command that fails, writes
  one line: time (UTC), error id, what was being done, the route or command,
  workspace, and the exception with its traceback. The same error id is shown
  on the screen or printed by the command ("Reference: E-7F3A…"), so the user
  can quote it and the line can be found by searching for it.
- **Write to standard output, as JSON lines.** That is what Render keeps and
  shows under Logs. A log *file* under the data folder is wiped with it on the
  free plan (`/tmp`), so a file alone is no record there. A local install also
  writes a rotating file under `OFFSETX_DATA_DIR/logs/`, size-capped.
- **Never log a secret or customer content.** No passwords, keys, tokens,
  cookies, database URLs with credentials, email bodies or prompts. Pass
  anything that may hold one through `db.connection.redact`; log ids and
  counts, not contents. A test proves it for each new log line.
- **Do not log and swallow.** Logging an error is not handling it: the caller
  still gets the readable sentence and next step (Conventions, first rule).
- **New code must log its own failure paths.** A feature is not done while a
  failure in it leaves no line (`DEFINITION_OF_DONE.md`).
- **Errors in the code are `DEFECT_LOG.md`; this is about the running app.**
  The two are different: the log says what happened at 3:12 today, the defect
  log says what was wrong and how it was found.

Built by `S-06.02.38`; until it is DONE, the app does not yet meet this.
