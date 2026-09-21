# Design decisions

**What this is.** Calls made while building, written down with what they cost.
Plain English.

**How this differs from the two files beside it.**

| File | Whose decision | Question it answers |
|---|---|---|
| `OPEN_QUESTIONS.md` | The **owner's** | "Which of these options do you want?" |
| `DECISIONS.md` | The **builder's** | "Why is it built this way and not the obvious way?" |
| `DEFECT_LOG.md` | Nobody's | "What broke, and how was it found?" |

**Why it exists.** These used to live in module docstrings and commit messages.
Docstrings are read by whoever opens that file; commit messages are read once.
Neither answers "have we already decided this?", which is the question that
wastes a session when nobody can answer it.

**The rules.**

1. Log a decision when the obvious thing was **not** done. Doing the obvious
   thing needs no entry.
2. Say what was given up. A decision with no cost was not a decision.
3. Say what would make it wrong. That is the trigger to revisit it.
4. Never delete an entry. If it is reversed, add a new one that says so.

---

| ID | Date | The call | Cost |
|---|---|---|---|
| DD-01 | 2026-08-25 | No proxy inside the browser box | The allow-list lives in the browser, not at the socket |
| DD-02 | 2026-08-28 | off_CRM never handles a password | Sign-in cannot be automated at all |
| DD-03 | 2026-09-05 | A signed-in page counts as private by default | Planning fails closed without an approved high-trust model |
| DD-04 | 2026-09-06 | **No Cloudflare or anti-bot evasion. Ever.** | Pages that challenge a real browser stay unreachable |
| DD-05 | 2026-09-06 | Ten verbs, closed. No `evaluate`, no code | Some pages cannot be driven at all |
| DD-06 | 2026-09-10 | The trace *is* the progress — no checkpoint file | Resume costs a full replay of the log |
| DD-07 | 2026-09-10 | Page text never enters `trace.jsonl` | Every quote needs a second file beside the log |
| DD-08 | 2026-09-10 | Injection is recorded, never blocked | An attack is visible but not stopped |
| DD-09 | 2026-09-10 | `goto` is exempt from the duplicate-action guard | A URL whose GET has a side effect is not protected |
| DD-10 | 2026-09-11 | The step's signature is the record of what ran, not its English | Every writer of an action step must add the marker |
| DD-11 | 2026-09-11 | A wall **may** stop a run, though injection may not | A wrong match costs the owner a glance at a browser |
| DD-12 | 2026-09-11 | `needs_human` can be resumed; `human_gate` cannot | Two endings that look alike behave differently |
| DD-13 | 2026-09-11 | The provider's own token counts beat our character count | Two numbers to explain instead of one, so each call says which it is |
| DD-14 | 2026-09-11 | The run's estimate rides on `run_started`, not its own step | Less visible in the log than a step of its own would be |
| DD-15 | 2026-09-11 | The ceiling predicts from the worst decision so far, not the average | Runs stop a little earlier than they strictly need to |
| DD-16 | 2026-09-11 | A resumed run re-applies the ceiling it was started with | Raising it needs an explicit argument, which is easy to forget |
| DD-17 | 2026-09-11 | An unattended run may not use a countdown at all | The attended and unattended paths through the gate are different code |
| DD-18 | 2026-09-11 | Shared state is shared by construction, not by asking callers | A class-level registry keyed by file, which is global state by another name |
| DD-19 | 2026-09-11 | The pace floor records a deadline, not a last-seen time | A run reserves its slot before it knows whether it will use it |
| DD-20 | 2026-09-16 | A latency ceiling stops new work at operation boundaries; it does not kill an operation already in flight | The run can exceed the ceiling by the latency of one already-started operation; the overrun is measured and reported |
| DD-21 | 2026-09-18 | Keep crawl scheduling deterministic and local; do not add ML, Redis or a second crawler framework | SQLite is a single-host frontier today; a future multi-host crawler must move this boundary to shared storage |
| DD-22 | 2026-09-20 | Owner-authorized build-ahead may consume a code-complete upstream story in IN_REVIEW, but downstream work also stops at IN_REVIEW until the dependency chain is verified | More review debt can accumulate before the owner's dedicated verification pass |
| DD-23 | 2026-09-20 | Extraction packs are validated JSON data over the existing Scrapling parser; no parser plugins, templates, code or AI | DOM changes require pack maintenance and semantic extraction is intentionally absent |
| DD-24 | 2026-09-20 | Competitor teardown starts as deterministic structure mapping into the existing recipe/assembly/review path | It cannot infer subjective creative intent; adding AI later requires measured eval evidence |
| DD-25 | 2026-09-20 | Explicit privacy deletion removes a whole matching trace run and deletes CRM identity data last | A run containing mixed subjects can lose unrelated trace context, but append-only audit history is never silently rewritten |
| DD-26 | 2026-09-20 | Browser platform identity, pacing and default budgets come from one packaged validated registry | Changing a built-in platform declaration requires a code/config release rather than a runtime admin edit |
| DD-27 | 2026-09-20 | PLAN.md is mutable steering state, while every model decision captures the exact plan version it saw into the append-only trace | The same plan text exists once as current state and again as historical evidence |
| DD-28 | 2026-09-20 | Companions are rows in the existing tool-registry SQLite DB, with exact memory scopes and execution-time tool-grant checks | Companion persistence is coupled to the local tool-control database until the broader workspace storage story moves it |

---

## Detail

### DD-04 — No Cloudflare or anti-bot evasion. Ever. · 2026-09-06

**The obvious thing.** The owner asked for the agent to understand Cloudflare
"and bypass it". Fingerprint spoofing, CAPTCHA solving, TLS forgery and
headless-detection evasion.

**What was done instead.** None of it, and none of it will be.

**Why.** Four reasons, and the first is the one that decides it.

1. **The penalty is losing the account, not being slowed down.** These platforms
   do not answer a suspected bot with a rate limit. They close the account. The
   thing being risked is the asset the owner spent months building.
2. **The race is permanently lost.** The other side has more people on it than
   this project will ever have, and they ship continuously.
3. **It destroys the only thing competitors cannot copy.** An auditable agent is
   the product. An agent that forges its way in cannot be audited by anyone.
4. **It moves the legal exposure onto the owner**, in a jurisdiction where that
   is not a theoretical cost.

**What was built instead, and why most of the want is already met.** A real
Chrome, with the owner's real profile and real operating-system input events, is
not challenged — because it is not a bot. `S-11.03.01` handles the rest: when a
challenge does appear, the run stops and asks the owner.

**What would make this wrong.** Nothing about the arms race. Only a change in
what the owner is willing to risk, and that is `OPEN_QUESTIONS.md`, not here.

### DD-06 — The trace is the progress · 2026-09-10

**The obvious thing.** Write a checkpoint file: where the run got to, what it
found, what it tried.

**What was done instead.** Nothing new. The run resumes by replaying its own
append-only log.

**Why.** A checkpoint is a second record of the same facts, and two records
disagree eventually — usually after a crash, which is the exact moment resume is
needed. The log is written before anything else happens and is already the thing
the audit depends on. A design note from August had already said this; two
thirds of the story was reading it rather than reinventing it.

**Cost.** Resuming reads the whole log. Runs are capped at 50 steps, so this is
not a real cost yet. It would become one if that cap moved a lot.

### DD-08 — Injection is recorded, never blocked · 2026-09-10

**The obvious thing.** Find an instruction hidden in a page and stop.

**What was done instead.** Write it down and carry on under the owner's goal.

**Why.** The agent is already contained by something stronger than a detector: a
model driving this browser can name one of ten verbs, cannot supply code, and
cannot reach the CRM. An instruction sitting on a page has nothing to reach for.
The fire door was built first; this is the smoke alarm. What was missing was not
containment — it was that an attack left **no mark at all**.

**Cost.** A real attack is visible and not stopped. Accepted, because the thing
it would be stopped from doing is already impossible.

**What would make this wrong.** The verb list growing something that can act
outside the page — a file write, a network call, a CRM update. Then this trade
has to be re-argued from scratch. See DD-11, where it was.

### DD-11 — A wall may stop a run, though injection may not · 2026-09-11

**The obvious thing.** Follow DD-08: detect, record, carry on.

**What was done instead.** The wall detector stops the run.

**Why the same project made the opposite call twice.** The costs are opposite. A
wrong injection match costs one line in a log, so those patterns can be broad
enough to catch a rephrasing. A wrong wall match costs the owner a glance at a
browser — so that detector reads structure rather than prose and wants
corroboration before it speaks.

What makes stopping safe is that it is **cheap and reversible**: the check runs
before the model is asked anything, so no budget is spent, and the run resumes
from the same step. Where the two errors are close it leans towards asking,
because a false negative costs a whole run spent against a locked door.

**Cost.** A settings page with a password field on it will pause a run.
Accepted; the owner resumes.

### DD-12 — `needs_human` resumes, `human_gate` does not · 2026-09-11

**The obvious thing.** Both are "the run stopped and a person is needed", so
treat them the same.

**What was done instead.** One resumes and one does not.

**Why.** They are opposite situations wearing the same coat.

- **A wall** — a person must act before the run *can* continue. Once they have
  signed in, the right thing is for the run to carry on from where it was.
- **A human gate** — the agent wants to do something consequential and a person
  must decide whether it happens *at all*. That is not a thing you resume into;
  it is a thing you approve or refuse.

**Cost.** Two endings that look alike behave differently, which is a thing
somebody will get wrong later. It is written at the line that decides it, in
`resume()`, and not only here.

### DD-13 — The provider's receipt beats our guess · 2026-09-11

**The obvious thing.** Keep estimating from character counts. It was already
written, it was close enough, and it needed no new code.

**What was done instead.** Read the `usage` block the provider already sends,
price that, and label every figure with where it came from — `provider` when it
is the receipt, `estimated` when it is not, `cache` when nothing was sent.

**Why.** The guess is wrong in a way that cannot be corrected: characters per
token varies by model and by language, and it cannot see the tokens a provider
adds itself. More importantly it made "what did this run cost" unanswerable with
authority — the number was off_CRM's opinion, and the owner is entitled to the
provider's.

**Cost.** Two numbers to explain instead of one, so every call now has to say
which kind it is. That is a real cost in the interface and it is the honest
version: reporting a guess without saying so is the cheaper option and the
worse one.

**What would make this wrong.** Nothing likely. If a provider reported usage
that disagreed with its own invoice, this would need a third source, which is
what the `usage_source` field leaves room for.

### DD-14 — The estimate rides on `run_started` · 2026-09-11

**The obvious thing.** Give the estimate its own step in the trace, the way
every other notable event gets one.

**What was done instead.** It goes in `run_started`'s own record, beside the
goal and the budget it was derived from.

**Why.** It is not an event that happened. It is a property of the run, computed
from the budget recorded in that same line — and splitting "what this run was
asked to do" from "what that should cost" across two adjacent steps makes each
of them half a record. A resumed run also reads it back for free.

**Cost.** It is less visible in a `grep` of the log than a `needs_human` or
`injection_suspected` line is. Mitigated by putting the sentence in
`run_started`'s detail as well as the JSON beside it.

**Honest note.** There was a second reason, and it is not a good one on its own:
a new step shifts every trace id after it, and five test files hardcode
`step-000002`. That fragility is `D-37` and is filed as `S-06.02.14`. It is
recorded here because a decision that happens to avoid a problem should say so,
rather than being remembered later as pure design.

### DD-15 — Predict from the worst, not the average · 2026-09-11

**The obvious thing.** Predict the next decision from the average of the ones
so far. It is the standard estimator and it is what everybody reaches for.

**What was done instead.** The most expensive decision the run has made.

**Why.** A ceiling is a promise, and the average lags a trend. A run whose pages
keep getting bigger — which is the normal shape of a search that is working —
would walk straight past the line while the average still said there was room.
The two errors are not symmetrical: stopping early costs the owner a run they
can restart with a higher ceiling, and going over costs them a limit they set
and did not get.

**Cost.** Runs stop a little earlier than they strictly need to, and one
unusually large page makes every subsequent check pessimistic for the rest of
the run.

**What would make this wrong.** If stopping early turned out to be expensive in
practice — a run that has to be restarted repeatedly — the answer is a smarter
predictor, not a more optimistic one.

### DD-16 — A resumed run keeps its ceiling · 2026-09-11

**The obvious thing.** `resume()` reconstructs the goal, the budget and the
schema from the trace. Let the caller pass a ceiling if they want one.

**What was done instead.** The ceiling is recorded on `run_started` and
re-applied automatically. Raising it takes an explicit
`resume(spend_ceiling_usd=…)`.

**Why.** The default would have been "no ceiling", and that turns the whole
feature into a speed bump: stop at the limit, resume, spend without bound. The
spend is read from the trace too, so a run killed and restarted ten times
counts one allowance rather than ten.

**Cost.** Raising a ceiling needs an argument somebody has to remember exists.
That is the right way round — forgetting it means the run stops, which is safe;
forgetting it the other way means the run spends, which is not.

### DD-17 — An unattended run may not use a countdown · 2026-09-11

**The obvious thing.** A countdown is a delay with a cancel. Let any caller
supply one; if nobody cancels, the action goes ahead.

**What was done instead.** `Page.click` refuses a countdown outright when the
page is in unattended mode, and sends the action back to the owner instead.

**Why.** A countdown with nobody watching is a sleep with extra steps — and
worse, it is the human gate deleted while still looking like it is there. Five
seconds pass, nobody cancels because nobody is there, and the agent has
effectively approved its own consequential action.
`docs/architecture/AUTONOMOUS_BROWSING.md` already said this in words —
*E-11 does not auto-confirm anything; autonomy is about the path, not about the
permission* — and a rule that lives only in a document is a rule somebody will
implement past.

**Cost.** The attended and unattended paths through the gate are now different
code, so there are two behaviours to keep in mind rather than one. That is the
right trade: the alternative is one behaviour that is wrong half the time.

**What would make this wrong.** Nothing about the mechanism. Only a decision
that unattended runs may act consequentially without a person, which is a much
bigger question than this and belongs in `OPEN_QUESTIONS.md`.

### DD-18 — Shared state is shared by construction · 2026-09-11

**The obvious thing.** `BudgetLedger` already takes a data directory. Tell
callers to build one and pass it around, the way they already pass the ledger
into each `Page`.

**What was done instead.** The lock is keyed by the resolved file path on the
class, so any number of `BudgetLedger` objects over one file share it
automatically.

**Why.** That instruction was already in the design and it was already being
ignored: concurrent runs each built their own ledger, the per-instance lock
protected nothing, and two thirds of the writes were lost (`D-43`). Correctness
that depends on every caller remembering a convention lapses the first time
somebody constructs one locally — and the failure is silent, which is the worst
combination.

**Cost.** A class-level registry is global state wearing a smaller hat. It never
shrinks, and two ledgers over paths that resolve the same are treated as one,
which is right here and would not be right everywhere.

**Why `Pace` is not keyed the same way.** Its natural boundary is a browser
session rather than a file — one browser is one set of logins acting as one
person — and there is no path to key on. So `BrowserSession` holds one and the
obvious construction picks it up. That is weaker than the ledger's guarantee,
and it is the reason `Page.pace`'s docstring says to pass `session.pace` rather
than mentioning it in passing.

### DD-19 — The floor records a deadline, not a last action · 2026-09-11

**The obvious thing.** Remember when each host was last acted on, and make a
caller wait until `floor` seconds after that. It is what the code did.

**What was done instead.** Remember when each host may *next* be acted on, and
have a caller claim that slot — moving the deadline forward — before it sleeps.

**Why.** The obvious version has a race that only appears with more than one
run, which is the entire point of this story. Two runs arrive together, both
read "the last action was ages ago", both conclude they need not wait, and both
act in the same millisecond. Claiming first means the second run is told to wait
by the first run's reservation rather than by its own observation.

**Cost.** A run reserves a slot before it knows whether it will use it, so an
action that raises after pacing leaves a gap nobody fills. The floor is a
minimum, so waiting slightly longer than necessary is the harmless direction.

### DD-20 — Latency stops at an operation boundary · 2026-09-16

**The obvious thing.** Wrap every provider or browser call in a wall-clock timeout
and cancel it at the exact millisecond ceiling.

**What was done instead.** Let an already-started operation finish, record its
measured latency, then refuse to start anything else once cumulative trace
latency reaches the ceiling.

**Why.** A cancelled browser operation may already have clicked, submitted or
changed remote state, and a cancelled provider request may still be billed. The
current interfaces have no transaction or cancellation acknowledgement that can
prove the side effect rolled back. Exact cancellation would make the number look
stronger while making execution less trustworthy.

**Cost.** The ceiling can be exceeded by one operation already in flight. That
overrun is explicit in the trace and `RunOutcome`, never hidden.

**What would make this wrong.** Every effectful provider/browser operation gaining
an idempotency or cancellation contract that proves whether the effect happened.


### DD-22 — Build ahead, never certify ahead · 2026-09-20

**The normal rule.** A story enters READY only after every dependency is DONE.

**The owner's explicit change.** The owner wants implementation to continue in
batches and will run a dedicated verification pass later. When an upstream
story is code-complete and only verification is deferred, an explicitly named
downstream story may therefore be built on top of it.

**Guardrail.** This changes implementation flow, not truth. The downstream
story may move only as far as IN_REVIEW. It cannot be DONE while any declared
dependency is unfinished. Automated/unit/static checks should still be run when
the available execution environment permits them; owner-side acceptance is not
invented.

**Cost.** Several stories can accumulate in review at once, so a defect in an
early slice can create rework in later slices.

**What would make this wrong.** If the upstream contract itself is still
ambiguous or changing, build-ahead stops. This exception is for deferred
verification, not unresolved design.


### DD-23 — Extraction configuration stays data · 2026-09-20

A new source declares domains, one record selector and bounded text/attribute
rules in JSON. The existing Scrapling parser executes those selectors after the
existing URL/robots/SSRF boundary. Python callbacks, templates, JavaScript,
remote packs and model extraction are refused.

**Cost:** a changed DOM can break a pack. **Revisit when:** stable public pages
cannot be represented with bounded selectors and measured semantic extraction
beats the deterministic baseline.

### DD-24 — Competitive analysis is structural and deterministic first · 2026-09-20

Normalized public facts map to an existing recipe and bounded shape parameters.
No competitor media, caption, transcript or audio crosses into a project. The
project then uses our own material and the existing human review queue.

**Cost:** it does not claim to know why a post worked. **Revisit when:** a fixed
evaluation set shows an AI structural classifier materially improves recipe
selection without leaking source content or bypassing review.

### DD-25 — Delete the matching trace run; do not edit history · 2026-09-20

Trace JSONL is append-only by design. A privacy deletion that rewrites selected
lines would turn that guarantee into a lie, so a run containing a verified
subject identifier is deleted as one filesystem unit, including screenshots and
captures. Auxiliary stores delete first; CRM identity rows delete last so a
failed auxiliary cleanup can be retried with the same join keys.

**Cost:** a mixed-subject run can lose unrelated trace context. **Revisit when:**
traces gain a cryptographically safe subject-partitioned storage format.


### DD-26 — One platform registry owns the moving pieces · 2026-09-20

Identity signals, domains/pacing and default account budgets used to be three
Python constants. Reddit was already present in the budget table and absent from
the other two, proving that drift was not theoretical. A packaged JSON registry
now owns all three and is validated all-or-nothing at load time.

**Cost:** editing built-in platform policy is a release, not an admin-panel
change. **Revisit when:** platform policy needs owner-specific runtime overrides;
those overrides should layer on top of this baseline rather than duplicate it.

### DD-27 — PLAN.md is mutable; the trace records what was seen · 2026-09-20

There is exactly one current PLAN.md in a run directory and the model reads it
fresh before every decision. The owner can edit it directly to steer the next
decision. The exact text seen by each decision is copied into that decision's
private trace capture, preserving auditability without turning the trace into a
second editable plan.

**Cost:** historical plan versions consume small extra run storage. **Revisit
when:** plans become large enough that content-addressed snapshots materially
reduce storage without making audit inspection harder.

### DD-28 — A companion narrows existing capabilities · 2026-09-20

A companion does not own a second model/tool/memory engine. It stores a name,
instructions, one exact memory scope and owner-granted tool IDs. Runtime starts
by intersecting those grants with tools that still exist and are enabled, and
tool execution checks the grant again.

Profiles live in the existing ToolRegistry SQLite database. This gives durable
transactions and multi-process writer safety without adding another storage
mechanism.

**Cost:** the companion table shares the tool-control DB. **Revisit when:** a
future workspace storage migration moves both tools and companions together.


### DD-29 — API privacy is default-deny; bootstrap and signed callbacks are explicit exceptions · 2026-09-22

All `/api/` routes are private unless they are in the closed public path/prefix
allowlist. Login/session bootstrap, signed unsubscribe and signed SES/SNS
callbacks cannot require an existing CRM session by definition; they are the
explicit exceptions and their own authentication/signature rules still apply.

**Cost:** adding a genuinely public endpoint requires an explicit allowlist edit
and a boundary-test change. **Why:** the alternative is a route becoming public
because somebody forgot to add an auth decorator.

### DD-30 — Accessibility is enforced as a frontend invariant, not a page checklist · 2026-09-22

The shared shell owns skip navigation, visible focus, current-page state, live
feedback and modal focus management. A recursive repository test rejects
pointer-only generic click targets, positive tab order and fake role-buttons
without keyboard handlers across every TSX screen.

**Cost:** unusual custom controls need a real semantic/keyboard contract rather
than a quick div+click implementation. That is intentional.

### DD-31 — Meeting audio is transient and provider-bound · 2026-09-22

Meeting capture exists only on a loopback backend reached from a loopback browser
Origin. The browser locally mixes microphone plus shared system/tab audio and
holds chunks in memory until they are sent through the existing governed
transcription broker. Raw audio is never stored by off_CRM.

The transcription provider/model is frozen when the meeting record is created;
later chunks cannot redirect audio to a different provider. Only derived
transcript/timing/provenance metadata is persisted.

**Cost:** capture cannot run from the hosted CRM and a browser must support
system-audio sharing. Failed chunks must be retried while the capture page still
holds them in memory. **Revisit when:** a native desktop capture process can
provide the same or stronger local custody with an inspectable permission model.
