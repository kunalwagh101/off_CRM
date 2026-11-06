# CRM tenancy — campaigns, contacts and drafts that belong to a workspace

**Status: owner authorised implementation; runtime isolation not activated.** Owner answered Q-27 on2026-11-06: workspace-owned CRM rows, isolate customers. Story S-06.01.06 remains open under the active production audit. No existing record may be assigned automatically. Defect D-135 remains open. The read-only ownership validator, optional PostgreSQL namespaces and leased native registry are implemented components. The registry is not yet connected to application requests. DD-160 selects native books after direct/pooler and encrypted recovery proofs; this revision replaces the earlier root-column/scoped-view implementation proposal.

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

**Roots — each belongs to exactly one native workspace book:**

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

**Explicit migration classifications:**

| Table | Why it is a decision |
|---|---|
| `email_suppressions` | Unsubscribe stays sender/workspace scoped. Hard-bounce/complaint protection stays private and install-wide; neither a customer-readable global book nor a copied stale snapshot suffices. |
| `expert_chunks` | Every mutable legacy reference row requires an explicit workspace owner. A separately declared shared read-only library is a future capability, not an automatic classification. |

Each book retains all34 tables, their native foreign keys and uniqueness constraints. Children and roots cannot refer to a different book through ordinary unqualified SQL. Existing workspace columns on memory, sales, research, chat and audits remain accurate and unchanged during migration. New operations must write the authenticated workspace there. Native partitioning supplements those existing checks. It does not authorize arbitrary SQL or cross-schema identifiers.

## The pieces

1. **Explicit migration and quarantine.** Existing unowned rows remain inaccessible to the new runtime until an operator supplies a complete ownership manifest. Never default legacy rows to `local`; preserve recorded owners. Reject missing, ambiguous or cross-root assignments before mutation. Archive the complete source privately, reconcile canonical source and destination counts/hashes and retain a guarded inverse. SQLite stages private book files durably before one root transaction publishes routing and closes legacy names. PostgreSQL can copy book schemas and publish routing in one database transaction. Uncertain or enabled external work requires explicit reconciliation/reactivation. Failed publication leaves the old source authoritative; leftover staging must be identified and safely retryable, never adopted by a normal request.
2. **A leased native store.** `WorkspaceCrmRegistry.lease(workspace_id)` returns an actual `OutreachEngine` backed by that workspace's SQLite file or PostgreSQL schema. It does not rewrite SQL or expose an unscoped connection behind a facade. Targets derive from trusted workspace/install/generation identifiers. Native equal-email uniqueness remains per book. PostgreSQL uses `SET LOCAL search_path` inside every transaction with no public fallback; real transaction-pooler proof is required. Ready books never silently recreate missing storage. Missing/replaced control files and mismatched book identity fail closed. Only idle engines evict; active leases prevent close/restore. Foreign IDs return ordinary not-found results. Owner-only backup/migration interfaces have explicit unscoped access; no customer browsing is implied.
3. **All runtime consumers.** `_engine(request)` binds the authenticated workspace without mutating shared state. Scoping this factory alone is insufficient. AIChatService, SalesTracker, CRMInsights, CampaignRelationships, deliverability, privacy, idempotency and runtime callbacks also access raw SQL. Each must bind the same workspace and enforce root ownership; unscoped access needs an explicit install-operation allowlist. Preserve the existing caller marker until replacement tests pass.
4. **Timers and shared controls.** The email and content automations currently run for the install. Scoped settings and cycles must resolve a workspace before selecting its campaigns, credentials or approval. Do not implicitly reactivate imported queues. Enumerating workspace IDs for an install worker does not authorize an unscoped CRM read. Private install-wide bounce/complaint and account-rate controls remain effective across books, with idempotency and conservative uncertain-action handling; customers cannot enumerate them. Cross-file writes require explicit failure/concurrency proof rather than an assumed shared transaction.
5. **GTM.** A campaign link must be in the campaign's own workspace — enforced
   when linking. The draft writer then reads the campaign's own workspace's
   product. Keep the caller marker (DD-60) until the full replacement isolation matrix proves it redundant.
6. **Privacy.** A subject-access or deletion request (`S-06.02.04`) comes from
   one client's customer, so the privacy inventory runs inside one workspace.
7. **Backups stay whole-install and owner-only** (`D-124`). A per-workspace
   export is a separate story, not part of this one.
8. **The owner's view.** The owner signs in as `local` and sees `local`'s rows. An all-workspaces browse is outside this authorisation. Install recovery/privacy operations require explicit target scope and existing admin authorization.
9. **Recovery lifecycle.** Drain and close every registry/service before swapping data, then reopen from verified routing. Constructors must participate in startup/recovery fencing. SQLite books and control must stay inside `OFFSETX_DATA_DIR`; the current registry refuses an external root whose sibling book files would escape recursive backup. PostgreSQL dump/restore includes every native schema. A restored generation must not blindly repeat external actions or revive deleted data; demonstrate reconciliation/pause behavior before release.

## Build order — each phase a vertical slice, green before the next

| Phase | Delivers | Proof |
|---|---|---|
| 1 | Read-only ownership, native transport, pooler and recovery proofs | consistent source hash; same-email/native-key isolation; real pooler reset; encrypted whole-root/multi-schema restore |
| 2 | Leased registry component, not default runtime activation | missing/foreign/replaced storage, concurrent initialization, eviction/restart, active lease and recovery errors |
| 3 | Manifest archive/apply/quarantine and guarded inverse | exact rows/hashes, failure before/after publish, retry and inverse on a real database copy |
| 4 | All request/service/worker factories and shared controls | authenticated alpha/beta/local route/SQL/send/privacy matrix; cross-book reputation/rate and uncertain-action tests |
| 5 | Complete supported runtime activation and recovery | full SQLite/PG/Python/frontend/real browser/security checks; drained restore; independent acceptance; no dependency bypass |

## Risks

- **Breadth.** The native book covers ordinary store queries and raw SQL together, but a single service using the old singleton can still leak. Audit every engine/store/service/worker factory and allowlist only explicit install operations. Do not activate a partial factory conversion.
- **Uniqueness.** Two clients can share a prospect. Merging those rows would
  leak one client's notes to the other, so they stay two rows by design.
- **Migration on live data.** The migration's inverse must be run on a real
  copy before release, not only written down.
- **Database roles.** Native PostgreSQL schemas isolate supported application operations, not malicious arbitrary SQL under one shared role. Customer inputs cannot select targets, schemas or qualified relations. Database-per-customer credentials would be a separate deployment model.

## Not in scope

Per-workspace backups, billing, per-workspace sending limits beyond what an
identity already has, and moving the CRM to PostgreSQL. `docs/architecture/POSTGRES.md`
covers the store boundary that last one would use.


## 2026-11-06 independent readiness review

The current34-table inventory includes campaign_reply_triage, campaign_followup_tasks and campaign_sales_links; all inherit campaign ownership and must validate linked membership, draft and sales-lead roots. A contact linked to campaigns assigned to different workspaces is ambiguous: do not pick an owner or silently duplicate it. The explicit manifest must resolve the records and their dependent references. Owner `local` sees its own rows; an install-level all-customer browse is not implied.

Contact identity_key and the partial case-insensitive email index must both permit the same prospect in distinct workspaces while refusing duplicates within one. Sending identity, consent, job/message/provider-event uniqueness and rate lanes require documented scope. Unsubscribes remain scoped to the relevant sender/workspace; reputation hard-bounce/complaint protections remain install-wide and cannot become readable customer records. Expert reference material must have an explicit private owner or a separately declared shared read-only library; no accidental global mutable library.

Worker claims recover the campaign workspace before selecting identities, credentials, consent, templates or product context. Quarantined legacy jobs never execute. Timer configuration and scoped execution must agree. Recall rebuild must read only the target workspace; relabelling an unfiltered store's messages with the caller's workspace is prohibited. Privacy must find/export/delete only that workspace's root and derived records.

Required matrix: fresh/legacy/mixed-owned SQLite and PostgreSQL; missing/ambiguous manifests; interrupted retry and exact archive restore; composite uniqueness and cross-root constraints; three sessions (alpha, beta, local) with list/search/count/export/guessed-ID/bulk/pagination; sales/relationships/analytics/discovery/chat/templates/memory/GTM/recall/audit; concurrent job claims/scoped unsubscribe/uncertain send; per-workspace timers and restart; same privacy identifier in two workspaces; complete backup/restore; raw-access allowlist and concurrent cross-workspace requests. An inverse must refuse after tenant data would conflict with the old global constraints. Recovery uses a verified snapshot, never merging or discarding customer rows.
