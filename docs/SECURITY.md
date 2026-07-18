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
- Supports a single-user demo login with constant-time credential checks, throttled failures and a signed, secure, HTTP-only, SameSite session cookie.
- Protects API documentation behind the configured login and adds HSTS and restrictive browser permission headers for non-loopback deployments.
- Applies per-provider data-minimisation policies before network calls.
- Stores provider payload bodies only when explicitly enabled; metadata-only audit is the default.
- De-identifies human corrections before adding them to reusable memory.
- Keeps reply observations unapproved until a human supplies an outcome label.

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

## Known deployment boundary

This release remains a single-user application. The Render configuration is only for a disposable, password-protected demonstration with synthetic data and local outbox mode. It is not a multi-tenant hosted service.

Do not upload Gmail tokens, personal contacts, private expert material or live provider credentials to the free demo. The current Gmail OAuth flow is designed for a local desktop callback, not hosted authorization.

If remote team access is later required, add authenticated tenancy, encrypted secret storage, a durable job queue, PostgreSQL and an audited deployment boundary before exposing the API.

## Reporting a failure

Pause the affected campaign first. Preserve the local database, event log and provider message IDs. Do not delete a failed-send record until the Gmail state is confirmed.
