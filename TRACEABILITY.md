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
| R-17 | S-02.02.01 | 2 | `tests/test_agent_run.py` | `agent/run.py`, `browser/trace.py` |
| R-27, R-28, R-29 | S-03.02.02 | 3 | `tests/test_browser_vault.py`, `tests/test_browser_vault_wiring.py` | `browser/vault.py`, `browser/signin.py`, `ai/scanner.py` |
| R-30 | S-03.02.03 | 1 | `tests/test_browser_revoke.py` | `browser/revoke.py`, `browser/vault.py`, `browser/identity.py`, `browser/trace.py` |
| R-72, R-73, R-74 | S-03.02.04 | 3 | `tests/test_browser_budget.py` | `browser/budget.py`, `browser/identity.py`, `browser/page.py`, `browser/signin.py` |
| R-52 | S-06.02.06 | 2 | `tests/test_verify_board.py` | `scripts/verify_board.py` |
| R-57 | S-06.02.07 | 2 | `tests/test_verify_board.py` | `scripts/verify_board.py` |
| R-61, R-62 | S-08.01.01 | 3 | `tests/test_email_delivery.py` | `outreach/deliverability/preflight.py`, `outreach/deliverability/store.py` |
| R-64, R-65, R-66 | S-08.01.02 | 3 | `tests/test_email_delivery.py` | `outreach/deliverability/service.py`, `outreach/deliverability/store.py` |
| R-67, R-68 | S-08.01.03 | 3 | `tests/test_email_delivery.py` | `outreach/deliverability/domain_auth.py`, `outreach/deliverability/ses.py` |
| R-69, R-70 | S-08.01.04 | 3 | `tests/test_email_delivery.py` | `outreach/deliverability/events.py`, `outreach/deliverability/service.py` |
| R-80 | S-11.02.01 | 3 | `tests/test_agent_structured_result.py` | `agent/result.py`, `agent/run.py` |
| R-81 | S-11.02.02 | 2 | `tests/test_agent_provenance.py` | `agent/result.py`, `agent/run.py`, `browser/trace.py` |
| R-82 | S-11.02.03 | 3 | `tests/test_agent_claim_verification.py` | `agent/verify.py`, `agent/result.py`, `agent/run.py` |
| R-83 | S-11.02.04 | 2 | `tests/test_agent_page_read_cache.py` | `agent/read_cache.py`, `agent/run.py` |

## In review — built, but this session cannot complete the proof

| Req | Story | Criteria | Current proof | Missing proof |
|---|---|---|---|---|
| R-63, R-71 | S-08.01.05 | 3 | 2 Python API/control tests pass | Promote the now-green frontend evidence through that story's own review/board update |

## Ready — decision and dependencies resolved, not yet pulled

| Req | Story | Criteria | Test | Code |
|---|---|---|---|---|
| R-75 | S-03.02.05 | 2 | — | — |
| R-76 | S-11.01.01 | 3 | — | — |
| R-78 | S-11.01.03 | 2 | — | — |
| R-85 | S-11.03.02 | 2 | — | — |
| R-88 | S-11.05.01 | 3 | — | — |
| R-90 | S-06.02.08 | 2 | — | — |

## Blocked externally — engineering is waiting on access

| Req | Story | Blocked on |
|---|---|---|
| R-58 | S-01.05.01 | Owner-created Google Cloud project, YouTube Data API v3 and channel OAuth consent |
| R-59 | S-01.05.02 | Meta review, TikTok audit and LinkedIn partner access |
| R-60 | S-01.05.03 | S-01.05.01 and its Google Cloud access |

## Planned — story and criteria written, nothing built

| Req | Story | Criteria | Test | Code |
|---|---|---|---|---|
| R-18 | S-02.02.02 | 2 | — | — |
| R-19 | S-02.02.03 | 1 | — | — |
| R-20 | S-02.02.04 | 1 | — | — |
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
| R-77 | S-11.01.02 | 3 | — | — |
| R-79 | S-11.01.04 | 3 | — | — |
| R-84 | S-11.03.01 | 2 | — | — |
| R-86 | S-11.04.01 | 3 | — | — |
| R-87 | S-11.04.02 | 2 | — | — |
| R-89 | S-11.05.02 | 2 | — | — |

## Deferred — cut, with the trigger to bring it back

*(Empty. The former S-03.01.02 trigger fired and that story is delivered.)*

---

## The honest reading of this table

The readable table now includes the later R-72–R-90 additions instead of
stopping at the original 71-requirement snapshot. `scripts/verify_board.py`
remains authoritative for the live counts, orphan detection, acceptance coverage
and rerunnable DONE evidence; those counts are intentionally not duplicated here
because they change every increment.

### Gaps that were open, and are now closed

- **S-02.02.01 closes the browser autonomy gap.** The browser already had safe
  perception, a closed ten-verb action vocabulary and an append-only trace, but
  nothing could turn an owner goal into repeated decisions and actions. The
  bounded run loop does that through the existing egress broker, refuses lower-
  trust planning, treats page content as untrusted input, stops at consequential
  human gates and records provider/model plus estimated usage in the trace.
- **S-03.02.02 closed the browser-session custody gap.** The browser can retain
  an attended login, but off_CRM keeps its managed copy under a different random
  key per workspace/platform account. The master source is OS-backed, with an
  explicit scrypt passphrase fallback, and sign-in refuses to record a green
  connection until vault capture succeeds. Generic cookie/token/password shapes
  are refused by the shared AI egress scanner even at `full` policy.
- **S-03.02.03 closes the browser-session exit path.** Disconnect deletes the
  exact vaulted cookies from real Chromium, destroys that account's encrypted
  vault envelope, forgets the public connection record, and writes the action —
  not the secret — to the append-only trace. Browser deletion failure keeps the
  encrypted vault and green record so the owner can retry instead of seeing a
  false disconnected state.
- **S-11.02.01 through S-11.02.04 close the first data-trust chain.** A caller
  declares the result shape; every fact points to host-owned provenance; observed
  claims are checked against the cited capture; and a page already captured in
  the same run is reused without manufacturing a second source or browser read.

### Gaps still open

- **S-08.01.05 remains `IN_REVIEW`** until its now-green frontend evidence is
  promoted through that story's own acceptance/evidence update; this increment
  does not silently absorb an unrelated board transition.
- **S-06.02.01 remains planned.** S-03.02.02 directly proves browser credential
  shapes cannot enter a provider payload, but the broader adversarial
  no-secret-in-any-prompt suite remains its own story and is not silently
  claimed here.
- **Agent evidence is durable but not yet a cross-run relational query store.**
  Per-run JSONL/text/screenshot artifacts are deliberately optimized for audit,
  provenance and resume. Indexing verified findings and evidence metadata into a
  workspace-scoped relational store should be a separate persistence slice so
  queryability does not weaken the immutable evidence boundary.
