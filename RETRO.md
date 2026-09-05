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