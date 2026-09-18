# Companions — persisted agent policy over AgentRun

**Story:** S-04.01.01  
**State:** IN REVIEW

A companion is not a second agent runtime. It is a persisted policy object that
is applied to the existing `AgentRun` execution loop.

## Stored profile

Each workspace stores:

- a stable companion id and human-readable name;
- owner instructions;
- exactly one memory scope;
- an explicit subset of the existing browser action vocabulary;
- enabled/disabled state and timestamps.

The store is SQLite/WAL at `companions.db`, names are unique per workspace,
and every lookup/update/delete includes the workspace id.

## Execution boundary

When an `AgentRun` is constructed with a `CompanionRuntime`:

1. the profile workspace must equal `WorkspaceEgressSettings.workspace_id`;
2. a disabled profile refuses before planning;
3. arbitrary owner instructions enter the ordinary `EgressRequest.instructions`
   payload, so the existing broker scanner sees them;
4. approved memory is loaded only from the profile's declared scope and is
   framed as trusted local **data**, not additional instructions;
5. the system prompt contains only host-derived policy and validated action
   names;
6. after the model returns a decision, host code checks the requested browser
   action against the companion grant before `_execute` can touch the page.

The prompt is advisory. The post-decision host check is the security boundary.

## Memory contract

`approved_memory_loader` calls the existing memory backend with all of:

- the current workspace id;
- the profile's exact memory scope;
- `approved_only=True`;
- a bounded row limit.

The loader never performs a broad search and filters afterwards. That matters:
a broad fetch would put data from another scope into process memory even if it
was later removed before the model call.

One run snapshots its loaded memory at start. A later run gets a fresh snapshot.

## Resume contract

The original `run_started` trace stores:

- companion id;
- SHA-256 fingerprint of the execution policy;
- companion name;
- memory scope;
- granted browser actions.

It does **not** store memory contents.

On resume, `replay()` restores the id/fingerprint. `AgentRun` refuses if the
companion is missing or if instructions, memory scope, grants, enabled state, or
workspace changed. A restart can therefore never widen the original run's
authority by omitting or editing the companion.

## API and UI

Authenticated CRUD lives at:

- `GET /api/v1/ai/companions`
- `POST /api/v1/ai/companions`
- `GET /api/v1/ai/companions/{id}`
- `PATCH /api/v1/ai/companions/{id}`
- `DELETE /api/v1/ai/companions/{id}`

The Companions screen exposes name, owner instructions, memory scope, explicit
browser-tool checkboxes, enabled state, edit and delete.

## Deliberate scope boundary

The field is called `granted_tools` in product language, but in this story it
means the existing ten `browser.page.ACTIONS` only. The sandbox tool registry
in `ai/tools.py` is **not** executable from `AgentRun` today. Pretending it is
would create a second, unreviewed execution contract.

Separate stories own:

- skills/procedure retrieval — S-04.01.02;
- child/sub-agent context isolation — S-04.01.03;
- the named Scout/Maker/Poster/Analyst/Director presets — S-04.01.04.

## Verification

Focused evidence:

```bash
uv run pytest tests/test_companions.py tests/test_companion_agent_run.py tests/test_agent_run.py -q
cd frontend && npm test && npm run build
```

Release evidence:

```bash
uv run pytest tests/ -q
uv run python scripts/verify_board.py
```

Do not mark S-04.01.01 DONE until those commands actually execute successfully.
