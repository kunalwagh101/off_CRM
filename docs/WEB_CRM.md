# Web CRM operating guide

## Run the application

```powershell
uv sync --extra dev
cd frontend
npm ci
npm run build
cd ..
uv run python run_offsetx_web.py
```

Open `http://127.0.0.1:8766`.

## Pages

- Overview: campaign pulse and review backlog
- Campaigns: daily limit, status, timezone and stable A/B split
- Contacts: import, search, edit and CRM checkbox
- Draft review: generate, audit, edit and approve
- Draft control: preview exact output, apply reviewed corrections in bulk and set not-before times
- Send queue: local outbox, Gmail send and reply sync
- Experiments: first-touch reply rates by variant
- Settings: provider profiles, automatic failover, automation, encrypted backups, local paths, expert sources and exports
- Intelligence controls: provider data policy and request audit, memory approval, routing strategy and health state

## Review and scheduling

Automation never bypasses the review model. A changed draft returns to pending approval. Campaign send windows, per-draft not-before times, daily caps and reply-stop state are enforced by the backend even when the UI is closed.

## Memory

Human edits and labelled outcomes become de-identified local memory. Automatic reply observations remain unapproved until reviewed. Only approved memory is retrieved during generation.

## Safe automation

Automation is disabled by default. It always syncs replies before claiming a send, respects campaign schedules and daily limits, and stops remaining follow-ups after a reply. Local-outbox automation can be enabled directly. Persistent Gmail automation also requires the exact phrase `ENABLE AUTOMATED GMAIL`.

## Provider failover

Add provider profiles in Settings and assign a priority. Draft generation tries healthy providers in order and records which provider completed the request. OpenAI, Anthropic, OpenAI-compatible, future template-app HTTP and local-command profiles use one normalized output contract.

## Backup and restore

Settings can export a passphrase-encrypted `.oxbackup` containing the CRM database, provider profiles, encrypted provider keys and automation settings. Gmail OAuth tokens and generated mail files are intentionally excluded. Restore creates a safety copy before replacing local state.

## Local development

Run the backend:

```powershell
uv run python run_offsetx_web.py
```

Run Vite in another terminal:

```powershell
cd frontend
npm run dev
```

Open `http://127.0.0.1:5173`.

## Local API token

Loopback use does not require a token by default. To enable one:

```env
OFFSETX_LOCAL_API_TOKEN=use-at-least-32-random-characters
```

Enter the same value through the Key button in the web UI. It is stored for the browser session only.

Non-loopback binding is refused unless this token has at least 32 characters.

## Local outbox reply simulation

Local sends create JSON files under:

```text
local_data/mail/outbox
```

For testing, place an inbound JSON file under `local_data/mail/inbox` with the outbound `thread_id`, sender email, body and received time. Use Sync local replies in the UI. Matching contacts move to replied and unsent follow-ups are cancelled.

## CRM export order

The first six columns are locked:

1. Checkbox
2. Outreach Date
3. POI Name
4. POI Response
5. Follow-Up
6. Meeting Transcript

Secondary evidence and sequence columns follow. Formula-like imported values are escaped before CSV or XLSX export.
