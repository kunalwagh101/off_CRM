# OffsetX v0.6 system architecture

## Decision

OffsetX remains a modular local-first monolith. It runs on the user's machine, stores product data in SQLite and connects directly to the user's selected AI and mail providers. The future template-intelligence application integrates through the same normalized provider boundary.

## Runtime components

| Component | Responsibility |
|---|---|
| React control centre | Campaign, contact, review, queue, provider and backup workflows |
| FastAPI control plane | Validation, loopback security, versioned API and file boundaries |
| Outreach engine | Sequences, schedules, approval, limits, reply-first sending and audit |
| Automation service | Optional local scheduler using the same guarded engine operations |
| Provider router | Priority failover, response normalization, health state and audit metadata |
| Provider vault | Local encrypted API-key storage outside SQLite |
| Backup service | Passphrase encryption, SQLite online backup, integrity checks and safe restore |
| SQLite store | Contacts, campaigns, drafts, messages, templates and append-only events |

## Provider data flow

1. The user stores one or more provider profiles with explicit priority.
2. Secrets are encrypted locally and never returned by the API.
3. Draft generation builds a provider chain from enabled profiles.
4. Each response is converted to the canonical subject/body schema.
5. Transport failures or malformed output move to the next healthy provider.
6. The successful provider is recorded in draft audit metadata.

## Automation safety

Every scheduled run syncs replies first, loads only active campaigns, applies working-day schedules and daily caps, and uses atomic send claims. Automation starts disabled. Gmail requires a separate exact confirmation, while local outbox mode remains the safe default.

## Persistence and backup

The CRM database, provider configuration, encrypted provider secrets and automation settings live under the configured local data directory. Backup export uses an online SQLite snapshot, integrity validation, path-safe packaging and passphrase encryption. Gmail OAuth tokens and mail folders are excluded so a backup cannot silently authorize another machine to send.

## Scale boundary

This release is a production-minded single-user local application, not a public multi-tenant SaaS. A hosted edition should retain the service interfaces while replacing SQLite with PostgreSQL, local secrets with a tenant vault and the in-process scheduler with a durable queue.
