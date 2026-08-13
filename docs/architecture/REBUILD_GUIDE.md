# Rebuild guide (§10)

How to rebuild this system by hand, from nothing, **without an AI assistant**,
and end up with the same security guarantee rather than something that looks
like it.

Written after the system exists, describing what is there — not a specification
that was implemented. Where the code and this document disagree, the code is
right and this document has a bug.

Facts as measured on 2026-08-10: `ai/` is 24 modules and 10,303 lines; the
package root adds 24 more; 663 Python tests pass, 1 skipped; 6 frontend tests;
33 tables across 6 named SQLite databases.

---

## Who this is for

Someone who has to reimplement off_CRM — different language, different company,
or the same one after a fire — and needs to know **what order to build it in**
and **which decisions are load-bearing**.

It is not an API reference. The modules document themselves; every file opens
with why it exists. This is the part that lives nowhere else: the sequence, the
reasons, and the mistakes that look like improvements.

---

## The one invariant

> **Models never pull. off_CRM pushes.**

A model receives a constructed payload and returns text. It never receives a
handle, a callback, a tool, a connector, a database cursor, a file path, or a
mailbox query.

A model that can *ask* for data has access to that data. A model that can only
*receive* a constructed payload does not. Every other rule in this document is
downstream of that one.

Corollary, from a real exchange with the owner:

> *"When you say the others can look but not touch — that's a problem. If
> they're looking, they are extracting the data."*

There is no looking. A model either receives a field or it does not.

---

## Stage order, and why it is this order

The order is not arbitrary and it is not about difficulty. **Each stage makes
the next one impossible to get wrong.** Build them out of order and the system
will work while being unsafe, which is the failure mode that does not announce
itself.

| # | Stage | Build it now because | Done when |
|---|---|---|---|
| 0 | Storage + models | Everything writes rows | `test_outreach_store` shape holds |
| 1 | **Trust tiers and data classes** | The vocabulary every later decision uses | `ai/tiers.py`, tables complete |
| 2 | **Payload construction** | The allowlist has to exist before anything can fill it | `PersonPublic` has no email field |
| 3 | **The scanner** | The thing that catches stage 2's bugs | Blocks and raises on 12 credential shapes |
| 4 | **The egress log** | You cannot audit calls you did not record | Stores the exact payload |
| 5 | **The broker** | The single gate — the only code that calls a provider | AST test: no module outside the allowlist imports a provider |
| 6 | Provider adapters | Now they can only be reached through the gate | Registry is config, not code |
| 7 | Quota + cost | Cheap routing that cannot override tier | Tier filter runs first |
| 8 | Run modes | Simple, verified, compare, orchestrated | Head model is tier A or B |
| 9 | Eval harness + scoreboard | Measurement, before optimisation | Unknown check kind *fails* |
| 10 | Verify loop | Uses stage 9's checks as the gate | Best attempt wins, not last |
| 11 | Context layer + bandit | Learning, once there is something to learn from | Code writes the summary, not a model |
| 12 | Cache | Only meaningful once payloads are stable | Keyed on the constructed payload |
| 13 | Sandbox + tool registry | Isolation before the first tool exists | `--network=none`, pinned SHA |
| 14 | Intake, exports, code graph | Peripheral; they consume the above | Each refuses what it must |

### The three orderings that matter most

**Stage 3 before stage 6.** Do not write a provider adapter until the scanner
and the log exist. If the adapter comes first you will call it directly to test
it, that call site will survive, and the "single gate" will have a second door
that nobody remembers.

**Stage 2 before everything.** Payload *construction* — building an outbound
object from an empty allowlist — has to be the first thing, because the
alternative is filtering, and filtering is a one-way door. Once code exists that
takes a CRM record and removes fields, every future field defaults to *sent*.

**Stage 9 before stage 10.** The verify loop's gate is the eval harness's
checks. Build the loop first and you will invent a second, weaker set of checks
inside it, and then measurement and enforcement will disagree — quietly, and in
the direction that makes the numbers look good.

---

## Stage detail

### Stage 1 — Trust tiers and data classes

Two axes, both required. **Jurisdiction alone is not enough.**

| Tier | Who | Ceiling |
|---|---|---|
| A | Europe, self-hosted | full |
| B | USA, Canada, allied | standard |
| C | China, *and anything demoted for weak data terms* | pseudonymous |
| D | Routers, aggregators, anything unlisted | strict — receives nothing |

Google's free tier is US-based and sits at **C**, because its terms permit
training on submitted content. That single row is the reason the second axis
exists; without it the tier table is a map and not a policy.

Data classes: `PUBLIC`, `PERSON_PUBLIC`, `CAMPAIGN`, `INTERNAL`, `MAILBOX`.
Policies, least to most: `strict`, `pseudonymous`, `minimal`, `standard`,
`full`.

**Tier belongs to the model, not to the key.** One NVIDIA key reaches Llama
(tier B) and DeepSeek (tier C). Getting this wrong is not theoretical: it was a
live bug here — the chosen model was stored, displayed, and then ignored at
resolution time, which made the provenance cap unreachable from the UI.

### Stage 2 — Payload construction

Build outbound objects **from an empty allowlist**, never by filtering a record.

The structural expression of this: `PersonPublic` has **no email field at all**.
Not an excluded one — absent. An address cannot arrive through the person path
because there is nowhere for it to sit.

Filtering fails open. Construction fails closed. That is the whole argument.

### Stage 3 — The scanner

Runs on the constructed payload, immediately before the call. Catches addresses,
owner domains, 12 credential shapes, mail headers, internal field names,
environment variables, local paths.

**It blocks and raises. It never redacts.**

A hit means the *builder* has a bug. Redacting and continuing hides that bug
forever, and the next payload leaks whatever the redactor did not anticipate.
The scanner is a smoke alarm, not a filter.

### Stage 5 — The broker

The only code in the system that calls a provider. Enforced by an AST test
that parses **every** file in the package and fails if any module outside a
three-file allowlist imports a provider constructor:

| Allowed to import a provider | Why |
|---|---|
| `outreach/providers.py` | The adapters themselves |
| `ai/broker.py` | The gate |
| `outreach/provider_profiles.py` | Pre-AI-module path; a second test asserts it only ever returns providers wrapped in a policy guard |

The allowlist is the point. When the test fails the fix is to route the new
caller through the broker — not to add a fourth line to the list.

Order inside `plan()` is load-bearing:

```
1. tier filter      ← FIRST. Cost cannot override it.
2. quota filter
3. same-tier-only failover chain
4. build_payload()  ← construct from empty
5. scan_payload()   ← block and raise
6. provider.generate
7. log.record()     ← provider, tier, exact payload, timestamp
```

Put cost before tier and a cheap tier-C model gets campaign data on a busy day.
Failover must never cross a tier boundary: a fallback is not a downgrade of the
policy.

### Stage 9 — Eval harness

Deterministic checks, one seam shared by measurement and enforcement:
`checks_for(suite_id, path)`. Both the scoreboard and the verify loop call it.

**An unknown check kind fails.** If a suite names a check the runner does not
implement, the case fails rather than passes. A typo in a check name must not
turn into a green test.

Promotion requires three things together: higher mean, `p < 0.05` on an exact
binomial sign test, and cost within ceiling. Any one alone promotes noise.

### Stage 10 — Verify loop

Write → check → repair → review. Deterministic checks are the **gate**; a model
review only advises.

**The best attempt wins, not the last.** A repair can make things worse, and a
loop that returns its final attempt will happily return the worst one. Ties go
to the earlier round, because a later round costs more for the same quality.

---

## The traps

Every one of these is a real mistake — most of them made and fixed in this
repository. They share a shape: **each looks like a simplification and each
quietly removes a guarantee.**

| Trap | What actually happens |
|---|---|
| "Filter the record before sending" | Fails open. Every field added later is sent by default |
| "Redact the finding and continue" | Hides the builder bug that produced it. Next leak is one the redactor did not know about |
| "Let the model decide what is safe" | Policy in judgement instead of in code. Enforcement must be mechanical |
| "Sort candidates by cost, then check tier" | On a busy day the cheap untrusted model gets the data |
| "Fall back to the next provider on failure" | Failover across a tier boundary is a silent downgrade |
| "Return the last attempt from the repair loop" | Returns the worst draft whenever repair overshoots |
| "Unknown check kind → skip it" | A typo becomes a passing test |
| "One `PERSON_1` token for everyone" | An anonymised list with no distinctions is a list with the answers removed — useless, so someone turns it off |
| "Store the identity key next to the bundle" | People select-all and upload. Put it outside the folder |
| "Default an unrecognised value to the safe-looking one" | An unknown campaign kind read as `email` hands it to the mail sender |
| "Regex the `?` placeholders to `%s`" | Corrupts `?` and `%` inside string literals, invisibly, until someone reads the row back |
| "`lstrip('./')` to normalise a path" | Strips *characters*, not a prefix: `/home/x` → `home/x`, and the absolute-path check never fires |
| "Expose `--code-only` as a parameter" | Puts the source-code-to-a-model call one keystroke away, in someone's autocomplete |
| "Add the settings blob now, validate later" | An unvalidated blob with no writer becomes a dumping ground |
| "`SELECT *` for a cross-engine copy" | Column order is not guaranteed; a new column shifts every value one place left |

### The one about SQLite that bites in production

```sql
SELECT provider_id, provider_name, COUNT(*) FROM t GROUP BY provider_id
```

SQLite runs this and picks an **arbitrary row** for `provider_name`. Postgres
refuses it. If you build on SQLite only, queries like this pass tests for years
and are quietly wrong. Group by every non-aggregated column.

---

## Enforced by tests, not by discipline

These are architecture rules a reviewer cannot forget, because the build fails.
Reimplement them first — they are cheap and they hold everything else in place.

| Rule | How it is enforced |
|---|---|
| One egress gate | AST walk of every file: only 3 may import a provider constructor |
| A provider is never offered tools or retrieval | Payload keys checked, **and** the broker's source searched for `tool_choice`, `"tools"`, `function_call`, `mcp_servers` |
| Intake never reaches a model | AST walk of `intake.py` imports; it also lives outside `ai/` |
| Chat service never imports a provider | AST walk |
| Notebook export never reaches a transport | AST walk |
| Notebook export reads only 6 store methods | AST walk of `self.store.*`, pinned as a set |
| Code graph never runs the semantic path | Asserts `--code-only` in the argv; asserts it is *not* a parameter |
| Every campaign method checks the kind | AST source check, **plus** a second test that walks every public method taking a `campaign_id` and fails if one is unlisted |
| Tool images and SHAs are pinned | Registry refuses a branch, a tag, or a short SHA |
| Sandbox isolation flags | Every flag asserted individually |
| Packaged config matches source config | Byte-identical comparison |

The doubled test on campaign kinds is the pattern worth copying: **a list that
must stay exhaustive needs a second test that checks the list itself.**
Otherwise it silently stops being exhaustive the day someone adds a method.

---

## Data model

7 SQLite databases, 33 tables. They are separate files on purpose — the AI
module owns its own and can be lifted out without dragging the CRM schema along.

| Database | Owns | Opened by |
|---|---|---|
| `offsetx_outreach.db` | CRM: contacts, campaigns, drafts, messages, templates, discovery, research, sales | web app |
| `ai_egress.db` | The egress log — **also runs on Postgres** | web app |
| `ai_context.db` | Template stats, task state, decisions | web app |
| `ai_recall.db` | Redacted sent-mail index | web app |
| `ai_evals.db` | Eval runs and champions | `offsetx-evals` only |
| `ai_tools.db` | Tool registry and runs | `offsetx-tools` only |

The response cache has no database in this list because **nothing constructs
one**. `ResponseCache` is implemented and tested, the broker accepts one as an
optional argument, and no caller passes it. Build it in a rebuild if you want
the feature; do not spend time looking for the wiring, because there is none.

Dependency direction, which a rebuild must preserve:

```
ai/  →  outreach/models.py   (dataclasses)
ai/  →  outreach/providers.py (HTTP adapters)
ai/  →  db/                  (backend seam)
```

`ai/` depends on the CRM through **exactly those two seams**. Nothing in `db/`
knows about any specific table — the generic layer takes a table name and a
schema; the store supplies them.

`intake.py`, `campaigns.py`, `notebook.py` and `codegraph.py` sit at the package
root, deliberately outside `ai/`. Their location *is* the argument: a contact
list must never meet a model, and a module that cannot import `ai` cannot
accidentally start.

---

## Configuration

Adding a provider is a **config edit, never a code change**
(`config/providers.yaml`). Model origin rules classify by name prefix: the
provider tells you model names, your config decides what they are trusted with.
An unmatched name lands at tier D and receives nothing.

Environment, in full:

| Variable | Effect |
|---|---|
| `OFFSETX_DATA_DIR` | Where the databases live |
| `OFFSETX_DATABASE_URL` | Postgres URL for the egress log; unset → SQLite |
| `OFFSETX_OUTREACH_DB` | CRM database path |
| `OFFSETX_AI_<PROVIDER>_KEY` | Provider keys, when the encrypted file cannot persist |
| `OFFSETX_GMAIL_CLIENT_SECRETS`, `OFFSETX_GMAIL_TOKEN` | Mail credentials |
| `OFFSETX_OWN_EMAIL`, `OFFSETX_SENDER_*`, `OFFSETX_SIGNATURE` | Sender identity |
| `OFFSETX_WEB_HOST`, `OFFSETX_WEB_PORT` | Server binding |
| `OFFSETX_LOCAL_API_TOKEN`, `OFFSETX_DEMO_*`, `OFFSETX_SESSION_*` | Access control |
| `OFFSETX_MAX_UPLOAD_BYTES` | Upload cap |
| `OFFSETX_PROVIDER_REGISTRY`, `OFFSETX_PROVIDER_PROFILE_KEY` | Registry overrides |
| `OFFSETX_GRAPHIFY_BIN`, `OFFSETX_SANDBOX_ALLOW_NESTED` | Tooling escape hatches |
| `OFF_CRM_TEST_POSTGRES_URL`, `OFF_CRM_SANDBOX_TEST_IMAGE` | Opt in to the two live test suites |

---

## Verifying a rebuild

Stage by stage, the test files are the definition of done. They are written to
be read as specifications — each says what property it protects and why.

| Stage | Test file | Cases |
|---|---|---|
| 1–6 | `test_ai_egress_wall.py` | 42 |
| 6 | `test_ai_model_selection.py` | 31 |
| 9 | `test_ai_evals.py` | 45 |
| 10 | `test_ai_verify.py` | 19 |
| 8 | `test_ai_modes.py` | 17 |
| 11 | `test_ai_context.py`, `test_ai_bandit.py` | 20 + 34 |
| 12 | `test_ai_cache.py` | 34 |
| 13 | `test_ai_sandbox.py`, `test_ai_tools.py` | 43 + 31 |
| 14 | `test_intake.py`, `test_notebook_export.py`, `test_codegraph.py` | 28 + 34 + 33 |
| — | `test_db_backend.py`, `test_campaign_kinds.py` | 35 + 20 |

```bash
uv sync --extra dev
python -m pytest tests/ -q                  # expect 663 passed, 1 skipped
cd frontend && npm ci && npm test && npm run build
```

Two suites opt in rather than skip silently, because a test that passes because
it did not run is worse than one that says it was skipped:

```bash
OFF_CRM_SANDBOX_TEST_IMAGE=python:3.12-slim python -m pytest tests/test_ai_sandbox.py
OFF_CRM_TEST_POSTGRES_URL='postgresql://…'  python -m pytest tests/test_db_backend.py
```

Then boot it and check the whole path end to end, which is the step that catches
what unit tests cannot:

```bash
OFFSETX_DATA_DIR=/tmp/v OFFSETX_WEB_PORT=8799 python run_offsetx_web.py
curl -s localhost:8799/api/v1/campaign-kinds
curl -s localhost:8799/api/v1/ai/egress-log/stats
```

---

## Deliberately not built

A rebuilder who does not know this list will waste time looking for these, or
worse, "restore" them.

| Absent | Why |
|---|---|
| A model-facing tool path | Nothing hands the tool catalogue to a model or lets a plan call a tool. The registry exists; the door does not |
| Model-written notebook bundles | Exports are read from your own database and formatted. No model touches one |
| Automatic promotion of a rewritten template | The system decides *how much* traffic a variant gets, never *whether* a new one goes live |
| Reply text anywhere outside the mailbox | Replies are counted; the words are never copied, exported or indexed |
| An ORM | Expression trees would cost the readability the security argument depends on |
| Postgres for the other six stores | Only the egress log moved. No Postgres migration path or FTS yet |
| Image and distribution campaign runners | Declared in the registry, refused at creation with what is missing |
| Error classification and retry policy | Deferred by the owner deliberately, pending research |
| UI for the tool registry, intake, notebook export | CLI only |

---

## If you only remember five things

1. **Models never pull; off_CRM pushes.** No handles, no callbacks, no tools.
2. **Construct payloads from an empty allowlist.** Never filter a record.
3. **Block and raise; never redact.** A hit means the builder has a bug.
4. **Tier is checked before cost, always, and failover never crosses a tier.**
5. **Put the architecture rules in tests that walk the source.** Discipline is
   forgotten between sessions; an AST test is not.
