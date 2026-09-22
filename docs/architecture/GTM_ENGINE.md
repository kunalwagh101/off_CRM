# The GTM engine — ProductTruth and the strategy brain

*Epic `E-12`. Phase 1 (`F-12.01`) and Phase 2 (`F-12.02`) of the path in
`GTM_ENGINE_GAP_ANALYSIS.md`. Written 2026-09-22, before the code, so that a
session that lost its context — or a smaller model handed one work order — can
build from this file alone.*

---

## 1. What this is, in one loop

```
owner writes the product once            (ProductTruth, S-12.01.01)
        │
        ├──► email templates and post captions use it   (S-12.01.02)
        │
owner sets a goal ──► the brain drafts a plan            (S-12.02.01)
        │               checked against a closed vocabulary
        │               and against what is actually connected
        ▼
owner presses Apply ──► paused campaigns, nothing sends  (S-12.02.02)
        │
        ▼  (the existing screens run them: contacts, drafts, approvals)
owner presses Review ──► diagnosis from real numbers,     (S-12.02.03)
        │                 in a fixed order: pipe before copy
        ▼
owner presses Revise ──► plan v2 written against the     (S-12.02.04)
                          measured numbers; Apply updates
                          the same campaigns
```

That loop is the whole milestone. It closes: every screen leads somewhere, and
the brain's second plan is written from what its first plan actually did.

---

## 2. The rules this module does not bend

Each one is enforced by a test, not by a comment.

1. **The model picks from a list; it never invents a plan shape.** The same rule
   `video/director.py` applies to recipes and `ai/tools.py` applies to tools.
   A model asked for a campaign structure emits invalid ones; a model asked to
   choose a channel from four and write two sentences does a job it is good at,
   and the answer is small enough to check completely. `parse_plan` and
   `parse_remedies` treat the reply as **untrusted input**.
2. **A required choice outside the vocabulary refuses. An optional preference
   outside it is dropped and named.** An unknown channel kind or audience source
   refuses the plan by name. An unknown platform, size band or recipe family is
   removed and a note says so.
3. **No owner text ever travels in a system prompt.** The broker does not scan
   or log the system prompt — only the payload (`D-81`). So `gtm` system prompts
   are built from code and registries only, and every word of the product
   travels in an `EgressRequest` field the payload builder governs.
4. **Product details go where the owner's policy says they may.** One-liner in
   `positioning_line` (leaves at `pseudonymous` and above). Everything else in
   `campaign_notes` (leaves at `standard` and above). Data class `campaign`, so
   tier C and D refuse it outright. Never smuggled into `instructions` to get
   round a policy — that would make the owner's per-provider choice meaningless.
5. **The deterministic checks are the gate; the model only proposes.** Volume is
   clamped to real capacity. Forbidden claims are removed by phrase match. A
   remedy the diagnosis does not permit is dropped. No model output reaches a
   campaign without passing code.
6. **Nothing sends by itself.** Apply creates campaigns **paused**. Contacts,
   draft approval and resuming stay with the owner, on the screens that already
   do them.
7. **The pipe before the copy.** The review diagnoses in a fixed order and stops
   at the first thing that is wrong. Bouncing mail is never answered with "rewrite
   the email".
8. **No verdict without enough data.** Below the sample floor the answer is
   "wait, and here is how long". A threshold on 12 sends is a coin toss.
9. **With no permitted model, it still works.** The rules-based plan and the
   rules-based remedies are the baseline the model has to beat, and they are what
   the owner gets when no tier A or B model is connected — with a note that says
   so.
10. **`gtm` owns no transport.** `ask` is injected, exactly as the director's is.
    A structural test walks every `gtm` module and fails on any import of the
    broker, a provider, or a network library.

---

## 3. Module map and seams

```
offsetx_apollo_builder/gtm/
├── __init__.py
├── products.py   ProductTruth: fields, validation, forbidden-claim matching.
│                 Pure. No database, no AI, no network.
├── store.py      GtmStore — owns gtm_products, gtm_campaign_links, gtm_plans,
│                 gtm_reviews. The only code that touches those tables.
├── strategy.py   The vocabulary, the envelope, the prompt, parse_plan,
│                 baseline_plan, feasibility. Pure; `ask` is a parameter.
├── review.py     diagnose() in a fixed order, the remedy table,
│                 parse_remedies, baseline_remedies. Pure.
└── service.py    GtmService — the only stateful orchestrator. Talks to other
                  modules through callables injected by the API, never through
                  their tables.

offsetx_apollo_builder/api/gtm.py   build_gtm_router() — the HTTP surface.
frontend/src/pages/Product.tsx      the product screen.
frontend/src/pages/Strategy.tsx     goal → plan → apply → review → revise.
```

**The seam rule.** `gtm` never reads or writes a table it does not own. It reads
campaigns through `campaign_summary()`, delivery health through `health()`,
identities through `list_identities()`, accounts through `list_accounts()`,
metrics through `latest_metrics()`. It creates campaigns through
`create_campaign()` and `update_campaign()`. Every one of those arrives as an
injected callable, so the service is testable with plain functions and can be
lifted out the way `ai/` can.

**Who reads the product, and how.** `outreach/email_expert.py` and the post
pipeline never import `gtm`. They receive a `product_reader(campaign_id)`
callable. `outreach/engine.py` and `outreach/automation.py` stay free of `ai/`
imports (AGENTS.md rule 7) — `gtm` is not `ai/`, and they do not import it
either.

---

## 4. Data model

All four tables are owned by `GtmStore`, opened through `open_database()` so
Postgres works the same way it does for distribution and video.

```sql
gtm_products (
  id TEXT PRIMARY KEY, workspace_id TEXT NOT NULL,
  name TEXT NOT NULL, one_liner TEXT NOT NULL, audience TEXT NOT NULL,
  problem TEXT NOT NULL, outcome TEXT NOT NULL DEFAULT '',
  offer TEXT NOT NULL,
  proof_json TEXT NOT NULL DEFAULT '[]',
  differentiators_json TEXT NOT NULL DEFAULT '[]',
  forbidden_claims_json TEXT NOT NULL DEFAULT '[]',
  voice TEXT NOT NULL DEFAULT '', website TEXT NOT NULL DEFAULT '',
  version INTEGER NOT NULL DEFAULT 1,
  created_at TEXT NOT NULL, updated_at TEXT NOT NULL
)

gtm_campaign_links (
  campaign_id TEXT PRIMARY KEY,          -- one product per campaign
  product_id TEXT NOT NULL, workspace_id TEXT NOT NULL,
  plan_id TEXT NOT NULL DEFAULT '',      -- set when Apply created it
  channel TEXT NOT NULL DEFAULT '',      -- email | image | distribution
  created_at TEXT NOT NULL
)

gtm_plans (
  id TEXT PRIMARY KEY, workspace_id TEXT NOT NULL, product_id TEXT NOT NULL,
  root_id TEXT NOT NULL, parent_id TEXT NOT NULL DEFAULT '',
  version INTEGER NOT NULL,
  status TEXT NOT NULL,                  -- draft | applied | superseded | discarded
  request_json TEXT NOT NULL,            -- the owner's goal, as validated
  product_snapshot_json TEXT NOT NULL,   -- copied, never looked up later
  product_version INTEGER NOT NULL,
  envelope_json TEXT NOT NULL,           -- capacity when drafted
  plan_json TEXT NOT NULL,               -- the validated plan
  feasibility_json TEXT NOT NULL,
  notes_json TEXT NOT NULL,              -- every correction, in words
  source TEXT NOT NULL,                  -- model | rules
  provider_id TEXT NOT NULL DEFAULT '', model_id TEXT NOT NULL DEFAULT '',
  policy TEXT NOT NULL DEFAULT '',
  created_at TEXT NOT NULL, applied_at TEXT
)

gtm_reviews (
  id TEXT PRIMARY KEY, plan_id TEXT NOT NULL, workspace_id TEXT NOT NULL,
  measurements_json TEXT NOT NULL,       -- exactly what was read
  findings_json TEXT NOT NULL,           -- one per channel, deterministic
  remedies_json TEXT NOT NULL,
  notes_json TEXT NOT NULL,
  source TEXT NOT NULL,                  -- model | rules
  provider_id TEXT NOT NULL DEFAULT '', model_id TEXT NOT NULL DEFAULT '',
  created_at TEXT NOT NULL
)
```

**Why the snapshot is copied.** The same call the video review queue made: a
plan read later must show the product it was written against, and the product
will have changed by then. `product_version` answers "is this plan stale?"
without a history table.

**Why reviews are kept, not overwritten.** They are the first labelled data this
product owns: what was planned, what was measured, what the brain concluded.
When a fine-tune finally happens (the owner's plan, deliberately last) it trains
on these rows. Deferring the adapter is right; deferring the labelling is not.

**Migration and rollback.** Four new tables, no change to any existing table.
Rollback is dropping them; nothing else reads them.

---

## 5. ProductTruth — fields and validation

| Field | Required | Bounds | Notes |
|---|---|---|---|
| `name` | yes | 1–80 | |
| `one_liner` | yes | 10–200 | the public pitch; the only field sent below `standard` |
| `audience` | yes | 10–600 | who it is for, in words |
| `problem` | yes | 10–600 | the pain, in the customer's words |
| `outcome` | no | ≤600 | what changes for them |
| `offer` | yes | 3–200 | the call to action |
| `proof` | no | ≤8 items, each 3–200 | customers, numbers, results |
| `differentiators` | no | ≤6 items, each 3–200 | |
| `forbidden_claims` | no | ≤20 items, each 2–120 | never said by anything this module writes |
| `voice` | no | ≤300 | tone |
| `website` | no | ≤300, `http(s)://host…` | |

Refusals, each a sentence naming the field and the fix:

- a required field missing or out of bounds;
- **an email address anywhere** — this text may be sent to a model, the scanner
  would block every call that carried it, and the owner would see a confusing
  refusal three screens later. Refused at the door instead;
- a website that is not `http` or `https` with a host;
- more list items than the bound.

Whitespace is collapsed, lists are de-duplicated case-insensitively.

**Forbidden-claim matching** (`find_forbidden(text, claims) -> list[str]`):
case-insensitive, whole-phrase, anchored on **alphanumeric lookarounds, not
`\b`**. `\b` never matches after `%`, which is exactly the bug that let the
margin leak through `ai/abstraction.py` (BUILD_STATE, abstraction defect 1). So
`100% uptime` matches "we promise 100% uptime." and `guaranteed` does not match
"unguaranteed".

Every update increments `version`.

---

## 6. The strategy brain

### 6.1 The owner's request (validated before anything else)

| Field | Bounds | Default |
|---|---|---|
| `product_id` | must exist in this workspace | — |
| `goal_kind` | `replies` \| `views` | — |
| `goal_target` | 1–100000 | — |
| `horizon_days` | 7–180 | 30 |
| `contact_budget` | 0–10000 new contacts (Apollo credits) | 0 |
| `channels` | subset of implemented kinds | all implemented |
| `assumed_reply_rate` | 0.001–0.5 | `ASSUMED_REPLY_RATE` |
| `per_identity_daily_cap` | 1–500 | `COLD_EMAILS_PER_IDENTITY_PER_DAY` |
| `notes` | ≤1000 | "" |
| `use_model` | bool | true |

**Why only `replies` and `views`.** They are the two outcomes this system can
measure per campaign today. Meetings and sign-ups are not linked back to the
campaign that earned them, so a plan aimed at them could never be reviewed —
a goal the loop cannot close is a dead end. (`DD-43`.)

### 6.2 The vocabulary — read from the registries at call time

| Choice | Values | Read from |
|---|---|---|
| channel `kind` | implemented kinds | `campaigns.implemented_kinds()` |
| audience `source` | `apollo_search`, `public_discovery`, `existing_contacts` | `strategy.AUDIENCE_SOURCES` |
| `company_sizes` | `1-10`, `11-50`, `51-200`, `201-1000`, `1001+` | `strategy.COMPANY_SIZES` |
| `platforms` | platform ids | `distribution.platforms.PLATFORMS` |
| `recipe_family` | `hook`, `list`, `story`, `montage`, `demo` | `video.recipes.RECIPE_FAMILIES` |
| `role` | `primary`, `support` | `strategy.ROLES` |
| `weekdays` | `weekdays`, `all` | `strategy.WEEKDAY_SETS` |

### 6.3 The envelope — capacity from what is actually connected

Computed by the service from injected readers, never by the model.

- **Email capacity** = active `targeted_outreach` identities × the per-identity
  cold cap. With no identity configured it assumes **one** mailbox and says so,
  so a plan still exists and the blocker is named. Identities whose SPF, DKIM,
  DMARC or alignment is not `pass` are counted and listed as blockers: preflight
  will refuse them at send time.
- **Post capacity** = Σ per connected account of `min(daily_cap or platform
  limit, platform limit)`; an account with neither counts as 1/day, the
  conservative end.
- **Apollo ready** = an Apollo key is present in the environment.

The plan never proposes more than the envelope. **Why the cold cap exists at
all:** automatic warm-up scheduling is not built (`EMAIL_DELIVERY.md` §236), and
the health threshold is per campaign rather than per identity (§237). Until both
exist, the ceiling on how hard one mailbox is pushed has to come from somewhere.

### 6.4 What the model is asked for

System prompt: `strategy.build_prompt()` — fixed text, the vocabulary rendered
from the registries, and the JSON shape. **No owner text.**

The request: `task_type="gtm_plan"`, data class `campaign`,
`positioning_line = one_liner`, `campaign_notes = product details + owner notes`,
`instructions = goal + capacity numbers + allowed channels` (code-authored).

```json
{
  "summary": "one or two sentences",
  "audience": {
    "description": "who, one sentence",
    "source": "apollo_search | public_discovery | existing_contacts",
    "titles": ["..."], "industries": ["..."],
    "company_sizes": ["11-50"], "regions": ["..."]
  },
  "channels": [
    {"kind": "email", "role": "primary", "angle": "...", "hypothesis": "...",
     "daily_volume": 30, "send_window": ["09:00", "17:00"],
     "weekdays": "weekdays", "timezone": "Europe/Berlin"},
    {"kind": "distribution", "role": "support", "angle": "...", "hypothesis": "...",
     "daily_volume": 1, "platforms": ["youtube"]},
    {"kind": "image", "role": "support", "angle": "...", "hypothesis": "...",
     "recipe_family": "demo"}
  ]
}
```

### 6.5 `parse_plan` — every rule, in the order it runs

| # | Rule | On failure |
|---|---|---|
| 1 | reply is JSON (fences unwrapped, leading prose read past) and an object | refuse |
| 2 | `channels` is a non-empty list of objects | refuse |
| 3 | each `kind` is a known kind | refuse, naming the known kinds |
| 4 | each `kind` is implemented and allowed by the owner | drop + note |
| 5 | a kind appears twice | keep the first + note |
| 6 | `image` with no `distribution` | drop + note (pictures exist to be posted) |
| 7 | no channel left | refuse |
| 8 | not exactly one `primary` | first becomes primary, the rest support + note |
| 9 | `audience.source` known | refuse, naming the known sources |
| 10 | size bands, platforms, family outside the vocabulary | drop + note |
| 11 | text fields: collapse whitespace, cut to bound | cut + note |
| 12 | email `daily_volume` in `1..email capacity` | clamp + note |
| 13 | distribution `daily_volume` in `1..post capacity` | clamp + note |
| 14 | `send_window` two `HH:MM`, start before end | default `09:00–17:00` + note |
| 15 | `weekdays` in the set | default `weekdays` + note |
| 16 | `timezone` loads in `zoneinfo` | campaign default + note |
| 17 | any text field contains a forbidden claim | **field removed** + note naming the claim |
| 18 | a field nobody asked for | ignored + named |

Email always goes out on the **`targeted_outreach`** stream. The model is not
offered the choice: contacts found by Apollo or discovery carry no recorded
permission, and `permission_marketing` requires one (`S-08.01.01`).

### 6.6 Baseline plan (rules, no model)

- `replies` goal → email primary; distribution support if allowed and an account
  is connected; image support only if distribution is present.
- `views` goal → distribution primary; image support; email only if the owner
  allowed it, as support.
- Angle = `one_liner`. Hypothesis = a fixed template over `audience`, `problem`
  and `offer`, cut to bound and checked for forbidden claims like any other text.
- Volume = full envelope capacity. Window `09:00–17:00`, weekdays.
- Source = `apollo_search` when Apollo is ready and `contact_budget > 0`, else
  `existing_contacts`.

### 6.7 Feasibility — arithmetic the owner can check by hand

For `replies`: `send_days = horizon_days × 5/7` (weekdays) or `× 1` (all);
`reachable = email daily_volume × send_days`, capped at `contact_budget` when the
source is Apollo; `expected = reachable × assumed_reply_rate`. Feasible when
`expected ≥ goal_target`; otherwise the gap and the three things that would close
it (more identities, a longer horizon, a better measured rate).

For `views`: **no estimate until 5 posts are measured** — the same floor
`distribution/pacing.py` steers by. Inventing a views-per-post number to fill the
gap would be a business rule nobody gave.

---

## 7. Apply

`POST /gtm/plans/{id}/apply`. Only a `draft` may be applied.

- **First version:** one campaign per channel through `create_campaign()`, then
  `update_campaign(status="paused")`. Email campaigns get `daily_send_limit`,
  window, weekdays, timezone, `experiment_hypothesis` and
  `approval_mode="each_message"`. A `views` goal on a distribution channel also
  gets `set_goal(metric="views", target, deadline)`. Each campaign is linked to
  the product and the plan.
- **A later version:** the campaigns linked to the root plan are **updated**, not
  duplicated — same contacts, same history. A channel new in this version is
  created; a channel dropped is paused, never deleted. The previous applied
  version becomes `superseded`.
- The response carries a **next-steps list**, each item naming the existing
  screen that does it (`#discovery`, `#contacts`, `#deliverability`, `#drafts`,
  `#campaigns`, `#posting`). Apply spends no Apollo credits and imports nobody.

---

## 8. Review — the fixed order

Measurements are read per linked campaign. One finding per channel: the **first**
row below that applies.

**Email**

| Order | Finding | When | Permitted remedies |
|---|---|---|---|
| 1 | `not_started` | campaign not `active` | `resume_campaign` |
| 2 | `no_contacts` | 0 contacts | `add_contacts` |
| 3 | `delivery_unhealthy` | health `breached` non-empty, or paused by health | `fix_list_quality`, `check_domain_authentication`, `reduce_volume` |
| 4 | `awaiting_approval` | drafts pending and fewer than half the expected sends | `approve_drafts` |
| 5 | `under_volume` | contacted < half of `daily_volume × send days elapsed` | `resume_campaign`, `raise_volume` |
| 6 | `insufficient_data` | contacted < 20 (`MIN_SENDS_TO_JUDGE`) | `wait_for_data` |
| 7 | `behind_target` | Wilson 90% upper bound < assumed rate | `test_new_angle`, `narrow_audience`, `change_offer`, `rewrite_weak_template`* |
| 8 | `ahead_of_target` | Wilson 90% lower bound > assumed rate | `hold`, `raise_volume` |
| 9 | `inconclusive` | otherwise | `wait_for_data`, `hold` |

\* only when the context layer reports a weak template.

`raise_volume` is **never** permitted while delivery is unhealthy — row 3 stops
the walk before row 5 or 8 can offer it. `inconclusive` says how many more sends
would tell a halving of the rate apart (`ai/bandit.sends_needed`).

**Distribution** reuses `distribution/pacing.decide()` rather than a second copy
of its arithmetic:

| Order | Finding | When | Permitted remedies |
|---|---|---|---|
| 1 | `no_account` | no connected account | `connect_account` |
| 2 | `not_started` | 0 posts published | `resume_campaign` |
| 3 | `insufficient_data` | pacing action `hold` | `wait_for_data` |
| 4 | `behind_target` | pacing action `raise` | `raise_post_rate`, `test_new_angle` |
| 5 | `ahead_of_target` | pacing action `lower` | `hold` |
| 6 | `on_track` | pacing action `on_pace` | `hold` |

**Image** has one finding, `supporting`, and no remedies — pictures are judged by
the swipe queue that already exists.

The model, when used, receives the findings and the permitted remedies per
channel (`task_type="gtm_review"`, data class `campaign`) and returns:

```json
{"summary": "...", "remedies": [
  {"channel": "email", "action": "test_new_angle",
   "why": "...", "proposal": "a new angle, one sentence"}]}
```

`parse_remedies` drops any action not permitted for that channel's finding, any
channel not in the plan, more than two per channel, and any proposal containing
a forbidden claim. With no model, each finding's first permitted remedy is used.

**Measured rates replace assumptions.** `revise` passes the email channel's
measured reply rate forward as the next version's `assumed_reply_rate` once
`contacted ≥ 20` — this is what "learns from where it went wrong" means in
checkable terms.

---

## 9. API contract

All under `/api/v1`. Errors are `{"error": code, "message": sentence}` with 404
(unknown id), 409 (wrong state), 422 (validation). No stack traces.

| Method | Path | Body | Returns |
|---|---|---|---|
| GET | `/gtm/products` | — | `{items: Product[]}` |
| POST | `/gtm/products` | ProductFields | `Product` (201) |
| GET | `/gtm/products/{id}` | — | `Product` |
| PATCH | `/gtm/products/{id}` | partial ProductFields | `Product` (version+1) |
| DELETE | `/gtm/products/{id}` | — | `{deleted: true}` |
| GET | `/gtm/products/{id}/campaigns` | — | `{items: Link[]}` |
| PUT | `/gtm/products/{id}/campaigns` | `{campaign_ids: string[]}` | `{items: Link[]}` |
| GET | `/gtm/envelope` | — | `Envelope` + vocabulary |
| POST | `/gtm/plans` | PlanRequest | `Plan` (201) |
| GET | `/gtm/plans?product_id=` | — | `{items: Plan[]}` |
| GET | `/gtm/plans/{id}` | — | `Plan` + latest review |
| POST | `/gtm/plans/{id}/apply` | — | `{plan, campaigns, next_steps}` |
| POST | `/gtm/plans/{id}/discard` | — | `Plan` |
| POST | `/gtm/plans/{id}/review` | `{use_model?: bool}` | `Review` (201) |
| POST | `/gtm/plans/{id}/revise` | `{use_model?: bool}` | `Plan` (201) |

---

## 10. Work orders

Operating shape: **solo** — one architect-tier model plans, writes the tests
first, then the code. The work orders below are what a session resumes from.

Every work order shares these FIXED decisions — do not re-decide them:
Python 3.10+, `from __future__ import annotations`, dataclasses, readable-sentence
errors, the store pattern of `distribution/store.py` (`open_database` +
`executescript(SCHEMA)`), the router pattern of `api/email_delivery.py`
(`build_*_router()` + `app.include_router`), the page pattern of
`frontend/src/pages/Deliverability.tsx` (`useResource`, `api.get/post/patch`),
and UI tests by `renderToStaticMarkup` in `frontend/src/components.test.tsx`.

**DO NOT TOUCH, in any work order:** `ai/broker.py`, `ai/payload.py`,
`ai/scanner.py`, `ai/tiers.py`, `outreach/engine.py`, `outreach/automation.py`,
`outreach/deliverability/*`, `video/director.py`, `distribution/pacing.py`, any
existing table's schema. If a work order seems to need one of them, stop and
report — do not widen the change.

### S-12.01.01 — The owner records the product once

- **Goal:** a product can be created, read, edited (version +1) and deleted over
  HTTP and on the Product screen; bad input is refused with a sentence.
- **Create:** `gtm/__init__.py`, `gtm/products.py`, `gtm/store.py`,
  `api/gtm.py`, `frontend/src/pages/Product.tsx`, `tests/test_gtm_products.py`.
- **Modify:** `api/app.py` (import, `app.state.gtm_store`, close on shutdown,
  `include_router`), `frontend/src/App.tsx` (page + nav row),
  `frontend/src/types.ts`, `frontend/src/components.test.tsx`.
- **Interfaces:**
  `validate_product(values: Mapping, *, partial: bool = False) -> dict`
  raising `ProductInvalid(field, message)`;
  `find_forbidden(text: str, claims: Sequence[str]) -> list[str]`;
  `GtmStore(database_path)` with `create_product(workspace_id, values) -> dict`,
  `get_product(product_id, workspace_id) -> dict` (KeyError),
  `list_products(workspace_id) -> list[dict]`,
  `update_product(product_id, workspace_id, changes) -> dict`,
  `delete_product(product_id, workspace_id) -> None`.
- **Done when:** criteria of S-12.01.01 each map to a named test in
  `tests/test_gtm_products.py`.

### S-12.01.02 — Everything that writes for a campaign uses its product

- **Goal:** a campaign linked to a product fills `{product_*}` placeholders in
  email templates, gets the product one-liner as its post angle when none is
  given, and a rendered email draft containing a forbidden claim is flagged.
- **Create:** `tests/test_gtm_product_wiring.py`.
- **Modify:** `gtm/store.py` (links), `api/gtm.py` (link endpoints),
  `outreach/email_expert.py` (optional `product_reader`, placeholders, audit
  flag), `distribution/automation.py` (optional `angle_resolver`),
  `api/app.py` (wire the reader and resolver; resolve the angle **before**
  `_pipeline` chooses its data class), `Product.tsx` (link checklist).
- **Interfaces:** `GtmStore.set_links(product_id, workspace_id, campaign_ids)`,
  `GtmStore.product_for_campaign(campaign_id, workspace_id) -> dict | None`;
  `LocalEmailExpert(store, *, product_reader=None)`;
  `ContentAutomationService(..., angle_resolver=None)`.
- **The trap to avoid:** resolving the angle inside the pipeline, after
  `_pipeline` has chosen `DataClass.PUBLIC` for an empty angle, would send the
  owner's positioning to tier C under a public label. The test for that case is
  `test_product_angle_is_resolved_before_the_data_class_is_chosen`.

### S-12.02.01 — A goal becomes a checked plan that fits what is connected

- **Create:** `gtm/strategy.py`, `gtm/service.py`,
  `frontend/src/pages/Strategy.tsx`, `tests/test_gtm_strategy.py`.
- **Modify:** `gtm/store.py` (plans), `api/gtm.py`, `api/app.py` (the `ask`
  closure: `EgressRequest(task_type="gtm_plan", data_class=CAMPAIGN, ...)`,
  `expect_json=True`; map `NoPermittedProvider` to the rules plan, never a 500),
  `App.tsx`, `types.ts`, `components.test.tsx`.
- **Interfaces:** `validate_request(values, *, implemented) -> PlanRequest`;
  `build_prompt() -> str`; `parse_plan(text, *, request, envelope, product) ->
  ParsedPlan`; `baseline_plan(*, request, envelope, product) -> ParsedPlan`;
  `feasibility(plan, request) -> dict`;
  `GtmService.draft_plan(workspace_id, values, *, ask=None) -> dict`.

### S-12.02.02 — An approved plan becomes paused campaigns

- **Modify:** `gtm/service.py` (`apply_plan`), `gtm/store.py`, `api/gtm.py`,
  `Strategy.tsx`. **Create:** `tests/test_gtm_apply.py`.
- **Interfaces:** `GtmService.apply_plan(plan_id, workspace_id) -> dict`
  using injected `create_campaign`, `update_campaign`, `set_goal`.

### S-12.02.03 — The brain says where it is going wrong

- **Create:** `gtm/review.py`, `tests/test_gtm_review.py`.
- **Modify:** `gtm/service.py` (`review_plan`), `gtm/store.py` (reviews),
  `api/gtm.py`, `api/app.py` (readers + `ask` with `task_type="gtm_review"`),
  `Strategy.tsx`.
- **Interfaces:** `diagnose(plan, measurements, *, min_sample, now) ->
  list[Finding]`; `permitted_remedies(finding) -> tuple[str, ...]`;
  `parse_remedies(text, *, findings, product) -> ParsedRemedies`;
  `baseline_remedies(findings) -> ParsedRemedies`.

### S-12.02.04 — A review becomes the next version of the plan

- **Modify:** `gtm/service.py` (`revise_plan`, apply-on-revision),
  `api/gtm.py`, `Strategy.tsx`. **Create:** `tests/test_gtm_revise.py`.

**Commands for every work order:**

```bash
uv run pytest tests/test_gtm_*.py -q
uv run ruff check --select E9,F63,F7,F82 .
uv run pytest -q                       # before and after; record both counts
cd frontend && npm test && npm run build
uv run python scripts/verify_board.py
```

**If blocked:** stop and report. Never invent a business rule, never widen the
scope, never edit a DO NOT TOUCH file.

---

## 11. Deliberately not built here

| Not built | Why | Where it lives |
|---|---|---|
| The video director using the product | its house style travels in the system prompt, which is neither scanned for data class nor logged (`D-81`) | `S-12.01.03` |
| Drafting against the expert corpus and the owner's winners | the "world data" half of the brain; needs its own eval cases first | `S-12.02.05` |
| Running Apollo from a plan | spends credits; Phase 5 compiles the audience into a search | `F-12.05` |
| Video in the email | Phase 3; the owner chose Google Drive storage (`Q-20`) | `F-12.03` |
| Driving Clay, Hunter, Mailchimp, Apollo as tools | the owner's GTM-engineer idea; its own milestone | `F-12.04` |
| Meetings and sign-ups as goals | nothing links them to the campaign that earned them | `DD-43` |
| Permission-marketing plans | a GTM plan is outbound; a newsletter is a different product | `DD-44` |
| A scheduler that reviews on its own | `S-06.01.04` routines, in flight on another branch | — |
