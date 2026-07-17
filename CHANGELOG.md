# Changelog

## 0.7.0

- Added a temporary single-user CRM login with signed HTTP-only sessions and login throttling.
- Added Render Blueprint configuration, automatic `PORT` handling, and a readiness health check.
- Added a dedicated responsive login screen and logout control.
- Documented disposable Render data and the hosted Gmail OAuth boundary.

## 0.6.0

- Added encrypted local AI provider profiles and secret storage.
- Added priority-ordered provider failover, response normalization and circuit breaking.
- Added reply-first campaign automation with daily caps and explicit Gmail activation.
- Added passphrase-encrypted local backup and verified restore.
- Added provider, automation and backup controls to the React Settings page.
- Expanded the release suite to 45 Python tests and 2 frontend tests.

## 0.5.0

- Added FastAPI local CRM API and React control centre.
- Added campaigns, contacts, drafts, queue, reply stop, exports and A/B reports.
- Added local SQLite schema, migrations, FTS expert library and event audit.
- Added strict OffsetX email expert and eight versioned A/B templates.
- Added OpenAI, Anthropic, compatible API and template-application adapters.
- Added Gmail OAuth and safe local outbox providers.
- Added daily limits, working-day scheduling, atomic send claims and idempotency.
- Added API token, upload, provider URL and spreadsheet export security controls.
- Preserved both Apollo search and existing-POI enrichment workflows.
- Expanded the release suite to 38 Python tests and 2 frontend tests.
