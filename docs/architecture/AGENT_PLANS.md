# Editable run plans · S-02.02.02

`AgentRun.run` creates `PLAN.md` beside the trace before choosing a model. The
file contains the goal and a Markdown checklist. Creation is exclusive, mode
0600, and never overwrites an existing owner plan. The owner can edit the file
with any text editor. Every next decision reads the file again. The run report
renders its checkboxes as a read-only, accessible checklist; regenerate with
`agent.report.write(trace)` to view later edits in an existing report.

PLAN.md replaces the original goal in decision instructions. The original goal
remains in audit metadata. Changing the plan does not grant tools, raise budgets,
change trust tiers or approve a consequential browser operation. Models receive
it only through the existing egress broker; the secret scanner still blocks it.
The model has no filesystem verb and cannot edit the plan.

Plans must contain 1–4500 UTF-8 characters (at most 18000 bytes). This keeps the
owner plan inside the broker's existing 6000-character instruction allowance.
Plan errors stop before the next provider call. Missing files during a run,
symlinks, directories, invalid UTF-8, empty plans and oversized plans are refused.
Keep secrets out of plans; they are local owner instructions, not a secret store.

Resume reuses the same trace directory and plan, including owner changes made
while the process was stopped. Old traces acquire a plan from their recorded goal
on first resume. No database migration is required. Rollback: previous code
ignores the extra file; preserve it before reverting if owner edits are needed.
Local tests cover creation, mid-run edits, resume, safe rendering and secret
blocking through the real broker. Live browser tests require a suitable browser.

Before downgrading the application, stop active runs and preserve their plans and
profile snapshots. Start fresh runs after downgrade. Older versions do not
understand companion grants or owner plan steering, so do not resume new bound
traces on old code. File restore/CRUD rollback is covered by acceptance tests.
