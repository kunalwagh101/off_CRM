# OffsetX v0.5 system architecture

## Decision

This release stays a modular local-first monolith. That is the correct architecture for one user running their own Gmail and AI credentials. The boundaries are clean enough to split later, but adding Kubernetes, Redis or microservices now would increase failure modes without improving the product.

## Runtime architecture

```text
React control centre
        |
        | JSON and file uploads on loopback
        v
FastAPI control plane
        |
        v
Outreach application service
   |         |             |
   v         v             v
SQLite   Email expert   Provider adapters
 local      local       AI / Gmail / outbox
```

The existing Apollo search and existing-POI enrichment modules stay separate from outreach. They share locked stakeholder categories and input normalization where useful.

## Component boundaries

| Component | Responsibility | Must not do |
|---|---|---|
| React | User workflow, review, filters and state display | Store provider secrets or send email directly |
| FastAPI | Validation, local security, versioned API and file limits | Contain campaign rules |
| OutreachEngine | Campaign orchestration, schedules, caps, reply-first send flow | Know React or HTTP details |
| OutreachStore | SQLite transactions, queries, migrations and atomic send claims | Call external providers |
| LocalEmailExpert | Retrieval, template rendering, AI prompt contract and audit | Invent facts or bypass audit |
| AI adapters | Normalize provider requests and responses | Store keys in SQLite |
| Mail adapters | Gmail or local-outbox send and reply sync | Decide whether a draft is approved |

## Data flow

1. A CSV or Excel file is uploaded to FastAPI.
2. The upload is size-checked, type-checked, stored in a temporary file and removed after import.
3. Contacts are normalized and deduplicated by email, LinkedIn URL or a stable identity hash.
4. Campaign membership receives a deterministic A/B variant.
5. The email expert selects a route-specific template and retrieves relevant expert notes.
6. Optional AI personalisation runs behind a normalized provider interface.
7. Every draft is audited and stored as pending.
8. A user reviews and approves a sendable draft.
9. A send run syncs replies, checks campaign state, daily cap and due time, then atomically claims one draft.
10. A reply marks the contact replied and cancels every unsent follow-up.

## Database schema

| Table | Purpose | Important constraints |
|---|---|---|
| `contacts` | Canonical POI data and source snapshot | Unique stable identity and case-insensitive email |
| `campaigns` | Limits, timezone, follow-up timing and variants | Positive limits and explicit status |
| `campaign_contacts` | CRM row and sequence state | One contact per campaign |
| `drafts` | Versioned message content, audit and approval | One stage per campaign contact |
| `messages` | Inbound and outbound provider records | Unique provider ID and idempotency key |
| `campaign_events` | Append-only operational audit trail | Campaign-scoped chronological log |
| `email_templates` | Versioned local templates and provenance | Match by stage, route, category and variant |
| `expert_chunks` | Retrieved guidance with rights metadata | Content hash deduplication |
| `idempotency_records` | Safe replay of mutating API requests | Unique scope and request key |

SQLite uses foreign keys, WAL mode, a busy timeout and transactional state changes. A future hosted edition can implement the same store interface with PostgreSQL.

## API groups

All product endpoints are under `/api/v1`.

- health and metadata
- dashboard and local settings status
- campaign create, list, update and summary
- contact import, list and update
- draft generate, list, edit and approve
- queue, send and reply sync
- A/B report and event log
- CSV/XLSX export
- template list and import
- expert-source import

The generated OpenAPI reference is available at `/api/docs`.

## UI architecture

```text
App shell
  Overview
  Campaigns
  Contacts
  Draft review
  Send queue
  Experiments
  Settings
```

The UI uses typed API models, reusable panels, buttons, badges, fields, loading states, empty states, error states and responsive tables. There is no frontend state library because server state is small and page-scoped.

## Scale path

The current release is designed for a local workspace, not millions of concurrent users. If a hosted multi-tenant edition is approved later, the safe order is:

1. PostgreSQL implementation of the store interface.
2. Encrypted tenant credential vault.
3. Durable job queue for sends and reply sync.
4. Per-tenant rate limits and audit retention.
5. Object storage for imports and exports.
6. Horizontal API replicas after state is externalized.

No product logic needs to move into the React app during that transition.
