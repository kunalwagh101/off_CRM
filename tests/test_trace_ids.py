"""Referring to a trace step without counting them.  `S-06.02.14`

`D-37`. Five test files named `step-000002` and meant "the read action step".
Adding any step earlier in a run shifts every id after it, so a story with
nothing to do with provenance breaks the provenance tests. It happened twice —
a `finding` step in `S-11.01.03` and an estimate in `S-06.01.03` — and both
times the fix was to bump a number, which buys one story of quiet.

The helper these tests cover is in `tests/trace_ids.py`. The *real* proof of
this story is not here: it is that inserting a step into `agent/run.py` and
re-running the five converted files leaves all 49 passing, which is recorded in
the board's evidence block because it cannot be asserted from inside them.
"""
from __future__ import annotations

import pytest

from offsetx_apollo_builder.browser.trace import Step, Trace
from trace_ids import CITE, fill_citations, offered_step_id, step_id_of


# ── citing what the run offered ─────────────────────────────────────────────


def test_the_offered_id_is_read_out_of_the_prompt():
    """`_observation` writes `step_id=step-000002` into the instructions. That
    is what a real model cites, so it is what the double cites."""
    assert offered_step_id("SOURCE EVIDENCE\nstep_id=step-000004\nurl=x") == "step-000004"


def test_the_most_recent_offer_wins():
    """A run that has read twice has offered two. The one being cited is the
    one just captured, not the first one it ever saw."""
    prompt = "step_id=step-000002 ... later ... step_id=step-000009"
    assert offered_step_id(prompt) == "step-000009"


def test_a_prompt_offering_nothing_yields_nothing():
    assert offered_step_id("no evidence here at all") == ""
    assert offered_step_id("") == ""


def test_a_scripted_answer_is_filled_in_with_what_was_offered():
    answer = '{"state": "done", "record": {"x": {"source_step_id": "%s"}}}' % CITE
    filled = fill_citations(answer, "step_id=step-000007")
    assert "step-000007" in filled
    assert CITE not in filled


def test_an_answer_that_cites_nothing_is_left_exactly_alone():
    answer = '{"state": "act", "action": "read"}'
    assert fill_citations(answer, "step_id=step-000007") == answer


# ── finding a step rather than counting to it ───────────────────────────────


def _trace(tmp_path) -> Trace:
    trace = Trace.open(tmp_path / "t")
    trace.append(Step(kind="run_started", detail="go"))
    trace.append(Step(kind="decision", detail="read"))
    trace.append(Step(kind="action", detail="read the page"))
    trace.append(Step(kind="decision", detail="click"))
    trace.append(Step(kind="action", detail="clicked"))
    return trace


def test_the_first_step_of_a_kind_is_found_not_counted(tmp_path):
    trace = _trace(tmp_path)
    assert step_id_of(trace, "action") == "step-000002"
    assert step_id_of(trace, "decision") == "step-000001"


def test_a_later_occurrence_can_be_asked_for(tmp_path):
    assert step_id_of(_trace(tmp_path), "action", occurrence=1) == "step-000004"


def test_inserting_a_step_moves_the_number_but_not_the_answer(tmp_path):
    """The whole point, in miniature. The literal `step-000002` would be wrong
    after this; "the first action" is still right."""
    trace = Trace.open(tmp_path / "t")
    trace.append(Step(kind="run_started", detail="go"))
    trace.append(Step(kind="estimate", detail="a step added by a later story"))
    trace.append(Step(kind="decision", detail="read"))
    trace.append(Step(kind="action", detail="read the page"))

    assert step_id_of(trace, "action") == "step-000003"


def test_asking_for_a_step_that_is_not_there_says_so(tmp_path):
    """Rather than returning an empty string that fails an assertion later with
    nothing to say about why."""
    with pytest.raises(AssertionError, match="occurrence 3"):
        step_id_of(_trace(tmp_path), "action", occurrence=3)

    with pytest.raises(AssertionError, match="0 'finding' step"):
        step_id_of(_trace(tmp_path), "finding")
