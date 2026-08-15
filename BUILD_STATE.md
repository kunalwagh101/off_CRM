# BUILD_STATE.md

Working record for the off_CRM AI orchestration module. Read **this file** to
recover context between sessions rather than re-reading the codebase.

Then read **`docs/architecture/CAMPAIGN_TYPES.md`** before designing anything
new. The product is a CRM *with an AI layer that runs the campaigns itself*, and
email is one campaign kind of several. Nothing built from here may assume email.

Last updated: 2026-08-14
Branch: `main`
Tests: **1057 Python passed, 0 failed**, 4 skipped (live Docker egress test;
set `OFF_CRM_SANDBOX_TEST_IMAGE` to a pre-pulled pinned image to run it), 22 frontend passed, frontend build clean.

The video editor is built: `offsetx_apollo_builder/video/` plus
`frontend/src/video/` and the **Video editor** screen. Read
`docs/architecture/VIDEO_EDITOR.md` before touching either resolver — there are
two implementations of one rule and a conformance fixture holding them together.
`docs/architecture/CAPCUT_FEATURE_MAP.md` is the feature inventory it was cut
from, and it now carries a **status column and a scoreboard**: 29 of its 158
rows built, 17 partly, 31% of the reachable rows touched.
`tests/test_capcut_scoreboard.py` recomputes those counts from the table, so the
summary cannot drift from what it summarises. Auto-captions is the first AI row
wired: `docs/architecture/AUTO_CAPTIONS.md`, and read its section on audio
before adding any other feature that sends bytes rather than text.

The long-standing `test_discovery.py::test_scrapling_parser…` failure was never
a code defect: `scrapling` is declared in `pyproject.toml` but omitted from
`requirements.txt`, so any environment installed from the latter lacked it. The
session-start hook installs via `uv sync --extra dev` and the test passes.

---

## 0. Session setup

`.claude/hooks/session-start.sh` runs on every session. It prints the repository
name, branch, HEAD and commit count **first**, then installs Python and frontend
dependencies so tests and linters work immediately.

The identity banner exists because of a real incident: a session started against
the empty sibling repo `email_agent`, found no commits, and reported "your repo
is empty" instead of noticing it was in the wrong place. A repo that announces
itself makes that failure impossible rather than unlikely. `AGENTS.md` carries
the same warning for the same reason.

---

## 1. What this module is

An AI layer inside off_CRM that runs outreach cheaply across many providers,
where the owner's mailbox, CRM database and context layers are **structurally**
unable to reach any provider.

The governing rule: **models never pull, off_CRM pushes.** A model that can
*ask* for data has access. A model that can only *receive* a constructed payload
does not.

---

## 2. Architecture as built

```
offsetx_apollo_builder/ai/          ← self-contained, extractable (§4M)
├── tiers.py      trust tiers, data classes, policy levels, the rules between them
├── registry.py   reads config/providers.yaml; resolves provider + owner override
├── payload.py    builds outbound payloads from an ALLOWLIST, starting empty
├── scanner.py    pre-flight scan; a hit BLOCKS and raises, never redacts
├── quota.py      local RPM/RPD/spend accounting, file-backed
├── broker.py     THE single egress gate — the only code that calls a provider
├── modes.py      run modes: simple, verified, compare, orchestrated
├── verify.py     write -> check -> repair -> review
├── sandbox.py    container isolation for AI-written code (§4J)
├── abstraction.py widens the *shape* of a request: bands, stages, margins
├── bandit.py     Thompson allocation between approved template variants
├── cache.py      exact + lexical near-match response cache, keyed on the payload
├── tools.py      the registry of owner-pinned tools that may run in it
└── tool_cli.py   `offsetx-tools` — register, inspect, run
├── discovery.py  asks a provider what models its key reaches
├── log.py        egress log; own table, exact payload, SQLite or Postgres
├── workspace.py  per-workspace settings + Fernet-encrypted provider keys
├── errors.py     structured refusals the API turns into readable answers
└── failures.py   what kind of failure this was, and what to do about it

config/providers.yaml               ← the registry. Adding a provider is a
                                       config edit, never a code change (§4E)

offsetx_apollo_builder/distribution/ ← the content distribution runner
├── platforms.py  what each platform permits, and what off_CRM refuses
├── youtube.py    Data API v3 read client; the only transport in the package
├── trends.py     competitor watch list + what is actually rising
├── topics.py     what several channels are covering at once
├── pipeline.py   trend -> brief -> swipe -> caption -> draft post
├── publishers.py the adapter interface + the local outbox
├── store.py      accounts, posts, goals, engagement snapshots
└── engine.py     plan -> approve -> schedule -> publish -> measure

offsetx_apollo_builder/imagery/     ← the image campaign runner
├── gates.py      deterministic quality gates; header parsing, no image library
├── store.py      briefs, candidate assets, generator scores
└── engine.py     generate -> gate -> review queue -> swipe -> score

offsetx_apollo_builder/video/       ← the timeline editor (CapCut's shape)
├── timeline.py   the document, its invariants, and the frame resolver
├── edits.py      every edit as a pure function; a default-deny registry
├── gates.py      MP4 + WebM + WAV header parsing; gates on the exported file
├── captions.py   transcript -> readable cues -> text clips, deterministic
├── store.py      projects, version history (undo), media, transcripts, renders
└── engine.py     create -> edit -> undo -> caption -> render -> gate

offsetx_apollo_builder/             ← deliberately OUTSIDE ai/
├── intake.py     two-mode campaign intake; a contact list never meets a model
├── campaigns.py  the registry of campaign kinds; email is one of them
├── notebook.py   research-notebook export; the destination is a trust tier
├── notebook_cli.py  `offsetx-notebook` — targets, plan, export
├── codegraph.py  Graphify wrapper; keeps the semantic path switched off
├── codegraph_cli.py `offsetx-codegraph` — policy, build, status, verify
├── db/           backend seam: SQLite or Postgres behind one interface
└── db_cli.py     `offsetx-db` — check the backend, copy the egress log
```

The module depends on the CRM only through `outreach/models.py` (dataclasses)
and `outreach/providers.py` (HTTP adapters). Lifting it into its own repo means
taking those two seams with it.

### The call path

```
caller → EgressRequest (task_type, data_class, person, template…)
       → broker.plan()      1. tier filter   ← runs FIRST, cost cannot override
                            2. quota filter
                            3. same-tier-only chain
       → build_payload()    4. construct from empty, per resolved policy
       → scan_payload()     5. block + raise on any hit
       → provider.generate  6. call
       → log.record()       7. record provider, tier, exact payload, timestamp
```

### Trust tiers (owner's ordering, 2026-07-25)

| Tier | Who | Policy ceiling | May receive |
|---|---|---|---|
| A | Europe, self-hosted | full | public, person, campaign, CRM internal |
| B | USA, Canada, allied | standard | public, person, campaign |
| C | China, and anything demoted for weak data terms | pseudonymous | public, person's public profile **as tokens** |
| D | Routers/aggregators, anything unlisted | strict | nothing |

Tier is derived from **two axes** — jurisdiction *and* retention terms. Passing
one is not enough. Google's free tier sits at C despite being US-based, because
its terms allow training on submitted content.

### Data policies (least → most)

| Policy | Sends |
|---|---|
| `strict` | Category and question structure. Nobody identifiable. |
| `pseudonymous` | Job title, category and the public hook, with the person and company as `PERSON_1` / `COMPANY_1`. Free text is scrubbed of the name too. Nobody identifiable. **Tier C ceiling.** |
| `minimal` | The person's public name, company, title, hook + your positioning line. Addresses tokenised. |
| `standard` | Above + your template text and campaign notes. Addresses tokenised. |
| `full` | No field restrictions. Real addresses can leave. Explicit opt-in. |

**Note on `minimal`:** it deliberately permits the person's public name so
enrichment can personalise — the owner's instruction. It is now reachable only
by tiers A and B: tier C's ceiling was lowered to `pseudonymous` (owner's
decision 2026-07-31, reversing §5.2 below). The older `outreach/providers.py`
path keeps its own stricter meaning for `minimal`; the two are documented
separately so existing profiles never silently widen.

`full` stays available on any tier via a recorded override with a mandatory
reason. Credentials, mailbox headers and internal field names are blocked at
**every** policy level including `full`.

---

## 3. Done

### Security core (§5)
- [x] Single egress gate. `create_provider` is reachable only from `ai/broker.py`,
      `outreach/providers.py` and `outreach/provider_profiles.py`; enforced by
      an AST test that walks every module.
- [x] Two former bypasses fixed: `api/app.py` (request-supplied provider) and
      `outreach_cli.py` now go through `create_guarded_provider`, which cannot
      return an unwrapped provider.
- [x] Payload **construction** replaces filtering. `PersonPublic` has no email
      field, so an address cannot arrive through the person path at all.
- [x] Pre-flight scanner blocks and raises. Catches addresses, owner domains,
      credentials (12 shapes), mail headers, internal field names, env vars,
      local paths.
- [x] Trust tiers on both axes, with per-model provenance caps (a US host
      serving a Chinese-origin model is capped at C).
- [x] Default-deny: an unlisted provider raises rather than being assumed safe.
- [x] Fail-closed: unknown tier, empty candidate set and exhausted quota all
      stop the call.
- [x] Failover never crosses a tier boundary.
- [x] Mailbox is unreachable by default for every provider; unlock needs the
      exact phrase `ALLOW MAILBOX CONTENT TO LEAVE`, and even then tier C is
      still refused.
- [x] Egress log with the exact payload + inspector UI (`#egress`).
- [x] Credential isolation: Fernet, `0600`, per workspace, env fallback.
- [x] §5.12 acceptance tests — 30 cases in `tests/test_ai_egress_wall.py`.

### Run modes (owner's design, 2026-07-25)
- [x] **Simple** — one model, cheapest permitted. The everyday path.
- [x] **Compare** — every permitted model answers at once, side by side. Each
      runs under *its own* policy, so a tier C model can contribute without
      seeing more than it should. Capped at 8 branches so one question cannot
      burn every quota.
- [x] **Orchestrated** — a head model writes a plan, each step routes normally.
      **The head model must be tier A or B.** Planning means seeing the whole
      job, so restricted models get steps to do, never the job to split.
      A plan cannot widen its own reach: a step asking for `mailbox` or
      `internal` is clamped to what the caller already offered.
- [x] Model strip in the AI screen: every connected AI, its trust badge, and a
      meter showing how close it is to its daily limit.

### Per-model connectors (2026-07-26)
- [x] A connector is a **key**, and a key reaches many models. One NVIDIA key
      offers Llama, DeepSeek, Qwen, Phi, Gemma, Granite, Mistral, Nemotron.
- [x] **Tier belongs to the model, not the key.** NVIDIA+Llama is B,
      NVIDIA+DeepSeek is C — in the same run, on the same key.
- [x] `model_origin_rules` in config classify a model by name prefix. The
      provider supplies names; config decides trust. Unmatched name -> tier D.
- [x] "Find models" calls the provider's `/models` endpoint. Sends no owner
      data; still written to the egress log so the record stays complete.
      Degrades to the config list on any failure, with the reason shown.
- [x] Connecting a model off_CRM cannot place is refused with the fix in the
      message, rather than failing later at call time.
- [x] **Per-model `request_options` in config** — `max_tokens`, `temperature`,
      and provider-specific keys such as NVIDIA's `reasoning_budget`. A large
      reasoning model with no `max_tokens` gets truncated by the provider's
      own default, so this is correctness, not tuning. Options are opt-in per
      model; models that declare none send a plain payload.
- [x] Reasoning models handled: `reasoning_content` is returned when
      `content` is empty, and `finish_reason: length` produces an error that
      names `max_tokens` as the fix instead of "no message content".
- [x] Nemotron Ultra 550B and DeepSeek R1 seeded with working options.
- [x] **Image generation.** Models carry `kind: chat | image`; image models
      go to `/images/generations` and return pictures. Same key, same tier
      rules, same scanner, same log — a prompt is text, so a prompt naming a
      real person is still person data. FLUX (German) and Stable Diffusion
      (British) seeded on the NVIDIA key with origin rules for their makers.
      Pictures come back as base64 so they never sit behind a provider URL;
      the image itself is not written to the egress log, only the prompt and
      a count, since the log exists to show what *left*.

### Fixed in this round
- [x] **The chosen model was ignored.** `candidates_for` resolved each provider
      with no model id, so every call fell back to `default_model` — and the
      provenance cap was therefore unreachable from the UI: picking a Chinese
      model on NVIDIA was treated as tier B. Three call sites had the same gap
      (broker, compare, orchestrated planner); all now route per model, each
      with a regression test.

### Features
- [x] §4B Connectors: own screen; Gmail moved out of Settings; every provider
      card shows **country, trust tier, retention terms**, usage and cost.
- [x] §4C AI chat: model selector, task mode, Markdown/HTML export, dictation
      where the browser supports it (degrades silently where it does not).
- [x] §4E config-driven registry: 17 providers in YAML with jurisdiction,
      retention, RPM/RPD, context window, cost, `verified_on` date.
- [x] §4E local quota counting + usage display + same-tier failover.
- [x] §4L: structured refusals surface as readable sentences with a next step,
      never a raw status code. Every empty state has an action.

### Context layer (§4F/§4H) — built

- [x] `ai/context.py` — job state (steps, decisions, facts) plus a **rolling
      summary assembled by Python**, not written by a model. Same inputs, same
      summary; no per-update AI cost and no drift.
- [x] Decisions survive a model swap mid-job, which is the point of the layer:
      the head model can change without the choices being quietly undone.
- [x] Reply-rate counting per template and variant. A template is not judged
      until 20 sends, so one lucky reply out of two is never a "50% success".
- [x] Weak templates (judged, at or under 5%) can be rewritten. The request that
      leaves carries **the template wording and two numbers** — no recipient, no
      name, no address — so it runs as public work under any permitted model.
- [x] Nothing goes live automatically. A rewrite is shown for approval and saved
      as a new variant to run against the old one.
- [x] The winning template is offered to other models as a reference to follow
      or beat (owner's request).
- [x] **Wired into the real send path.** `OutreachEngine` counts a send when the
      message actually leaves and a reply against the template that was sent —
      not the contact's current stage, which has usually moved on. The unattended
      automation sender counts too. A counter failure can never lose a send.
- [x] Two safety rules with their own tests: **no model can query this store**
      (no tool, no function, no retrieval interface, no provider import), and
      **only code writes to it** — so the numbers stay facts.
- [x] `record_reply` takes no reply text. Detecting that a reply arrived is a
      fact; reading what it says would be mailbox content leaving. There is
      nowhere to put it.
- [x] Memory screen in the UI: reply rates, weak flags, the rewrite awaiting
      approval, and jobs in progress.
- [x] This is **not fine-tuning**. No data is shipped away to retrain anything.

### Eval harness — built (2026-07-31)

Answers what the run modes could not: does orchestration beat one good model?

- [x] `ai/evals.py` — twelve **deterministic** check kinds, pure functions of the
      output text. No model judges anything, for the same reason no model
      enforces policy: a grader that varies is not a measurement.
- [x] An unknown check kind **fails** rather than passing, so a typo in a check
      name cannot silently inflate every score that uses it.
- [x] `config/evals.yaml` — suites are config, like `providers.yaml`. Adding a
      case is a data edit.
- [x] `ai/scoreboard.py` — run history, leaderboard, and the champion per suite.
- [x] **Champion/challenger gate.** A mode is promoted only if it beats the best
      single model on the mean, **and** wins case-by-case beyond chance, **and**
      stays inside a cost ceiling. Every other path keeps the champion.
- [x] Significance by **exact binomial sign test**, not `>`. Both subjects run
      the same cases, so the comparison is paired. Comparing raw means on a
      thirty-case suite flips the winner on noise about half the time when the
      two are actually equal, and every flip costs money because the challenger
      runs several models per task.
- [x] `route_for()` returns `simple` when nothing has been measured. An
      unmeasured system routes to one model, never to an unchecked ensemble.
- [x] `offsetx-evals` CLI: `list`, `run --modes`, `champion`, plus `--dry-run`
      that prints the call count without spending tokens.
- [x] Same rules as the rest of the module: evals go through the broker with
      ordinary tier rules (verified against a tier D aggregator), and **no model
      can read or write the scoreboard** — asserted by an AST walk.

**First result, and the reason this was worth building.** On the shipped suite,
compare mode scored *identically* to the champion — not close, equal — because
`first_permitted_text` returns the highest-tier branch, which is the champion's
own answer. Compare mode paid for two calls and returned what one model would
have said alone. That is fine for its designed use (the owner reads every branch
and picks) but means calling it programmatically buys nothing. Nobody could have
known without measuring.

**Honest limitation:** seven cases ship. That is a skeleton, not a suite. Thirty
or more is the floor for trusting a close verdict, and the CLI warns on every
`list`. The cases worth adding are ones from real work that disappointed you.

### Two-mode intake — built (2026-07-31)

Two ways a campaign gets its people, kept apart because conflating them is how
mistakes happen. **Generate**: describe who you want, discovery finds them.
**Parse**: you already have the list — CSV, spreadsheet or PDF.

**Deliberately outside the `ai/` package.** A contact list is the densest
concentration of exactly what the system protects — real names, addresses,
companies. If a model parsed it, that one feature would leak more than every
other path combined. Parsing is deterministic and local; a test walks the module
and fails the build if it ever gains a route to a provider or an import from
`ai/`. Same rule as the campaign runner: the parts touching real contacts have
no AI, the parts with AI have no real contacts.

- [x] CSV and XLSX through the existing loader. A column is a column, so nothing
      is flagged and the result is immediately usable.
- [x] **PDF reading via `pypdf`, locally.** Addresses are found exactly — an
      email has a shape a pattern matches. Names are inferred from layout: the
      same line first, then the line above, which are the two arrangements a
      printed table actually uses.
- [x] **Every PDF row is flagged `needs_review` and can never be sent
      unreviewed.** Not a placeholder for better parsing later — guessing which
      name belongs to which address and being wrong means emailing a real person
      by the wrong name. `ready_to_send` is False whenever anything is flagged.
- [x] When no name is convincing, the row says "no name found near this address"
      rather than guessing. A wrong name is worse than a missing one.
- [x] Column headers are not mistaken for people; duplicate addresses read once;
      page numbers recorded so a row can be found again.
- [x] **No OCR.** A scan has no text layer, and pretending otherwise produces
      confident nonsense — the warning says to export the original as CSV.
- [x] Refusals are readable: missing file, unsupported type, a file that is not
      really a PDF.
- [x] Generate mode is a validated brief. No contact in a generated list is
      invented by a model; the data source produces them.

**Defect found while building.** The row builder read `full_name` and `company`,
but `normalize_input_rows` emits the CRM's own field names, `name` and
`organization_name`. Every parsed row came back with no name — which looked like
a parsing failure and was really a mapping one. Caught by exercising it against
a real CSV rather than trusting the field names. Regression-tested.

**Not built:** no UI screen, and wiring generate mode to discovery is separate
work. Tests build a real PDF by hand rather than mocking extraction, so the
genuine `pypdf` path is exercised without adding a test dependency.

### Response cache — built (2026-07-31)

**Named honestly.** The literature's "semantic cache" and its 60-90% hit rates
come from chat systems where users repeat questions. Personalised outreach gives
every payload a different token and hook, so those numbers do not transfer. It is
also not embedding-based — that would mean a network call from a module whose
point is avoiding calls, or a heavy dependency. It does exact match plus lexical
near-match, which fully covers where caching actually pays here: re-running eval
suites, retries, verify-loop repair rounds, and repeated public or code work.
The cache reports its own hit rate, because whether it earns its place is a
question for the owner's numbers rather than a published average.

- [x] **Keyed on the constructed payload**, not the question. Payloads are built
      per policy — verified, not assumed — so a response produced from a richer
      payload can never be served for a thinner one. That matters beyond the
      obvious: a response can travel back out as `prior_drafts`, so a cache that
      blurred policy boundaries would be a slow path for tier A material to
      reach a tier C provider.
- [x] Partitioned by workspace, data class, policy, task type and provider.
      Near-matching is confined to one partition, so fuzzy comparison cannot
      cross a boundary however similar two texts look.
- [x] **Consulted after construction and scanning, never before.** A lookup must
      not become a way around the checks that precede it — if the scanner
      blocks, nothing is served and nothing is stored.
- [x] **A hit is logged as `cache_exact`/`cache_near`, not `succeeded`.** Nothing
      left the machine, and the egress log is the one thing that must never lie.
- [x] Near match at 0.92 Jaccard over **word triples**. Single-word overlap would
      call two different questions similar; triples require the phrasing to line
      up. The threshold errs towards missing, because serving a stale answer to
      a different request is worse than missing a hit. Switchable off.
- [x] Never stores empty responses or failed calls — that would turn one
      transient outage into a week of them — and never stores `MAILBOX`.
- [x] 7-day TTL, 5,000-row cap with oldest-first eviction, manual purge and
      clear. A cache, not an archive; the egress log holds the record.
- [x] Exact and near hits counted separately, since they carry different risk.

### Traffic shifting — built (2026-07-31)

`context.py` counts sends and replies; this decides the split. Thompson sampling
over Beta posteriors, in `ai/bandit.py`, reached through
`context.traffic_split()`.

**Why not a threshold.** The arithmetic of low reply rates rules it out:
separating 2% from 4% needs ~1,140 sends per variant, 2% from 3% needs ~3,800,
and twenty sends with no replies has a 54% chance of occurring even at a healthy
3% true rate. A threshold rule fed that data does not become cautious — it
becomes confidently wrong.

- [x] Thompson allocation: the share a variant wins **is** its probability of
      being best. Near-even when posteriors overlap, shifting as they separate —
      correct at both ends with no cut-off to choose. That graceful degradation
      is the whole reason for the choice: a threshold has to be right, this does
      not.
- [x] `sends_needed()` tells the owner how far off an answer is. On two nearly
      identical rates it reports tens of thousands of sends, which is the useful
      answer: stop trying.
- [x] 5% floor per active variant. Without a holdout a winner that later
      degrades looks fine forever, and a variant unlucky in its first twenty
      sends could never recover.
- [x] Rates reported as posterior means, not raw fractions — one reply from two
      sends is not a 50% reply rate.
- [x] Seeded runs are reproducible, so a split can be re-derived later.
- [x] Retired variants excluded entirely. Structural test: `bandit.py` imports
      no database and no provider, so the maths can be tested exactly.
- [x] **Decides how much, never whether.** It allocates only between variants
      the owner already approved; an unapproved rewrite is not an active row for
      it to see, so it cannot promote one. §3 is unchanged.

**Defect caught while building.** The verdict read "traffic stays near even"
while allocating 80/20 — the sentence contradicted the numbers. Thompson does
shift below the confidence bar; the text was simply false. It now describes the
real split, with a parametrised regression test asserting the even-split wording
only appears when the leader is under 65%.

### Abstraction layer — built (2026-07-31)

Tokenisation hides *who*. This hides *how the business works*, which no PII rule
touches. Verified against the real builder first: a tier B provider was
receiving company size, funding stage, the stated ICP band, the **gross margin**,
the **close rate**, the sequence length and engagement counts — verbatim, with
every identifier already removed.

- [x] `ai/abstraction.py` + `config/abstraction.yaml` — 14 deterministic rules,
      three kinds (`bucket_number`, `replace_pattern`, `replace_terms`). Rules,
      not a model: a protection that varies is not a protection.
- [x] **Every rule only ever widens.** None can make text more revealing, which
      is why applying it twice is safe — asserted by an idempotence test.
- [x] Applied below `full` only; at `full` the owner has explicitly trusted one
      provider with everything. Off per workspace via `abstract_business_shape`,
      defaulting **on**, so a caller that forgets gets protection not a leak.
- [x] Loud config validation: unknown kind, missing `(?P<value>)` group, absent
      open-ended bucket and malformed pattern all raise at load. A rule that
      silently does nothing is worse than no rule, because it looks like
      protection.
- [x] A broken rules file does not stop a send — failing to widen must not
      become failing to send.

**Three defects found and fixed, each with a regression test.**

1. **The margin was leaking.** The percentage rule ended in `\b`, and `%` is not
   a word character, so that boundary can never match. The single most
   commercially sensitive number in a payload passed straight through the rule
   written to catch it.
2. **A rule was lying.** The sequence-position rule turned "a warm *first*
   email" into "a warm *a later message in the sequence*", inverting the
   meaning. Caught by an existing test failing. `first` is now left alone
   entirely: every sequence has a first message, so the word leaks nothing —
   it is the high ordinals that disclose how many steps exist.
3. **Rule order was wrong.** `headcount` preceded `headcount_ranges` and
   consumed the right-hand number of "100-250 staff", so the range rule never
   fired. The more specific pattern must run first.

Cost to quality is near zero: ordinary copy instructions pass through untouched,
and where the rules do fire they leave the useful signal intact.

### Tool registry — built (2026-07-31)

The list of who may enter the locked room. One sentence carries the design:
**a model names a tool that already exists; it cannot describe a new one.**

- [x] `ai/tools.py` — register, list, enable/disable, remove, run, run history.
- [x] **`run()` takes a `tool_id`, never an image or a command.** A test asserts
      this at the *signature* level: if the parameter list ever grows `image=`
      or `command=`, the build fails, because the registry would have stopped
      being a registry.
- [x] Three mandatory pins, none defaultable: a `github.com/owner/repo` URL, a
      **full 40-character commit SHA** (branches and tags refused — they move),
      and a version-pinned image (`:latest` refused).
- [x] **The catalogue withholds the recipe.** A model sees id, name, description
      and whether arguments are accepted. No image, no command, no repository —
      so a leaked catalogue is not a leaked attack surface. A disabled tool is
      *absent* rather than marked, so a model cannot tell it exists.
- [x] Extra arguments are **opt-in per tool**, capped at 8, values only —
      anything starting with `-` is refused so a caller cannot change how the
      tool behaves.
- [x] **Source is fetched on the host, not in the container.** The container has
      no network, so it cannot clone; off_CRM materialises the pinned commit
      first and then proves `rev-parse HEAD` equals what was registered. That
      puts the integrity check somewhere a compromised tool cannot reach. Source
      lands in `inbox/`, which mounts read-only, so a tool cannot rewrite its own
      source mid-run.
- [x] Every run is logged with **the commit and image it actually used**, not
      just the tool name. A timeout is recorded as a run, not raised away.
- [x] `offsetx-tools` CLI: `register`, `list`, `show`, `catalogue` (prints
      exactly what a model would see), `run`, `enable`/`disable`, `remove`,
      `runs`.

**Defect found and fixed while building this.** `sandbox_available()` checked
for the docker *binary* with `shutil.which`, which is not the same as a running
*daemon* — the dev machine has the binary and no engine, and the first CLI run
sailed past the check and failed several steps later inside a git fetch with a
much worse message. It now probes with `docker version --format
{{.Server.Version}}`; `docker info` is unusable here because **it exits zero
even when the server half fails**. Both a zero exit and a non-empty server
version are required, with a parametrised test over all four combinations.
`check_daemon=False` skips the subprocess where the answer is only advisory.

**Not built on purpose:** no model-facing path. Nothing yet hands the catalogue
to a model or lets an orchestrated plan call a tool. Storage and isolation
should be solid before anything automated can reach them.

### Sandbox isolation — built (2026-07-31), salvaged not written

`agent/off-crm-v0-12-ai-studio` — an abandoned parallel design from 24 July —
had already solved container isolation before the `ai/` module existed. Rather
than merge that branch (14 conflicts, and it carries a whole second AI module
with no `ai/` at all), the isolation layer was lifted into `ai/sandbox.py`.

- [x] `docker_command()` — `--network=none`, `--read-only`, `--cap-drop=ALL`,
      `--security-opt=no-new-privileges`, `--user=65534:65534`, pids/memory/cpu
      caps, and `noexec,nosuid` scratch space.
- [x] **`--pull=never`**, the sharpest idea in the original: the image must
      already be present. Without it, a crafted image name *is* a network fetch
      — a way to reach the internet from the one feature that must not.
- [x] **Improved on the original:** `--memory-swap` equal to `--memory`. Without
      it the memory cap is advisory, since a container can exceed it by
      swapping. The salvaged version omitted this.
- [x] Images must be **version-pinned**; `:latest` is refused, because the image
      you reviewed is then not necessarily the image that runs. Image names are
      validated against a strict character set so a name cannot smuggle extra
      arguments into the docker invocation.
- [x] Workspace is `inbox/` (read-only), `work/` (writable) and `store/` —
      which is **not mounted at all**. Not read-only: absent. The context layer,
      recall index, egress log and encrypted keys do not exist in the
      container's view of the filesystem.
- [x] Sandbox jobs are `DataClass.PUBLIC` only, enforced. Anything carrying a
      person belongs on the egress path where the tier rules apply.
- [x] Refuses rather than degrading: Render and other nesting hosts are detected
      up front, and a missing Docker is a refusal, not a fallback. Python cannot
      sandbox Python, so there is no weaker option worth offering.
- [x] Disk budget counted by off_CRM (10 GB default), because Docker cannot
      size-cap a bind mount. Documented as a safety limit rather than a lock.
- [x] **§5.12(c) now covered.** Composition is asserted on every invocation, and
      a live test starts a real container and tries to open a socket — skipped
      unless `OFF_CRM_SANDBOX_TEST_IMAGE` names a pre-pulled image, since
      `--pull=never` forbids fetching one and a network-isolation test that
      quietly downloads from the internet would be self-defeating.

**Still unverified:** the flags themselves need a real Docker daemon. Everything
around them is tested; run the live test on your machine to close that.

### Verify loop — built (2026-07-31)

Where the quality per credit actually comes from. Not models voting: a cheap
model writes, **code** judges, the specific failures go back, and a more trusted
model reads the result. Checking is easier than producing, and output tokens
cost several times what input tokens do, so the checking half is the cheap half.

- [x] `ai/verify.py` — `VerifyLoop`: generate, check, repair, optional review.
- [x] **Enforces the same checks the eval harness scores with.** `checks_for()`
      reads the suite's `default_checks` from `config/evals.yaml`, so what
      production enforces and what the harness measures cannot drift apart —
      one edit moves both.
- [x] **The best attempt wins, not the last.** A model told to fix a length
      problem will cheerfully break the subject line; returning the final
      attempt would ship that. Ties go to the earlier round, since a later round
      that only matched it cost money for nothing.
- [x] **Deterministic checks are the gate; a model review only advises.** A
      glowing review cannot turn a failing draft into a passing one — tested.
- [x] Round cap: default 3, hard cap 5 regardless of what a caller asks for.
      Rounds 1-2 capture most of the available gain, and a loop that can run
      twenty times is a way to spend twenty times the money on a task that is
      not converging.
- [x] A policy refusal **stops** the loop rather than retrying it. Retrying
      produces the identical refusal.
- [x] No checks supplied means nothing was verified, and it says so rather than
      reporting a pass.
- [x] The repair prompt carries the previous draft in `instructions`, not
      `prior_drafts` — so a tier C model can fix its own work without the
      payload widening to carry campaign material. Tested: a repair round to a
      restricted provider stays pseudonymous and never gains the template.
- [x] The reviewer prefers a **second opinion within the same tier**, never
      dropping a tier to find one. Self-review is labelled as such.
- [x] Shipped as a fourth run mode, `verified`, so the eval harness can score
      it against the champion. The API dispatches it explicitly rather than
      letting it fall through to `simple`.

### Recall over sent mail (RAG) — built

Retrieval where the access rules, not the search, were the work. A normal RAG
stack leaks in four places; each is closed by construction here.

- [x] `ai/recall.py` — local full-text search (SQLite FTS5) over the owner's own
      sent mail. **No embeddings, no API key, no network call.** Indexing the
      whole archive posts nothing to anyone and works offline.
- [x] **Redacted before it is stored, not on the way out.** Most stacks keep the
      raw text and clean it at query time, which makes the index the most
      dangerous file in the product. Here names, companies, addresses, phone
      numbers and links are removed before the write. A test reads the raw bytes
      of the database file and asserts no identity survives in it.
- [x] Redaction is **targeted, not guessed**: off_CRM knows exactly who its
      contacts are, so it deletes their names precisely. The vocabulary covers
      *every* contact, not just the recipient — an email to one person routinely
      names another. A pattern pass then catches what no contact list could know.
- [x] Over-redaction is the deliberate choice where the two disagree. A common
      first name is removed even though it costs a legitimate word sometimes.
      Dates are kept: a date identifies nobody and losing them makes the
      snippets useless.
- [x] **Sent mail only, enforced twice.** `index_message` refuses an inbound row,
      and `store.sent_messages` filters to outbound in the SQL with no parameter
      that could switch it.
- [x] **Quoted threads are cut off first.** A follow-up usually quotes the reply
      underneath it — that block is *their* mail inside *your* mail, and it never
      reaches the index.
- [x] **No model can search it.** No tool, no function, no retrieval interface,
      no provider import, no network import. off_CRM chooses the search, reads
      the result and pushes a payload. Asserted structurally.
- [x] Snippets leave as `DataClass.CAMPAIGN` — the honest label for the owner's
      own business writing. Calling it `public` would have smuggled it past the
      rule keeping campaign material from restricted providers. **Two
      independent barriers, neither special-cased for this feature:** tier C and
      D refuse the class outright, and the snippets travel as `prior_drafts`,
      which a `minimal` policy does not carry at all.
- [x] The payload is still scanned on the way out, so a regression in redaction
      blocks the call rather than leaking.
- [x] Wired into the live send path and the unattended sender. A reply sets a
      "this one worked" flag and is otherwise not stored, which makes
      "show me emails like this that actually earned replies" possible.
- [x] Deletion: forget one message, forget one person, or clear everything.
      Redaction is not an answer to a deletion request.
- [x] Past emails screen: search, and a preview that renders the **real**
      outbound payload rather than a description of it.

### Orchestration audit (2026-07-31)

Full design review in `docs/architecture/`. Two defects found and fixed; both
reproduced against the real code before changing anything.

- [x] **Simple mode never picked the cheap model.** `candidates_for` returns
      permitted pairs cheapest-first, then `broker.plan` discarded everything
      below the top tier — so with Mistral (A, cost 20.0) and DeepSeek (C, 3.57)
      connected, a `public` coding task ran on Mistral at **5.6x the cost**,
      while the free model that was fully permitted sat idle. The same-tier rule
      exists to stop *failover* demoting restricted data; it was also gating
      *initial selection*, which is a different thing — `candidates_for` has
      already checked `permits(data_class)` on every candidate, so picking a
      cheaper one is not a demotion. Narrowed to: `public` uses the full
      cost-sorted list across tiers, everything else keeps the old behaviour.
      Each candidate still builds its own payload under its own policy.
      Switchable per workspace via `cross_tier_public_routing` (default on).
- [x] **`best_text` did not mean best.** It returned `branches[0]` after a sort
      on `(tier, ok, duration_ms)` — the fastest reply from the highest tier, not
      the best answer. Nothing scores quality; no scorer exists. The docstrings
      were honest (compare mode says the *owner* picks) but the name promised a
      judgement, and it ships through `to_dict()` into `frontend/src/types.ts`.
      Renamed `first_permitted_text`; `best_text` kept as a deprecated alias so
      the API contract is unchanged. A real `best_text` can land with the evals.
- [x] The Simple mode UI description claimed "cheapest" unconditionally. Now
      states the actual rule: cheapest for public work, most-trusted for person
      and campaign data.

### Notebook export (§4G, 2026-08-10)
- [x] `notebook.py` + `offsetx-notebook` (`targets`, `plan`, `export`).
      Docs: `docs/architecture/NOTEBOOK_EXPORT.md`.
- [x] **NotebookLM has no public write API**, so this produces a bundle you
      upload by hand rather than an integration that would break the week
      Google moves a button. The same bundle suits a Claude Project, a ChatGPT
      Project, or a notebook you host.
- [x] **The destination is a trust tier.** An export you drag into NotebookLM
      is a push, and the rules do not care that the transport is a person.
      `notebooklm` is C (Google free tier, terms permit training on input),
      `hosted_notebook` B, `self_hosted` A. Raising a tier needs a written
      reason; lowering one does not.
- [x] Built from a declared allowlist of sections, each naming its data class.
      The tier decides which survive; a withheld section's data is never even
      fetched.
- [x] Scanned with `ai/scanner.py` before the first byte reaches disk. A hit
      blocks the whole export and leaves no folder behind — a partial bundle is
      worse than none, because it is uploadable.
- [x] Every withholding is written down with its reason and its fix, in the
      README and `MANIFEST.json`. Nothing is silently absent.
- [x] **Mailbox content is unreachable structurally**, not by a runtime check:
      no section carries the class, and a test pins the exact set of store
      methods this module may call. `sent_messages`, `last_outgoing` and
      `record_reply` are not in it.
- [x] Addresses never appear at any tier, including `full`.
- [x] Below `minimal`, people and companies are tokenised **per bundle**
      (`PERSON_1..PERSON_n`) — one shared token for 200 people is a list with
      the answers removed. Free text is scrubbed too, so a public hook reading
      "Ana Silva spoke at the EU trade summit" survives as "PERSON_1 spoke at
      the EU trade summit". The campaign's own name is withheld below `minimal`
      as well: it is usually the ICP written out.
- [x] The map back to real people is written **outside** the uploaded folder,
      at `0600` — not a warning inside it, because "select all and upload" is
      what people actually do.
- [x] **Does not assume email.** Sections declare campaign kinds; outcomes and
      templates are email-only and refuse by *kind*, not by tier, so the owner
      is not sent looking for a permission problem that does not exist.
      `campaign_kind()` reads a `kind` column that does not exist yet and falls
      back to `email`; a test asserts the column is still absent, so the day it
      lands the test points at the reader that needs checking.
- [x] No model touches a bundle. An AST test fails the build if this module
      ever gains a route to a transport.

### Stage 2 — transitions, animations, the preset registry (2026-08-14)
- [x] `video/presets.py` + `frontend/src/video/transitions.ts`. **46 transitions
      over 9 families, 32 animations over 3, 12 text styles, 16 blend modes, 12
      more animatable properties.** Feature map: 29 → **40 built**, 37% of the
      reachable rows touched.
- [x] **Transitions without relaxing the invariant.** A dissolve needs both
      clips on screen and clips cannot overlap by a tick. The clips stay
      adjacent and a `Transition` on the track declares how far either side of
      the cut both are drawn — a bounded, declared property of the boundary
      instead of an accident of two clips' positions. Both sides share one
      `progress`; a clip drawn past its end is held at its last frame; one
      transition per cut; halves at both ends must fit inside the clip; an edit
      that destroys the cut removes the transition.
- [x] **Presets are rows, families are code.** A new transition is a line of
      YAML-shaped data, which is what makes the space searchable by the
      orchestrator later. `CAPCUT_TOOL_INVENTORY.md` argued this; this is it.
- [x] **An animation is ordinary keyframes**, so it survives a split, travels
      with a trim and resolves identically in both languages — none of which
      was rebuilt.
- [x] **A real bug found by the new tests: splitting inside a non-linear ease
      was not transparent.** The old resampler synthesised boundary keyframes
      from interpolated values, which is exact for a linear segment and wrong
      for every other kind — a sub-range of an ease-out curve is not an ease-out
      curve. The original split test passed only because it used a linear
      segment. Keyframes are now shifted rather than rebuilt: exact, and bounded
      by keeping only the nearest anchor either side.
- [x] Conformance fixture regenerated with a transition, a blend mode and an
      applied animation across it, and the TS test now asserts the transition
      field — the one place a clip is drawn outside its own bounds.
- [x] 36 new preset/transition tests, 3 regression tests for the eased split and
      trim, and the scoreboard guard now checks **both** directions: nothing
      claims to be built that is not, and nothing that shipped loses its mark.

### Goal-driven pacing (2026-08-14)
- [x] `distribution/pacing.py` — posting volume is adjustable **and the goal
      moves it**. `(target − measured views) ÷ views per post ÷ days left`, with
      every term checkable by hand. Blueprint §6.4.
- [x] **No data, no steering.** Below 5 measured posts there is no
      views-per-post figure, so it holds the declared rate and says why. A
      controller with nothing to measure is a random number generator, and that
      is the rule most likely to be broken by someone making it look clever.
- [x] **Raise slowly (+25%/cycle), lower immediately.** The errors are not
      symmetrical: a missed goal is recoverable next week and a banned account
      is not. An engine that notices it is behind and posts ten times more *is*
      a spam bot at that moment.
- [x] **10% deadband**, or the rate moves every cycle on noise and the schedule
      becomes unplannable. **Platform caps are hard** — Instagram's 25/day is a
      ceiling the arithmetic may approach and never cross, and the capping
      platform is named so a throttled campaign does not look like an
      under-performing one.
- [x] The new rate is stored, so the ramp compounds instead of restarting from
      the declared number every cycle and never arriving. `auto_pace` off by
      default.
- [x] A falsy-zero bug found by its own test: `float(x or 1.0)` turned a rate
      deliberately set to 0 — a paused campaign — back into 1/day.
- [x] 26 pacing tests + 8 in the automation cycle, including a live HTTP run
      against a real goal and 20 real metric rows: holds at zero data, then
      raises to a ramped 1.25 against a measured requirement of 9.8.

### Stage 1 — the content engine runs itself (2026-08-14)
- [x] `distribution/automation.py` — `ContentAutomationService`. Sweep → plan →
      draft → publish-due, on a timer, started and stopped with the app.
      Blueprint: `docs/architecture/CONTENT_ENGINE_BLUEPRINT.md` Stage 1.
- [x] **This was the highest-value missing line in the project.** Every piece of
      the content pipeline worked and none of them ran on their own; the Amul
      point in the brief is about time, and a trend acted on tomorrow is one
      somebody else already used.
- [x] **Which campaigns run is declared, not inferred.** The pipeline needs a
      distribution campaign *and* an image campaign, and nothing in the schema
      says which pairs with which. Guessing would post from the wrong brand, so
      the pairs live in the service's own config, a half-declared pair is
      dropped, and enabling with none declared is refused with a message.
- [x] **A failing step does not cost the cycle.** A YouTube quota error at the
      sweep must not stop posts a person already approved from going out. Each
      step is caught, recorded and reported; the next cycle tries again.
- [x] **The two human gates are untouched.** `publish_due` can only act on posts
      that already carry an approval. This service drives the machine either
      side of the swipe and the approval and stops at both.
- [x] The loop **waits before it runs**, so a restart loop cannot become a burst
      of sweeps against a quota. Interval clamped to 300s–24h.
- [x] Separate from the email `AutomationService` on purpose: that one is
      email-shaped, and nothing built from here may assume email.
- [x] `_TimerScope` — the four per-request engine factories read only
      `request.app.state`, so the timer passes an object with an `.app`. The
      alternative was changing thirty call sites to land in the same place.
- [x] 26 tests: declaration rules, corrupt-config safety, bounds, step order,
      per-step failure isolation, switch-off-by-name, no overlapping cycles,
      the wait-then-run loop, clean start/stop, and a live HTTP cycle through
      the app's real factories. Plus a structural test that this module imports
      no transport.

### Video projects on Postgres (2026-08-14)
- [x] `VideoStore` is opened through `resolve_target`, the same seam the egress
      log uses: explicit target, then `OFFSETX_DATABASE_URL`, then the local
      file. One variable moves timelines off a disposable disk.
- [x] The reason is not tidiness. `render.yaml` writes to `/tmp` on the free
      plan, and an instance that sleeps comes back empty — an hour of editing
      disappearing at that point is the work, not a storage detail.
- [x] **What it does not fix, stated rather than implied:** renders, uploaded
      recordings and generated pictures are bytes on a disk. The document is the
      part that took the work and the part that moves; files still need a real
      disk or object storage.
- [x] `tests/test_video_postgres.py` — 17 tests over **both backends**: schema
      creation, a whole edit session surviving a cold reopen with its undo
      history, undo/redo after a reopen, media and transcripts, the
      `ON CONFLICT ... DO UPDATE` upsert, the hash uniqueness that stops paying
      twice for one recording, and history trimming. Run against a real
      Postgres 16, not asserted.
- [x] A structural test parses `api/app.py` and fails if `VideoStore` is ever
      handed a bare path again — that mistake shows up only as work quietly lost
      on the next restart.

### Auto-captions (2026-08-14)
- [x] `video/captions.py`, `broker.call_transcript`, `OpenAITranscriptionProvider`,
      media import, and an **Auto captions** button. Docs:
      `docs/architecture/AUTO_CAPTIONS.md`.
- [x] **Half of it is a media import path, and that is not padding.** Nothing in
      off_CRM generates speech, so the caption button had nothing to listen to.
      `POST /campaigns/{id}/video-media` takes a voiceover or a clip, reads its
      header before storing anything, and refuses a file that does not declare
      its own length — a clip whose `source_duration` is a guess cannot be
      stopped from reading past its end. WAV is in for that reason and **MP3 is
      refused**: a WAV's length is in its header, an MP3's needs every frame
      walked. Uploading the same file twice returns the existing row.
- [x] **The scanner cannot read a waveform, and that changes the rules.** Every
      other egress path is protected by a pre-flight scan; a recording of
      somebody reading a customer list scans clean because there is nothing to
      read. So `TRANSCRIBE_FORBIDDEN_CLASSES` refuses `mailbox` and `internal`
      **by class, before a provider is looked up** — their protection *is* that
      scan. The tier filter still applies in full, the text part of the request
      is still built from the allowlist and still scanned, and the egress log
      records the size and word count but **never the audio or the transcript**.
- [x] **Word timings, not sentence timings.** A caption timed to a sentence
      appears in full before it is spoken. Three response shapes are read (flat
      words, words nested in segments, segments alone) and a segment-only answer
      is kept rather than refused.
- [x] **Where to break is deterministic, not a second model call.** Sentence end,
      then pause (>0.6s), then line length (42 chars), then maximum hold (5s). A
      comma only breaks once the line is over half full — breaking at every comma
      gives a stutter of two-word captions. A test asserts no word is lost
      between transcript and captions.
- [x] **The timeline's invariant is the specification.** Clips cannot overlap by
      one tick and speech does not respect that, so `lay_out` snaps to frames,
      holds each cue back from the next, stretches short cues only into the gap
      actually in front of them, and **merges a cue that cannot get one frame
      into its neighbour** rather than dropping a word.
- [x] Media time is mapped through the clip's start, `in_point` **and** speed, so
      captioning a trimmed clip captions what is left and a slowed clip stretches
      its captions with the speech. Both have tests.
- [x] **Captions are ordinary text clips** on a Captions track, so every existing
      edit works on them and a person reads them before publication — the same
      judgement the swipe and the post approval are. The whole set is one step of
      undo; running it twice replaces rather than stacks; new pictures never land
      on the caption track.
- [x] The transcript is stored per file and reused. Deliberately **not** the
      response cache, which refuses anything whose output is a message: a
      transcript is a fact about a file that cannot change unless the file does.
- [x] `whisper-large-v3` and `-turbo` on Groq (same key as its chat models) and
      `whisper-1` on OpenAI, in both copies of `providers.yaml`. The `kind`
      filter in `candidates_for` needed no change — it was already generic.
- [x] Verified against an independent implementation: WAV files written by
      Python's stdlib `wave` module parse to the exact sample rate, channel count
      and duration.
- Not built: karaoke highlighting (the word timings are stored, the renderer
  cannot colour part of a line), translation, speaker labels, browser recording.
  **Imported footage is audible but not drawable** — its sound captions fine, the
  picture is not painted, and the manifest says so and marks the project
  unrenderable rather than exporting a hole.

### Video editor — timeline core and browser render (2026-08-14)
- [x] `offsetx_apollo_builder/video/` + `frontend/src/video/` + the **Video
      editor** screen. Docs: `docs/architecture/VIDEO_EDITOR.md`; the feature
      inventory it was cut from is `docs/architecture/CAPCUT_FEATURE_MAP.md`.
- [x] **The server owns the document; the browser draws it.** Every edit is a
      named operation, validated server-side, returned as a new document. One
      round trip per edit, and one place that decides whether an edit is legal —
      the same place that checks the exported file.
- [x] **Time is an integer at 90kHz**, the MPEG timebase, because it is the
      smallest rate whose frames are whole numbers at 24/25/29.97/30/50/60. A
      split at frame 100 is the same integer however many times the project is
      saved and re-split. An unlisted frame rate is refused, not rounded.
- [x] **Clips on a track cannot overlap.** Made unrepresentable rather than
      handled: an overlap means the renderer picks one, and which one it picks
      can differ between the preview and the export — the worst bug class an
      editor has.
- [x] **Every edit copies before it changes anything**, through
      `to_dict`/`from_dict`. A refused edit cannot half-apply and does not
      consume a step of undo.
- [x] **A split is transparent.** Both halves carry a synthesised keyframe at
      the cut, so the resolved animation is identical either side of it. A test
      resolves every tick across a split and asserts the two lists are equal.
      Trimming the head moves keyframes with the material for the same reason.
- [x] **Two resolvers, one fixture.** The browser must resolve keyframes itself
      — a preview cannot make a request per frame — so `timeline.py` and
      `resolve.ts` implement one rule twice.
      `tests/fixtures/timeline_conformance.json` holds a deliberately awkward
      document and the frame Python resolves at fifteen *chosen* ticks (the tick
      before a cut, the cut, the tick after, one past the end). Both suites
      assert against it. It forced `roundHalfToEven` in TypeScript, because
      Python breaks rounding ties to even and JavaScript breaks them upward.
- [x] **WebCodecs, and deliberately no MediaRecorder fallback.** MediaRecorder
      records in real time, drops frames silently, and writes no Duration —
      which would make the export gate unable to do its job. A fallback whose
      output cannot be verified is a quieter failure, so an old browser is told
      what it needs instead.
- [x] **A WebM muxer written by hand** (`frontend/src/video/webm.ts`), the same
      call `imagery/gates.py` made about Pillow. It buys an exact Duration
      written from the timeline that produced it.
- [x] **MP4 and WebM headers parsed by hand** (`video/gates.py`). Handles the
      display matrix (a phone records sideways) and version-1 64-bit boxes — a
      test caught a twelve-byte offset error in the latter during the build.
- [x] Gates: decodes, not_empty, readable_header, has_video_track, aspect_ratio,
      duration_matches, not_duplicate — checked against the project the file
      claims to be a render of. A failing render is **stored anyway** with its
      report: a gate result nobody can check the file against is an assertion,
      not evidence.
- [x] **Undo is a pointer move over stored history**, so there is no "unsplit"
      reconstructing what a split destroyed, and it survives a reload. Editing
      after an undo drops the abandoned branch. Capped at 300 versions.
- [x] Verified outside this project, not only by unit tests: the committed
      `muxed_sample.webm` is written by the TypeScript muxer and parsed by the
      Python gates in CI; ffmpeg reads it as `matroska,webm 1080x1920 3.00s vp9`;
      a real headless Chromium export passes the gates; and frame 0 of that
      export decodes to a blue rectangle of exactly 432x768 at (324, 576) —
      precisely scale 0.4 of a 1080x1920 canvas, measured rather than eyeballed.
- [x] Owned by the **image** campaign, whose registry entry always named video
      as what it was missing. `missing` is narrowed rather than cleared.
- Not built, and said plainly in the docs: **no AI feature is wired** (captions,
  cutout, reframe, text-to-video — every M row in the feature map); nothing
  generates video or audio material yet; no transitions (a dissolve is an
  overlap, which the invariant forbids — it needs a real transition object);
  the export holds the whole file in memory.

### Trend to post (2026-08-10)
- [x] `distribution/pipeline.py` — the piece that joins the three campaign
      kinds. Everything it needed already existed; this is the wiring, and it is
      what "run this campaign" finally means end to end. Docs:
      `docs/architecture/TREND_TO_POST.md`.
- [x] **Where the automation stops is the whole design.** Two halves, and the
      boundary between them is a judgement that already existed. `plan` goes
      topic -> brief -> candidates and **stops at the review queue**; `draft`
      takes the pictures the owner kept, writes captions and creates **draft**
      posts, which still need the approval the distribution runner has always
      required. The machine fetches, composes, generates and does the scheduling
      arithmetic; a person decides *is this picture good* and *does this go
      out*. Removing either would let the system publish something nobody saw,
      under the owner's name.
- [x] Both campaign ids are kind-checked in one call — the first must be
      distribution, the second image. A swapped id would otherwise write image
      briefs against an email campaign.
- [x] **The same topic is not planned twice.** Recorded by a key built from
      sorted terms rather than the label, because the label is the first three
      and a topic can gain a term between sweeps without becoming a different
      subject. A week's cooldown, or the review queue fills with the same
      picture every sweep.
- [x] Composition is **deterministic by default**, with an optional writer. The
      brief describes the subject and not the composition — over-specifying
      produces the same picture from every generator, defeating both running
      several and the swipe that compares them.
- [x] **The data class is chosen by what is sent**: topic terms and competitor
      titles are `public`; adding the owner's angle makes it `campaign`. The
      module decides nothing about trust — it labels honestly and the broker
      applies the rules it already has.
- [x] A failing or empty writer **falls back to the deterministic version**
      rather than costing the sweep. Tested both ways.
- [x] 21 new tests, all passing first run. Verified over HTTP, including the
      kind gate refusing a swapped campaign id.

#### Still not built
- Nothing calls it on a timer; that belongs in `AutomationService`.
- No UI for the plan/draft calls (the swipe half has one).
- One picture to three accounts carries the same caption to all three.
- The angle is a string the owner supplies — nothing derives it from their
  positioning or from what performed before, though `generator_performance` and
  the context layer both hold material that could.

### Topic clustering across channels (2026-08-10)
- [x] `distribution/topics.py`, surfaced at `GET /trends/topics` and inside the
      trends report. One channel running hot is a good week; several on one
      subject is an event, and the stronger signal.
- [x] **Distinct channels, not videos.** A channel posting five times about its
      own product has a content calendar, not a trend, so a term one channel
      uses scores one however often it repeats.
- [x] **A topic is a term common now and not before** — the same shape as the
      outlier multiple, one level down: share of channels inside the window
      against share outside, needing 2x lift. A term with no history at all is
      the strongest case, not a division by zero.
- [x] **Adaptive stopwords fall out of that for free.** Watch twenty logistics
      channels and "logistics" has a high baseline by definition, so the same
      arithmetic that finds a spike removes it. No per-industry list to
      maintain, and a hand-written one would still miss the words that matter to
      one owner and not another.
- [x] **Merging is on shared videos, not shared terms.** Term chaining is how
      clustering turns everything into one blob — A shares a word with B, B with
      C, and three unrelated stories become one topic. Tested with two
      simultaneous unrelated stories that must stay apart.
- [x] **Lexical, not semantic, and there is a test that says so.** "Rotterdam
      port strike" and "Dutch dockworkers walk out" share no word and will not
      group. Deliberate: semantic grouping means an embedding or a model call
      per sweep — a cost, a provider dependency, and a feature that dies with a
      key. The limitation is pinned by a named test so it is found here rather
      than by someone trusting the output.
- [x] 14 new tests, all passing first run.

### Trend detection on YouTube (2026-08-10)
- [x] `distribution/youtube.py` + `distribution/trends.py`. Docs:
      `docs/architecture/TREND_DETECTION.md`.
- [x] **YouTube because it is the only one of the four whose terms allow reading
      public data at scale** — no research application, no scraping. Instagram's
      Business Discovery is thin, TikTok's Research API needs approval, Facebook
      offers competitors almost nothing.
- [x] **The quota decides the design.** 10,000 units/day, and
      `search.list` costs **100** while a channel's uploads playlist costs **1
      for 50 videos**. A 1,000-channel sweep via playlists is ~1,100 units —
      daily. The same coverage via search is impossible: the whole budget buys
      100 searches. So `search` **exists only to refuse**, with the arithmetic
      in the message, and statistics are fetched batched 50 at a time.
- [x] Quota counted locally from documented per-call costs (Google exposes no
      live balance). A sweep that would exceed it **stops cleanly with a note**
      rather than raising halfway and leaving the day's picture half-updated.
- [x] **Raw view count is the wrong signal** — it returns the biggest channels'
      oldest videos every week, both already known. Two measures instead:
      velocity (views/hour, correcting for age) and **outlier multiple** (times
      the channel's *own* median). The multiple is the one that finds a subject
      rather than a channel, and there is a test where a small channel's
      20,000-view video outranks a big one's 520,000-view video because the
      first is 20x its baseline and the second is 1.04x.
- [x] A channel needs **5 observations** before its multiples are ranked; below
      that the video is listed and flagged rather than hidden, because hiding it
      would make the list depend on how long each channel had been watched. A
      20x multiple from two videos looks like insight and is arithmetic on noise.
- [x] Read-only, so **not** through the broker — same reasoning as
      `ai/discovery.py`: no owner data, only a channel id and a region code.
      Still written to the egress log so the record stays complete, and a test
      asserts the API key never appears in what is logged.
- [x] One module in `distribution/` has a transport and it is this one. The
      publishing path has none, and browser automation is refused across the
      whole package with no exception. The old blanket test was replaced by two
      precise ones rather than deleted.
- [x] 20 new tests, all passing first run. `/trends` works without a key from
      already-collected data; watching without one says so plainly.

#### Found while wiring it
- [x] `api/app.py` used `os.getenv` without importing `os`. It imported fine —
      the failure would have been a runtime `NameError` the first time anyone
      opened the trends screen.

#### Still not built
- Turning a trend into a post: `/trends` reports, nothing composes a caption
  from it. That is where this and the image campaign meet.
- Scheduled sweeps (nothing calls `/trends/sweep` on a timer).
- Topic clustering across channels — "six competitors posted about the same
  thing today" is a stronger signal than any one of them, and is not computed.

### Content distribution runner (2026-08-10)
- [x] `distribution/` — the third campaign kind, and the one that composes the
      others. All three kinds now have runners. Docs:
      `docs/architecture/DISTRIBUTION_CAMPAIGNS.md`.
- [x] **The hard part here is not code.** Each platform allows far less
      automated posting than it appears to, and the tools that seem to offer
      more are what get accounts banned. off_CRM publishes through **official
      APIs only**, and `platforms.py` declares every platform with its API, its
      preconditions, its quotas and what off_CRM refuses. Connecting an account
      it cannot post to is refused **at connection**, not at send time.
- [x] **One working adapter today: the local outbox** — not a stub, the same
      device `LocalOutboxProvider` is for email. The whole pipeline runs and is
      reviewable without touching a real account.
- [x] Quota facts recorded rather than assumed. YouTube's is **per API project,
      not per channel** (~6 uploads/day across every channel you own);
      Instagram's 25/day genuinely is per account. A planner assuming both were
      per-account would over-promise on YouTube by however many channels exist.
      Instagram's ceiling is checked **when a post is scheduled**, because a
      schedule that cannot be delivered looks like a plan.
- [x] Instagram's personal-account impossibility is refused by name; TikTok's
      unaudited private-only posting is refused rather than counted as reach.
- [x] **Goal-shaped**: "a million views", with progress against it.
- [x] **This closes the benchmark.** Gates and swipe were layers one and two
      from the image runner; engagement is layer three, and
      `generator_performance` joins it back — views grouped by the generator
      that drew the picture, so the owner's taste and the audience's can be
      compared and can disagree.
- [x] 20 new tests, and the whole loop verified over HTTP: campaign, account,
      goal, post, approve, schedule, publish, measure, progress (250,000 of
      1,000,000 views, 25%).

#### A real bug the tests caught
- [x] **Engagement snapshots were being summed.** `latest_metrics` picked rows
      by `MAX(measured_at)`, but timestamps were second-precision, so two
      readings a moment apart *both* matched the maximum and were added —
      reporting 100 views where there were 60, and a goal met when it was not.
      Now ordered by time then id, with microsecond precision on measurements.
      The test that caught it was written before the bug was known to exist.

#### Not built, recorded on the spec
- Adapters for the real platforms — each declared with the route that would
  serve it; each needs OAuth per account and, for Meta and TikTok, app review.
- Competitor watching and trend detection: the `read` column is the groundwork,
  the collector is not written, and it must be built on what terms permit.
- Automatic caption generation, scheduled publishing on a timer, and a UI.

### Image campaign runner (2026-08-10)
- [x] `imagery/` — the second campaign kind, and the first that produces
      something other than a message. `image` is now `implemented=True` with a
      runner. Docs: `docs/architecture/IMAGE_CAMPAIGNS.md`.
- [x] **The swipe is the label**, which is the answer to the owner's benchmark
      question. Not a model rating its own output — the owner's own decisions,
      collected free as a side effect of use. Every decision scores the
      generator that made the picture, and `ai/bandit.py` allocates the next
      batch on those scores using the same Thompson sampler that shifts traffic
      between email templates. The allocator does not know its arms are image
      models.
- [x] Three consequences, each tested: **a decision is made once** (or a score
      moves by clicking twice); **refresh counts as a rejection** (dropping the
      no would bias scores towards whatever got refreshed most); **rejection
      deletes the bytes and keeps the verdict** (the record of rejecting is what
      the benchmark is made of).
- [x] **It waits before steering.** Under 12 decisions per generator the
      allocator stays out of the way — a lopsided result from four swipes is
      noise, and acting on it would starve a generator that never had a fair run.
- [x] **Gates are layer one and are not about taste**: decodes, not_blank,
      readable_header, aspect_ratio (5% tolerance so a generator rounding to
      1152x648 still satisfies 16:9), not_duplicate. A gate failure is a
      separate status from a rejection — mixing "this came back broken" with
      "I do not like it" would poison the only real signal this kind has.
- [x] Failed candidates are **stored, not dropped**: "this generator returns the
      wrong ratio four times in five" is worth knowing, and a discarded
      candidate cannot say it.
- [x] **No image library.** Reading a width and a height is a header parse —
      PNG IHDR, JPEG start-of-frame walk, GIF, three WebP variants — so Pillow
      was not added to decode two integers. Fails closed on an unknown format,
      because a zero would silently pass a dimension check.
- [x] **Everything protective is inherited.** Generation goes through
      `EgressBroker.call_image`: same tier filter, same allowlist payload, same
      blocking scanner, same egress log. A structural test asserts `imagery/`
      imports no transport.
- [x] The kind gate now runs from **both sides** — `OutreachEngine` refuses an
      image campaign and `ImageCampaignEngine` refuses an email one.
- [x] Own database (`imagery.db`), three tables, and **pictures are files** at
      `0600` with the row holding a path and a hash. Same decision the egress log
      made when it chose to record the prompt and never the picture.
- [x] Seven API endpoints, and an **Image review** screen: one candidate at a
      time, three buttons, arrow-key shortcuts. One at a time rather than a grid
      because a grid invites picking a favourite and ignoring the rest, and
      "ignored" is not a label.
- [x] 22 new tests. Verified over HTTP end to end: an image campaign can now be
      created, the email runner refuses it by name, and generation with no image
      model connected fails with "Open Connectors and add one".

#### Still missing on this kind (recorded on the spec, not hidden)
- Video — the gates read image headers; duration, frame rate and audio are a
  different piece of work, and claiming video without them would claim a
  benchmark that does not exist.
- Publishing — an approved picture is an asset; posting it is the distribution
  campaign, which has its own credentials and per-platform rules.
- Layer three of the benchmark (views, watch time) needs distribution to exist.
- Brief authoring in the UI, and prompt improvement between rounds.

### Error classification (2026-08-10)
- [x] `ai/failures.py` + wiring in `ai/broker.py`. Docs:
      `docs/architecture/FAILURES.md`. The item deferred pending reading; the
      reading was of the codebase, and it changed the design twice.
- [x] **What it did before:** every provider failure treated identically —
      record, fail over, cool the model off after two. Right for a provider
      having a bad day, wrong for most of the rest.
- [x] **Three failures that cost money.** A rejected key failed over silently to
      a model that worked, so nobody found out while every call ran on a model
      the owner had not chosen. A payload *we* built wrong was tried against
      every provider in the tier and opened the circuit breaker on each. A 429
      fell through to a second provider's quota instead of waiting.
- [x] Four actions, and the classes exist only to choose between them:
      `RETRY_SAME`, `FAILOVER`, `STOP_REQUEST`, `STOP_CONFIG`. Both stops refuse
      to fail over, which is the point of them.
- [x] **Only provider-health failures open the circuit breaker.** A 400 says
      nothing about their service; letting it trip the breaker is how one
      malformed payload takes a whole tier offline.
- [x] **`unknown` fails over once and never retries** — default-deny applied to
      spending, and it lands in the log so the gap shows up there not in a bill.
- [x] **Reading the code changed the plan.** `outreach/providers.py` already
      retries three times for connection errors, 429 and 5xx, so no second retry
      loop was added: nine attempts at one model is a stuck request, not
      resilience. `RETRY_SAME` covers only what the transport does not, bounded
      by 2 retries and a **120s wall clock over the whole chain** — attempts,
      retries and failover share one deadline, and exceeding it is reported as
      `deadline_exceeded` rather than hidden.
- [x] `Retry-After` honoured when sent, capped at 300s.
- [x] `ProviderFailure` -> **502** carrying the kind, action and owner action.
      502 not 503: the upstream answered definitely and off_CRM chose not to
      route around it, so "try again later" would be the wrong advice.
- [x] `failure_kind` recorded in the egress log and grouped by
      `GET /ai/egress-log/stats`. This is the payoff: "NVIDIA has been returning
      auth errors for a week" is answerable with a kind column and not with a
      pile of 500-character strings.
- [x] **The log's first migration**, additive on both backends via the new
      `Database.add_column_if_missing` — which also closes one of the gaps the
      Postgres doc listed. Verified against a log built without the column:
      rows survive, the column appears.
- [x] `GET /ai/failure-kinds` serves the taxonomy so the inspector need not
      hard-code it.
- [x] 34 new tests.

#### Bugs found while building it
- [x] **`refus` matched "Connection refused".** The first content-filter pattern
      filed a dead network as a content filter, so off_CRM would have failed
      over politely instead of reporting nothing could be reached. Patterns on
      an error path are exercised by text nobody chose. A test pins the pair.
- [x] **A stray backspace character was written into that regex** by a patch
      script whose replacement string was not raw, so the word-boundary escape
      became a literal control character and the alternative could never match.
      Found by tracing which pattern fired, not by reading the file — the
      character is invisible. The package and test tree were scanned; it was the
      only occurrence.
- [x] `quota.record(rate_limited=...)` was a substring search for `"429"` over
      the message, which also fired on a body that merely contained those
      digits. Now driven by the classification.
- [x] A test of mine asserted failover between `mistral` (tier A) and `nvidia`
      (tier B) and got one candidate. That was the **failover-never-crosses-a-
      tier rule working**; the test was wrong and now uses two US providers.

### Response cache wired (2026-08-10)
- [x] The gap the rebuild-guide audit found is closed: `ResponseCache` is now
      constructed in `api/app.py` and passed to `EgressBroker`. Before this it
      was implemented, tested and exported with **no caller**, so no request had
      ever reached it.
- [x] **Switching it on surfaced a real defect first.** At `pseudonymous`
      policy a payload carries no name — everyone is `PERSON_1` — so two
      different prospects with the same title, category and an equivalent public
      hook build a **byte-identical** payload. Measured: two logistics directors
      who both "opened a new depot" score **1.000**, an exact hit. Wiring the
      cache as it stood would have sent both of them the same email body, which
      is the opposite of the product and exactly what spam filters cluster on.
      The 0.92 near-match threshold is no defence, because this is not a near
      match.
- [x] Fixed with an allowlist rather than a patch: **cache work whose output is
      a fact, never work whose output is a message.** `CACHEABLE_TASK_TYPES`
      holds `classify_reply`, `summarise`, `extract`, `enrich`,
      `orchestrator_plan`, `ai_chat`. An unlisted task type is not cached —
      default-deny, as everywhere else.
- [x] `NEVER_CACHE_TASK_TYPES` names `draft_email`, `template_rewrite` and
      `image_generation` **with the reason for each**, so the refusals are
      documented rather than merely absent. A test asserts every one carries a
      reason; refusals without reasons get "fixed" by the next reader.
- [x] Both axes checked independently: a never-cache data class wins even for an
      allowlisted task type.
- [x] **Evals never use the cache**, now explicitly `cache=None` with the reason
      in the source. An eval exists to measure a model; a cached answer makes it
      measure the cache, and those numbers feed a promotion decision. A test
      asserts the source still says so — the risk is someone "fixing" the
      missing cache later as an oversight.
- [x] `GET /ai/cache/stats` reports the hit rate **with** the allowlist and the
      named refusals; `POST /ai/cache/clear` empties a workspace. The published
      60–90% figures come from chat systems and do not apply to personalised
      outreach, so the only honest answer is a measured one.
- [x] Verified live: the app boots, `ai_cache.db` is created, and the stats
      endpoint serves the allowlist.
- [x] 14 new tests (48 in `test_ai_cache.py`). The existing suite had been
      written against "cache everything" and used `draft_email` throughout; it
      now uses a cacheable task type, and drafting has its own test that asserts
      the two-prospect payload collision and that nothing is stored or served.

### Rebuild guide, §10 (2026-08-10)
- [x] `docs/architecture/REBUILD_GUIDE.md`. Written **after** the system,
      describing what exists rather than specifying what should. Says so at the
      top: where the code and the guide disagree, the guide has the bug.
- [x] The abandoned `agent/off-crm-v0-12-ai-studio` branch had a 1,015-line
      rebuild guide. It was **not** reused: it describes `off_ai/`, a parallel
      module that was never merged. A rebuild guide for a system that is not
      there is the worst version of this document.
- [x] The content that lives nowhere else: **stage order with the reason each
      stage must come before the next**. Three orderings carry the security
      properties — scanner before any provider adapter (or the direct call site
      you made to test it survives as a second door); construction before
      everything (filtering is a one-way door); eval harness before the verify
      loop (or the loop invents weaker checks and measurement quietly disagrees
      with enforcement).
- [x] **15 traps**, each a real mistake, most of them made and fixed here. They
      share a shape: every one looks like a simplification and silently removes
      a guarantee.
- [x] The architecture rules that are enforced by AST tests rather than by
      discipline, listed with what enforces each. Includes the doubled-test
      pattern from campaign kinds: a list that must stay exhaustive needs a
      second test that checks the list itself.

#### Facts corrected while writing it
Every number in the guide was measured rather than recalled, and four claims
written from memory were wrong:
- [x] `ai/` is 24 modules / 10,303 lines; the package root has 24 more, not 15.
- [x] The single-gate test does not assert "three call sites". It parses every
      file in the package and fails if any module outside a **three-file
      allowlist** imports a provider constructor. Different rule, stronger.
- [x] Six named SQLite databases, not seven — and only four are opened by the
      web app; `ai_evals.db` and `ai_tools.db` belong to their CLIs.
- [x] **The response cache is not wired into anything.** `ResponseCache` is
      implemented, tested (34 cases) and exported, and `EgressBroker` accepts
      one as an optional argument — but no caller constructs one, so no request
      has ever hit it. Recorded in the guide so a rebuilder does not hunt for
      wiring that does not exist. Left unwired rather than switched on in the
      same change as a documentation task.

#### Fixed while writing it
- [x] `db/copy.py` imported `ai/log.py` for its schema — the generic backend
      layer knowing about one specific store, and the reverse of the dependency
      rule the guide states. Writing the rule down is what exposed it. `db/`
      now has a table-agnostic `copy_table(table, columns, schema, key)`, and
      the egress-log wrapper lives in `ai/log.py` where its schema is defined.

### Postgres backend, egress log first (2026-08-10)
- [x] `offsetx_apollo_builder/db/` — ~250 lines. `open_database()` returns
      something that behaves like the `sqlite3.Connection` the stores already
      use: same `execute` / `executescript` / `transaction`, same `row["col"]`
      and `dict(row)`. Docs: `docs/architecture/POSTGRES.md`.
- [x] **No ORM.** SQLAlchemy would have replaced auditable SQL with expression
      trees in a codebase whose security argument depends on reading the
      queries, for a much larger diff and the same result.
- [x] `?` → `%s` translation in `db/translate.py`, as a **character walker, not
      a regex**: both `?` and `%` occur inside string literals, and a blind
      replace corrupts data invisibly until someone reads the row back. Handles
      `'it''s'` (a doubled quote is an escape, not the end of the string) and
      doubles literal `%`, which psycopg treats as a placeholder marker.
      `outreach/store.py` alone has 449 `?`, so rewriting them was never the
      option.
- [x] Postgres runs in **autocommit** to match SQLite's `isolation_level=None`.
      The stores expect a statement to be durable when it returns; psycopg's
      default open transaction block would have changed that contract silently.
- [x] **The egress log is the store that moved, because it is the one broken in
      the deployed environment today.** §6.4: on Render `OFFSETX_DATA_DIR` is
      `/tmp`, wiped every restart. Everything else there is an inconvenience to
      lose; the audit trail is a hole in the argument — a verification trail
      that resets verifies nothing. It also has no foreign keys into the CRM.
- [x] **A bug the second engine found.** `EgressLog.stats()` selected
      `provider_name` and `jurisdiction` while grouping only by `provider_id`.
      SQLite runs that and picks an arbitrary row; Postgres refuses it. Now
      grouped on all three, which is also the answer that was meant.
- [x] `offsetx-db check` and `offsetx-db copy-log`. The copy never deletes the
      source, is idempotent by primary key, counts both sides and reports, uses
      an explicit column list (a test fails if it drifts from the schema), and
      masks passwords in everything it prints.
- [x] Only an explicit `postgresql://` / `postgres://` / `psql://` scheme means
      Postgres; everything else is a path, so a mistyped DSN fails loudly rather
      than silently creating an empty SQLite file that looks like it worked.
- [x] Resolution order is explicit → `OFFSETX_DATABASE_URL` → default path. The
      middle rung lets a deployment set one variable; the top rung keeps a
      test's scratch file safe from the environment reaching in.
- [x] Missing psycopg raises a sentence containing the install command, not
      `No module named 'psycopg'`.
- [x] Log tests are **parametrised over both backends**, 35 of them. The
      Postgres half skips with a reason unless `OFF_CRM_TEST_POSTGRES_URL` is
      set — same rule as the live Docker test.
- [x] Verified end to end against a real Postgres 16: the app boots with the log
      on the server, `GET /ai/egress-log/stats` reports `"backend": "postgres"`,
      no `ai_egress.db` appears in the data directory, and the CRM keeps working
      on SQLite in the same process.

### Campaign kinds (2026-08-10)
- [x] `campaigns` gained `kind TEXT NOT NULL DEFAULT 'email'`, schema v8.
      Registry in `offsetx_apollo_builder/campaigns.py` — **package root, not
      inside `outreach/`**, because the registry is above the email runner
      rather than part of it. Docs: `docs/architecture/CAMPAIGN_KINDS.md`.
- [x] **The migration was the easy half.** Every pre-existing row was an email
      campaign because nothing else existed, so the column default backfills
      them and there is no data migration to get wrong. The hard half is the
      code written when email was the only possibility.
- [x] **The gate.** `OutreachEngine._require_own_kind` refuses a campaign of
      another kind at all nine entry points that act on one: `import_contacts`,
      `generate_drafts`, `edit_draft`, `bulk_replace_drafts`, `schedule_drafts`,
      `approve_drafts`, `sync_replies`, `run_due`, `export_crm`. Without it the
      first image campaign would be handed to the mail sender.
- [x] Two tests keep that list honest: one asserts each listed method contains
      the check, and one walks every public method taking a `campaign_id` and
      fails if any is missing from the list. Without the second, the first
      quietly stops being exhaustive the day someone adds a method.
- [x] `run_due` is checked **before** it syncs replies, with a test whose mail
      provider raises if touched — a refusal after the mailbox has been read has
      already done the thing it was meant to prevent.
- [x] Three kinds declared, one implemented. `image` and `distribution` refuse
      at creation with **what is missing**, rather than being omitted. The
      failure mode of a bare `kind` column is a database of campaigns nothing
      will ever run; a refusal at creation is the alternative to discovering
      that a week later.
- [x] **Absent means email, wrong means stop.** A missing value is a row written
      before the column; a present unrecognised value raises. Falling back to
      email there would hand an unknown campaign to the mail sender.
- [x] `kind` is fixed at creation — `update_campaign` refuses a change rather
      than dropping it through the allowlist, because the campaign's contacts,
      drafts and messages were all made under the original kind.
- [x] The index over the new column is applied **after** the migration
      (`POST_MIGRATION_SQL`): on an existing database `CREATE TABLE IF NOT
      EXISTS` is a no-op, so an index over a brand-new column in `SCHEMA_SQL`
      would be asked for before `ALTER TABLE` added it and every upgrade would
      fail on startup.
- [x] Surfaced end to end: `GET /api/v1/campaign-kinds`, `kind` on create and as
      a list filter, `offsetx-outreach campaign-kinds`, and a picker in the
      Campaigns screen that shows unbuilt kinds greyed with their reason and
      hides the email-shaped fields when one is selected.
- [x] **Settings blob deliberately not built.** Email's settings are real
      validated columns and no other kind can be created, so `settings_json`
      today would be an unvalidated blob with no writer. The column is additive
      and costs the same later; the validator is what has to come first.

### Code graph (§4K, 2026-08-10)
- [x] `codegraph.py` + `offsetx-codegraph` (`policy`, `build`, `status`,
      `verify`, `ignore`). Docs: `docs/architecture/CODE_GRAPH.md`.
- [x] Wraps Graphify (`graphifyy==0.9.39`, pinned, run via `uvx` so it never
      enters the project venv). 7 seconds for this repo: 3,047 nodes, 7,935
      edges.
- [x] **The reason it is a module and not a shell command:** `graphify extract`
      is, in its own help, "AST + **semantic LLM**" — it finds an API key and
      posts chunks of source to gemini/openai/deepseek/claude/kimi/ollama.
      `--code-only` makes it "local AST, no API key". Two flags separate a build
      step from an egress event. The previous attempt put them in
      `scripts/build_code_graph.ps1`: PowerShell only, and editable.
- [x] `--code-only` is not a parameter of `extract_command()`. A keyword
      argument would put the unsafe call one keystroke away.
- [x] Seven refusals, each with its reason: the semantic path, `label`,
      `add <url>`, `--global` (merges into a shared file in `$HOME`), the
      `install` subcommands (they write to AGENTS.md and install git hooks),
      `--no-gitignore`, `--postgres`.
- [x] **Verified, not asserted.** After every build the graph is read back and
      **deleted** if any indexed file lives under a runtime-data path. Kept-with-
      a-warning is not an option: someone queries it anyway because the file is
      there.
- [x] `.graphifyignore` is generated from `RUNTIME_DATA_PATHS` in code,
      overwriting hand edits, and a test cross-references that list against
      `api/config.py` so the two cannot drift.
- [x] **Live probe run, three ways** (recorded in the doc): a planted
      `local_data/leak_probe.py` is excluded by `.gitignore` alone (0 nodes) and
      by `.graphifyignore` alone (0 nodes); with **both** bypassed it leaks 2
      nodes and the verifier rejects the graph by name. Each layer holds
      independently and the backstop fires when both are cut.
- [x] Staleness: `graph.json` records `built_at_commit`; `status` compares it to
      HEAD. A graph recording no commit is treated as stale.
- [x] `graphify-out/` gitignored — build artefact plus a 4.6 MB cache, rebuilt
      in seconds.

### Fixed defects found during the audit
- [x] **AI chat leaked.** It passed the raw conversation to a provider with no
      policy applied, while its own docstring claimed the opposite. Chat now
      goes through the broker. `ai_chat.py` no longer imports any transport, and
      a test asserts it never will again.
- [x] **Scanner newline bug.** Patterns ran against a JSON dump, which escapes
      `\n` and silently disabled every `^`-anchored mail-header rule — the
      payload looked clean exactly when it held a pasted email. Patterns now run
      against raw string values.
- [x] Removed `frontend/src/providerCatalog.ts`, which hardcoded providers in
      TypeScript and recommended DeepSeek for "bulk email generation".

---

## 4. Not built yet

Listed honestly. Nothing below is silently assumed done.

| § | Item | Note |
|---|---|---|
| 4D | Two-mode campaign intake | **Built** (`intake.py`). Generate/Parse split, plus PDF reading. Deliberately outside `ai/` — a contact list must never reach a model. Remaining: no UI screen, and generate mode is the brief object only; wiring it to discovery is separate. |
| 4G | NotebookLM export | **Built** (`notebook.py`, `offsetx-notebook`). Remaining: no API endpoint and no UI screen — and the web shape has a real problem to solve first, since a zip download would put the identity key back inside the folder the owner uploads. Two separate downloads is probably the answer and needs deciding, not defaulting. No scheduled re-export. |
| 4H | Bandit / automatic traffic shifting | **Built** (`ai/bandit.py`, `context.traffic_split`). Decides *how much* traffic each approved variant gets; still never decides *whether* a rewrite goes live — that stays with the owner per §3. |
| 4J | Bring-your-own tools, sandboxed | **Built.** Isolation in `ai/sandbox.py`, registry in `ai/tools.py`, CLI `offsetx-tools`. §5.12(c) covered. Remaining: no model-facing path yet (nothing hands the catalogue to a model or lets a plan call a tool — deliberate), no UI screen, and the container flags still need one live run against a real daemon. |
| 4K | Graphify code graph | **Built** (`codegraph.py`, `offsetx-codegraph`). Remaining: no CI job, no automatic rebuild on commit (Graphify's git hooks are on the refused list), and nothing inside off_CRM reads the graph — handing a model a map of the codebase is a separate decision. |
| — | Campaign `kind` column | **Built** (`campaigns.py`, schema v8). Remaining: no `settings_json` blob — deliberately deferred until there is a kind whose settings are known, since a validator has to exist before the blob does. |
| — | Postgres | **Partly done.** The seam is built and tested (`db/`), and the **egress log** runs on either backend. The other five stores — CRM, context, recall, scoreboard, cache, sales — are still SQLite-only. Also missing: a Postgres migration path (`PRAGMA table_info` / `user_version` have no equivalent yet), FTS (`fts5` → `tsvector` is a reimplementation), and connection pooling. |
| 10 | Rebuild guide | **Written** — `docs/architecture/REBUILD_GUIDE.md`. Stage order with the reason each stage must precede the next, the 15 traps, the invariants that are enforced by AST tests, and what is deliberately absent. |

---

## 5. Decisions and why

1. **`full` policy kept as a user choice.** The brief said addresses never leave;
   the owner overrode that and asked to keep the freedom. Implemented as: full
   is available on any tier, but above a tier's ceiling it needs an override
   with a written reason, stored with who decided and when. Never silent, never
   a default, never reached by failover.
2. **Chinese providers stay enabled and useful — but pseudonymously.**
   *Superseded 2026-07-31.* The original decision gave tier C the person's real
   public name, company and title. The owner then identified client and POI
   identity as the business secret, which contradicts it. Resolved by adding a
   `pseudonymous` policy between `strict` and `minimal` and lowering tier C's
   ceiling to it: a restricted provider still receives the job title, category
   and public hook — enough to write something specific — but the person and
   company arrive as `PERSON_1` and `COMPANY_1`, and owner-typed free text is
   scrubbed of the name as well. off_CRM re-attaches the real values locally,
   the same way it already does for addresses. `minimal` is unchanged for tiers
   A and B. Tier C is still useful for public and coding work at full detail.
3. **Google demoted to C.** Acceptable jurisdiction, but free-tier terms permit
   training on input. If billing moves to paid, re-verify and pin `trust_tier: B`
   with a note.
4. **SQLite kept.** Swapping the 2,221-line store to Postgres mid-hardening
   would have risked 88 passing tests for no security gain. Flagged above.
5. **Per-workspace, not global.** Multi-user from the start: one colleague
   raising a provider cannot change what another's calls send.
6. **Log payloads on by default.** The older audit defaulted to off, which meant
   it could only report "42 characters were sent" — useless for the question the
   owner actually has. Bounded at 20k rows.

---

## 6. Open questions for the owner

1. **Recall coverage** — the index covers sent mail. Whether attachments and
   older archives outside off_CRM should be pulled in is an owner decision.
2. **Orchestrator** — confirm the §7 reversal, and which model is the head.
2b. **Tier C and person identity — resolved 2026-07-31.** Pseudonymised; see
   §5.2. Open sub-question: whether `PERSON_1` / `COMPANY_1` should become
   stable *across* jobs for the same contact, so a model could in principle
   recognise a returning prospect. Today they are constant per payload, which
   means no mapping table exists and there is nothing to leak. Making them
   durable would need a stored mapping and is a real trade — flagged, not built.
   *Partly answered 2026-08-10:* the notebook export needs distinct tokens
   within one bundle or the export says nothing, so it numbers `PERSON_1..n`
   **per bundle** and writes the mapping to a file outside the uploaded folder.
   That is a stored mapping, but a local one with a single obvious owner. If
   cross-job stability is ever wanted, that file is the shape it should take —
   not a column on `contacts`.
3. **Positioning line** — set per workspace in Connectors; no default shipped.
4. **Render deployment** — `render.yaml` deploys `branch: main` with
   `autoDeploy: true`, so nothing ships until this branch is merged there.
   Two things to set up before the first deploy:
   - Provider keys as environment variables `OFFSETX_AI_<PROVIDER>_KEY`
     (e.g. `OFFSETX_AI_MISTRAL_KEY`). `OFFSETX_DATA_DIR` points at `/tmp`
     on Render, which is wiped on every restart, so the encrypted key file
     will not survive. The env fallback is why keys still work there.
   - **The egress log lives in the same disposable `/tmp` directory.** It is
     the audit trail, and on Render it resets on every restart. Fine for a
     demo; a real shared deployment needs a Render disk or Postgres.
5. **Postgres** — needed before "millions of users"; say when.

---

## 7. How to verify the wall yourself

```bash
python -m pytest tests/test_ai_egress_wall.py -v   # 30 security cases
python -m pytest tests/test_ai_api.py -v           # 15 API cases
```

Then in the app: **Connectors** → connect a provider → **What was sent** →
Inspect any row. The payload shown is byte-for-byte what left the machine.
