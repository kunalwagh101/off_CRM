"""One-shot governance close-out for S-06.02.03 and the CI verifier defect.

Assertion-backed for the same reason as the product transform: fail closed if
an artifact moved instead of silently corrupting project state.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PRODUCT_COMMIT = "7071213"
CI_COMMIT = "0434081"


def replace_once(path: str, old: str, new: str) -> None:
    p = ROOT / path
    text = p.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{path}: expected one anchor, found {count}: {old[:80]!r}")
    p.write_text(text.replace(old, new, 1), encoding="utf-8")


def append(path: str, text: str) -> None:
    p = ROOT / path
    current = p.read_text(encoding="utf-8")
    if text.strip() in current:
        raise SystemExit(f"{path}: certification block already present")
    p.write_text(current.rstrip() + "\n\n" + text.strip() + "\n", encoding="utf-8")


# Backlog refinement: replace the placeholder story with the actual shipped contract.
replace_once(
    "PRODUCT_BACKLOG.md",
    '''#### S-06.02.03 — Cost and latency budgets per run
- **Given** a run, **when** it exceeds its budget, **then** it stops and says so.
- **Dependencies:** S-06.01.03. **Size:** S. **Indicator:** budget overruns.
''',
    '''#### S-06.02.03 — Cost and latency budgets per run
**As an** owner running unattended work, **I want** each run to respect the
spend and measured-latency ceilings I supply, **so that** autonomous work cannot
silently keep consuming money or execution time beyond my chosen limits.
- **Given** a positive spend ceiling, **when** the next model decision would
  cross it, **then** no provider call starts and the run ends `over_budget` with
  the ceiling and projected next spend recorded.
- **Given** a positive latency ceiling, **when** a completed provider or browser
  operation makes cumulative recorded `took_ms` reach or exceed it, **then** no
  new unit of work starts and the run ends `over_latency` with ceiling, actual
  latency and any in-flight overrun recorded.
- **Given** a run that is resumed, **when** no new latency ceiling is supplied,
  **then** its original ceiling and all earlier measured latency still count;
  raising the ceiling requires an explicit argument.
- **Given** a zero ceiling, **when** the run executes, **then** that dimension is
  uncapped exactly as before; a negative, boolean or non-integer latency ceiling
  is refused before the run starts.
- **Dependencies:** S-06.01.03, S-11.01.04. **Size:** S. **Indicator:** new work
  started after a recorded run ceiling — target zero. **Business value:** E-06,
  bounded production operation owners can trust.
- **Blocking risk:** none after the dependencies above. Exact millisecond
  cancellation of an operation already in flight is unsafe for side-effectful
  browser/provider operations; DD-20 records the operation-boundary rule.
- **Tasks:** T-06.02.03.a integrate latency with the existing trace/run/resume
  path (<=1 day); T-06.02.03.b acceptance and regression tests (<=1 day);
  T-06.02.03.c demo, traceability, evidence and verifier certification (<=1 day).
''',
)

# Change control for the session-open process defect. It gets its own stable ID.
replace_once(
    "PRODUCT_BACKLOG.md",
    '''#### S-06.02.12 — A recorded commit must be on the branch
''',
    '''#### S-06.02.15 — CI gives the verifier the repository it claims to verify
**As an** owner, **I want** CI to give the board verifier complete Git history
and every dependency its evidence commands require, **so that** a red or green
verifier result measures the repository rather than an incomplete CI checkout.
- **Given** a DONE evidence commit older than `HEAD`, **when** CI runs the
  verifier, **then** full ancestry is available and a reachable commit passes.
- **Given** DONE frontend evidence, **when** CI runs the verifier, **then**
  `npm ci` has already completed and the named frontend test can execute.
- **Given** the CI workflow itself, **when** its regression test runs, **then**
  both ordering constraints above are pinned in code.
- **Dependencies:** S-06.02.08, S-06.02.12. **Size:** S. **Indicator:** verifier
  failures caused by CI environment rather than repository state — target zero.
  **Business value:** E-06, trustworthy release evidence.
- **Blocking risk:** none. GitHub Actions run 393 proved the repaired workflow
  end to end on a clean runner.
- **Tasks:** T-06.02.15.a repair checkout/dependency ordering (<=1 day);
  T-06.02.15.b pin the workflow contract with regression tests (<=1 day);
  T-06.02.15.c record the defect and evidence (<=1 day).

#### S-06.02.12 — A recorded commit must be on the branch
''',
)
replace_once(
    "PRODUCT_BACKLOG.md",
    '''| R-99 | A test addresses a trace step by finding it, not by counting | S-06.02.14 |
''',
    '''| R-99 | A test addresses a trace step by finding it, not by counting | S-06.02.14 |
| R-100 | CI gives the verifier full history and evidence dependencies before it runs | S-06.02.15 |
''',
)
replace_once(
    "PRODUCT_BACKLOG.md",
    '''| Multi-tenant SaaS hosting | The product is local-first by design; hosting other people's session cookies is a different business with a different threat model. |
''',
    '''| Multi-tenant SaaS hosting | The product is local-first by design; hosting other people's session cookies is a different business with a different threat model. |
| Hard-cancelling an already-running provider/browser operation to hit an exact millisecond latency wall | The current interfaces cannot prove rollback of a side effect. S-06.02.03 stops *new* work at the operation boundary and reports any one-operation overrun. Revisit only when every effectful operation has a cancellation/idempotency contract. |
''',
)

# Board: chat was never state; make the two delivered stories inspectable here.
replace_once(
    "BOARD.md",
    '''- S-06.02.03 · Cost and latency budgets per run
''',
    '''''',
)
replace_once(
    "BOARD.md",
    '''## DONE

''',
    f'''## DONE

- S-06.02.03 · Cost and latency budgets per run
  tests: tests/test_agent_run_budgets.py, tests/test_agent_money_ceiling.py
  command: python -m pytest tests/test_agent_run_budgets.py tests/test_agent_money_ceiling.py -q
  result: 33 passed (2026-09-16); full Python regression 1928 passed, 4 skipped
  live: the run stops before a browser action when the model call consumes the remaining latency; stops before another model call when a browser action crosses it; resume preserves prior measured latency; raising the ceiling explicitly resumes; existing spend pre-check still prevents the provider call. A first full-suite run also exposed an unrelated Chromium startup timeout; the clean rerun passed all 1928 Python tests before this code was committed.
  code: offsetx_apollo_builder/agent/run.py, tests/test_agent_run_budgets.py
  commit: {PRODUCT_COMMIT}

- S-06.02.15 · CI gives the verifier the repository it claims to verify
  tests: tests/test_ci_verifier_environment.py, tests/test_verify_board.py
  command: python -m pytest tests/test_ci_verifier_environment.py tests/test_verify_board.py -q
  result: 55 passed (2026-09-16); GitHub Actions test run 393 passed end to end
  live: the pre-fix CI passed 1915 Python tests and then the verifier failed because checkout depth 1 hid historical evidence commits and frontend evidence ran before npm dependencies existed. Run 393, commit {CI_COMMIT}, passed after fetch-depth 0 and npm ci were moved before verification.
  code: .github/workflows/ci.yml, scripts/verify_board.py, tests/test_ci_verifier_environment.py
  commit: {CI_COMMIT}

''',
)

# Defect + design-decision ledgers.
replace_once(
    "DEFECT_LOG.md",
    '''| D-45 | 2026-09-12 | process | medium | A `git reset --hard` used to tidy up a live check destroyed an hour of uncommitted work | fixed · `S-06.02.12` |
''',
    '''| D-45 | 2026-09-12 | process | medium | A `git reset --hard` used to tidy up a live check destroyed an hour of uncommitted work | fixed · `S-06.02.12` |
| D-46 | 2026-09-16 | process | high | CI gave the verifier shallow Git history and no frontend dependencies, so truthful DONE evidence looked broken | fixed · `S-06.02.15` |
''',
)
replace_once(
    "DECISIONS.md",
    '''| DD-19 | 2026-09-11 | The pace floor records a deadline, not a last-seen time | A run reserves its slot before it knows whether it will use it |
''',
    '''| DD-19 | 2026-09-11 | The pace floor records a deadline, not a last-seen time | A run reserves its slot before it knows whether it will use it |
| DD-20 | 2026-09-16 | A latency ceiling stops new work at operation boundaries; it does not kill an operation already in flight | The run can exceed the ceiling by the latency of one already-started operation; the overrun is measured and reported |
''',
)
append(
    "DECISIONS.md",
    '''### DD-20 — Latency stops at an operation boundary · 2026-09-16

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
an idempotency or cancellation contract that proves whether the effect happened.''',
)

# Traceability: remove the old planned row and add the completed chains.
replace_once(
    "TRACEABILITY.md",
    '''| R-49 | S-06.02.03 | 1 | — | — |
''',
    '''''',
)
replace_once(
    "TRACEABILITY.md",
    '''## In review — built, but this session cannot complete the proof
''',
    '''| R-49 | S-06.02.03 | 4 | `tests/test_agent_run_budgets.py`, `tests/test_agent_money_ceiling.py` | `agent/run.py` |
| R-100 | S-06.02.15 | 3 | `tests/test_ci_verifier_environment.py`, `tests/test_verify_board.py` | `.github/workflows/ci.yml`, `scripts/verify_board.py` |

## In review — built, but this session cannot complete the proof
''',
)

# Changelog, demo and retro are inspectable release/review artifacts.
replace_once(
    "CHANGELOG.md",
    '''## Unreleased

''',
    '''## Unreleased

- **Per-run cost and latency budgets are now one enforceable contract**
  (`S-06.02.03`). Existing pre-emptive money ceilings are reused rather than
  duplicated. A caller can also supply `latency_ceiling_ms`; cumulative
  provider/browser `took_ms` is read from the existing append-only trace, is
  preserved across resume, and stops new work with `status=over_latency` once
  reached. Outcomes expose actual latency, ceiling, remaining headroom and any
  one-operation overrun. Zero remains uncapped and invalid ceilings fail before
  a run starts.
- **CI now gives the board verifier the environment it actually verifies**
  (`S-06.02.15`, closing `D-46`): full Git history for evidence-commit ancestry
  and frontend dependencies before DONE evidence is replayed. GitHub Actions
  run 393 passed the repaired pipeline end to end.

''',
)
append(
    "DEMO.md",
    '''---

## S-06.02.03 — prove cost and latency ceilings stop new work

```bash
uv run pytest tests/test_agent_run_budgets.py tests/test_agent_money_ceiling.py -q
```

Expect: `33 passed`. The acceptance cases prove both sides of the boundary: a
model call can consume the remaining latency and prevent the next browser
action; a browser action can cross the ceiling and prevent the next model call;
resume keeps the original allowance; the existing money ceiling still stops
before a provider call.

Then run the independent delivery gate:

```bash
uv run python scripts/verify_board.py
```

Expect: exit code 0 and `OK — the board matches the repository.`''',
)
append(
    "RETRO.md",
    '''---

## 2026-09-16 — S-06.02.03, cost and latency budgets per run

**What was cut.** Nothing from the promised budget control. Exact cancellation
of an operation already in flight is explicitly *not claimed*: with the current
browser/provider contracts it can leave an unknown remote side effect. The run
stops new work at the next operation boundary and reports the measured overrun;
DD-20 records the trigger for revisiting that choice.

**What the estimate got wrong.** The product change was small because the money
ceiling and trace timing already existed. The expensive part was process truth:
the session-open verifier exposed `D-46`, where CI itself gave the verifier a
shallow checkout and no frontend dependencies. The first full regression also
hit an unrelated Chromium startup timeout after 1927 tests had passed; the clean
rerun passed all 1928 before the source commit was allowed through.

**What to change next time.** Run the session-open verifier before any product
patch and treat a red verifier as its own change-controlled defect immediately.
This session repaired it first but wrote its formal backlog/board artifacts only
at close-out; that ordering is recorded here rather than rewritten as if the
ceremony happened earlier. Also keep budget controls on existing ledgers and
traces: a second cost/timing subsystem would have created drift rather than
safety.''',
)

print("S-06.02.03 governance artifacts certified")
