# Orchestration design — answers, grounded in the code

Written after reading the AI module (5,571 lines, 14 files) and running the
suite: **258 passed, 1 pre-existing failure** (`test_scrapling_parser…`, an
optional dependency, failing before this work and unrelated).

Every claim below cites a file and line. Where the code disagrees with what was
asked for, that is said plainly rather than smoothed over.

---

## Part 1 — "Look but not touch" is not a real thing

The objection was right, and the phrase was wrong. There is no looking. When a
model receives a field, that field left the machine, sat in someone's RAM, and
likely landed in a log.

**The good news: off_CRM never implemented "looking" anyway.** It implemented
exactly the right thing — a field either goes into the payload or it does not.

`ai/payload.py:167` builds every payload from an **empty dict**:

```python
built: dict[str, Any] = {
    "schema_version": 1,
    "task": _clean(request.task_type, 120),
    ...
}
```

Nothing is copied then stripped. Each `built[...] = ...` is one deliberate
decision to let one field leave. A new column added to the contacts table cannot
appear in a payload unless somebody edits `PersonPublic.from_contact`
(`payload.py:50`).

That is stronger than filtering. Filtering fails **open** when you forget a
field. Construction fails **closed**.

### The exact field list

This is the "which detail, which document" answer. Read from
`payload.py:115-232`.

| Field | strict | minimal | standard | full |
|---|:--:|:--:|:--:|:--:|
| `category`, `route`, `tension`, `contribution` | ✔ | ✔ | ✔ | ✔ |
| `questions` (up to 3) | ✔ | ✔ | ✔ | ✔ |
| `full_name` | ✖ | ✔ | ✔ | ✔ |
| `first_name` | ✖ | ✔ | ✔ | ✔ |
| `title` | ✖ | ✔ | ✔ | ✔ |
| `company` | ✖ | ✔ | ✔ | ✔ |
| `public_hook` | ✖ | ✔ | ✔ | ✔ |
| `sender_positioning` | ✖ | ✔ | ✔ | ✔ |
| `hook_source` | ✖ | ✖ | ✔ | ✔ |
| `linkedin_url` | ✖ | ✖ | ✔ | ✔ |
| `template` | ✖ | ✖ | ✔ | ✔ |
| `campaign_notes` | ✖ | ✖ | ✔ | ✔ |
| `prior_drafts` (max 3) | ✖ | ✖ | ✔ | ✔ |
| `conversation` | 6 turns | 6 turns | 20 turns | 20 turns |
| `public_context` | ✔ | ✔ | ✔ | ✔ |
| **real email address** | ✖ | ✖ | ✖ | ✔ (opt-in) |
| **credentials** | ✖ | ✖ | ✖ | **✖ always** |
| **mailbox headers** | ✖ | ✖ | ✖ | **✖ always** |
| **internal field names** | ✖ | ✖ | ✖ | **✖ always** |

The last three rows are the important ones. `scanner.py:160` blocks them at
*every* policy level **including `full`**. There is no setting that lets a
credential or a mail header leave.

### And which tier gets which class

`tiers.py:189`:

| Tier | Who | May receive |
|---|---|---|
| A | Europe, self-hosted | public, person_public, campaign, internal |
| B | US, CA, GB, AU, NZ, JP, KR, IL, IN | public, person_public, campaign |
| C | China, HK, RU, and anything demoted | public, person_public |
| D | Routers/aggregators, anything unlisted | **nothing** |

`MAILBOX` is deliberately absent from every row (`tiers.py:187-189`). It needs
the exact phrase `ALLOW MAILBOX CONTENT TO LEAVE` **and** tier B or above
(`tiers.py:280`). Tier C is refused even after unlocking.

---

## Part 2 — Layer 1: private email. Confirmed, and stronger than asked.

The requirement was: nobody touches received mail, directly or indirectly.

**Built, and enforced four separate ways:**

1. `DataClass.MAILBOX` is in no tier's permitted set (`tiers.py:189`).
2. `broker.plan()` raises before any provider is even considered
   (`broker.py:219`).
3. The scanner blocks ten mailbox markers — `Message-ID:`, `Received: from`,
   `DKIM-Signature:`, `-----Original Message-----`, `On … wrote:` — at every
   policy level (`scanner.py:41-52`).
4. `recall.py` indexes **sent mail only**, enforced twice: `index_message`
   refuses an inbound row, and the SQL filters to outbound with no parameter
   that could flip it.

And the detail that shows the idea was actually understood:
`context.record_reply` **takes no reply text**. Detecting that a reply arrived
is a fact; reading what it says would be mailbox content leaving. There is
nowhere to put it.

One earlier bug is worth knowing about because it shows the scanner is load-
bearing: patterns used to run against a JSON dump, which escapes `\n` and
silently disabled every `^`-anchored mail-header rule. The payload looked
cleanest exactly when it held a pasted email. Fixed; patterns now run against
raw string values (`scanner.py:169-172`).

---

## Part 3 — The cron job. Confirmed correct.

The guess was: sending is a cron job, no AI. **Correct, and verified.**

- `outreach/engine.py` imports no AI module. Its only intelligence import is
  `LocalEmailExpert`, which is local and imports no provider.
- `outreach/automation.py` — the unattended sender — imports nothing from `ai/`.
- Sends are idempotent: a SHA-256 key is computed and checked against
  `get_message_by_idempotency` **before** sending (`engine.py:704-707`).
- Daily caps are counted from the store, not from memory (`engine.py:671`).

So the split already holds:

> **The runner has credentials and no judgement. The models have judgement and
> no credentials.**

A model cannot send an email. Not "is instructed not to" — there is no code path
from a provider response to `send`.

---

## Part 4 — Layer 2, and a conflict you should resolve

This is the one place where what was asked for and what is built disagree.

**Asked for, in this round:** Chinese models get information about you (your own
Gmail address), and client / POI email addresses are the business secret to
protect.

**What is built** (`BUILD_STATE.md` §5.2, recorded 2026-07-25): tier C providers
receive the prospect's **real public name, company and title** — because that is
what personalisation actually needs.

Both cannot be true. Concretely, at `minimal` policy a Chinese provider today
receives:

```json
{"recipient": {"full_name": "Ana Silva", "company": "Acme GmbH",
               "title": "Head of Trade", "public_hook": "spoke at the EU trade summit"},
 "sender_positioning": "We help exporters cut customs cost."}
```

No email address — that part is airtight, `PersonPublic` has no field for one
(`payload.py:28-34`). But the person is fully identified.

Also note the inverse of what was asked: **your own Gmail address never leaves at
any tier.** `scanner.py:271-280` blocks owner addresses, and `owner_domains`
blocks your domain even without an address. That is stricter than requested and
should stay.

### Three options

| Option | Tier C receives | Cost |
|---|---|---|
| **Keep today** | Real name, company, title | Best personalisation, prospect identified to a tier C provider |
| **Pseudonymise C** | `PERSON_1`, `COMPANY_1`, real title/category | Nobody identified; copy quality drops slightly |
| **Drop C to strict** | Category and question structure only | Maximum safety; tier C becomes useful only for public/code work |

**Recommendation: option 2.** A stable token per entity keeps the model able to
reason coherently ("write to PERSON_1 at COMPANY_1"), and off_CRM re-attaches
the real values locally — the same trick already used for addresses. It costs
very little quality and closes the gap between the stated intent and the code.

This is a decision only the owner can make, so nothing has been changed.

### The part nobody usually catches: shape leaks

Redaction is not enough, and this matters for the "business secret" concern.
Send this with every name stripped:

> *"Third follow-up to a technical buyer at a 180-person Series B fintech in
> Berlin who opened twice and never replied."*

Zero PII. Full leak — ICP, buyer persona, sequence design, engagement data. No
scrubber catches it because there is no identifier in it.

Today `standard` sends `template` + `campaign_notes` + `prior_drafts`, and
`campaign_notes` is free text. Tier B (US) gets all of it.

So there are two operations, not one:

| Operation | Removes | Protects | Status |
|---|---|---|---|
| **Tokenisation** | Names, addresses, companies | Identity | ✅ built |
| **Abstraction** | The *situation's shape* | Business strategy | ❌ not built |

Abstraction is a genuine gap. It is also genuinely novel — no product sells it.

---

## Part 5 — Layer 3: models access only what they created

**Built, and structurally proven rather than asserted.**

- No model can query the context store — no tool, no function, no retrieval
  interface, no provider import (`test_ai_context.py`).
- No model can search the recall index — same, asserted structurally
  (`test_ai_recall.py`).
- `test_ai_egress_wall.py:336` — `test_broker_exposes_no_retrieval_or_tool_interface_to_a_provider`.
- `test_ai_egress_wall.py:353` — `test_a_prompt_asking_the_model_to_fetch_internal_data_changes_nothing`.
- `test_ai_egress_wall.py:412` — an **AST walk over every module** proving
  `create_provider` is imported nowhere outside the broker.

That last one is the technique worth keeping. Architecture rules that are only
in a document rot. A test that walks the AST fails the build the day someone
breaks the rule.

The governing sentence in `BUILD_STATE.md` is exactly right:

> **Models never pull. off_CRM pushes.**

---

## Part 6 — The guard-model idea: don't

The proposal was to have trusted models (NVIDIA, Grok, Gemini, European) police
what the orchestrator receives.

**Don't build this.** It would be a downgrade from what already exists.

- It is non-deterministic. 95% correct is not a control, it is a leak with extra
  steps.
- The guard can be prompt-injected itself. That is a new attack surface, not a
  removed one.
- It costs latency and money on every call.
- It cannot be audited: "why was this allowed?" has no answer.

The current design already does this correctly — `payload.py` and `scanner.py`
are pure functions with no model in the loop. Google DeepMind's CaMeL reached
the same conclusion: enforcement belongs in an interpreter with capability
metadata, not in a model's judgement. Even then it stopped only 67% of attacks
on AgentDojo. A model asked politely to be a gatekeeper does far worse.

**Keep the guard as code. Use models for work, never for permission.**

---

## Part 7 — Peak output: where it actually comes from

The goal: better than any single model, every time, on fewer tokens.

That is achievable, but **not** by asking several models and blending. Research
on Mixture-of-Agents found the opposite is common: sampling your single best
model several times ("Self-MoA") beat mixed-model ensembles by up to 6.6 points.
There is a quality–diversity tradeoff, and a weak model in the mix drags the
result down.

### Where the real win is

**1. The generator–verifier gap.** Checking is easier than producing, and
cheaper — output tokens cost 3–5× input tokens. So generate with a cheap model,
verify with a strong one. Verification is mostly reading.

**2. Ground truth beats opinion.** For anything with a checkable answer:

| Task | Verifier | Cost | Reliability |
|---|---|---|---|
| Code | Test suite, type checker, linter | ~$0 | 100% |
| Extraction | Schema validation | ~$0 | 100% |
| Email copy | Length, placeholder, banned-phrase rules | ~$0 | 100% |
| Email copy tone | Model judge | cheap | ~85% |

**3. The guarantee — champion / challenger.** This is how "better every time"
becomes structural instead of hopeful:

```
champion   = best measured SINGLE model on the eval set
challenger = the orchestrated pipeline

route to challenger ONLY IF it beats champion on held-out tasks
otherwise route to champion
```

The system then cannot be worse than the best single model, because when the
ensemble loses it is not used.

### What is missing today

Grepping the AI module for `eval`, `champion`, `win_rate`, `benchmark` returns
**zero hits**. Nothing measures whether compare or orchestrated mode beats
simple mode. So today the claim is untested — and compare mode may be spending
N calls to produce a worse answer than one call.

**This is the highest-value thing to build next.** Everything else in this
document is guessing until it exists.

---

## Part 8 — What to build next, in order

| # | Item | Why first |
|---|---|---|
| 1 | **Eval harness + scoreboard** | Without it, no claim about orchestration is checkable |
| 2 | **Cross-tier cost routing for public work** | See `FINDINGS.md` — 5.6× overspend on code tasks today |
| 3 | **Verify loop** (cheap generate → deterministic check → strong review) | Where the quality actually comes from |
| 4 | **Semantic cache** | Documented 60–90% hit rates; biggest cost win for the least work |
| 5 | **Abstraction layer** | Closes the shape-leak gap in Part 4 |
| 6 | **Sandbox (§4J)** | See `SANDBOX_DESIGN.md` |
| 7 | Tier C pseudonymisation | Owner decision from Part 4 |

Fine-tuning is **last**, not first. An evolving playbook plus prompt
optimisation (GEPA beat RL by 6% average using 35× fewer rollouts) gets most of
the benefit, is readable, is editable, and is not locked to one model.

---

## Sources

- [Rethinking Mixture-of-Agents](https://arxiv.org/abs/2502.00674) — quality–diversity tradeoff
- [CaMeL](https://simonwillison.net/2025/Apr/11/camel/) — enforcement in code, not in a model
- [The lethal trifecta](https://simonwillison.net/2025/Jun/16/the-lethal-trifecta/)
- [Design patterns for securing LLM agents](https://arxiv.org/pdf/2506.08837)
- [GEPA](https://arxiv.org/abs/2507.19457) · [ACE](https://arxiv.org/abs/2510.04618)
