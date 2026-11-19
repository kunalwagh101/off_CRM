# Companion profiles · S-04.01.01

A companion is an owner-created profile with `id`, `name`, `workspace_id`,
`instructions`, `tools` and `memory_scopes`. It is not an independent provider.
The existing AgentRun and its broker, browser policy, review gates and budgets
execute the work. Profiles may grant a subset of the ten existing browser verbs;
empty grants permit decisions and completion, but no model-selected browser act.
Automatic page perception and audit evidence remain host operations.

## Create and select a profile

```python
from pathlib import Path
from offsetx_apollo_builder.agent import (
    AgentRun, Companion, CompanionStore, MemorySnapshot,
)

profiles = CompanionStore(Path('local_data'))
profiles.save(Companion(
    id='scout', name='Scout', workspace_id='local',
    instructions='Read public research and cite the evidence.',
    tools=('goto', 'read', 'scroll', 'back'),
    memory_scopes=('public_research',),
))
selected = profiles.get('local', 'scout')
# broker, settings, page and trace are the existing configured run dependencies.
run = AgentRun(
    broker=broker, settings=settings, page=page, trace=trace,
    companion=selected,
    memory=(MemorySnapshot('local', 'public_research', 'The owner prefers primary sources.'),),
)
outcome = await run.run('Research the public announcement', step_budget=8)
```

Use `profiles.list('local')` to inspect profiles and `profiles.delete('local',
'scout')` to delete one. Saving the same ID atomically replaces the profile for
future runs. Unrelated profiles use different files, so concurrent saves do not
lose one another. Workspace/profile IDs cannot contain paths. Directories are
0700 and profile files are 0600. Invalid, corrupt, swapped and symlink profiles
are refused. Profiles contain instructions, not passwords or provider keys.

## Memory and enforcement

The trusted host supplies explicit MemorySnapshot values. Only snapshots with a
scope in the companion grant enter the outbound decision. Workspace mismatches
are refused before egress. No provider gets a store reference, retrieval tool,
filesystem handle or automatic recall access. Companion runs require INTERNAL
classification, including when a caller requests a lower class. All context goes
through the existing payload builder and scanner; secrets still block the call.

The run refuses an ungranted verb in host code, before dispatch or memo reuse.
Owner plan edits and model output cannot widen the grants. The profile is frozen
and recorded in run-start metadata. Resume requires the identical original
profile; removing, changing or widening it is refused. Keep a run's original
profile snapshot when editing its stored profile. To apply different grants,
start a new run. Deleting a profile does not revoke an already-bound run; browser
session revocation remains a separate control.

Instructions are limited to 1500 characters; snapshots to 1500 each. Combined
companion instructions, plan and permitted memory must fit within 5000 characters
so the broker cannot truncate the control section. Shorten owner context if the
run refuses the limit. The model cannot modify the profile or plan. Memory is
labelled as data, not instructions.

## Storage, verification and rollback

Profiles live at `local_data/companions/<workspace>/<id>.json`. The format is
additive and introduces no database migration. Back up the companions directory
before editing profiles. Rollback: restore a saved JSON profile using `save`, or
remove the new directory after saving any profiles you need. Prior application
versions ignore it. The CRUD and isolation tests execute save/update/delete and
restore behaviour; the resume test executes an interrupted bound run.

Focused evidence is in `tests/test_agent_companions.py`: persistent CRUD,
concurrency, malformed profiles, path/symlink probes, workspace isolation, all ten
verb refusals, scoped memory, internal classification, real broker secret checks,
and unchanged-grant resume. The broader live-browser suite requires an environment
that can launch Chromium and load its local test pages.

Before downgrading the application, stop active runs and preserve their plans and
profile snapshots. Start fresh runs after downgrade. Older versions do not
understand companion grants or owner plan steering, so do not resume new bound
traces on old code. File restore/CRUD rollback is covered by acceptance tests.
