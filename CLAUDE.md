# off_CRM

**You are in `kunalwagh101/off_CRM`.** If you expected a different repository —
say so and stop. Do not report on this one as if it were another.

There is a sibling repo named `email_agent` that is **empty and unused**. If a
session lands there and finds no commits, that is the wrong repo, not a missing
project. The work is here.

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

Dependencies are installed by `.claude/hooks/session-start.sh` on session start.

```bash
uv sync --extra dev          # python deps (includes scrapling; requirements.txt omits it)
uv run pytest -q             # 264 tests, all passing
uv run pytest tests/test_ai_egress_wall.py -v   # the 34 security cases

cd frontend && npm install
npm test                     # 6 tests
npm run build                # tsc -b && vite build
```

`requirements.txt` is a **subset** of `pyproject.toml` — it omits `scrapling`.
Install from `pyproject.toml` via `uv sync`, or `tests/test_discovery.py` fails
with a misleading "Scrapling is not installed".

---

## Storage

SQLite, behind a boundary in `outreach/store.py`. Postgres is a swap, not a
rewrite, and is not needed until this is a shared multi-user server.

On Render, `OFFSETX_DATA_DIR` points at `/tmp`, which is wiped on restart — so
the encrypted key file does not survive and the egress log resets. Provider keys
come from `OFFSETX_AI_<PROVIDER>_KEY` environment variables there instead.

---

## Conventions

- Errors are readable sentences with a next step, never a raw status code.
  Every empty state has an action (§4L).
- Adding a provider is a **config edit** in `config/providers.yaml`, never a
  code change.
- Comments explain *why*, especially where a simpler-looking approach was
  rejected for a reason. Match that density — do not add narration.
