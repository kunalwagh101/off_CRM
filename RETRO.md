# Retro

Three lines per increment: what was cut, what the estimate got wrong,
and what to change next time. Appended, never edited.

---

## 2026-08-25 — Phases 1-3, the delivery process itself

**What was cut.** Nothing was cut. One thing was *added* against my own plan:
S-06.02.07, because answering the first question exposed that an answered
question still blocked READY, and the only way forward would have been deleting
the question and losing its reasoning.

**What the estimate got wrong.** I decomposed from the conversation rather than
from the product's purpose, and so wrote 33 stories with no story for
*actually publishing to a platform* — the reason the product exists. Caught on
review, added as F-01.05 with three new IDs. A coverage table only catches
orphan requirements I thought to write down.

**What to change next time.** Decompose twice: once from what was asked, once
from what the product is for. The second pass is what would have caught F-01.05
before it needed a change-control entry.

---

## 2026-08-27 — Retrospective certification of protected email

**What was cut.** Nothing was cut. S-08.01.05 remains `IN_REVIEW` because its
Python controls pass but the clean environment cannot install an uncached npm
dependency to re-run the existing dashboard test.

**What the estimate got wrong.** The implementation in `d96ea9d` was much
larger than its governance footprint: it shipped with no epic, feature, story or
requirement IDs. The first focused rerun also exposed a date-bound fixture that
worked on August 24 and failed after the calendar moved.

**What to change next time.** Pull the story before coding, and make time-based
tests relative to the run unless the test explicitly controls every stored
timestamp. Add a verifier check that flags major shipped modules which appear in
`BUILD_STATE.md` but have no story ID.
## 2026-08-25 — S-03.01.01, the browser box

**What was cut.** Nothing from the story. One thing was deliberately *not*
built: a proxy inside the box to enforce the allow-list at the socket rather
than in the browser. The box runs one process, that process is Chrome, and
`--cap-drop=ALL` means nothing in it can raw-socket around Chrome's own network
stack — so a proxy would be a large architectural addition solving a problem the
existing architecture already solves. Written into the blueprint rather than
left as an unexplained absence.

**What the estimate got wrong.** I sized this as container work and half of it
was concurrency work. The CDP client deadlocked the moment a listener answered
an event with a command — which is exactly what request interception is — and
finding it took longer than writing the feature, because it presented as a test
that *hung* rather than a test that failed. The lesson is narrower than "async is
hard": an event loop that awaits its own listeners cannot serve a listener that
needs the loop.

**What to change next time.** Two of the three bugs were in things I had already
written and believed. A validator checked its own prefix, so its first rule
never fired. An allowed-path test passed with the feature deleted, because
`data:` URLs never touch the network. Both would have been caught by asking, of
each test, *what would make this pass if the feature were removed?* — a question
worth asking before the test is written down, not after.

---

## 2026-08-28 — S-03.02.01, signing in inside the box

**What was cut.** Nothing. One thing was deliberately *not* built: any code that
handles a credential. Storing a password encrypted, filling a login form,
holding one "just for the moment" — all rejected, and the story is shaped so the
person types it into the browser themselves. That is not a shortcut; it is the
only version of this feature where a compromise of off_CRM cannot yield a
password, because there is no password to yield.

**What the estimate got wrong.** I sized this as "drive a browser to a login
page and watch it change", and the driving part was the easy half. Two of the
three real defects were in code that was already `DONE` and that I had watched
pass its own tests. `profile_is_locked` counted a lock file rather than reading
it — so a browser stopped by a signal made the profile unopenable *forever*,
which is this story's first acceptance criterion failing in the most expensive
possible way: the login is safely persisted and permanently unreachable. And
`close(quit_browser=True)` killed the browser instead of closing it, so Chrome
never flushed the cookie jar and the login that had just succeeded was gone.

**What to change next time.** Last retro's lesson was *ask of each test what
would make it pass if the feature were removed*. This one is its twin: **ask of
each acceptance criterion whether it is tested or argued.** The first draft of
`tests/test_browser_signin.py` opened by explaining that persistence "is a
property of the box rather than of any code here" — a true sentence, a
reasonable sentence, and not a test. Both defects lived in the gap that sentence
covered, and both appeared within a minute of actually stopping a browser and
starting it again. A criterion defended by an argument is a criterion nobody has
checked.

---

## 2026-09-04 — S-03.02.02, the browser session vault

**What was cut.** Nothing from the story. `S-03.02.03` still owns destructive disconnect and key/session deletion; absorbing revocation into this increment would have violated change control. The model-facing browser vocabulary also stayed at ten verbs: vault capture/restore is trusted host orchestration, never an agent tool.

**What the estimate got wrong.** The encryption was not the expensive part. The existing sign-in path could report `connected` before any vault existed, and the shared egress scanner recognised vendor API-key shapes but not opaque cookies/password/token fields. The first CI proof then exposed a separate process defect: `verify_board.py` was started with the runner's bare Python, so every historical `python -m pytest` evidence command failed despite the full suite passing inside `uv`.

**What to change next time.** For a security slice, test the entire custody chain rather than the cryptographic primitive: source → capture → encryption → record state → restore → egress refusal. Also run the verifier inside the same locked environment as the release tests; a lie detector that replays evidence under a different interpreter is measuring the environment mismatch, not the product.

---

## 2026-09-04 — S-03.02.03, revoke and forget

**What was cut.** Nothing from the acceptance criterion. The story deletes the browser session material off_CRM actually owns: vaulted cookies plus the per-account vault envelope and public connection record. Server-side sessions on other devices, password rotation, account deletion, unrelated site storage and general subject-access deletion remain outside this story rather than being silently absorbed.

**What the estimate got wrong.** "Delete the encrypted file" was not enough. A reusable cookie could still be alive inside Chromium, so the browser had to be cleared before the vault could be destroyed. The first two live proofs caught exactly the defects unit tests missed: `Storage.deleteCookies` does not exist at browser scope, and broad `Storage.clearDataForOrigin` was the wrong boundary. The working path is the narrower one the architecture already supports: `Network.deleteCookies` on an attached page CDP session.

**What to change next time.** For destructive lifecycle work, prove absence against the real runtime, not just deletion from our database. Plant the thing, verify it exists, revoke it, then ask the runtime whether it survived. Also make failure ordering explicit before implementation: never destroy the retry material or show a green disconnected state until the external/runtime deletion has actually succeeded.

---

## 2026-09-05 — S-02.02.01, bounded Run Loop

**What was cut.** PLAN.md, steering/resume and countdown continuation stayed in their own stories. This slice stops at the existing human confirmation gate and does not self-approve consequential actions.

**What the estimate got wrong.** The loop itself was small; the important work was classifying browser state correctly. Treating a logged-in page as public would have let private CRM/dashboard text reach a lower-trust model, so decision context defaults to `INTERNAL` and planning fails closed without an approved Tier A/B model.

**What to change next time.** Define the data class and trust floor before designing any autonomous loop. For agent work, the dangerous boundary is not only which action can run; it is also which page content is allowed to leave the machine while deciding that action.
---

## 2026-09-06 — S-03.02.04, several accounts and their budgets

**What was cut.** One thing was refused rather than cut: the owner asked for the
agent to understand Cloudflare "and bypass it". Fingerprint spoofing,
CAPTCHA-solving, TLS forgery and headless-detection evasion are not built and
will not be, and the reason is not squeamishness — it is that the enforcement on
these platforms is *account termination*, not a rate-limit response, so the
thing being risked is the asset the owner spent months building. The legitimate
version already exists and is most of what was actually wanted: a real Chrome
with the owner's real profile and real OS-level input events does not get
challenged, because it is not a bot. The codebase already held that position —
`test_crawl4ai_adapter_hard_disables_evasive_browser_features` — and it now has
a second reason to.

Scope was also split rather than absorbed. "Many accounts with their limits
understood" and "add any of a hundred platforms" are two stories, and running
them as one is how an increment triples. `S-03.02.05` waits in READY.

**What the estimate got wrong.** I sized this as a storage change — a key with an
account in it — and the storage was the easy third. The real work was deciding
*which verbs spend*, and that question exposed a defect: `press` had never gone
through the pace gate at all, so Enter could be sent at machine speed on a host
that was slowed for every other action. The list of verbs that act and the list
of verbs that were paced had quietly diverged, and nothing would have noticed
until an account was gone.

**What to change next time.** The last two retros were about tests that would
pass with the feature removed, and criteria defended by argument rather than
checked. This one is their sibling: **when a rule applies to a set, test that the
set is complete, not that the rule works.** `test_every_costed_action_is_a_real_verb`
and the assertion that every acting verb is charged are worth more than any
individual budget test, because the failure mode here was never a wrong rule —
it was a correct rule applied to nine of ten things.

---

## 2026-09-06 — S-11.02.01, structured autonomous run results

**What was cut.** Provenance and claim verification stayed in `S-11.02.02` and
`S-11.02.03`. This story defines only which fields are allowed to exist and
whether the run filled them; it does not pretend a schema makes a fact true.

**What the estimate got wrong.** The return-type change did not need a general
JSON-Schema engine. The E-11 contract eventually stores `Finding.value` as a
string, so a closed ordered set of required string fields was enough. A broader
type system here would have created an abstraction the next provenance story
would immediately have to work around.

**What to change next time.** For model-produced data that will enter the CRM,
make the caller own the output shape and validate after generation in plain code.
Also prove the live path: the real-Chromium test checks the correct boundary —
browser observation → model decision → deterministic record — rather than only
a validator in isolation.

---

## 2026-09-06 — S-11.02.02, source-bound browser findings

**What was cut.** Mechanical claim verification stayed entirely in
`S-11.02.03`. Provenance answers *where did this value come from?*; it does not
claim that the cited page actually contains or supports the value.

**What the estimate got wrong.** The trace already had most provenance fields,
but they were not yet addressable: steps had no stable id, normal reads did not
carry screenshots, and the read text itself was only passed forward to the model
rather than retained as host-owned evidence. Binding facts therefore required
fixing the evidence boundary, not merely wrapping the old record in metadata.

**What to change next time.** When a model cites evidence, let it name only the
smallest host-owned locator. Here that is a stable trace step id. Resolve URL,
time and screenshot from our own append-only record instead of accepting those
fields from model output. Also save a sourced fact before navigating away; model
memory is not a provenance store.

---

## 2026-09-06 — S-11.02.03, deterministic claim verification

**What was cut.** Nothing from the acceptance criteria. One larger idea was
explicitly not absorbed: a universal arithmetic or summarisation language for
recomputing every possible derived result. A derived finding stays visibly
labelled `derived` and may survive only when every declared input is already a
verified observed finding; the derivation itself is not misrepresented as a
verbatim page fact.

**What the estimate got wrong.** Provenance closed only half the trust gap. A
model could cite the correct page and still return the wrong value. The first
obvious matcher was also unsafe in exactly the way production data fails: a
substring check accepts `42` inside `420`, and a word-presence check can accept
`profitable` from `not profitable`. The hard part was defining what
normalisation is harmless without quietly changing the claim.

**What to change next time.** Adversarial tests for model-produced data should
use *almost true* values, not only invented sources: adjacent digits, negation,
unrelated quotes and truncated captures. Confidence is never evidence. Verify
against host-owned material after generation, fail closed when support is not
there, and distinguish "not in the bounded capture" from "proved false".
---

## 2026-09-09 — S-06.02.09, the half the lock did not cover

**What was cut.** Nothing. What was nearly cut was the root cause: the first fix
that made the story's own test pass was the `GuardedConnection` wrapper, and it
did not work — the holder thread still raised "cannot start a transaction within
a transaction". Stopping at a green test would have shipped a lock around a
problem that was really about `isolation_level`.

**What the estimate got wrong.** I sized this as "wrap 155 call sites" and the
call sites were the easy part. The actual defect was one keyword argument. The
2026-09-08 fix treated the symptom — two transactions colliding — and the
symptom was produced by Python opening transactions nobody asked for. Two
sessions of work, both correct, and the second only found the cause because the
first fix's own test failed in a way that did not fit the story I had in my head.

**What to change next time.** The previous retros were about tests that pass
with the feature removed, and criteria defended by argument rather than checked.
This one is about **a fix whose test passes for the wrong reason.** The
`GuardedConnection` reproduction went green while the bug was still there — the
bystander survived because the holder timed out after five seconds and released
the lock, not because anything was correct. A concurrency test that passes needs
its *timing* inspected, not just its assertion: if it took five seconds, it did
not demonstrate what it claims.

---

## 2026-09-09 — S-11.02.04, and a story that was already built

**What was cut.** Nothing, but the story I was asked to pull was already DONE.
S-11.02.01 through .03 shipped from another session during the security audit.
Rather than take the board's word for it I re-exercised all three acceptance
criteria and the S-11.02.03 normaliser directly, including the trap the manual
warns about: `+44 20 7946 9999` is refused against a page carrying
`+44 20 7946 0001`, and `07946 0001` is refused as a substring. Digits are not
fuzzed and truncation stays distinct from unsupported. It was built correctly.

**What the estimate got wrong.** I sized this as a memo — a dict keyed on URL —
and the dict was the smallest part. The real work was deciding *when the memo is
wrong*, and the acceptance criteria I wrote in the spec did not cover it: a page
can change while its URL does not, so a capture taken before a `scroll` is no
longer what the page says. That criterion was added during the build and is
recorded in the backlog as added, not backfilled silently.

**What to change next time.** I wrote these criteria myself two days ago and
they had a hole in them, which is the more useful observation than any of the
code. **A caching story needs an invalidation criterion before it is READY.** The
Definition of Ready asks whether criteria are machine-testable; it does not ask
whether they are complete, and completeness is the thing a cache gets wrong. The
question to add: *what makes the stored answer stop being true, and which
criterion says so?*

---

## 2026-09-09 — S-11.01.01, and a criterion the code could not meet

**What was cut.** One acceptance criterion was corrected rather than met. The
story asked for retry on "navigation timeout, 5xx", and 5xx is not observable
through the ten verbs: a server returning 500 still sends a page, the browser
renders it, and `goto` succeeds. Writing a retry that claimed to handle 5xx
would have been a comment describing something the code cannot see. The
criterion now says timeout-shaped, and a status-aware retry has to earn its own
ID.

**What the estimate got wrong.** I sized this as retry logic and the retry was
the small half. The larger half was deciding what counts as *the same attempt* —
and the answer had to exclude the model's stated reason, because otherwise
rewording why it wants to click element 7 makes clicking element 7 a new thing
to try, and the guard never fires.

**What to change next time.** Two stories running, two acceptance criteria of my
own that did not survive contact with the code: S-11.02.04 had no invalidation
criterion, and this one asked for something unobservable. Both were written in
the same sitting, from the spec rather than from the code. **A criterion written
without opening the module it constrains is a guess.** The Definition of Ready
asks whether criteria are machine-testable; it should also ask whether anyone
checked that the thing they describe is *visible from where it will be checked*.

---

## 2026-09-10 — S-11.01.02, and a test that caught the definition

**What was cut.** Nothing. The story's wording was widened twice, both times
because the third acceptance criterion — *a false positive is worse than a
wasted step* — made the literal reading wrong.

**What the estimate got wrong.** I thought the hard part was picking thresholds.
It was picking the *definition*. My first implementation counted "a URL
different from the last step" as progress, which is a reasonable sentence and
completely wrong: bouncing between two pages is a different URL every single
step, so the detector could never fire on the one cycle the story names. The
looping test failed and that is the only reason I noticed.

**What to change next time.** The last two retros were about criteria that did
not survive the code. This is the pleasant inverse and worth recording as such:
**writing the false-positive tests first is what made the definition right.**
The form-filling and search-and-browse cases were written before the detector
existed, and they are what forced progress to be a union rather than the story's
literal "no new fact and no new URL". A detector is defined by what it must not
catch at least as much as by what it must, and the order the tests are written
in decides which of those you think about.

---

## 2026-09-10 — S-11.01.03, and a design decided a month early

**What was cut.** Nothing, and unusually little was decided: the blueprint had
already named the design in August — *a run is resumable because the trace is
complete; the trace* is *the progress* — and `Trace.read`'s own docstring said
replaying it was what resuming would be built on. Two thirds of this story was
reading what a previous session had already written down and not inventing a
checkpoint file next to it.

**What the estimate got wrong.** I planned to serialise each finding into its
trace step's `detail`, and only checked the sizes afterwards: a value may be
20,000 characters and a quote 4,000, against a 4,000-character detail cap. That
would have truncated the JSON, which then fails to parse on replay — a resumed
run losing exactly the facts it exists to keep, silently. The capture-artefact
mechanism the trace already had for page text was the answer, and it was there
the whole time.

The other correction came from a test rather than from me. My `finding` step
carried `finding.value` in its detail, and
`test_declared_schema_returns_a_valid_record_not_prose` failed on
`assert "Acme Ltd" not in trace.path.read_text()`. Harvested content is
deliberately kept out of the JSONL and confined to the 0600 artefacts, and I had
not known that invariant existed. A test written by an earlier session defended
a property nobody had written into a story.

**What to change next time.** **Check the size limits of a store before choosing
what to put in it.** Both of this story's mistakes were the same shape as each
other: a field that looked like it would hold a thing, and a cap two files away
that said otherwise. The trace has four such caps — `MAX_DETAIL_CHARS`,
`MAX_FIELD_VALUE_CHARS`, `MAX_QUOTE_CHARS`, `MAX_READ_CHARS` — and none of them
is visible from the line where the decision gets made.

---

## 2026-09-10 — S-11.05.02, and a gate with a door beside it

**What was cut.** One thing was filed rather than fixed: `press` does not go
through the consequential-action check that `click` does, so the gate that stops
the agent clicking Send does not stop it pressing Enter in the same form. That is
`S-11.03.03` and it belongs with the human-gate story, not smuggled into a
resume story — but it is worth noting how it was found. I only looked because I
needed to know which verbs could have side effects, and the answer to *that*
question was in a different file from the answer to *which verbs are gated*.

**What the estimate got wrong.** The guard was ten lines. What took the time was
noticing that the signature was recorded on **failed** action steps and not
successful ones — added in the last story for a different purpose — so replay
could see everything the run had tried and nothing it had actually done. The
test said "the trace did not record what was performed", which is exactly the
sentence I would have written if I had thought about it first.

**What to change next time.** `goto` is excluded from the guard on purpose, and
that exclusion is the interesting part of this story rather than the guard. A
rule with an exception is only honest if the exception is written where the rule
is, with its cost: *a URL whose GET has a side effect is not protected*. **When a
control has a deliberate hole, the hole goes in the code comment and the backlog
entry, not only in the commit message** — commit messages are read once and code
is read forever.

---

## 2026-09-10 — S-11.03.02, and an evasion found by a test about readability

**What was cut.** Nothing, but the honest limit is written into the module
rather than left to be discovered: this reports *injection-shaped text*, not
proven malice, and a page explaining prompt injection to humans will match.
Because nothing is blocked that is the cheap side to err on — and the module now
says in its own docstring that it must never be given the power to stop
something without that trade being re-argued.

**What the estimate got wrong.** I thought the work was writing patterns. The
work was *narrowing* them: every clause in the final version exists in the shape
it does because an earlier version flagged ordinary business text. "You are now
viewing page 2 of 5." "Our new role this quarter is Head of Growth." "We act as
a broker for European fintech firms." "Send us your CV at careers@acme.test."
Four false positives, four narrowings, all against sentences that are on real
pages by the million.

**What to change next time.** The evasion was found by a test that was not
looking for it. `test_a_quote_is_readable_rather_than_mostly_whitespace` split
an attack over newlines only because that is what messy page text looks like —
and nothing matched at all, because the patterns used `[^.\n]` to stay inside a
sentence and a newline ended them. A detector that reads text has to be given
text in the shape it actually arrives in: **write at least one test with the
input ugly rather than clean.** Every other test in the file used tidy
single-line strings, and every one of them passed while the detector could be
walked past with a carriage return.

---

## 2026-09-10 — S-11.04.01, and an XSS test that was testing nothing

**What was cut.** Nothing. Two criteria were added rather than removed, both
about the report being an attack surface itself, which the story had not
considered at all.

**What the estimate got wrong.** I sized this as rendering and the rendering was
the easy half. The first version of the hostile-input test planted `<script>` in
the **page body** and asserted it came back escaped — and it passed while
proving nothing, because a page's raw text never reaches the report. It lives in
a capture artefact, by the privacy rule from two stories ago. The attack had to
be planted in what the model *quoted*, which is the same words arriving by a
narrower road.

Then the assertion itself was wrong. `assert "onerror=" not in page` failed
against correctly escaped output, because `&lt;img src=x onerror=&quot;…` is
inert text that still contains the substring. The real question is whether
anything became a *tag*, so the tests now parse tag names out of the document
and compare against the set `report.py` is allowed to emit.

**What to change next time.** Both mistakes were the same one twice: **testing
the shape of the output instead of the property.** "Is this string absent" is a
proxy for "is this inert", and the proxy broke in both directions — it passed
when the input never arrived, and failed when the output was correct. Ask what
the *browser* would do, not what the string looks like. And the check that made
this trustworthy took thirty seconds: delete the escaping, watch three tests go
red, put it back.

---

## 2026-09-11 — S-11.04.02, progress visible while it happens

**What was cut.** The live gate could not click. This container's egress proxy
refuses to serve Chromium (`ERR_CONNECTION_RESET` on a URL `curl` fetches with a
200), so the only page reachable was one served on loopback — and `policy.py`
refuses to act on loopback, correctly, because that rule is the whole SSRF
boundary. I left the rule alone and recorded the hole in the evidence block
rather than widening a security control to make my own gate go green.

**What the estimate got wrong.** I wrote `Progress.action` as
`detail.split(" ")[0]` and it passed the unit test I wrote next to it, because
the detail I invented for that test was `"read the page"` and the verb happened
to be the first word. A real click records `"clicked More"`. The fixture made
the bug invisible: I chose the input *and* the expectation in the same breath,
so they agreed with each other instead of with the system. The integration test
caught it, an hour later.

The story also looked like "hang a hook on the trace", and it was — but making
the verb visible found a hole in `S-11.02.04`: a read answered from the run's
memo was recording no signature at all. Nothing had needed the verb back from
that step before, so nothing had missed it. Building the reader is what audited
the writer.

**What to change next time.** When a test needs a sample of something the system
produces, take the sample *from* the system. `[signature=...]` had been on every
action step since `S-11.05.02`; one `grep` for a real detail string would have
shown me "clicked More" before I wrote the parser, instead of after. A fixture I
invented is a second guess dressed up as evidence.

---

## 2026-09-11 — S-11.03.01, a wall pauses the run and asks

**What was cut.** Nothing, but one thing was inherited and then refused on its
own terms. `injection.py` says at length that it must never be given the power
to stop anything without the trade being re-argued. This module *does* stop
runs, so I re-argued it instead of quoting it, and it came out the other way —
because the two detectors have opposite costs. A wrong injection match costs one
trace line, so those patterns can be broad. A wrong match here costs the owner a
glance at a browser. What makes that acceptable is not the precision, it is that
pausing is cheap and reversible: the check runs before the model is asked
anything, so nothing is spent, and the run resumes with its whole budget.

**What the estimate got wrong.** I thought the hard part was recognising a
CAPTCHA. It was not — those widgets announce themselves. The hard part was every
ordinary page that looks a bit like a wall, and I only found those by writing the
false-positive tests first. Two rules were wrong when written and would have
shipped: `/auth\b` matched `/help/two-factor-authentication`, so a page
*explaining* two-step verification paused runs; and "second-factor language plus
a text box" turned that same help article into a wall via its search box. Both
were caught by a test about a page that is not a wall, which is the only kind of
test that could have caught them.

I also nearly duplicated `identity.py`. It already had the accessible-name
reader and the word-boundary lesson that goes with it — a signal `me` matching
inside `so-me-thing`. Reading the neighbouring module before writing mine turned
a new helper into a `Snapshot.names` property both use.

**What to change next time.** For any detector, **write the negative fixtures
before the positive ones, and take them from pages that actually exist** — a
marketing homepage with a "Sign in" link, a help article, a search results page.
The positive cases were right on the first attempt because a CAPTCHA is
unmistakable; every real defect lived in the cases I had to go looking for. And
when a detector can *stop* something rather than only record it, that asymmetry
is a design input, not a footnote — it decides how much corroboration each rule
has to carry.

---

## 2026-09-11 — S-06.02.13, the log that found a defect by existing

**What was cut.** Nothing. One thing was deliberately *not* done: `RETRO.md` was
not merged into the new log or replaced by it. They answer different questions —
a retro says *what should I do differently*, a defect log says *what broke and
how was it found* — and a file that tries to be both is read as neither.

**What the estimate got wrong.** I sized this as writing a file. The writing was
the small half. Putting 34 scattered defects into one table with a `Found`
column made something visible that eighteen separate retros had not: **the same
defect has been fixed three times under three different names.** `D-14` (`press`
acted but was never paced), `D-24` (the signature was written on the failing
path and not the succeeding one) and `D-32` (a read served from memory recorded
nothing at all) are one bug wearing three coats — two lists that must match each
other, drifting apart where nobody looks. Each was found by accident, months
apart, while doing something else.

The other surprise was that adding the check broke five existing verifier tests
immediately, because their fixture repository had no logs in it. That is the
check working on its first run, against the only repository that was not
expecting it.

**What to change next time.** **A record that is only readable one story at a
time is not a record.** Everything in that table already existed in the
repository — in commit messages, in retro prose, in changelog entries — and none
of it was answerable. The column that did the work was `Found`, not `Fixed`: the
pattern lives in when things were noticed, not in how they were repaired. When
something is written down in three places and queryable from none, the next
thing to build is the table, not the fourth place.

---

## 2026-09-11 — S-06.01.03, a cap that had never stopped anything

**What was cut.** Nothing, and the story got *bigger* honestly rather than
quietly: it was written as "show an estimate, reconcile after", and the
reconciliation half turned out to be sitting on a dead control. `S-11.01.04`,
the story this was pulled ahead of, keeps its ceiling — what landed here is the
measurement that ceiling will be enforced against, which is the right split.

**What the estimate got wrong.** I expected to write an estimator. The estimator
was twenty lines. What took the time was discovering that the owner's daily
spend cap had never refused anything in its life: `quota.record` was being
called with `spend_usd=0.0`, a hardcoded zero, so a $1.00 cap sat at $0.00
through five thousand calls. Everything around it was real — the limit, the
check, the usage bar on the Connectors screen — and the one number feeding it
was a constant.

Underneath that was something more useful than the bug: **the price of a call
was being computed in three separate places.** One in the broker (zero), one in
`agent/run.py` (characters over four), one implied by the model's rate fields
that nothing used. That is the defect log's pattern 3 — two things that must
agree drifting apart — except in arithmetic rather than in a list, and it is why
the log was worth writing four hours before I needed it.

**What to change next time.** **When the same calculation appears twice, one of
the two is already wrong — go and look rather than reconciling them.** I found
this by asking where a real number could come from, not by auditing. The
provider had been sending exact token counts in every response the whole time
and the adapter was throwing them away to make room for a guess.

And the smaller lesson, again: I proved the dead cap by *running* it — 5,000
calls, print the total — before writing a line of the fix. Twenty seconds, and
it turned "this looks wrong" into a number I could put in a commit message.

---

## 2026-09-11 — S-11.01.04, and a fixture that disagreed with itself

**What was cut.** Nothing. The story arrived two-thirds built, which is what
pulling `S-06.01.03` first was for: the pre-run estimate and per-step spend were
already there, so this was the ceiling alone. Splitting them was the right call
and it was the owner's.

**What the estimate got wrong.** Not the feature — forty lines. What cost the
time was a test fixture that contradicted itself: the registry said the model
was free while the broker reported five cents a decision. Four tests failed and
the obvious reading was "the ceiling does not fire early enough".

It was not. The ceiling predicts the first decision from the pre-run estimate,
the estimate is priced from the registry, and a free model estimates at zero —
so with a zero estimate nothing could be predicted and the first decision went
through. The code was right and my fixture was two different models wearing one
name.

**That is worth more than the fix.** Chasing it turned an accident into a
specified limit: an unpriced model costs exactly one decision of headroom,
because from the second one the run has its own observed costs. That is now a
named test rather than something the next person rediscovers at three in the
morning.

**What to change next time.** **A fixture that contradicts itself will be read
as a bug in the code.** The two halves of this one — what the registry charges
and what the broker reports — are the same number in production and were
different numbers in my test, and nothing forced them to agree. When a double
stands in for two views of one thing, derive the second view from the first
instead of typing it twice. The rates in that file now compute the per-decision
cost rather than asserting it, and the comment shows the arithmetic.

---

## 2026-09-11 — S-02.02.04, and a design written down in August

**What was cut.** Nothing, and unusually little was decided. `policy.py` had
carried the design in its own docstring since August — *sensitive actions get a
countdown, not a dialog; a confirm box trains people to click through it* — and
even named the five seconds. `check_action` already returned a variable called
`needs_countdown`, and `ActionResult.needs_confirmation` already documented
itself as "set when the action needed a countdown **and the caller has not run
one**". The contract was complete. What was missing was the countdown.

This is the second time that has happened — `S-11.01.03` was the same story with
a different module. Reading the neighbouring docstring before designing is worth
more here than it is on most codebases, because a previous session has usually
already thought about it.

**What the estimate got wrong.** I sized it as a delay and the delay was ten
lines. The work was in the three things around it: that cancelling has to be
possible **from another thread**, because the cancel comes from a person and a
person is never on the event loop; that a spent countdown must not be reusable,
or "the owner watched this one elapse" becomes a token; and that an unattended
run must be refused one outright.

That last one is worth more than the feature. A countdown with nobody watching
is not a weaker gate — it is the gate deleted while still looking like it is
there. The architecture note had said so in words for weeks, and words are not
enforcement.

**What to change next time.** **Ask what the feature looks like when the person
it was built for is absent.** Every property that makes a countdown a control —
visible, cancellable, prompt — is a property of somebody *being there*. Take the
person away and it degrades into a sleep that approves things. The test that
matters most in this story is the one that has nothing to do with counting.

A smaller note on proof: the live check asks the *page* whether it received the
click, by reading an element the page updates on click, rather than trusting the
return value. A cancelled action that reports failure and still sends the click
is precisely the defect this feature would have, and only the page can say.

---

## 2026-09-11 — S-11.03.03, and a gate over a key that did nothing

**What was cut.** Nothing, and something was deliberately *added*: the fix for
`D-40`. That was a judgement call against change control, so here is the
reasoning. The story is "Enter is gated **like the button beside it**". A button
click works; an Enter press did not do anything at all. Shipping a gate over an
inert key would have been shipping theatre — and worse, shipping a security
control whose necessity I had just disproved, on top of a broken verb. The two
belong in one commit because the gate is only meaningful once the key works.

**What the estimate got wrong.** I sized this as wiring one existing check into
one more place, and that part took twenty minutes. Then the live check failed
in a way that made no sense: the gate refused Enter correctly, and when Enter
was *allowed through*, the form still did not submit.

`press` had been dispatching `keyDown`/`keyUp` with no `text` field. Chrome
raises the event — a listener sees it, `isTrusted` is true — and then performs
no default action. So Enter had never submitted a form, Tab had never been
typed, and nothing had noticed, because every test of `press` had asked what the
*call returned* rather than what the *page did*.

Which means `D-25` was a hole nobody could fall through yet. It would have
opened silently the day somebody fixed `press`.

**What to change next time.** **For anything that acts on the world, assert on
the world.** Every `press` test in this repository checked the return value, and
the return value was `ok=True` the whole time it was doing nothing. The live
checks in this session that have been worth most — the countdown, the wall, this
— all ask the page what happened instead of asking the code what it thinks
happened. That is now the habit for any verb with an effect.

And a second, smaller one that cost half an hour: `new_tab` returns when the
target exists, not when the document has parsed. `focus()` against a page with
no elements in it silently does nothing, and that reads *exactly* like a broken
gate. A live check needs to wait for the page before it tests anything on it.

---

## 2026-09-11 — S-11.05.01, and the reason it was scheduled last

**What was cut.** Nothing. The manual said in August to build this last and the
reason turned out to be better than "it is hard": every other E-11 story put
state somewhere, and this is the one that asks whether that state was in the
right place. Doing it first would have been guessing about code that did not
exist yet.

**What the estimate got wrong.** I expected to build a coordinator. There was
nothing to build — both failures were one-line placements. A pace clock on the
tab that should have been on the browser; a lock on the object that should have
been on the file. The work was in *finding* them, and the finding took one probe
because I measured before reading.

Which is the thing worth keeping. **A sequential probe passed both of these
while both were broken.** Twelve of twelve actions counted; the pace floor
looked fine. Run the same two probes concurrently and it is 33 of 100 and a
floor halved. A concurrency story tested sequentially is a story tested in the
one condition it does not care about.

**What to change next time.** **Measure the acceptance criteria before writing
any code, and measure them under the condition the story names.** Three criteria
went in, one came back holding — and knowing which one saved building anything
for it. That is now the first thing I do on a story that claims to fix
something: prove it is broken, in the shape it is broken in.

A second note, on knowing when to stop. The check-then-record gap lets the
account ceiling be overshot by one action per concurrent run. Closing it needs a
reserve-and-release protocol threaded through every action's error path, and it
would reverse a decision `S-03.02.04` made with its own reasoning — that a
failed action must not cost budget. So it is measured (N-1, at 1, 2, 3, 5 and 8
runs), pinned by a test, and written down as a known limit. **A bound you have
measured is not the same as a bug you have ignored**, and the difference is
whether the number is in a test.

---

## 2026-09-12 — S-06.02.11, and a rule that had never once fired

**What was cut.** Nothing. The audit script from 2026-09-10 already had the
logic and already carried the warning that mattered — *story ids contain
periods, so `[^.]*` parses `S-03.02.04` as `S-03`* — so folding it in was mostly
reading what a previous session had written down. That is the third time this
week; it is becoming the cheapest habit in this repository.

**What the estimate got wrong.** I sized this as moving a script into a
function. Then a test I had written for a *different* rule failed: a story with
an open question against it was still being reported as available to pull. My
first instinct was that my test was wrong.

It was not. `open_questions()` splits the file on question headings and returns
what comes *after* each heading — and every question in this repository names
the story it blocks *in the heading*. So the Definition of Ready rule, which has
been in the verifier since it was written, had never fired in its life. Three
open questions were blocking nothing.

**What to change next time.** This is the third control in two days that existed,
was configurable, was displayed, and could never refuse anything: a spend cap fed
a hardcoded zero, a key event with no default action, and now a rule handed the
wrong half of a parsed file. They do not go red. They do not look broken. They
look like a feature.

So the question has gone into the defect log as a standing one: **for every
control, ask when it last actually refused something.** Not "is it implemented",
not "is it tested" — both were true all three times. *When did it last say no?*
If the answer is never, that is the finding, and the way to prove it either way
is to make it say no on purpose against real data.

---

## 2026-09-12 — S-06.02.12, and a live check that ate its own subject

**What was cut.** Nothing. The check is fifteen lines, and the only interesting
decision in it is which question to ask: `git cat-file -e` or `git merge-base
--is-ancestor`. The first is the obvious one and it is the reason the defect
survived thirteen days — a dangling object still answers yes.

**What the estimate got wrong.** Not the feature. The *proof*. A live check for
this needs a genuinely orphaned commit, so I made one in the working tree, and
then ran `git reset --hard HEAD~1` to tidy up. That threw away every uncommitted
change, including the check I was proving and its tests.

It then presented as a bug in the feature: the check stopped firing and my first
few minutes went into wondering why, rather than into `grep check_commits`
coming back empty. Recovered from a scratch copy, and the tests rewritten.

**What to change next time.** **A live check that mutates state does it on a
copy.** `git clone -q . /tmp/gate2` takes half a second, has the same history
and the same board, and nothing it does can reach work in progress. The check is
no less real for being in a clone — it found the orphan there exactly as it
would have here.

The second half is simpler and I have been doing it inconsistently all session:
**commit before running a live check.** Every one of these checks exists to
touch something real, and "something real" is the same tree the work is in.

---

## 2026-09-12 — S-06.02.14, and a fixture that could not look anything up

**What was cut.** Nothing, and one thing was deliberately left alone: tests *of*
the numbering keep their literals. That a trace with no ids gets them assigned
in order, that `step-000002` follows `step-000001` — there the number is the
subject, not a way of pointing at something. Converting those would have
replaced a test with a tautology.

**What the estimate got wrong.** I expected a search and replace. The obstacle
was that half the literals are in *scripted model answers*, written before the
run exists — so there is nothing to look up yet, which is exactly why somebody
typed a number in the first place.

The way out was to stop asking how a test refers to a step and ask how the
**model** does. It does not count. The observation puts `step_id=step-000002`
in front of it and it repeats that back. So the double does the same: an answer
says `CITE`, and the broker fills it in from the instructions it was just
handed. That is immune to renumbering *and* a closer imitation of the thing it
stands in for, which is the rare case where the robust version is also the more
honest one.

**What to change next time.** **Prove the criterion by doing the thing it
forbids.** The acceptance criterion is "adding a step anywhere breaks nothing",
and there is no way to assert that from inside the tests it protects. So I put
a junk step into `agent/run.py`, shifted every id in every run, and re-ran the
five converted files: 49 passing. Then took it out. That took ninety seconds and
it is the only evidence that means anything here — a suite of green tests proves
only that today's numbering is today's numbering.

It also found a straggler I would have missed. One assertion still failed:
`screenshot == "0002.png"`. Artefact filenames encode the step index too, so it
was the same defect in another costume, and only the shifted run showed it.

