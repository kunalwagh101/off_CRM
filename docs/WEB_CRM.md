# OFF_CRM web operating guide

## Run

```powershell
uv sync --extra dev
cd frontend
npm ci
npm run build
cd ..
uv run python run_off_crm.py
```

Open `http://127.0.0.1:8766`.

## Navigation

- **AI:** prompt/model workspace, campaign file intake, local context inspector.
- **Overview:** campaign pulse and review backlog.
- **Campaigns:** limits, status, timezone, windows, weekdays, and stable A/B split.
- **Lead discovery:** bounded prompt, guarded crawl, one-to-four worker control, research graph, evidence review, exclusion, Apollo queue, and rejection ledger.
- **Contacts:** import, search, edit, and CRM status.
- **Draft review:** generate, regenerate, inspect, edit, bulk-correct, schedule, and approve.
- **Send queue:** local outbox, Gmail send, and CRM-thread reply sync.
- **Sales tracker:** Kanban, lead log, setter/closer/money dashboard, and projection.
- **Experiments:** reply-rate reporting and human-reviewed template recommendations.
- **Connectors:** Gmail OAuth, provider trust/quota registry, egress inspector, owner exports, and sandboxed GitHub tools.
- **Settings:** local storage, learning memory, automation, encrypted backups, expert sources, templates, and one-way Notion export.

AI is first in the global left navigation. The left navigation closes independently. In AI, Chats and Projects open from the right and have their own close/reopen control.

Discovery workers share one per-domain rate gate. Increasing workers can shorten a multi-site run, but it does not increase request frequency to a single site.

Notion sync writes selected campaign contacts or sales leads into existing Notion databases. OFF_CRM remains the source of truth and does not import Notion changes.

## Draft review and sending

Changed or regenerated drafts return to pending approval. Send windows, per-draft not-before times, daily limits, and reply-stop state are enforced by the backend even when the UI is closed.

Use the local outbox first. Gmail sending requires a connected account and the exact live-send confirmation shown in the UI.

## Safe automation

Automation is disabled by default. It syncs replies before claiming sends, honors campaign schedules and daily limits, and stops unsent follow-ups after a reply. Persistent Gmail automation has a separate activation phrase.

## Local API token

Loopback use needs no token by default. To require one:

```env
OFF_CRM_LOCAL_API_TOKEN=use-at-least-32-random-characters
```

Enter it through the Key control. The browser stores it for the current session only. A non-loopback host is refused without this token or complete login configuration.

## Local reply simulation

Local sends create JSON files under `local_data/mail/outbox`. For tests, place an inbound JSON record in `local_data/mail/inbox` using the outbound `thread_id`, sender, body, and receive time. Sync local replies. Matching contacts move to replied and remaining follow-ups are canceled.

## CRM export order

The first six columns remain:

1. Checkbox
2. Outreach Date
3. POI Name
4. POI Response
5. Follow-Up
6. Meeting Transcript

Secondary evidence and sequence columns follow. Formula-like values are escaped in CSV/XLSX exports.

See `OFF_AI_OPERATOR_GUIDE.md` for provider, Gmail, campaign-intake, export, and sandbox-tool operations.
