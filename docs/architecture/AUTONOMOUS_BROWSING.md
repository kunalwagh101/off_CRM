# The autonomous browsing agent

*What "the agent goes and finds out" has to mean before it is safe to leave running.*

This is the build manual for **E-11**. It supersedes nothing in
`BROWSER_AGENT_BLUEPRINT.md` — that document mapped Strawberry's feature list
onto eight stages and is still the map. Stages 1 and 2 of that map are now
built. **This document is about the gap between "stage 2 is built" and "you can
leave it running overnight and trust what it brings back."**

Read `BROWSER_AGENT_BLUEPRINT.md` first if you have not. Read this before
writing a line of E-11.

---

## 1. The sentence this whole epic defends

> **An autonomous agent whose output cannot be audited is a rumour generator.**

Everything below follows from that. It is easy to build an agent that browses.
It is easy to build one that browses and returns a confident paragraph. The
paragraph is the problem: a language model asked to summarise what it saw will
produce something fluent whether or not it saw it, and by the time that
paragraph is in your CRM nobody can tell which sentence came from a page and
which came from the model's priors.

So the measure of this epic is not "did it browse." It is:

**Can every fact it returns be traced to a page, and does that page actually
say it?**

If yes, the agent is a research assistant. If no, it is a very expensive way of
generating plausible text, and the fact that it visited real websites first
makes it *more* dangerous rather than less, because the URLs lend it credibility.

---

## 2. What is already built

Do not rebuild any of this. It is shipped, tested against a real Chromium, and
its evidence is re-run by `scripts/verify_board.py` on every push.

| Piece | Where | What it guarantees |
|---|---|---|
| CDP client | `browser/cdp.py` | Hand-written DevTools client. Events are scheduled, never awaited by the read loop — that deadlock is fixed and has a test. |
| Session | `browser/session.py` | Attaches to a real Chrome on the owner's real profile. Stale singleton locks are interrogated, not counted. Graceful `Browser.close` before any signal, so the cookie jar flushes. |
| Perception | `browser/perceive.py` | The page as an accessibility outline in document order, with integer handles. Not HTML. A tenth the tokens and it does not break when a class name changes. |
| Actions | `browser/page.py` | **Ten verbs, closed.** Real `Input.dispatch*` events, not JS shortcuts. A handle from a previous snapshot is **refused**, never silently re-resolved. |
| Policy | `browser/policy.py` | Per-host pace floor, attended-only hosts, refused actions. Enforced in code, not requested in a prompt. |
| Request guard | `browser/guard.py` | Per-request allow-list through the `Fetch` domain, before Chrome dispatches. Deny-by-default unattended. The list can only narrow. |
| The box | `browser/box.py` | Network yes, host filesystem never. Named volume, not a bind mount. `--cap-drop=ALL`, `--read-only`, non-root. |
| Identity | `browser/identity.py` | Six platforms, several accounts each. **No function in the sign-in path accepts a password**, and a test reads every signature to keep it that way. |
| Vault | `browser/vault.py` | Session material encrypted per account. |
| Budgets | `browser/budget.py` | Per-account hour and day ceilings, checked before the action. Looking is free. |
| Trace | `browser/trace.py` | Append-only. URL, timestamp, screenshot per step. No way to remove a step. |
| **The run loop** | `agent/run.py` | perceive → decide → act → record. Every decision through the broker. Closed vocabulary enforced. Page content framed as untrusted data. Hard step ceiling. |

**That is a genuinely good foundation and it is further along than most things
calling themselves browser agents.** What it is not yet is autonomous.

---

## 3. What is missing, and why each gap matters

This is the honest audit that produced E-11. Each row was verified by reading
`agent/run.py`, not assumed.

| Missing | Consequence today | Story |
|---|---|---|
| Failure recovery | One stale handle ends a twenty-minute run | `S-11.01.01` |
| Loop / stall detection | The agent can spend 50 steps on two pages and report success | `S-11.01.02` |
| Checkpoint and resume | A deploy throws away the whole run | `S-11.01.03` |
| Money ceiling | Only steps are capped. A run left overnight has no cost bound | `S-11.01.04` |
| **Structured result** | `RunOutcome.result` is `str`. A sentence cannot enter a CRM | `S-11.02.01` |
| **Provenance binding** | The trace has URLs and screenshots; nothing ties a *fact* to one | `S-11.02.02` |
| **Claim verification** | Nothing checks that the page said what the model says it said | `S-11.02.03` |
| Visited-page memory | The same page can be fetched five times in one run | `S-11.02.04` |
| Human handoff | A CAPTCHA or 2FA wall looks like a failure | `S-11.03.01` |
| Injection detection | Injection is *contained* by the closed vocabulary but invisible in the record | `S-11.03.02` |
| Auditable report | The trace is machine-readable; a person cannot check a claim from it | `S-11.04.01` |
| Live progress | You find out at step 40 that step 4 went wrong | `S-11.04.02` |
| Concurrency safety | N runs on one account draw N budgets and break the pace floor | `S-11.05.01` |
| Idempotency | A resumed run can send the same message twice | `S-11.05.02` |

**The three in bold are the epic.** The others are hygiene — real, necessary
hygiene, but a competent engineer will produce them from the acceptance criteria
without further guidance. The bold three are where the design decisions are, so
the rest of this manual is about them.

---

## 4. The shape of an answer

### 4.1 Why a string is the wrong return type

`RunOutcome.result: str` was right for `S-02.02.01`. That story's job was to
prove a bounded loop could run at all, and a sentence is the smallest thing that
demonstrates it. It becomes wrong the moment the output is meant to *be used*:

- a string cannot be validated, so a run that found nothing and a run that found
  everything are the same type;
- a string cannot be diffed, so you cannot tell what changed since last week;
- a string cannot be sourced field by field, so it is all-or-nothing trustworthy,
  which in practice means untrustworthy;
- a string cannot be written to a CRM without a second parsing step that is
  itself a model call and therefore itself unverifiable.

### 4.2 The shape

```
Finding
  field        str          the schema field this fills
  value        str          what was found, verbatim from the page where possible
  kind         observed | derived
  source       Provenance   required — a Finding without one is not returned
  confidence   float        the model's, recorded but never load-bearing

Provenance
  url          str          the page, after redirects
  captured_at  str          UTC, ISO 8601
  step_id      str          the trace step that captured it
  screenshot   str          filename beside the trace
  quote        str          the span of page text the value came from
```

**`kind` is doing real work.** `observed` means the value appears in the page
text and can be checked mechanically. `derived` means it was computed — a count,
a sum, a normalisation — and it carries the ids of the observed findings it was
computed from. Conflating the two is how "there are 14 engineers" ends up
sourced to a page that never said 14.

### 4.3 The schema is the caller's, not the model's

The caller declares the fields it wants. The model fills them. It may not add
fields, and a field it cannot fill comes back absent with the run marked
`incomplete` — **never** filled with a guess.

This is the same rule the rest of off_CRM already runs on. `payload.py` builds
outbound requests from an allowlist starting empty; `page.py` offers a closed set
of ten verbs; `edits.py` is a default-deny registry. A model choosing the shape
of its own output is the same category of mistake as a model choosing its own
tools, and off_CRM has consistently refused it.

---

## 5. Verification: the only part that is genuinely hard

### 5.1 The rule

> A `Finding` with `kind=observed` is returned **only if** its `value` appears
> in the captured text of the page named by its `Provenance`.

Not "the model was confident." Not "the model quoted it." The captured text is
already stored — `page.read()` returns it and the trace holds it. Checking is a
string operation against a document off_CRM captured itself.

### 5.2 Normalisation, and where to stop

Comparison must survive the difference between what a page displays and what a
model transcribes. Normalise:

- whitespace runs → one space, and strip
- case → fold
- unicode → NFKC, so `＋44` matches `+44`
- typographic punctuation → ASCII (curly quotes, en/em dashes, non-breaking space)

Do **not** normalise away:

- digits, in any form — a phone number that matches only after digit-fuzzing is
  not a match, it is a different number
- word order
- negation

**The failure mode to design against is a normaliser so eager that everything
matches.** A verifier that never rejects is worse than no verifier, because it
puts a green tick next to an invention. Write the test that proves it rejects
before you write the one that proves it accepts.

### 5.3 Truncation is not invention

`MAX_READ_CHARS` is 20,000. A long page is cut. If a claim is not found in a
capture that was truncated, the honest report is *"not found in the 20,000
characters captured"* — not *"unsupported."* Those are different states and
conflating them will make the agent look like it hallucinates when it did not.

Where the claim matters and the page was cut, re-read scoped to the region the
model cites rather than declaring failure.

### 5.4 What verification is not

It is not fact-checking. A page can be wrong. Verification proves **the agent
faithfully reported the page**, which is the only thing the agent is responsible
for. Whether the page is true is the source's problem and the owner's judgement,
and pretending otherwise would be a promise this system cannot keep.

---

## 6. Provenance: available and unclaimed

`browser/trace.py` already records URL, UTC timestamp and a screenshot filename
for every step. `S-11.02.02` is therefore not "build provenance" — it is
**bind** provenance: give every step a stable id, and make `Finding.source` carry
it. Most of the work is already done and nobody has connected the two ends.

The rule that makes it worth having: **a `Finding` with no resolvable
`Provenance` is not returned.** Not returned with a warning. Not returned with
`confidence=0.3`. Dropped, and the drop reported in the run report, because a
returned fact is a claim off_CRM is making on the owner's behalf.

---

## 7. Non-negotiables

These are settled. They are written here so that a future session, or a
different AI, does not helpfully re-open them.

1. **No anti-bot evasion.** No fingerprint spoofing, CAPTCHA solving, TLS/JA3
   forgery, residential proxy rotation or headless-detection evasion. Recorded in
   `RETRO.md` 2026-09-06. The reason is not squeamishness: enforcement on these
   platforms is *account termination*, not a 429, so the thing at risk is the
   asset the owner spent months building — and the evasion arms race is
   permanently lost against a vendor who ships weekly. The legitimate path is
   already built and is most of what is wanted: a real browser, the owner's real
   profile, real OS-level input events, human pace. It is not challenged because
   **it is not a bot.** `tests/test_discovery.py` has held this line since
   discovery was written.
2. **The ten verbs stay ten.** No `evaluate`. No arbitrary code. If E-11 appears
   to need an eleventh verb, that is a design smell — say so and stop.
3. **`broker.py` remains the only code that calls a provider.** The agent is a
   tool *user*. A test fails the build if a second caller appears.
4. **Page content is data, never instruction.** Already in the run loop's system
   prompt. `S-11.03.02` makes attacks *visible*; it does not make them
   *survivable*, because containment is already structural.
5. **Consequential actions keep their countdown.** E-11 does not auto-confirm
   anything. Autonomy is about the path, not about the permission.
6. **Local-first.** No run state leaves the machine.

---

## 8. Build order, and why

```
  S-11.02.01  the shape of an answer          ← the spine; nothing else lands without it
      │
      ├── S-11.02.02  bind provenance          ← mostly wiring; the trace already has it
      │       │
      │       └── S-11.02.03  verify the claim ← the hard one; the epic's value hypothesis
      │
      └── S-11.02.04  never read a page twice  ← small, immediate budget win

  S-11.01.01  recover from failure             ← independent; start in parallel
      └── S-11.01.02  detect looping/stalling
  S-11.01.03  checkpoint and resume
      └── S-11.05.02  no duplicate side effects
  S-11.01.04  money ceiling

  S-11.03.01  pause and ask                    ← needs resume (S-11.01.03)
  S-11.03.02  report injection                 ← independent, small

  S-11.04.01  auditable report                 ← needs provenance
      └── S-11.04.02  live progress

  S-11.05.01  concurrency                      ← last. Do not make it fast before it is right.
```

**Start with `S-11.02.01`.** It is the only story that changes the shape of what
a run returns, so every story after it either builds on that shape or has to be
reworked when it lands.

**`S-11.05.01` is last on purpose.** Concurrency is the one item here that makes
every other bug harder to reproduce. Correct first, then parallel.

---

## 9. How each story is proven

Both gates, every story. The second one is the one people skip.

**Gate 1 — the code test.** Named in the evidence block, run this session,
output pasted, re-run by the verifier.

**Gate 2 — the live check.** A real Chromium, driven through the real loop, and
an assertion on something observable. This project's strongest work was always
proven this way — the video export against a real encoder, the pacing cap against
a live uvicorn comparing bytes in the outbox, the guard against a real page
calling `fetch()`. E-11 is held to the same bar.

**Fixtures, not the live web.** Serve the pages from the test file as `data:`
URLs, or from a local server the test starts. A test that depends on a real site
fails the week that site redesigns, and a test that exercises somebody's rate
limits to prove it respects them has missed the point.

**The specific test that decides `S-11.02.03`:** feed the verifier a `Finding`
whose value is *not* on the page and assert it is dropped. Write that one first.
A verifier is only worth having if it rejects, and the natural failure mode of a
normaliser is to accept everything.

---

## 10. Definition of done for the epic

E-11 is finished when all of these are true at once, and not before:

- [ ] A run returns records against a declared schema, or says which fields it
      could not fill.
- [ ] Every returned field names its page, its time, its trace step and its
      screenshot.
- [ ] Every `observed` field's value is present in that page's captured text,
      and a field that is not is dropped and reported.
- [ ] A run stops on: budget, spend, failure, looping, stalling — each with a
      distinct status the owner can act on.
- [ ] A killed run resumes without repeating a consequential action.
- [ ] A CAPTCHA, login wall or 2FA pauses and asks, and never triggers an
      attempt to defeat it.
- [ ] One report per run shows every claim beside its evidence.
- [ ] Concurrent runs share pace and account budget rather than multiplying them.
- [ ] `scripts/verify_board.py` is green, and every E-11 story carries both gates.

**Nothing here is a stretch goal.** A capability that meets eight of nine is not
90% done; it is an agent that can still return an unsourced claim, which is the
one outcome this epic exists to prevent.
