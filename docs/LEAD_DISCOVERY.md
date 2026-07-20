# Lead discovery, research graph and Apollo hand-off

## Implemented flow

```text
Research prompt + public seed pages
  -> bounded discovery plan
  -> safe HTTP or guarded Crawl4AI renderer
  -> Scrapling structured Person parser
  -> old-POI and CRM dedupe
  -> local research graph + evidence
  -> human review
  -> Apollo inbox or CRM
```

The prompt is stored and compiled into inspectable controls such as target count,
role keywords, source adapters and missing connector requirements. It is never
executed as JavaScript, SQL, a shell command or an unrestricted browser-agent
instruction.

## Crawler engines

`safe_http` is lightweight and is the default for local use and the free Render
demo. `crawl4ai_public_js` renders public JavaScript pages and is intended for a
local or separately sized crawler worker.

Install the optional engine locally:

```powershell
uv sync --extra dev --extra crawler
uv run crawl4ai-setup
```

Crawl4AI is pinned to the current 0.9 release line. The adapter fixes stealth,
user simulation, navigator overrides, proxy retries, cookies, downloads and
persistent profiles off. It checks `robots.txt`, enforces page/time/size caps,
checks public DNS for browser routes and restricts document navigations to the
run allow-list. It does not bypass Cloudflare, CAPTCHAs or access controls.

Good seed pages include company team pages, speaker directories, association
directories, public biographies and public research pages. A search API adapter
or supplied competitor URLs are required to expand a prompt into 100 unrelated
competitor websites.

## Social-platform boundary

LinkedIn, Instagram, Facebook, Threads, TikTok and X are blocked crawler targets.
Public pages may contain profile links; the CRM records those as reference-only
graph nodes but does not visit them.

Interaction evidence can enter through:

- an approved official platform API adapter
- an explicit manual import with source URL and rights basis

Social OAuth tokens, browser cookies and connected-account sessions remain in
the CRM connector boundary. They are never copied into the crawler or an AI
provider payload.

## Research graph and context

SQLite stores de-duplicated `person`, `company`, `source_page` and
`social_profile` entities plus `WORKS_AT`, `MENTIONED_ON`,
`HAS_SOCIAL_PROFILE` and `INTERACTED_WITH` relationships. Each entity links to a
hashed evidence observation. Raw HTML and email addresses are not placed in the
graph.

This is the local context layer. Its `workspace_id` boundary allows the same
contract to move to a centralized multi-tenant graph later without changing the
discovery API.

## Exclusion and Apollo ledgers

Before review, discovery checks `old_pois`, previous accepted outputs, the data
directory, existing CRM contacts and earlier candidates in the same run.

Selecting **Queue for Apollo** writes a non-overwriting CSV to:

```text
local_data/poi_file_queue/inbox
```

Apollo only runs through the explicit enrichment command and its credit cap.
Accepted contacts automatically enter `old_pois/offsetx_auto_exclusion_ledger.csv`.
Every live reject/no-match/policy outcome also enters
`output*/offsetx_apollo_rejection_ledger.csv` and appears in the CRM.

The two ledgers are intentionally separate:

- accepted and hard-duplicate rows are permanent exclusions
- no-match/no-email outcomes block automatic credit reuse but allow a deliberate manual override
- credit-cap and target-cap rows remain retryable in a later run

## API

- `POST /api/v1/campaigns/{campaign_id}/discovery/runs`
- `GET /api/v1/campaigns/{campaign_id}/discovery/runs`
- `GET /api/v1/discovery/runs/{run_id}/candidates`
- `POST /api/v1/discovery/runs/{run_id}/decision`
- `POST /api/v1/discovery/runs/{run_id}/apollo-queue`
- `POST /api/v1/campaigns/{campaign_id}/discovery/runs/{run_id}/import`
- `GET /api/v1/research/graph`
- `POST /api/v1/research/interactions`
- `GET /api/v1/apollo/rejections`
- `GET /api/v1/apollo/exclusions`
