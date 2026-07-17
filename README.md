# OffsetX Local Outreach CRM
Version 0.7 adds a protected single-user demo deployment while retaining the existing local-first outreach CRM, strict email expert, provider failover, safe automation, encrypted local backups, FastAPI backend and responsive React control centre.

## What is included

- Apollo search for new POIs
- Existing POI CSV/XLSX/XLS enrichment with queue safety and credit caps
- Campaigns, contacts, draft review, send queue, A/B reporting and CRM exports
- Three-stage email sequences: first touch, follow-up 1 and follow-up 2
- Reply detection that cancels all unsent follow-ups
- Human approval before every eligible send
- Safe local outbox by default
- Gmail OAuth with explicit live-send confirmation
- Provider-neutral AI adapters for OpenAI, Anthropic, compatible APIs and the future template application
- Priority-ordered AI failover with normalized output and provider health tests
- Encrypted local provider profiles and API keys
- Reply-first automation with hard daily limits and a disabled-by-default Gmail gate
- Passphrase-encrypted local backup and restore
- Local SQLite storage with no OffsetX server between the user and their providers
- Expert-source retrieval with source and rights provenance
- Temporary demo login with signed, secure, HTTP-only sessions and login throttling
- Render Blueprint configuration and automatic `PORT` support

The old Apollo workflows remain intact. Outreach does not use the legacy team-assignment engine.

## Quick start

Install Python and frontend dependencies:

```powershell
uv sync --extra dev
cd frontend
npm ci
npm run build
cd ..
```

Copy `.env.example` to `.env`. Keep the default loopback host.

Start the complete application:

```powershell
uv run python run_offsetx_web.py
```

Open `http://127.0.0.1:8766`.

The API reference is at `http://127.0.0.1:8766/api/docs`.

## Render demo

The checked-in `render.yaml` defines a free Docker web service in Singapore. A manual Render setup needs these private environment variables:

```env
OFFSETX_DEMO_USERNAME=choose-a-demo-username
OFFSETX_DEMO_PASSWORD=choose-at-least-12-characters
OFFSETX_SESSION_SECRET=generate-at-least-32-random-characters
OFFSETX_SESSION_HOURS=8
```

`OFFSETX_WEB_HOST=0.0.0.0` is already set by the Docker image. Render supplies `PORT` automatically. Do not add Gmail or AI keys for a basic UI demo.

The free Render filesystem is temporary. SQLite data, outbox files and configuration can disappear after a restart or redeploy. Use the Render service only for disposable demonstration data.

## First outreach workflow

1. Create a campaign and choose a daily limit.
2. Import `examples/outreach_contacts_sample.csv` or an Excel file.
3. Generate the three-stage sequence using local templates or a configured AI provider.
4. Review and approve drafts.
5. Run the local outbox first.
6. Connect Gmail only after reviewing the local results.
7. Sync replies before every send run. The backend also does this automatically.

Local outbox files are written under `local_data/mail/outbox`.

## Required contact evidence

A sendable first touch requires:

- POI name
- valid email before sending
- one of the nine locked categories
- verified public hook
- public hook source
- route-specific CTA
- exact OffsetX signature
- one question mark
- no confidential or manipulative language

## AI provider portability

API keys are never stored in the database. They can remain in environment variables or be stored in an encrypted local provider vault. The Settings page can manage a priority-ordered provider chain, test each provider and automatically fail over when a provider is unavailable or returns malformed output.

Examples are in `config/`.

The separate template-intelligence application will integrate through:

```text
POST /v1/generate
```

The normalized contract is documented in `docs/TEMPLATE_INTELLIGENCE_CONTRACT.md`.

## Gmail connection

Create a Google OAuth desktop client and set:

```env
OFFSETX_GMAIL_CLIENT_SECRETS=path/to/client_secret.json
OFFSETX_GMAIL_TOKEN=local_data/gmail_token.json
OFFSETX_OWN_EMAIL=your-email@example.com
```

Then authorize locally:

```powershell
uv run python run_offsetx_outreach.py gmail-authorize
```

Gmail live send requires the exact confirmation `SEND LIVE EMAILS` in the UI or CLI.

The current Gmail authorization is a local desktop OAuth flow. Do not upload a personal Gmail token to the free Render demo. A hosted Gmail connection requires a separate web OAuth callback and durable encrypted credential storage.

## Tests

```powershell
uv run pytest -q
cd frontend
npm test
npm run build
```

Release result:

```text
49 Python tests passed
3 frontend tests passed
production frontend build passed
```

## Apollo workflows

Existing POI queue status:

```powershell
uv run python run_offsetx_apollo.py --queue-status
```

Existing POI dry run:

```powershell
uv run python run_offsetx_apollo.py `
  --enrich-existing-pois `
  --outdir output_existing_poi_enrichment `
  --run-id dry_existing_pois_001 `
  --credit-cap 10 `
  --batch-size 5 `
  --dry-run
```

Apollo search dry run:

```powershell
uv run python run_offsetx_apollo.py `
  --outdir output_dry_run `
  --run-id search_dry_001 `
  --target-count 250 `
  --credit-cap 250 `
  --dry-run
```

See `docs/EXISTING_POI_ENRICHMENT.md` for the full legacy workflow.

## Documentation

- `docs/SYSTEM_ARCHITECTURE_V06.md`
- `docs/WEB_CRM.md`
- `docs/TEMPLATE_INTELLIGENCE_CONTRACT.md`
- `docs/SECURITY.md`
- `docs/DEPLOYMENT.md`
- `docs/TROUBLESHOOTING.md`

## Important safety rule

Do not upload copied paid courses or private material to the expert library. Use owned notes, licensed material, permissioned transcripts or public material with clear provenance.
