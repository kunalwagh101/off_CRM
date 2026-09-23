# CRM tenancy — campaigns, contacts and drafts that belong to a workspace

**Status: design only, not built.** Build it only if the owner answers `Q-27`
with option 2. Story: `S-06.01.06` (BLOCKED on `Q-27`). Defect it answers:
`D-135`. Written 2026-09-23.

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

## The tables (`offsetx_apollo_builder/outreach/schema.py`, 31)

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
   `workspace_id TEXT NOT NULL DEFAULT 'local'`: every existing row becomes the
   install's own workspace, which is where the owner already works. Unique
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
3. **The engine per request.** `_engine(request)` in `api/app.py` returns the
   engine bound to `_workspace_id(request)`. Every CRM route already goes
   through `_engine`; the scoping arrives with no route changing its shape.
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

- **Breadth.** `OutreachStore` has about 90 methods. Missing one is a leak.
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
