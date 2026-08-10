# BUILD_STATE.md

Working record for the off_CRM AI orchestration module. Read **this file** to
recover context between sessions rather than re-reading the codebase.

Then read **`docs/architecture/CAMPAIGN_TYPES.md`** before designing anything
new. The product is a CRM *with an AI layer that runs the campaigns itself*, and
email is one campaign kind of several. Nothing built from here may assume email.

Last updated: 2026-08-10
Branch: `main`
Tests: **572 Python passed, 0 failed**, 1 skipped (live Docker egress test;
set `OFF_CRM_SANDBOX_TEST_IMAGE` to a pre-pulled pinned image to run it), 6 frontend passed, frontend build clean.

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
├── log.py        egress log; own SQLite table, stores the exact payload
├── workspace.py  per-workspace settings + Fernet-encrypted provider keys
└── errors.py     structured refusals the API turns into readable answers

config/providers.yaml               ← the registry. Adding a provider is a
                                       config edit, never a code change (§4E)

offsetx_apollo_builder/             ← deliberately OUTSIDE ai/
├── intake.py     two-mode campaign intake; a contact list never meets a model
├── notebook.py   research-notebook export; the destination is a trust tier
└── notebook_cli.py  `offsetx-notebook` — targets, plan, export
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
| 4K | Graphify | Not started. |
| — | Postgres | Still SQLite. Fine for local and small teams; a shared multi-user server needs Postgres. Storage is behind a boundary, so it is a swap not a rewrite. |
| 10 | Rebuild guide | Produced last, per the brief. Not yet written. |

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
