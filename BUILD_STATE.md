# OFF_CRM build state

Last updated: 2026-07-24

## Current release target

v0.12.0: add OFF_AI Studio as an extractable module inside OFF_CRM.

## Existing systems kept

- Outreach CRM, human draft approval, Gmail/local outbox and reply-stop flow.
- Apollo discovery, exclusion, rejection and credit-control workflows.
- Sales tracker, dashboard and projections from v0.11.
- Encrypted provider-profile storage and the existing provider HTTP adapters.
- Local SQLite remains the current single-user runtime database. PostgreSQL remains the production migration target.

## Duplication audit

- The current outreach provider profiles and HTTP adapters will be reused. OFF_AI Studio will add policy, routing, quota and egress controls around them, not add another credential vault.
- The current campaigns, contacts, drafts, templates, A/B reports and reply flags stay authoritative. AI intake will use a narrow CRM adapter instead of creating parallel campaign tables.
- Existing learning-memory rows stay separate from OFF_AI runtime state. Runtime state records task continuation; learning memory records approved reusable writing guidance.
- Existing discovery and Apollo systems remain responsible for public POI enrichment and exclusion checks.
- The v0.11 worktree contained one truncated `outreach/engine.py`. It was restored byte-for-byte from the verified v0.11 handoff ZIP before this build.

## Module boundary

`offsetx_apollo_builder/off_ai/` owns:

- Projects, conversations and messages.
- Runtime task state and deterministic rolling summaries.
- File inspection jobs and private attachment storage.
- Trust-aware model routing, usage counters and the single provider egress broker.
- Exact egress audit records and exports.
- The narrow adapter that asks the existing CRM to create campaigns and drafts.

The frontend boundary is `frontend/src/pages/AIStudio.tsx`,
`frontend/src/pages/Connections.tsx`, the OFF_AI contracts in
`frontend/src/types.ts`, and the shared layout/design system.

## Hard security decisions

- Models are pure text functions. They receive no tools, database handles, file access, mailbox access, retrieval callbacks or CRM credentials.
- All AI calls go through one broker.
- Payloads are built from allowed fields. Internal objects are never copied and stripped.
- Email addresses are blocked before egress and reattached only inside the CRM.
- Unknown providers are Tier D and receive nothing.
- Tier B receives public, non-personal tasks only.
- Tier C is off by default, may run explicitly enabled public task types only, and never participates in failover.
- Failover stays inside the same trust tier.
- Private mailbox, CRM, sales, context-state and evidence data fail closed.
- Exact outbound payloads are stored locally for the owner to inspect.

## UI decisions

- AI is the first item in the global left navigation.
- The left navigation collapses and reopens independently.
- Chats and projects live in a separate right drawer inside the AI workspace.
- The right drawer collapses and reopens independently.
- Model and task-data controls remain beside the composer.
- On mobile, both side surfaces become overlays and keep visible close controls.

## Provider registry

The encrypted local `provider_profiles.json` remains the config-driven registry. Each profile is extended with jurisdiction, retention, trust tier, host/model origin, checked date, quotas, prices, allowed task types and nominated failovers. Old profiles default to Tier D until the owner reviews them.

## Parked by v4

- Decompose-and-recombine multi-agent orchestration.
- Synthetic-user A/B testing.
- A “will people pay” oracle.
- Graphiti until relationship queries exceed the stated trigger.

## Verification ledger

- Baseline Python syntax: restored and passed before OFF_AI changes.
- OFF_AI domain and zero-access acceptance tests: passed in the full suite.
- Combined backend regression suite: 94 passed and 1 live Docker isolation test skipped because Docker was unavailable on 2026-07-24.
- Runtime Docker network-wall test: explicitly skipped because this workspace
  has no Docker runtime; the test executes a real external connection attempt
  when `OFF_CRM_SANDBOX_TEST_IMAGE` names a pre-pulled pinned image.
- Frontend component tests: 9 passed on 2026-07-24.
- Frontend TypeScript and optimized Vite build: passed on 2026-07-24.
- Python dependency lock check: passed on 2026-07-24.
- Python source distribution and wheel builds: passed on 2026-07-24.
- Live FastAPI readiness and metadata smoke test: passed on 2026-07-24
  against a clean temporary database; runtime reported OFF_CRM v0.12.0 and
  OFF_AI Studio.
- Graphify 0.9.25 source-only refresh: passed against 106 code files with
  1,322 nodes, 3,958 clustered edges, 49 communities, and zero model tokens.

## Remaining work

The frozen implementation is complete. `docs/OFF_AI_REBUILD_GUIDE.md` is the
final authored file, written from this verified state. The only remaining
operation is to produce and verify the clean v0.12 handoff archive.
