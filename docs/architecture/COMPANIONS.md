# S-04.01.01 — Persisted companions

## What a companion is

A companion is a persisted narrowing of capabilities, not another AI engine.

Each row stores:

- name;
- owner-written instructions;
- one exact memory scope;
- owner-granted ToolRegistry ids;
- enabled state and timestamps.

The default memory scope is `companion:<companion-id>`, so two companions do
not share memory accidentally. Global CRM memory is not inherited implicitly;
a companion sees only the exact scope recorded on its profile.

## Storage

Profiles are rows in the existing `ai_tools.db` SQLite database:

```text
agent_companions
```

This deliberately reuses the tool-control database rather than introducing a
JSON store or a second service. SQLite uniqueness constraints protect companion
name and memory-scope ownership per workspace, and transactions handle
concurrent writers.

## Runtime boundary

`CompanionRegistry.start()` resolves the exact context for a run:

1. load the profile inside the authenticated workspace;
2. read approved memory only from that exact memory scope; the CRM memory
   store's normal global+scope merge is explicitly disabled for companion runs;
3. intersect granted tool ids with tools that still exist and are enabled;
4. return only those tools and that memory.

Tool execution checks the grant again in `run_tool()`. Hiding an ungranted tool
from a prompt is not considered authorization.

Disabling or removing a tool takes effect immediately without editing the
companion profile.

## API

Authenticated routes provide list/create/get/update/delete plus runtime-context
inspection and companion-scoped memory creation under `/api/v1/companions`.

The API never accepts a workspace id for these operations. Workspace is derived
from the authenticated request.

## Privacy

Companion names/instructions are registered with the subject-access/deletion
inventory. A matching strong subject identifier is redacted without deleting
unrelated companion profiles. Companion memory already lives in the CRM memory
store and is covered by that adapter.

## Migration and rollback

`CREATE TABLE IF NOT EXISTS agent_companions` is additive inside the existing
tool registry DB. No existing ToolRegistry table is changed.

Rollback may leave the unused table in `ai_tools.db`; old code ignores it.
Removing the table is unnecessary and would make rollback destructive.

## Verification

```bash
uv run pytest tests/test_agent_companions.py tests/test_privacy.py -q
```
