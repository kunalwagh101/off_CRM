# Defect log

**What this is.** Every bug, security hole and broken connection found in
off_CRM, written down in plain English, with the date it was found.

**Why it exists.** The reasons things broke were scattered across commit
messages, `RETRO.md` prose and `CHANGELOG.md`. That is fine for a person reading
one story and useless for the question that actually matters later: *has this
kind of thing happened before?* One table answers that.

**Who it is for.** The next session — human or otherwise. A tool that reads this
file should be able to tell, without opening the code, what class of mistake
this codebase keeps making.

**The rules.**

1. Every defect found gets a row, whether it was fixed or filed for later.
2. Plain English. "The lock file was counted, not read" — not "stale mutex
   semantics".
3. Say **how it was found**. That is the most useful column, because it says
   which kind of checking works.
4. A defect found and not fixed gets a backlog ID, or it is not recorded
   honestly.
5. Design decisions do **not** go here. They go in `DECISIONS.md`.

**Kinds.** `security` · `data-loss` · `bug` · `gap` (built but not connected to
anything) · `process` (the way we work went wrong, not the code).

---

## The table

| ID | Found | Kind | Severity | What went wrong, in one line | Status |
|---|---|---|---|---|---|
| D-01 | 2026-08-25 | bug | high | The CDP client froze forever when a listener replied to an event | fixed · `S-03.01.01` |
| D-02 | 2026-08-25 | security | high | A URL checker checked its own prefix, so its first rule never ran | fixed · `S-03.01.01` |
| D-03 | 2026-08-25 | process | medium | A test passed with the feature deleted | fixed · `S-03.01.01` |
| D-04 | 2026-08-27 | process | medium | A large shipped module had no story, feature or requirement ID | fixed · `d96ea9d` follow-up |
| D-05 | 2026-08-27 | bug | low | A test hard-coded a date and started failing when the calendar moved | fixed |
| D-06 | 2026-08-28 | bug | high | A browser profile became permanently unopenable after a crash | fixed · `S-03.02.01` |
| D-07 | 2026-08-28 | data-loss | high | Closing the browser killed it, so a just-completed login was lost | fixed · `S-03.02.01` |
| D-08 | 2026-09-04 | security | high | A platform was reported "connected" before the vault existed | fixed · `S-03.02.02` |
| D-09 | 2026-09-04 | security | high | The outgoing-data scanner did not recognise cookies, passwords or tokens | fixed · `S-03.02.02` |
| D-10 | 2026-09-04 | process | medium | The board verifier ran under a different Python than the tests | fixed · filed again as `S-06.02.08` |
| D-11 | 2026-09-04 | security | high | Deleting the vault file left a working cookie alive inside Chromium | fixed · `S-03.02.03` |
| D-12 | 2026-09-04 | bug | medium | `Storage.deleteCookies` does not exist at browser level | fixed · `S-03.02.03` |
| D-13 | 2026-09-05 | security | high | A signed-in page counted as public, so private text could reach a weaker model | fixed · `S-02.02.01` |
| D-14 | 2026-09-06 | security | high | `press` was never paced, so Enter could be sent at machine speed | fixed · `S-03.02.04` |
| D-15 | 2026-09-06 | bug | medium | A value check accepted `42` inside `420`, and `profitable` from `not profitable` | fixed · `S-11.02.03` |
| D-16 | 2026-09-08 | data-loss | critical | Two writes at once destroyed 40 of 80 rows and reported success | fixed · `S-06.02.09` |
| D-17 | 2026-09-08 | bug | high | The first fix for D-16 passed its own test while the bug was still there | fixed · `S-06.02.09` |
| D-18 | 2026-09-08 | security | high | The login rate limiter never freed keys — 50,000 retained, all expired | fixed · `S-06.02.09` |
| D-19 | 2026-09-08 | security | medium | Demo login answered faster for a wrong username than a wrong password | fixed · `S-06.02.09` |
| D-20 | 2026-09-09 | security | critical | Every `/api/` route returned 200 with no login on a default local install | fixed · `S-06.02.10` |
| D-21 | 2026-09-09 | security | high | Nothing checked the `Host` header, so a rebound name reached the API | fixed · `S-06.02.10` |
| D-22 | 2026-09-09 | bug | low | The server advertised one auth header name and read another | fixed · `S-06.02.10` |
| D-23 | 2026-09-09 | security | high | A stale element handle was silently re-resolved instead of refused | fixed · `S-03.02.01` |
| D-24 | 2026-09-09 | gap | medium | Action signatures were recorded on failed steps only, never successful ones | fixed · `S-11.05.02` |
| D-25 | 2026-09-10 | gap | medium | Enter is not gated the way the Send button beside it is | open · `S-11.03.03` |
| D-26 | 2026-09-10 | bug | high | The loop detector could never fire, because its idea of progress was wrong | fixed · `S-11.01.02` |
| D-27 | 2026-09-10 | data-loss | high | A resumed run would have silently lost the facts it exists to keep | fixed before shipping · `S-11.01.03` |
| D-28 | 2026-09-10 | security | high | An injection attack split across two lines escaped the detector entirely | fixed · `S-11.03.02` |
| D-29 | 2026-09-10 | process | high | An XSS test was passing against output that was never escaped | fixed · `S-11.04.01` |
| D-30 | 2026-09-10 | bug | medium | A board audit script read story IDs wrongly and gave the opposite answer | fixed · filed as `S-06.02.11` |
| D-31 | 2026-09-11 | bug | medium | A watcher read the verb out of English prose, so `click` never matched | fixed · `S-11.04.02` |
| D-32 | 2026-09-11 | gap | medium | A read served from memory recorded no signature at all | fixed · `S-11.04.02` |
| D-33 | 2026-09-11 | process | medium | Two board entries pointed at a commit that no longer existed | fixed · filed as `S-06.02.12` |
| D-34 | 2026-09-11 | bug | medium | A page *explaining* two-factor login would have paused every run | fixed before shipping · `S-11.03.01` |
| D-35 | 2026-09-11 | security | high | The daily spend cap can never be reached — every call is recorded as costing $0.00 | fixed · `S-06.01.03` |
| D-36 | 2026-09-11 | gap | high | Providers tell us exactly what each call used, and we throw it away and guess from character counts | fixed · `S-06.01.03` |
| D-37 | 2026-09-11 | process | medium | Five test files hardcode `step-000002`, so adding any step to a run breaks them | open · `S-06.02.14` |
| D-38 | 2026-09-11 | bug | medium | The same pricing arithmetic existed in three places, one of which returned zero | fixed · `S-06.01.03` |

---

## What these add up to

Read the `Found` column, not the `Fixed` one. Five patterns keep repeating, and
each one is a thing to check rather than a thing to feel bad about.

**1. The bug is usually in code that was already finished and passing.**
D-06, D-07, D-02, D-23 and D-24 were all in slices marked `DONE`. The new story
did not break them; it was the first thing that *looked*. When a story touches
old code, the old code is the suspect.

**2. A green test is not the same as a working feature.**
D-03 passed with the feature deleted. D-17's test went green while the bug was
still there — the other thread survived because a five-second timeout released
the lock, not because anything was correct. D-29 checked for a string that
correctly escaped output legitimately contains. Ask of every test: *what would
make this pass if the feature were gone?* And if a test involves timing, look at
how long it took, not only whether it passed.

**3. Two lists that must match will drift apart, silently.**
D-14: the verbs that act and the verbs that are paced were different lists, and
`press` fell in the gap. D-24: signatures were written on one code path and not
the other. D-32: the same again, on a shortcut path. D-38 is the same shape in
arithmetic rather than in a list — the price of a call was computed in three
separate places, and one of them returned zero, which is what `D-35` actually
was underneath. When a rule applies to a set, test that the **set is complete**,
not that the rule works; and when a calculation appears twice, one of the two is
already wrong.

**4. A limit two files away will not be seen from the line that matters.**
D-27: a value may be 20,000 characters and the field holding it caps at 4,000,
so the JSON would have been cut in half and failed to parse on resume — losing
exactly what the feature exists to keep. Check the size limits of a store before
choosing what to put in it.

**5. For anything that detects, the false positives are the hard part.**
D-26 and D-34 were both definitions that sounded reasonable and were wrong.
Both were caught by a test about a case that must **not** match. Write those
tests first.

---

## Detail

### D-35 — The daily spend cap can never be reached · 2026-09-11

**What went wrong.** The owner can set a daily spend limit per provider. The
check for it is real and works. But the line that records what a call cost
passes `spend_usd=0.0` — a hardcoded zero — so the running total never moves off
zero and the cap never fires.

**How it was found.** By running it instead of reading it. A cap of $1.00, then
5,000 calls recorded the way the code records them today:

    calls recorded   : 5000
    cap the owner set: $1.00
    spend counted    : $0.0000
    still allowed?   : True   (nothing refused it)

The same 5,000 calls priced at the number the run's own log already computes
come to $8.00, and the cap refuses immediately.

**Why it mattered.** This is the only thing standing between an agent left
running overnight and an unbounded bill. It is a control that exists, is
configurable, is displayed on the Connectors screen as a usage bar, and does
nothing.

### D-36 — The provider tells us what we spent and we throw it away · 2026-09-11

**What went wrong.** Every major provider returns a `usage` block with the exact
token counts for the call. The adapter receives the whole JSON response, pulls
the text out of it, and drops the rest. Cost is then guessed elsewhere by
dividing the number of characters by four.

**How it was found.** Looking for where a real number could come from, while
fixing D-35.

**Why it mattered.** Two separate problems. The guess is wrong — characters per
token varies by model and by language, and it does not count the tokens a
provider adds itself. And it makes "what did this run cost" unanswerable with
authority: the number in the log is off_CRM's opinion, not the provider's
receipt.


Only where the one-line version is not enough.

### D-16 — Two writes at once destroyed half the rows · 2026-09-08

**What went wrong.** The outreach store shares one database connection across
threads, and the web server runs 193 of its 206 handlers in a thread pool — so
two requests really do arrive at the same moment. Python's SQLite driver
promises to serialise one *statement*. A transaction is several statements, and
it did nothing for that.

    thread A   BEGIN, INSERT 'holder', raise  ->  ROLLBACK
    thread B   INSERT 'bystander'             ->  reported success
    rows left: none

Thread B's write was undone by thread A's failure, and B was told it worked.

**How it was found.** Two threads writing forty rows each. Forty of the eighty
were gone.

**Why it mattered.** 64 call sites depended on this, including `claim_next` —
the thing that stops the email worker sending the same message twice.

**The fix.** The transaction holds a reentrant lock for its whole body. But see
D-17: that was not the whole story.

### D-17 — The fix passed its own test while the bug was still there · 2026-09-08

**What went wrong.** Wrapping the connection made the test green. The bug was
still there — the real cause was `isolation_level`, a default that makes Python
open a transaction nobody asked for and leave it open.

**How it was found.** By not stopping at a green test. The holder thread was
still raising "cannot start a transaction within a transaction", which did not
fit the explanation in my head.

**Why it mattered.** Shipping it would have put a lock around the symptom and
left the cause in place, and the next person would have had no reason to look.

### D-20 — Every API route was open on a local install · 2026-09-09

**What went wrong.** Login was enforced only when a token or a demo login
happened to be configured. A default local install had neither, so it served
every contact to anything that could reach the port.

**How it was found.** Calling every `/api/` route with no credentials. All 200.

**Why it mattered.** "It only listens on localhost" is not a boundary. Every
other process and user on the machine can reach it, so can a browser extension,
and so can any web page that points a hostname it controls at 127.0.0.1.

**The fix.** Auth required on every host, loopback included. A local install
provisions its own token instead of failing. See also D-21.

### D-27 — A resumed run would have lost its facts, silently · 2026-09-10

**What went wrong.** The plan was to store each gathered fact inside its log
line. A fact's value can be 20,000 characters and its supporting quote 4,000.
The log line caps at 4,000 characters total. The JSON would have been cut off
mid-string, and then failed to parse when the run resumed.

**How it was found.** Checking the caps before writing the code, for once. The
mechanism that solves it — a separate file beside the log, for page text — had
existed the whole time.

**Why it mattered.** A run resumed after a crash would have come back having
lost exactly the facts it exists to collect, and nothing would have said so.

### D-29 — An XSS test that was testing nothing · 2026-09-10

**What went wrong.** The test planted a `<script>` tag in the page body. Page
bodies never reach the report — they live in a separate file — so the test was
checking that something absent stayed absent.

Rewriting it to plant the tag in text the model *quoted* then produced a second
wrong test: `assert "onerror=" not in page` **fails against correctly escaped
output**, because escaping turns `<` into `&lt;` and leaves the word `onerror`
sitting there harmlessly.

**How it was found.** By deleting the escaping and watching which tests noticed.
Three did, after the rewrite. None did, before.

**The fix.** Parse the tag names the browser would actually run and compare them
against the list the report is allowed to emit. Test the **property**, not the
shape of the output.

### D-34 — A help page about 2FA would have paused every run · 2026-09-11

**What went wrong.** Two rules in the new wall detector. One matched `/auth` as
a bare word, so `/help/two-factor-authentication` looked like a login URL. The
other counted "two-step verification language plus any text box" as a wall — and
a help article has a search box.

**How it was found.** By writing the *not-a-wall* tests before the wall tests: a
marketing homepage, a help article, a search results page.

**Why it mattered.** This detector is allowed to stop a run. A detector that
pauses on ordinary pages teaches the owner to ignore it, which is worse than not
having one.
