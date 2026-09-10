# S-11.02.04 — Run-scoped page-read cache

This story prevents an autonomous run from spending browser work on a page it has already captured, without turning caching into stale evidence or cross-run memory.

## Boundary

The cache belongs to `AgentRun`, not `browser.Page`.

A browser tab may outlive one logical run. If the cache lived on `Page`, a later run could inherit page text gathered under a different goal, schema or authorization context. Each run therefore starts with an empty cache and may reuse only evidence captured during that same run.

A successful `read` now stores its text as a private trace sidecar even when the caller did not request a structured result schema. The cache points at that original trace step. A hit:

1. does not call `Page.read`;
2. does not increment the browser-action count;
3. appends a `read_cache_hit` audit step;
4. returns the stored text to the next decision; and
5. for structured runs, keeps the original source step as provenance rather than manufacturing duplicate evidence.

The append-only trace remains the durable evidence record. The in-memory cache is only the run-time index that avoids duplicate work. Rebuilding run state after a process death belongs to S-11.01.03 and is not silently implemented here.

## URL identity

`canonical_page_url` is deliberately conservative. It strips only known analytics and advertising identifiers such as `utm_*`, `fbclid`, `gclid`, `msclkid`, `mc_cid` and similar parameters.

It does **not** drop generic names such as `source`, `ref`, `page`, `id` or arbitrary query parameters because those frequently select different application state. URL fragments are also preserved because hash-routed applications can render different screens at one path.

The target is zero duplicate reads, not aggressive URL collapsing.

## Invalidation

The same URL can represent different content after an interaction. A cache that survives that change is a correctness defect.

- `click`, `type`, `press`, `scroll`, `select` and `wait_for` invalidate the affected current-page identity because they may mutate or lazy-load content.
- `goto` and `back` invalidate the destination identity because navigation may reload newer content.
- `read` and `screenshot` do not mutate the page.

This means the story avoids redundant reads of an unchanged page while still allowing a legitimate re-read after the browser has done something that can change that page.

## Storage

A real page read is durable evidence under the run directory:

- `trace.jsonl` — append-only ordered metadata with stable step ids;
- `NNNN.txt` — private captured page text;
- `NNNN.png` — private screenshot when provenance requires one.

These files are audit/replay evidence, not a relational query store. `RunOutcome.record` and `RunOutcome.findings` are the structured return values. Cross-run relational indexing is a separate persistence concern and should preserve pointers back to these immutable evidence artifacts rather than replacing them.

## Proof gates

`tests/test_agent_page_read_cache.py` proves:

- an exact duplicate read invokes the browser only once;
- tracking-only URL variants share one read;
- functional query changes remain different pages;
- a page-changing action invalidates the cached read;
- structured results reuse the original provenance step and screenshot; and
- a real Chromium tab receives only one `Page.read` call across two model read decisions.
