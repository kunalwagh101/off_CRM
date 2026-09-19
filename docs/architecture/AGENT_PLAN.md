# S-02.02.02 — PLAN.md as run memory and steering

## Contract

Every agent trace directory owns exactly one current file:

```text
<run>/PLAN.md
```

`agent/plan.py` creates it when a run starts and never overwrites an existing
owner edit. Legacy trace directories receive one on first resume.

Immediately before every model decision, `AgentRun` reads PLAN.md fresh from
disk. There is deliberately no plan cache. If the file is missing, empty,
oversized, unreadable, non-UTF8 or replaced by a symlink, the run refuses to
continue rather than using stale memory.

## Steering and audit

PLAN.md is mutable steering state. The owner may edit it while the run is
working; the next model decision sees that edit.

The append-only trace remains history. Each decision captures the exact PLAN.md
text that decision saw into the step's private captured-text artefact. This
answers both questions without creating two editable sources of truth:

- "What should the run do now?" → current PLAN.md.
- "What instructions did decision N actually see?" → trace capture.

The original owner goal remains separately present in the decision prompt. Page
content remains explicitly untrusted data and cannot become plan instructions.

## Filesystem safety

Creation is exclusive and does not overwrite. The plan is bounded at 64k
characters and created with private permissions where the filesystem supports
them. A symlink is refused.

## Migration and rollback

No database migration. Existing runs are compatible: first resume creates a
PLAN.md from their original run goal unless a plan already exists.

Rolling code back leaves PLAN.md files beside traces as harmless text files.

## Verification

```bash
uv run pytest tests/test_agent_plan.py tests/test_agent_run.py tests/test_agent_resume.py -q
```
