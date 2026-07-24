# OFF_CRM security model

The complete OFF_AI threat model and acceptance tests are documented in `OFF_AI_SECURITY.md`.

## Application controls

- Loopback binding by default.
- Non-loopback binding refused without a strong API token or complete demo login.
- Signed, secure, HTTP-only, SameSite session cookie and throttled login failures.
- CSP, HSTS for non-loopback deployments, frame denial, no-referrer, no-store, MIME controls, and limited browser permissions.
- Upload type/size limits, contained filenames, private content-addressed attachment storage, and formula-safe exports.
- SQLite foreign keys, WAL, bounded transactions, idempotency keys, and audit/event records.
- Provider keys encrypted outside SQLite with a user-restricted local key.
- Passphrase-encrypted backups with integrity validation and pre-restore safety copy.
- Local outbox by default and exact confirmation before live Gmail sending.
- Backend-enforced campaign limits, send windows, scheduling, atomic claims, and stale-send review.
- Reply synchronization before sending and deterministic cancellation after a reply.
- CRM-owned Gmail thread retrieval only; broad production mailbox scans are disabled.
- Guarded public crawling with robots.txt, SSRF, allowed-domain, rate, redirect, size, and content-type controls.
- One shared per-domain rate gate across all discovery workers, so parallel work does not raise the request rate to one site.
- No authenticated social scraping, session-cookie use, CAPTCHA bypass, or protection evasion.
- Optimistic revision control and append-only events for the sales board.
- One-way Notion writes only. The token is encrypted outside SQLite, responses are bounded, and OFF_CRM does not treat Notion as a source of truth.

## OFF_AI controls

- One provider egress broker.
- Task-specific field allowlists.
- Email/secret/path/mailbox/CRM/context preflight blocking.
- Deterministic PII backstop.
- Tier A/B/C/D default-deny policy with host/model provenance.
- Quota and cost caps, cheapest-eligible routing, and same-tier failover only.
- Exact egress packet inspector.
- No provider tools, connectors, database, memory, file, or mailbox path.
- Human approval before draft sending and template changes.
- Networkless, read-only, version-pinned GitHub tools.

## Secrets

Never commit:

- `.env`;
- Google client-secret JSON or Gmail tokens;
- provider API keys;
- Notion integration tokens;
- `.provider_master.key` or `provider_secrets.enc`;
- local databases, attachments, mail folders, exports, backups, or tool checkouts.

Verify release archives even though these paths are ignored.

## Deployment boundary

v0.12 is single-user and local-first. Render is a disposable synthetic-data demo. It is not a multi-tenant hosted service.

Before remote team access, implement tenant-scoped authentication/authorization, PostgreSQL isolation, managed secrets, durable workers, encrypted storage, centralized logs, migrations, backups, and a reviewed network boundary.

## Incident response

Pause automation and campaigns, disable the provider, preserve audit/event records, revoke affected keys/tokens, inspect the exact egress packet, fix and test the policy, then re-enable.
