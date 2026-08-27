# Traceability

Every row is completable. A row that cannot be filled in is a gap, and the gap
is the point of the table.

**Read the columns as a chain:** a requirement you asked for → the story that
carries it → the acceptance criteria that define "carried" → the test that
proves it → the code it lives in. A break anywhere in that chain means the
requirement is an intention rather than a feature.

`scripts/verify_board.py` checks columns 1–2 (no orphan requirement, no orphan
story) and, for `DONE` rows, columns 4–5 (the test exists, the command passes,
the code exists and holds no stub).

---

## Delivered — the chain is complete

| Req | Story | Criteria | Test | Code |
|---|---|---|---|---|
| R-01 | S-01.01.01 | 2 | `tests/test_video_timeline.py` | `video/timeline.py` |
| R-02 | S-01.01.02 | 1 | `tests/test_video_mixdown.py` | `tests/fixtures/timeline_conformance.json` |
| R-03, R-04 | S-01.02.01 | 2 | `tests/test_video_engine.py` | `video/mixdown.py`, `video/gates.py` |
| R-05 | S-01.02.02 | 1 | `tests/test_video_retime.py` | `video/presets.py`, `video/timeline.py` |
| R-06 | S-01.02.03 | 2 | `tests/test_video_effects.py` | `video/effects.py`, `frontend/src/video/shaders/` |
| R-07 | S-01.03.01 | 2 | `tests/test_video_assembly.py` | `video/assembly.py`, `video/recipes.py` |
| R-08 | S-01.03.02 | 2 | `tests/test_video_director.py` | `video/director.py` |
| R-09 | S-01.04.01 | 3 | `tests/test_video_review.py` | `video/engine.py`, `video/store.py` |
| R-10, R-11 | S-01.04.02 | 3 | `tests/test_pacing_cap.py` | `distribution/pacing.py`, `distribution/engine.py` |
| R-12 | S-02.01.01 | 2 | `tests/test_browser_agent.py` | `browser/cdp.py`, `browser/session.py` |
| R-13 | S-02.01.02 | 2 | `tests/test_browser_agent.py` | `browser/perceive.py` |
| R-14 | S-02.01.03 | 2 | `tests/test_browser_agent.py` | `browser/page.py` |
| R-15, R-40 | S-02.01.04 | 2 | `tests/test_browser_agent.py` | `browser/policy.py` |
| R-16 | S-02.01.05 | 2 | `tests/test_browser_agent.py` | `browser/trace.py` |
| R-52 | S-06.02.06 | 2 | `tests/test_verify_board.py` | `scripts/verify_board.py` |
| R-57 | S-06.02.07 | 2 | `tests/test_verify_board.py` | `scripts/verify_board.py` |
| R-61, R-62 | S-08.01.01 | 3 | `tests/test_email_delivery.py` | `outreach/deliverability/preflight.py`, `outreach/deliverability/store.py` |
| R-64, R-65, R-66 | S-08.01.02 | 3 | `tests/test_email_delivery.py` | `outreach/deliverability/service.py`, `outreach/deliverability/store.py` |
| R-67, R-68 | S-08.01.03 | 3 | `tests/test_email_delivery.py` | `outreach/deliverability/domain_auth.py`, `outreach/deliverability/ses.py` |
| R-69, R-70 | S-08.01.04 | 3 | `tests/test_email_delivery.py` | `outreach/deliverability/events.py`, `outreach/deliverability/service.py` |

## In review — built, but this session cannot complete the proof

| Req | Story | Criteria | Current proof | Missing proof |
|---|---|---|---|---|
| R-63, R-71 | S-08.01.05 | 3 | 2 Python API/control tests pass | Re-run `frontend/src/components.test.tsx`; npm dependency is not cached in this environment |

## Ready — the decision exists, code does not

| Req | Story | Decision recorded | What will be built |
|---|---|---|---|
| R-21, R-22, R-23 | S-03.01.01 | Q-02 | Attended and unattended browser-box policy |
| R-25, R-26, R-42 | S-03.02.01 | Q-03 | LinkedIn-first sign-in flow |
| R-27, R-28, R-29 | S-03.02.02 | Q-01 | OS-keychain master key with passphrase fallback |

## Blocked externally — engineering is waiting on access

| Req | Story | Blocked on |
|---|---|---|
| R-58 | S-01.05.01 | Owner-created Google Cloud project, YouTube Data API v3 and channel OAuth consent |
| R-59 | S-01.05.02 | Meta review, TikTok audit and LinkedIn partner access |
| R-60 | S-01.05.03 | S-01.05.01 and its Google Cloud access |

## Planned — story and criteria written, nothing built

| Req | Story | Criteria | Test | Code |
|---|---|---|---|---|
| R-17 | S-02.02.01 | 2 | — | — |
| R-18 | S-02.02.02 | 2 | — | — |
| R-19 | S-02.02.03 | 1 | — | — |
| R-20 | S-02.02.04 | 1 | — | — |
| R-30 | S-03.02.03 | 1 | — | — |
| R-31, R-35 | S-04.01.01 | 1 | — | — |
| R-32 | S-04.01.02 | 1 | — | — |
| R-33 | S-04.01.03 | 2 | — | — |
| R-34, R-35 | S-04.01.04 | 2 | — | — |
| R-36, R-37, R-40 | S-05.01.01 | 3 | — | — |
| R-38 | S-05.01.02 | 1 | — | — |
| R-39 | S-05.01.03 | 2 | — | — |
| R-41, R-42 | S-06.01.01 | 1 | — | — |
| R-43 | S-06.01.02 | 2 | — | — |
| R-44 | S-06.01.03 | 2 | — | — |
| R-45, R-46 | S-06.01.04 | 2 | — | — |
| R-47 | S-06.01.05 | 2 | — | — |
| R-29 | S-06.02.01 | 1 | — | — |
| R-48 | S-06.02.02 | 2 | — | — |
| R-49 | S-06.02.03 | 1 | — | — |
| R-50 | S-06.02.04 | 1 | — | — |
| R-51 | S-06.02.05 | 1 | — | — |
| R-53 | S-07.01.01 | 2 | — | — |
| R-54 | S-07.01.02 | 1 | — | — |
| R-55 | S-07.01.03 | 1 | — | — |
| R-56 | S-07.01.04 | 1 | — | — |

## Deferred — cut, with the trigger to bring it back

| Req | Story | Reason | Trigger |
|---|---|---|---|
| R-24 | S-03.01.02 | The no-network guarantee holds today and nothing in this increment touches it | S-03.01.01 entering IN_PROGRESS |

---

## The honest reading of this table

**71 requirements, zero orphans. 20 stories are DONE, 1 is IN_REVIEW, 3 are
READY, 3 are externally BLOCKED, 26 are planned in BACKLOG and 1 is DEFERRED.**

44% of the acceptance criteria in the backlog sit behind something `DONE`. That
number is recomputed by the verifier from the repository every run, so it moves
when the work moves and not when the summary is edited.

### Gaps that were open, and are now closed

- **`tests/test_email_delivery.py` had a failing test** on `d96ea9d`, and that
  work had no backlog ID — it entered the repository without passing through
  this process. It has IDs now (E-07 / F-08.01, R-61 to R-71) and the failing
  test is fixed: its queue time was derived from a hardcoded 2026-08-24 fixture
  and expired when the date passed. **The suite is green: 1,495 passed, 0
  failed.** Applying change control to somebody else's commit is the only way
  it means anything, and it worked.

### Gaps still open

- **Frontend tests are not named in most evidence blocks.** The video work has
  115 of them and they are real, but only one story's evidence command reaches
  them. Either the frontend command joins the rest or the coverage figure keeps
  understating what is proven.
- **S-08.01.05 sits in `IN_REVIEW`**, not `DONE`, because its frontend test has
  not been re-run in an environment with the locked npm dependencies. That is
  the Definition of Done working: code written and not verified is `IN_REVIEW`.

---

## Delivered since this table was written

| Req | Story | Criteria | Test | Code |
|---|---|---|---|---|
| R-21, R-22, R-23 | S-03.01.01 | 2 | `tests/test_browser_box.py` | `browser/box.py`, `browser/guard.py` |
| R-24 | S-03.01.02 | 1 | `tests/test_ai_sandbox.py`, `tests/test_browser_box.py` | `ai/sandbox.py` |

S-03.01.02 was on the `DEFERRED` shelf with the trigger *"S-03.01.01 entering
IN_PROGRESS"*. The trigger fired, it came back, and it is done — which is the
only reason a deferred register is worth keeping.
