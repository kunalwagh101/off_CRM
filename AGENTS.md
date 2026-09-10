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

---

## Read this before reading code

**`BUILD_STATE.md` is the working record.** It is kept current deliberately so a
new session can recover context without re-reading 47,000 lines. Read it first.
It lists what is built, what is explicitly *not* built, the decisions made and
why, and the open questions for the owner.

Design documents live in `docs/architecture/`.

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
uv sync --extra dev --extra email --locked # reproducible Python deps, including SES
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

SQLite is used by the CRM store. The Postgres boundary covers selected stores;
it is not a completed migration of the whole application. Choose storage from
the actual deployment, concurrency, isolation and recovery requirements.

The current `render.yaml` points `OFFSETX_DATA_DIR` and `OFFSETX_OUTREACH_DB`
at `/tmp/offsetx/local_data`. That configuration can lose CRM data, encrypted
keys and audit records on restart. It is a production release blocker until
the affected stores use durable storage and restart/restore checks pass.
Environment-provided AI keys do not make CRM data or audit records durable.

---

## Conventions

- Errors are readable sentences with a next step, never a raw status code.
  Every empty state has an action (§4L).
- Adding a provider is a **config edit** in `config/providers.yaml`, never a
  code change.
- Comments explain *why*, especially where a simpler-looking approach was
  rejected for a reason. Match that density — do not add narration.
