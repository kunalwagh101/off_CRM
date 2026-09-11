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

