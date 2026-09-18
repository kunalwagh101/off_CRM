# Security model

## Implemented controls

- Binds to `127.0.0.1` by default.
- Refuses non-loopback binding without a strong local API token.
- Reads AI and Gmail secrets from local environment or protected token files.
- Never stores AI API keys in SQLite.
- Encrypts locally managed provider keys with a dedicated master key restricted to the current user.
- Uses Gmail OAuth PKCE with a loopback callback and refresh-token storage permissions.
- Requires exact confirmation before live Gmail sending.
- Uses a safe local outbox by default.
- Syncs replies before sending and cancels unsent follow-ups after a reply.
- Enforces daily campaign limits and working-day schedules in the backend.
- Uses atomic draft claims and message idempotency keys.
- Moves uncertain stale sends to manual review instead of retrying automatically.
- Limits upload size and file types and removes temporary uploads.
- Blocks web API access to the trusted local-command AI adapter.
- Allows plain HTTP AI endpoints only on loopback.
- Rejects provider URLs with embedded credentials.
- Escapes formula-like fields in CSV and XLSX exports.
- Sends CSP, frame, referrer, cache and MIME security headers.
- Records campaign events and provider identifiers for audit.
- Encrypts exported backups with a user passphrase and verifies SQLite integrity before restore.
- Keeps scheduled Gmail sending disabled until the operator enters the exact activation phrase.
- Supports workspace-bound logins with constant-time credential checks, throttled failures and signed, secure, HTTP-only, SameSite session cookies; the legacy demo login remains the `local` workspace.
- Protects API documentation behind the configured login and adds HSTS and restrictive browser permission headers for non-loopback deployments.
- Applies per-provider data-minimisation policies before network calls.
- Stores provider payload bodies only when explicitly enabled; metadata-only audit is the default.
- De-identifies human corrections before adding them to reusable memory.
- Keeps reply observations unapproved until a human supplies an outcome label.
- Restricts discovery to explicit public URL and domain allow-lists with robots.txt, rate, redirect, response-size, content-type and SSRF checks.
- Blocks automated crawling of LinkedIn, Instagram and other major social platforms; no browser cookie or social login is passed to the crawler or an AI provider.
- Stores normalized POI evidence and a page hash instead of raw crawled HTML.
- Runs Crawl4AI only with stealth, user simulation, navigator overrides, proxy retry, persistent profiles, cookies and scripted interaction disabled.
- Intercepts Crawl4AI browser routes and blocks private/reserved DNS targets; document requests must remain inside the explicit run allow-list.
- Keeps email addresses out of the research graph and accepts social-interaction evidence only from an official API adapter or explicit manual import with a rights basis.
- Keeps Apollo rejection/audit ledgers outside `old_pois`, preventing retryable no-match rows from becoming accidental permanent exclusions.
- Uses optimistic card revisions to reject stale sales-board writes and records every sales lead create, edit and status change in an append-only event trail.
- Calculates sales metrics server-side from validated SQLite records; browser-supplied earnings, rates and projections are never trusted.

## Secrets

Never commit:

- `.env`
- Google client secrets
- Gmail tokens
- provider API keys
- local CRM databases
- local mail folders
- `.provider_master.key`
- `provider_secrets.enc`
- encrypted backup passphrases

These paths are covered by `.gitignore`, but operators must still verify release archives.

## Workspace credential boundary

A login is bound to one signed `workspace_id`. That server-side identity selects
AI provider settings/keys and browser connection/vault state. Workspace choice
is never taken from a request header, query parameter or body. The local API
token is intentionally bound to the `local` workspace.

The AI broker is process-wide but provider-key lookup is not mutable shared
state: each call scopes key resolution to `WorkspaceEgressSettings.workspace_id`
using context-local state, so concurrent requests cannot switch the resolver
under one another.

## Known deployment boundary

This increment provides workspace-specific logins, provider keys and browser
session custody. It **does not yet make every CRM database row tenant-scoped**
and it does not invent team roles/approval hierarchy. `S-06.01.02` owns the
permission model; broader data tenancy must be explicitly traced before this is
described as a general multi-tenant hosted CRM.

The free Render configuration remains unsuitable for personal contacts, Gmail
tokens, private expert material or live provider credentials. The current Gmail
OAuth flow is still designed for a local desktop callback.

For remote team production, require the remaining permission/data-isolation
stories, durable storage, deployment monitoring and rollback evidence before
exposing customer data.

## Reporting a failure

Pause the affected campaign first. Preserve the local database, event log and provider message IDs. Do not delete a failed-send record until the Gmail state is confirmed.
