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
