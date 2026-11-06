# CRM tenancy — campaigns, contacts and drafts that belong to a workspace

**Status: owner authorised implementation; isolation not built yet.** Owner answered Q-27 on2026-11-06: workspace-owned CRM rows, isolate customers. Story S-06.01.06 is BACKLOG under the active production audit. No existing record may be assigned automatically. Defect D-135 remains open. This revision replaces the old auto-assignment rule before implementation.

## Why this exists

Workspaces already own their logins, provider keys, browser sessions, AI
settings and GTM products (`S-06.01.01`, `E-12`). The CRM does not: every login
reads and changes the same campaigns, contacts, drafts and templates. For one
team that is the point. For two unrelated clients on one install it is a leak —
a draft written from one client's private product is readable from the other's
login (`D-135`), and a workspace can link a campaign nobody linked yet.

`D-125` closed the worst path, one workspace *creating* drafts from another's
product, with a per-request caller marker (DD-60). That marker is a patch over
the missing tenancy; this design removes the need for it.

**Reversal cost: irreversible in practice.** It changes the tenancy model and
migrates live rows. That class of decision is the owner's (`Q-27`), and nothing
here is built before it is made.

## The tables (`offsetx_apollo_builder/outreach/schema.py`, 34)

**Roots — each gets a `workspace_id`:**

| Root | Children that inherit it through their foreign key |
|---|---|
| `campaigns` | `campaign_contacts`, `drafts`, `messages`, `campaign_events`, `discovery_runs` → `discovery_candidates` → `research_observations`, `email_campaign_settings`, `email_send_jobs`, `email_delivery_events`, `email_unsubscribe_tokens` |
| `contacts` | reached through `campaign_contacts` |
| `email_templates` | — |
| `memory_items` | — |
| `sales_leads` | `sales_lead_events` |
| `sales_setter_activity`, `sales_monthly_goals` | — |
| `ai_chat_projects` | `ai_chats` → `ai_messages` |
| `research_entities` | `research_edges` (observations also hang off discovery) |
| `email_sending_identities` | `email_rate_state`; referenced by campaign settings and send jobs |
| `email_contact_permissions` | — |
| `idempotency_records` | — (the key becomes workspace + key) |
| `provider_calls` | — (the audit becomes per workspace) |

**Decide first — each a question for the owner once `Q-27` is option 2:**

| Table | Why it is a decision |
|---|---|
| `email_suppressions` | An unsubscribe is from one sender, so per workspace. A hard bounce or a complaint protects the shared sending reputation, so install-wide. Likely answer: both kinds, scoped differently |
| `expert_chunks` | Licensed reference notes may be the install's library, shared read-only, or each client's own |

Children do **not** get their own column. They are reached through their root,
and every store method that takes a child's id joins to the root and checks its
workspace. One column per root is one place to be right. A child copy would be a
second place to be wrong.

## The pieces

1. **Schema and migration.** Each root gains
   an explicit workspace owner. Existing unowned rows stay quarantined until an
   operator reviews a complete ownership manifest. Never default legacy rows to
   `local`. Preserve ownership already recorded on sales, chat, memory, research
   and audit rows. Refuse missing, invalid or ambiguous assignments before any
   data change; retain a private archive and count/hash reconciliation. Unique
   constraints that mean "one per install" become "one per workspace" — for
   example a contact's email becomes unique per `(workspace_id, email)` —
   which in SQLite means rebuilding those tables inside the migration's
   transaction. The migration has a written inverse, and the inverse is run
   once on a copy of a real database before release (Definition of Done).
2. **A scoped store.** `OutreachStore.scoped(workspace_id)` returns a view with
   the same methods, each adding its root's `workspace_id = ?`. A row in
   another workspace is "not found" (404), never "forbidden": existence is not
   leaked. The unscoped store stays for the owner's install-level jobs only
   (backup, migrations), and a test lists every call site that uses it.
3. **All runtime consumers.** `_engine(request)` binds the authenticated workspace without mutating shared state. Scoping this factory alone is insufficient. AIChatService, SalesTracker, CRMInsights, CampaignRelationships, deliverability, privacy, idempotency and runtime callbacks also access raw SQL. Each must bind the same workspace and enforce root ownership; unscoped access needs an explicit install-operation allowlist. Preserve the existing caller marker until replacement tests pass.
4. **Timers.** The email and content automations run for the install today.
   With tenancy they run per workspace: each workspace declares its own
   automation, and a cycle acts for each campaign's workspace, on that
   workspace's keys. *(Decide: are automation settings per workspace, or the
   owner's for all?)*
5. **GTM.** A campaign link must be in the campaign's own workspace — enforced
   when linking. The draft writer then reads the campaign's own workspace's
   product, and the caller marker (DD-60) can be deleted.
6. **Privacy.** A subject-access or deletion request (`S-06.02.04`) comes from
   one client's customer, so the privacy inventory runs inside one workspace.
7. **Backups stay whole-install and owner-only** (`D-124`). A per-workspace
   export is a separate story, not part of this one.
8. **The owner's view.** The owner signs in as `local` and sees `local`'s
   rows. *(Decide: does the owner need an all-workspaces view? If yes, it is
   an admin screen of its own, not an unscoped store behind every route.)*

## Build order — each phase a vertical slice, green before the next

| Phase | Delivers | Proof |
|---|---|---|
| 1 | Schema, migration and its inverse; no behaviour change | migration forward and back on a copy of a real database; the full suite unchanged |
| 2 | Campaigns, contacts, drafts and templates scoped per request | a two-workspace test per route, built like `tests/test_workspace_isolation.py::_two_workspaces_and_a_shared_campaign`; a row in the other workspace is 404 |
| 3 | Deliverability, sales, AI chats, research, memory, provider audit | the same two-workspace pattern, per table |
| 4 | Timers per workspace; the GTM link rule; the caller marker removed | a timer cycle touches only its own workspace; `D-125`'s tests still pass without the marker |
| 5 | Privacy inventory per workspace | subject access in one workspace finds nothing of another's |

## Risks

- **Breadth.** `OutreachStore` has 101 methods including connection/transaction helpers. Missing one is a leak.
  The scoped view must be total: a test walks every public method and fails on
  one that does not scope — the same idea as `tests/test_api_boundary_contract.py`
  walking every route.
- **Uniqueness.** Two clients can share a prospect. Merging those rows would
  leak one client's notes to the other, so they stay two rows by design.
- **Migration on live data.** The migration's inverse must be run on a real
  copy before release, not only written down.

## Not in scope

Per-workspace backups, billing, per-workspace sending limits beyond what an
identity already has, and moving the CRM to PostgreSQL. `docs/architecture/POSTGRES.md`
covers the store boundary that last one would use.


## 2026-11-06 independent readiness review

The current34-table inventory includes campaign_reply_triage, campaign_followup_tasks and campaign_sales_links; all inherit campaign ownership and must validate linked membership, draft and sales-lead roots. A contact linked to campaigns assigned to different workspaces is ambiguous: do not pick an owner or silently duplicate it. The explicit manifest must resolve the records and their dependent references. Owner `local` sees its own rows; an install-level all-customer browse is not implied.

Contact identity_key and the partial case-insensitive email index must both permit the same prospect in distinct workspaces while refusing duplicates within one. Sending identity, consent, job/message/provider-event uniqueness and rate lanes require documented scope. Unsubscribes remain scoped to the relevant sender/workspace; reputation hard-bounce/complaint protections remain install-wide and cannot become readable customer records. Expert reference material must have an explicit private owner or a separately declared shared read-only library; no accidental global mutable library.

Worker claims recover the campaign workspace before selecting identities, credentials, consent, templates or product context. Quarantined legacy jobs never execute. Timer configuration and scoped execution must agree. Recall rebuild must read only the target workspace; relabelling an unfiltered store's messages with the caller's workspace is prohibited. Privacy must find/export/delete only that workspace's root and derived records.

Required matrix: fresh/legacy/mixed-owned SQLite and PostgreSQL; missing/ambiguous manifests; interrupted retry and exact archive restore; composite uniqueness and cross-root constraints; three sessions (alpha, beta, local) with list/search/count/export/guessed-ID/bulk/pagination; sales/relationships/analytics/discovery/chat/templates/memory/GTM/recall/audit; concurrent job claims/scoped unsubscribe/uncertain send; per-workspace timers and restart; same privacy identifier in two workspaces; complete backup/restore; raw-access allowlist and concurrent cross-workspace requests. An inverse must refuse after tenant data would conflict with the old global constraints. Recovery uses a verified snapshot, never merging or discarding customer rows.
