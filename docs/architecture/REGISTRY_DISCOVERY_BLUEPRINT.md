# Registry discovery — the account universe from public registers

**Blueprint, not built.** Written 2026-09-17. Proposed stories are named at the
bottom; none is on `BOARD.md` yet. Read
[`docs/research/COMPETITOR_THROXY.md`](../research/COMPETITOR_THROXY.md) for why
this exists.

---

## Read this first: this is not a crawl, and `discovery.py` is the wrong entry point

The request that produced this document was "point `discovery.py` at Companies
House". **Do not do that.** It would be slower, more fragile, and worse-mannered
than the alternative, for one reason:

> Companies House publishes a **free monthly CSV snapshot of every live company**
> and a **free JSON API** for officers and beneficial owners.

`discovery.py` is a guarded HTML crawler. Pointing an HTML crawler at a service
that hands you the same data as structured CSV and JSON means parsing rendered
pages that can change layout, at one request per 0.75s, to obtain records you
could have downloaded in one ZIP. It also burns someone else's web servers for
no reason, which is the thing `CrawlPolicy` exists to avoid.

**So the shape is:**

```
   registry/          ← NEW. An API + bulk-file client. No crawling.
       ↓  company universe, SIC-filtered, with named officers
   discovery.py       ← EXISTING. Crawls the company's OWN website
       ↓              for the one thing the register never holds: an email
   DiscoveredPerson   ← EXISTING contract. Unchanged.
```

The crawler keeps a real job, and it is the job it is good at. The register
gives you *which company and which human*. The company's own website gives you
*how to reach them*. Neither source can do the other's half.

---

## Why this is worth building

Throxy reached a reported $1.5M ARR selling into manufacturing and logistics on
exactly this insight. Their co-founder, in interview:

> "Every single country has company registers. Every single company also has
> directors, and all that information is publicly available and you can download
> it. Yet at my previous companies, we were not using that."

Two properties make registry data strategically different from Apollo data.

**It is a different population.** Apollo, ZoomInfo, Clay and every waterfall
built on them index the digitally visible — people with LinkedIn profiles,
companies with marketing sites. A 40-person injection-moulding firm with a
two-page website and an owner who has never posted on LinkedIn is invisible to
all of them, and is fully documented in a national register with the director
named, the address given, and the accounts filed.

**It does not decay.** Roughly 30–40% of B2B contact records go stale each year,
which is the entire reason waterfall enrichment exists. In traditional
industries tenure runs to decades — a director recorded in 2011 is often still
the director. A registry-derived list *appreciates* relative to a rented one,
because the rented one is re-sold to everyone and re-verified against the same
decaying sources.

For off_CRM specifically: this is the first data strategy found in five
competitor teardowns that a single person can execute without a vendor contract.

---

## What Companies House actually gives you, and what it does not

Verified against the live service on 2026-09-17.

### Source A — the Free Company Data Product (bulk)

`download.companieshouse.gov.uk` · ZIP of CSV, split into several files ·
**free, no key, no rate limit** · refreshed within 5 working days of month end ·
explicitly unsupported.

Every **live** company on the register. Per row: company number, name, status,
registered office address, incorporation date, company type, up to four **SIC
codes**, accounts and returns dates, and a URI link to the API record.

This is the account universe. It is the cheapest high-value corpus in B2B data
and it costs one HTTP GET a month.

### Source B — the Public Data API (targeted)

`api.company-information.service.gov.uk` · free API key · **600 requests per
rolling 5 minutes**, then `429` for the remainder of the window.

Endpoints that matter here:

| Endpoint | Gives you |
|---|---|
| `GET /company/{number}` | Full profile, current address, SIC codes, status |
| `GET /company/{number}/officers` | **Named directors and secretaries**, appointment dates, role, nationality, partial DOB, resignations |
| `GET /company/{number}/persons-with-significant-control` | Beneficial owners — often the actual decision-maker in an owner-operated firm |
| `GET /advanced-search/companies` | Filter by SIC code, incorporation date, status. **Capped at 10,000 results.** |
| `GET /search/officers` | Officer name search across the register |
| `GET /company/{number}/filing-history` | Filing cadence — a weak but real activity signal |

### What the register never contains

**No email address. No phone number. No website.** Not once, anywhere, for any
company. This is the single most important constraint in this document and it
determines the whole architecture: the register identifies a *person at a
company*, and finding a way to contact them is a separate problem that
`discovery.py` already solves.

Also absent: employee count, revenue, technology stack, and any behavioural
signal. Small companies file abridged accounts with almost nothing in them.

### The arithmetic that forces the design

The bulk file holds roughly 5.4 million live UK companies. The API permits 120
requests per minute, so about 172,000 officer lookups per day at a perfect duty
cycle.

Enriching the whole register with officers would take **roughly a month of
continuous, maximum-rate API traffic**. Filtering first by SIC code to one
vertical reduces 5.4 million to a few thousand.

**Therefore: filter on the free bulk file, then enrich the survivors over the
API.** This is not an optimisation. It is the only order that works — and it
happens to be exactly the order Throxy describes on their lead-finding page:
*"We qualify accounts before we find people."*

---

## The design

### New package: `offsetx_apollo_builder/registry/`

```
registry/
├── __init__.py
├── sources.py     the registry catalogue, as DATA not code (see below)
├── bulk.py        download, verify, stream-parse the monthly CSV snapshot
├── companies_house.py  the API client: officers, PSC, profile, advanced search
├── sic.py         SIC code sets per vertical, declared as data
├── budget.py      the 600-per-5-minutes window, file-backed
├── normalize.py   registry row + officer record -> DiscoveredPerson
└── store.py       the company universe, its officers, and refresh state
```

Seven modules. `bulk.py` and `companies_house.py` are the only two that touch
the network.

### `sources.py` is a catalogue, not a client

Every other country has a register too, which is the whole point of the
strategy, and the repo already has the right pattern for this:
`config/providers.yaml` makes adding an AI provider a config edit rather than a
code change (§4E). Do the same here.

```yaml
# config/registries.yaml
uk_companies_house:
  jurisdiction: GB
  licence: ogl-v3            # Open Government Licence
  bulk:
    url: http://download.companieshouse.gov.uk/en_output.html
    format: csv_zip
    cadence: monthly
  api:
    base: https://api.company-information.service.gov.uk
    auth: http_basic_key
    budget: {requests: 600, per_seconds: 300}
  officers: true
  psc: true
  contact_details: false     # the register never has an email. State it.
```

A second jurisdiction is then a YAML block plus a parser, and the parser is the
only code. Do **not** write a `CompaniesHouseDiscoveryService`; write a
`RegistrySource` that Companies House is one instance of.

### The output contract does not change

`normalize.py` returns the existing `DiscoveredPerson` from `discovery.py`.
Nothing downstream learns that registries exist:

| `DiscoveredPerson` field | From the register |
|---|---|
| `full_name` | Officer `name`, reordered from `SURNAME, Forename` |
| `first_name` / `last_name` | Split from the officer record's own parts |
| `company` | Bulk CSV `CompanyName` |
| `company_domain` | **Empty.** Resolved later by `discovery.py`, or never. |
| `title` | Officer `officer_role` — `director`, `secretary`, `llp-member` |
| `country` | `jurisdiction` from the source, plus officer `nationality` |
| `email` | **Always empty from this path.** |
| `public_hook` | Composed: SIC description, incorporation year, appointment date |
| `confidence` | See the confidence rule below |
| `evidence` | `{source: "uk_companies_house", company_number, officer_link, snapshot_month, fetched_at}` |

`evidence` carrying `snapshot_month` is not decoration. It is how a record dated
2011 can be trusted in one vertical and distrusted in another, which is the
entire strategic premise.

### The confidence rule, stated once

A registry record is *authoritative about the appointment* and *silent about
everything else*. Encode that rather than guessing a number:

- Officer **currently appointed**, company **active** → `0.9`
- Officer currently appointed, company **dormant or in liquidation** → `0.4`
- Officer **resigned** → `0.0`, and do not emit the record at all
- Any field inferred rather than read (a role mapped to a seniority band, a
  guessed email) → cap the record at `0.5`

A resigned director is the classic registry trap: the API returns them by default
in the same list as current officers. Filter on `resigned_on` being absent, and
write a test that a fixture containing one resigned and one active officer emits
exactly one person.

---

## Where the existing code is reused, and where it must not be

### Reused

| Existing | How |
|---|---|
| `DiscoveredPerson` | The output contract, unchanged. |
| `discovery_duplicate()` | Dedupe registry-sourced people against Apollo-sourced people. Two paths to one human must collapse. |
| `validate_public_url()` | Applied to every URI followed out of a registry record — the register contains third-party URIs and an SSRF guard is still an SSRF guard. |
| `DomainRateLimiter` | The shape is right; the window is different. `budget.py` wraps it for 600-per-300-seconds rather than a per-request delay. |
| `PublicWebCrawler` | **Stage 2 only.** Given a company name and registered address, crawl that company's own site for a contact address. This is what the crawler is for. |
| `intake.py` | A registry-derived list is a campaign input like any other, and `intake.py` already sits deliberately outside `ai/` because a contact list must never reach a model. That boundary holds here unchanged. |

### Must not be reused

**Do not route registry fetches through `SafePublicFetcher` or
`Crawl4AIPageFetcher`.** Both exist to fetch untrusted third-party HTML under a
robots policy. The Companies House API is a first-party JSON API with a licence,
an API key and a published rate limit. Putting it behind the crawler would apply
the wrong controls (robots.txt on an API), miss the right one (the 5-minute
request window), and parse JSON with an HTML parser.

**Do not put the registry behind `ai/broker.py`.** The broker is the egress gate
for *models*. Companies House is a data source, not a model, and the governing
rule — models never pull, off_CRM pushes — is unaffected: registry data enters
off_CRM, and only an allowlisted payload built by `ai/payload.py` ever leaves it.
Worth stating explicitly in the module docstring so a later session does not
"fix" it.

---

## The two-stage pipeline

```
STAGE 1 · THE UNIVERSE                                  free, monthly, no key
  bulk.py downloads the CSV snapshot, verifies size and header, streams rows
  sic.py filters to the vertical's SIC set
  store.py writes the surviving companies as the account universe
  -> a few thousand companies from 5.4 million, at zero API cost

STAGE 2 · THE PEOPLE                                    600 req / 5 min
  companies_house.py calls /officers for each company in the filtered set
  budget.py refuses the call that would cross the window, rather than eating a 429
  normalize.py emits DiscoveredPerson for each currently-appointed officer
  -> named humans, no email

STAGE 3 · THE CONTACT ROUTE                             the existing crawler
  discovery.py resolves the company's website, then crawls it under CrawlPolicy
  for a public contact address
  -> email where one is published; otherwise the record stands without one,
     which is what the phone is for
```

Stage 3 is where this honestly runs out. The register gives you a named director
at a named company with a postal address and no email. Throxy's answer to that
gap is 3.6 million cold calls. off_CRM has no calling capability at all, so a
registry-derived list is, today, a list off_CRM cannot fully act on. **Build
stages 1 and 2 anyway** — the account universe is independently useful for ICP
scoring and for Apollo lookups that currently start from nothing — but do not
pretend the loop closes.

---

## Legal and licensing, because this is personal data

- **Licence.** Companies House data is published under the **Open Government
  Licence v3.0**. Commercial reuse is permitted with attribution. Record the
  licence in `config/registries.yaml` per source and put the attribution string
  in the export, not in a comment.
- **It is still personal data.** A named director with a partial date of birth
  and a correspondence address is personal data under UK GDPR and the DPDP Act,
  and "it was public" is not a lawful basis. The lawful basis for B2B outreach
  is legitimate interests, which requires a balancing test and an honest
  retention period. Write both down.
- **Do not store the partial DOB.** The API returns month and year for natural
  officers. off_CRM has no use for it and storing it raises the sensitivity of
  the whole table for nothing. Drop it at the `normalize.py` boundary and assert
  in a test that it never reaches the store.
- **Use the registered office, not the residential address.** The API
  distinguishes these. Only the service address is intended for correspondence.
- **PPS and protected officers.** A small number of officers have their details
  suppressed for personal safety and appear as "super secure". Never attempt to
  resolve these, and skip them explicitly rather than by accident.
- **Identity verification flags.** Since late 2025, under ECCTA, records
  increasingly carry whether a director has completed Companies House identity
  verification. A verified director is a stronger record. Read the flag; do not
  depend on it being present yet.

---

## Traps, all of which will otherwise be found by hand

1. **Resigned officers come back in the same list.** Filter on `resigned_on`.
   Test with a fixture holding both kinds.
2. **`SURNAME, Forename` order.** The API returns officer names surname-first,
   uppercased. Reordering naively produces "Smith John" in emails. Use the
   record's own `forenames`/`surname` parts where present, and never
   title-case a name containing an apostrophe or a hyphen without testing it.
3. **Corporate officers are not people.** `officer_role` includes
   `corporate-director`. A company can be a director of a company. Emitting one
   as a `DiscoveredPerson` produces an email addressed to a holding entity.
4. **The bulk snapshot is live companies only.** A company dissolved mid-month
   is absent, and a company dissolved the day after the snapshot is present and
   wrong. Re-check status over the API before any send, not at list-build time.
5. **SIC codes are self-declared and often lazy.** `82990` — "other business
   support service activities" — is the dustbin. A SIC-only filter will be both
   noisy and incomplete; treat the code as a first pass, not as ground truth.
6. **10,000-result cap on advanced search.** Any vertical broader than that
   silently truncates. This is a second reason to filter on the bulk file
   instead, where there is no cap.
7. **The 429 is a 5-minute penalty box, not a retry-after-a-second.** Exceed the
   window and every further request in it fails. `budget.py` must refuse
   *before* the call, the way `ai/quota.py` already refuses before a model call.
8. **The monthly file is unsupported.** Its columns have changed historically.
   Verify the header row against a declared schema and fail loudly on a
   mismatch rather than silently mapping the wrong column.

---

## Test plan

Mirroring the repo's existing standard — deterministic fixtures, no live calls
in the default suite.

| Test | Asserts |
|---|---|
| `test_bulk_header_schema` | A snapshot whose header differs from the declared schema raises, not warns. |
| `test_bulk_streams_without_loading` | A 200MB fixture parses with bounded memory. |
| `test_sic_filter_declared` | The vertical's SIC set comes from data; an unknown code is refused, not silently dropped. |
| `test_resigned_officer_excluded` | Fixture with one active and one resigned officer emits exactly one person. |
| `test_corporate_officer_excluded` | A `corporate-director` emits no person. |
| `test_name_reordering` | `O'NEILL, Seán Patrick` becomes `Seán Patrick O'Neill`. |
| `test_dob_never_stored` | Partial DOB is absent from every stored row, asserted against the schema. |
| `test_super_secure_skipped` | A protected officer is skipped with a recorded reason. |
| `test_budget_refuses_before_429` | The 601st request in a window raises locally; no HTTP call is made. |
| `test_email_always_empty_from_registry` | No registry path can populate `email`. |
| `test_confidence_rules` | Each of the four confidence cases produces its stated value. |
| `test_dedupe_against_apollo` | The same human from Apollo and from the register collapses to one record via `discovery_duplicate()`. |
| `test_registry_not_behind_broker` | An AST test that `registry/` does not import `ai.broker` — the same style of invariant test the repo already uses. |
| `test_live_companies_house` | Marked, environment-gated, one real call. Skipped without a key. |

---

## Proposed stories

These belong in the E-05 crawler epic, beside `S-05.01.01` (a crawler with a
frontier) and `S-05.01.02` (extraction packs as declared data), which this
extends rather than duplicates.

- **`S-05.03.01` · The company universe from a free bulk register.** `bulk.py`,
  `sic.py`, `store.py`, `config/registries.yaml`. No API key needed. Ships a
  filtered account universe for one vertical.
- **`S-05.03.02` · Named officers, inside a request budget.**
  `companies_house.py`, `budget.py`, `normalize.py`. Emits `DiscoveredPerson`.
  Depends on `S-05.03.01`.
- **`S-05.03.03` · A registry is a row, not a code change.** Second jurisdiction
  added by config plus one parser, proving the catalogue shape. Depends on
  `S-05.03.02`.
- **`S-05.03.04` · Contact resolution from the company's own site.** Wires stage
  2 output into the existing `PublicWebCrawler`. Depends on `S-05.03.02` and on
  `S-05.01.01`.

`S-05.03.01` is the one worth doing first and alone: it is free, keyless,
network-light, and produces something useful on its own.

---

## What this blueprint will not pretend

- **A registry list is not a contactable list.** No emails, no phones, ever. The
  gap is real and off_CRM currently has no phone channel to close it with.
- **Companies House is one country.** The strategy generalises because registers
  are universal; the *implementation* does not, because every register has its
  own format, licence and access rules. Germany's Handelsregister, India's MCA
  and the US state-by-state patchwork are each their own story, and the US is
  the worst of them.
- **This does not make off_CRM competitive with Throxy.** They pair registry
  data with 3.6 million dials and a human SDR team. This blueprint reproduces
  the data half of their advantage, which is the half that can be built by one
  person.
- **SIC-code targeting is weak.** A serious version of this needs classification
  from the company's own website — which is `S-05.01.02`, extraction packs, and
  is why that story matters more after this one than before it.
