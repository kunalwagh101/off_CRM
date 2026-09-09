# Audit Work Package 1 — Durable Customer State and Safe Recovery

This is the first remediation story from the 7 September 2026 production audit.
It is intentionally a story-level delivery: no individual finding is considered
complete until the complete work package passes its acceptance evidence.

## Findings carried by this story

- **A01 / P0 — durable customer state:** the supported production-shaped deployment must not place durable CRM or asset state on an ephemeral filesystem.
- **A02 / P0 — transaction ownership:** concurrent requests must never commit or roll back another request's SQLite transaction.
- **A03 / P1 — safe restore:** a successful or rejected restore must leave every dependent service usable; normal work must not overlap the state swap.
- **A04 / P1 — complete recovery:** the encrypted backup must contain every durable local store, asset and operational secret required to rebuild the workspace, with a versioned manifest and consistent size handling.
- **A17 / P1 — truthful readiness:** `/health/ready` must fail when any required local durable component is unavailable or the runtime is in maintenance/recovery.

## Engineering boundary

The supported topology for this increment remains a single-instance modular
monolith. That is deliberate. A persistent disk plus correct SQLite transaction
ownership is a valid production shape for one company installation and avoids a
premature all-store PostgreSQL rewrite. The deployment must not scale this shape
to multiple web instances while writable SQLite state is shared.

The story does not absorb individual user identity, browser/network safety, AI
spend/cache fixes or workflow defects. Those are later audit work packages.

## Story-level acceptance

The story is DONE only when all of the following are proven together:

1. Production configuration uses durable storage for every local durable path and refuses the known ephemeral production shape.
2. Deterministic interleaved writers cannot roll back each other; concurrent API writes remain durable.
3. A backup is validated before live services are disturbed. Successful and rejected restores leave sales, AI chat, delivery and core CRM routes healthy.
4. A fully populated local workspace can be restored into an empty workspace, including all SQLite stores, generated assets, automation/settings files and the unsubscribe signing key. Rebuildable caches are explicitly identified rather than silently omitted.
5. Backup export and restore use one declared maximum archive size and reject oversized input before unbounded memory growth.
6. Readiness is red during maintenance and when required durable stores/paths cannot be opened or written.
7. Restart/redeploy-shaped tests prove records and assets survive on the configured durable root.
8. Existing Python/frontend suites, board verification and the live audit gates remain green for the scope touched here.

## Evidence rule

A code patch does not close an audit finding. Each finding remains open until its
acceptance test is attached to the story evidence and passes on the final branch
head.
