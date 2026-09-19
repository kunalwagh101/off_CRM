# S-05.01.02 — Extraction packs as declared data

## Problem and success measure

Today `ScraplingPageParser` has one generic extraction path: JSON-LD Person
objects. A site that exposes useful public people data only in ordinary HTML
would require another Python parser. That makes each source a deployment.

Success is simple: add a new supported public source by adding validated data,
with no Python change. The existing crawler safety boundary must remain exactly
where it is.

## Baseline and rejected alternatives

The baseline is the existing JSON-LD parser. It remains the fallback and is not
rewritten.

Rejected:

- one Python parser class per source — works, but every source becomes code;
- arbitrary expressions/Jinja/Python in config — turns configuration into an
  unreviewed execution surface;
- an LLM extractor — higher cost/latency, nondeterministic fields, and no need
  for AI when the page already has stable DOM structure;
- remote pack downloads — creates a supply-chain path that is not required.

## Smallest production design

Add one standard-data registry, loaded from a repository-controlled JSON file.
JSON is deliberate: Python already provides a strict parser, so no dependency
is added.

Each pack is a row with:

- stable `id`;
- one or more exact/parent domains;
- one CSS `record_selector`;
- a bounded map of normalized person fields to extraction rules;
- each extraction rule is either text or one named HTML attribute.

Allowed normalized fields are limited to the current `DiscoveredPerson`
contract. Unknown fields or modes fail registry loading.

No pack can contain code, JavaScript, templates, network locations, callbacks
or dynamic imports.

## Data flow

```text
public URL
  -> existing validate_public_url / robots / SSRF / frontier
  -> Scrapling page
  -> matching extraction pack?
       yes -> bounded card/field extraction -> DiscoveredPerson[]
       no  -> existing JSON-LD Person extraction
  -> existing dedupe / scoring / research graph / discovery store
```

The pack does not decide whether a URL is safe to fetch. It only sees a page
after the existing safety path has fetched it.

## Validation and failure behaviour

Registry load is all-or-nothing. Before a pack is usable, validate:

- non-empty unique pack id;
- normalized non-empty domains;
- one record selector;
- only allowed person fields;
- extraction mode in `text | attr`;
- `attr` names limited to ordinary data/link attributes needed by the current
  model;
- bounded selector/field string sizes;
- no two packs claiming the same effective domain at the same precedence.

A bad pack raises a clear configuration error before parsing any page. There is
no partial registry.

## Test strategy

The acceptance proof should include:

1. a fixture site extracted entirely from a JSON pack;
2. the same source added by editing only the pack file;
3. invalid/duplicate/unknown rules fail closed;
4. an unmatched domain still uses the existing JSON-LD path;
5. session-gated/off-domain URLs never reach pack selection;
6. regression against existing discovery tests.

## Migration and rollback

No CRM schema migration. The pack file is additive.

Rollback is removing the pack row. Existing JSON-LD extraction continues to
work. Stored discovery records are unchanged.

## Known limits

This is deterministic DOM extraction, not semantic understanding. If a site
changes its DOM, its pack can stop matching and should produce no fabricated
person. S-05.01.03 owns competitor-content structure analysis.
