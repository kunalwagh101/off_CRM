# OFF_AI operator guide

## First run

```powershell
uv sync --extra dev
cd frontend
npm ci
npm run build
cd ..
Copy-Item .env.example .env
uv run python run_off_crm.py
```

Open `http://127.0.0.1:8766`.

OFF_CRM works without an AI provider by using local templates, Parse & send intake, CRM, discovery, Apollo, sales tracking, and the local outbox.

## Configure an AI provider

1. Open **Connectors → Add AI provider**.
2. Choose OpenAI, Anthropic, OpenAI-compatible, or an owner-operated template HTTP service.
3. Enter a model and official base URL where required.
4. Store the API key locally or name an environment variable.
5. Enter the host jurisdiction and retention classification.
6. Record host origin, model origin, model-origin jurisdiction, and the date the terms were checked.
7. Assign Tier A/B/C/D. Unknown or aggregator services must remain Tier D.
8. Select allowed task types.
9. Enter RPM/RPD, context window, prices, and daily/monthly caps.
10. Nominate only same-tier fallbacks.
11. Save, then select **Test**.

At a glance, each provider card shows effective tier, chat/outreach eligibility, health, jurisdiction, retention, credential source, and current usage.

### Choosing a tier

- Use Tier A only for a direct provider with acceptable jurisdiction and documented no-training/no-retention API terms.
- Use Tier B for weak-retention/free-tier services and public, non-personal work.
- Use Tier C for China-jurisdiction services. Enable only explicit public task types; select it manually for each task.
- Use Tier D when any required fact is unknown or the service is an aggregator/router.

The UI declaration cannot make an unsafe configuration effective: policy downgrades are recalculated on every route.

## Use AI chat

1. Open **AI** at the top of the left navigation.
2. Select automatic routing or one eligible model.
3. Keep **Same-tier failover** enabled unless a single-provider test is desired.
4. Enter public, non-sensitive content only.
5. Select **Inspect packet** under a response to see the exact provider payload.
6. Use **Context** to view local continuation state; the provider cannot open it.

The right-side history drawer contains Chats and Projects. It supports search, pin, rename, archive, new chat/project, and project Markdown/HTML export. Close/reopen it independently from the global left navigation. On mobile both are overlays with their own close controls.

Project instructions are treated as approved public constraints. Do not put contacts, addresses, CRM notes, mailbox content, credentials, or confidential business data in them.

## Dictation

Select the microphone-style control beside the composer. OFF_CRM uses the browser's speech-recognition capability if available. Unsupported browsers show a plain-language message and retain normal typing.

## Import a campaign

1. Open **AI → +**.
2. Choose a CSV, XLSX, XLS, PDF, TXT, or Markdown file.
3. Leave Mode on **Detect automatically**, unless the desired mode is known.
4. For Generate, enter the owner template and approved public positioning.
5. Select **Inspect file**.
6. Review the masked preview, detected headers, missing fields, and row errors.
7. If the file is ambiguous, choose Generate or Parse & send once.
8. Create the campaign.
9. Open **Draft review**, edit/retry/bulk-correct, and approve each draft.
10. Use **Send queue** with the local outbox first, then Gmail.

Generate requires a Tier A outreach-eligible provider. If the selected chat model is not outreach-eligible, OFF_CRM automatically uses the cheapest eligible Tier A provider. If none exists, the flow stops before creating a campaign.

Parse & send never calls a model. It preserves mapped subject/body fields and still creates pending review drafts.

Missing addresses enter `poi_file_queue/inbox`. Existing contacts and exclusion files are removed before drafting. Intake-created campaigns are capped at 20 sends/day.

## Prepare POIs

Use **Lead discovery** before AI intake when contacts need public evidence or Apollo enrichment:

1. enter a bounded research prompt and explicit public seed URLs;
2. review the compiled target/source plan;
3. run safe HTTP or the guarded local Crawl4AI worker;
4. approve candidates;
5. send missing addresses to Apollo;
6. import approved, deduplicated contacts into the CRM.

LinkedIn/Instagram cookies and protection bypass are unsupported. Use official APIs or manual imports.

## Connect Gmail

Set:

```env
OFF_CRM_GMAIL_CLIENT_SECRETS=path/to/client_secret.json
OFF_CRM_GMAIL_TOKEN=local_data/gmail_token.json
OFF_CRM_OWN_EMAIL=you@example.com
```

Restart, open **Connectors**, and select **Connect Gmail**. Complete Google's consent flow in the popup. Disconnecting removes the local token file.

Gmail live sending still requires the exact confirmation shown by the Send Queue. Automation is disabled by default and has a separate activation phrase.

## Review provider egress

Open **Connectors → Provider egress audit**. Filtered API access is also available at:

```text
GET /api/v1/ai/egress
GET /api/v1/ai/egress/{call_id}
```

Inspect:

- provider, model, host/model origin, jurisdiction, retention, and tier;
- task and data class;
- exact constructed packet and SHA-256;
- blocked reasons or error;
- provider response;
- input/output token estimate, cost, and duration.

## Export the owner record

Connectors provides:

- **NotebookLM Markdown**
- **Notion-ready JSON**

The one-way export contains projects/egress statistics and CRM campaign/contact/message activity: campaign, contact, variant, timestamps, reply state, status, stage, and subject. Message bodies and raw mailbox/provider payloads are omitted.

## Template feedback

Open **Experiments**. Once a variant has at least 20 sends, request a rewrite. The provider receives only the current template, sample size, and numeric reply rate. Compare the candidate and approve or reject it. No reply body is used and no candidate silently replaces a live template.

## Register a GitHub tool

Docker is required.

1. Open **Connectors → Register GitHub tool**.
2. Use a public `https://github.com/owner/repository` URL.
3. Paste the exact 40-character commit SHA.
4. Name a pre-pulled, version-pinned image; `latest` is refused.
5. Enter the command as a JSON array.
6. Select **Prepare pinned commit**.
7. Run it only with public, non-sensitive text.

Execution has no network and a read-only source mount. A tool cannot use Gmail, CRM, provider, or host credentials.

## Backups

Use **Settings → Encrypted backup**. Gmail tokens and generated mail files are intentionally excluded. Keep the passphrase outside the repository and test restore before relying on a backup.

## Troubleshooting

| Symptom | Resolution |
|---|---|
| No eligible AI provider | Verify enabled state, terms date, jurisdiction, retention, trust tier, task allowlist, and credential |
| Generate button disabled | Add a Tier A provider eligible for `outreach_draft`, or use Parse & send |
| Call blocked before egress | Inspect the audit; remove email, credential, path, mailbox/CRM request, owner domain, or forbidden field |
| Provider quota blocked | Review RPM/RPD and daily/monthly spend in Connectors; wait or select a same-tier provider |
| Gmail Connect disabled | Configure client-secret and token paths, then restart |
| Reply sync unavailable | Confirm Gmail connection, own email, and CRM-owned thread IDs |
| Tool prepare fails | Verify public repository, exact commit, Git availability, and outbound GitHub access |
| Tool run fails | Install Docker, pre-pull the pinned image, and verify the command works without network or writes |
| Voice unavailable | Use typing or a browser that exposes Web Speech Recognition |
| Parsed file needs mapping | Add recognizable headers or use the structured text format shown in the API/parser tests |
