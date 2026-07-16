# Security model

## Implemented controls

- Binds to `127.0.0.1` by default.
- Refuses non-loopback binding without a strong local API token.
- Reads AI and Gmail secrets from local environment or protected token files.
- Never stores AI API keys in SQLite.
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

## Secrets

Never commit:

- `.env`
- Google client secrets
- Gmail tokens
- provider API keys
- local CRM databases
- local mail folders

These paths are covered by `.gitignore`, but operators must still verify release archives.

## Known deployment boundary

This release is a single-user local application. It is not a multi-tenant hosted service. Do not expose it directly to the public internet.

If remote team access is later required, add authenticated tenancy, encrypted secret storage, a durable job queue, PostgreSQL and an audited deployment boundary before exposing the API.

## Reporting a failure

Pause the affected campaign first. Preserve the local database, event log and provider message IDs. Do not delete a failed-send record until the Gmail state is confirmed.
