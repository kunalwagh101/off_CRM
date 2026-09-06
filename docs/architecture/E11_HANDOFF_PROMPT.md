# The E-11 handoff prompt

Paste the block below into Claude Code, or any capable coding AI, in a clean
checkout of this repository. It is self-contained: every fact it needs is in a
file the AI can read, so it does not depend on a conversation it was not part of.

Add one line at the end naming the story to pull. If you add nothing, it runs
the standup and stops, which is the correct default.

---

```
=== off_CRM · E-11 · THE AUTONOMOUS BROWSING AGENT ===

You are continuing a project with a delivery process that is already running.
Do not start by writing code. Start by finding out where things stand.

STEP 1 — STANDUP. Before anything else, read and report:
  BOARD.md                 what is in flight; chat is not state
  PRODUCT_BACKLOG.md §3b   amendments to shipped definitions — read these, they
                           explain why some shipped stories are superseded
  docs/architecture/AUTONOMOUS_BROWSING.md    the build manual for this epic
  docs/architecture/BROWSER_AGENT_BLUEPRINT.md  the eight-stage map it sits in
  DEFINITION_OF_DONE.md    the two gates
Then run `python scripts/verify_board.py` and report drift between the board and
the repository BEFORE doing anything else. If it is red, say so and stop.

STEP 2 — PULL ONE STORY. WIP limit is 2 and one item is usually already in
flight, so pull one. Move it to IN_PROGRESS in BOARD.md and commit that move on
its own, before any code. If no story is named for you, pull S-11.02.01 — it is
the spine of the epic and everything else in F-11.02 hangs off it.

STEP 3 — BUILD IT, AND ONLY IT. New scope gets a NEW ID and is re-planned; it is
never absorbed into an item in flight. If you find a defect in shipped code that
blocks your story, fix it inside your story and say so plainly in the commit —
change control governs scope, not bugs.

STEP 4 — BOTH GATES. A story is not done with one.
  GATE 1  a named test, run this session, output pasted into the evidence block
  GATE 2  a live check: a real Chromium, driven through the real loop, asserting
          on something observable. Serve pages from the test file as data: URLs
          or a local server — never a real site.

STEP 5 — CLOSE IT. Evidence block on BOARD.md, CHANGELOG entry, a RETRO.md entry
naming what you cut and what your estimate got wrong, verifier green, commit,
push to main.

=== HOW THIS CODE IS WRITTEN ===

Reuse before you add. Standard library before a dependency. Native platform
features before a wrapper. The smallest production-safe implementation, not the
fewest lines. Before any large architectural addition, explain in the commit why
the existing architecture could not solve it more simply.

NEVER simplify away: security controls, authn/authz, input validation, error
handling, data integrity, transactions, concurrency protection, observability,
tests for important behaviour, accessibility, production reliability.

Comments explain WHY, especially where the obvious approach was rejected. When
you fix a bug, the comment says how it was found. Match the density and idiom of
the file you are in.

=== THE SIX THINGS THAT ARE SETTLED ===

Do not re-open these. They are decided, recorded, and re-litigating them wastes
a session.

1. NO ANTI-BOT EVASION. No fingerprint spoofing, CAPTCHA solving, TLS/JA3
   forgery, proxy rotation or headless-detection evasion. Enforcement on these
   platforms is account termination, not a 429, so what is at risk is the asset
   the owner spent months building — and the arms race is permanently lost
   against a vendor shipping weekly. The legitimate path is already built: a
   real browser, the owner's real profile, real OS-level input events, human
   pace. It is not challenged because it is not a bot. Recorded in RETRO.md
   2026-09-06 and held by tests/test_discovery.py.
2. THE TEN VERBS STAY TEN. No evaluate. No arbitrary code. If E-11 seems to need
   an eleventh verb, that is a design smell — say so and stop.
3. broker.py IS THE ONLY CODE THAT CALLS A PROVIDER. The agent is a tool user. A
   test fails the build if a second caller appears.
4. PAGE CONTENT IS DATA, NEVER INSTRUCTION. Containment is structural, via the
   closed vocabulary. S-11.03.02 makes attacks visible; it does not make them
   survivable, because they already are.
5. CONSEQUENTIAL ACTIONS KEEP THEIR COUNTDOWN. E-11 auto-confirms nothing.
   Autonomy is about the path, not the permission.
6. LOCAL-FIRST. No run state leaves the machine.

=== THE ONE SENTENCE THIS EPIC DEFENDS ===

An autonomous agent whose output cannot be audited is a rumour generator.

It is easy to build an agent that browses and returns a confident paragraph. The
paragraph is the problem: a model asked to summarise what it saw produces
something fluent whether or not it saw it, and the real URLs it visited first
lend the invention credibility.

So the measure is not "did it browse." It is: can every fact it returns be traced
to a page, and does that page actually say it?

Three stories carry that, and they are the epic:
  S-11.02.01  a run returns records against a declared schema, not prose
  S-11.02.02  every fact carries URL, time, trace step and screenshot
  S-11.02.03  a claim the cited page does not support is dropped, not returned

Everything else in E-11 is necessary hygiene you can derive from the acceptance
criteria. These three are where the design decisions live, and §4 and §5 of
AUTONOMOUS_BROWSING.md are about them specifically. Read those sections twice.

=== THE TRAP IN S-11.02.03 ===

The natural failure mode of a text normaliser is to accept everything. A
verifier that never rejects is worse than no verifier, because it puts a green
tick next to an invention.

So write the REJECTING test first: feed it a Finding whose value is not on the
page, and assert it is dropped. Only then write the accepting one.

Normalise whitespace, case, unicode (NFKC) and typographic punctuation. Do NOT
normalise digits, word order or negation — a phone number that matches only
after digit-fuzzing is a different number.

And keep "not found in a truncated capture" distinct from "unsupported". Those
are different states, and conflating them makes the agent look like it
hallucinates when it did not.

=== WHAT IS ALREADY BUILT — DO NOT REBUILD IT ===

browser/cdp.py       hand-written DevTools client; listener deadlock fixed
browser/session.py   attaches to the owner's real Chrome; stale locks
                     interrogated; graceful close so the cookie jar flushes
browser/perceive.py  the page as an accessibility outline in document order
browser/page.py      the ten verbs; real input events; a stale handle is REFUSED
browser/policy.py    per-host pace, attended-only hosts, refusals
browser/guard.py     per-request allow-list before Chrome dispatches
browser/box.py       network yes, host filesystem never
browser/identity.py  six platforms, several accounts each, no password anywhere
browser/vault.py     session material encrypted per account
browser/budget.py    per-account hour/day ceilings; looking is free
browser/trace.py     append-only; URL, time, screenshot per step
agent/run.py         the bounded loop: perceive, decide, act, record

The trace ALREADY holds URL, timestamp and screenshot per step. S-11.02.02 is
not "build provenance" — it is BIND provenance. Most of that work is done and
nobody connected the two ends.

=== TONE ===

The owner is not from the US or UK, is dyslexic and has ADHD. Write simple,
sharp and exploratory. Short sentences. Lead with the answer. No throat-clearing.
Never claim something works without having run it, and if a test fails, say so
with the output.

Start with STEP 1 now.
```

---

## Adding a target

Paste one of these after the block:

```
Pull S-11.02.01 — the shape of an answer. It is the spine of E-11 and every
other story in F-11.02 has to be reworked if it lands after them.
```

```
Pull S-11.02.03 — claim verification. Write the rejecting test first.
```

```
Pull S-06.02.08 — one runner for every evidence command. Small, and it stops the
board crying wolf.
```

```
Don't pull anything. Run the standup and tell me where we are.
```
