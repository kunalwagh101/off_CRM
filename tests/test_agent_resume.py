"""A run survives the process dying.  `S-11.01.03`

There is no checkpoint file. The trace is append-only, written a step at a time
with the handle opened per write, so a process killed mid-run leaves a complete
record up to its last step — and `Trace.read` says in its own docstring that
replaying it is what resuming is built on.

That is the design the blueprint named a month ago: *a run is resumable because
the trace is complete. Not "we save progress" — the trace* is *the progress.*
The alternative, a snapshot written every few steps, has a failure mode this does
not: the snapshot and the trace can disagree, and then the resumed run believes
something that never happened.
"""
from __future__ import annotations

import asyncio
import json
from types import SimpleNamespace

import pytest

from offsetx_apollo_builder.agent import AgentRun, ResumeState, replay
from offsetx_apollo_builder.agent.result import Finding, Provenance, ResultSchemaError
from offsetx_apollo_builder.agent.run import RunRefused
from offsetx_apollo_builder.ai.broker import WorkspaceEgressSettings
from offsetx_apollo_builder.ai.tiers import TrustTier
from offsetx_apollo_builder.browser.page import ActionResult
from offsetx_apollo_builder.browser.perceive import Node, Snapshot
from offsetx_apollo_builder.browser.trace import Step, Trace


# ── the round trip a resumed fact depends on ────────────────────────────────


def test_a_finding_survives_being_written_down_and_read_back():
    finding = Finding(
        field="employees", value="42", kind="observed", confidence=0.9,
        source=Provenance(url="https://acme.test/about", captured_at="2026-09-10T00:00:00Z",
                          step_id="step-000002", screenshot="0002.png", quote="Employees: 42"),
    )
    assert Finding.from_dict(json.loads(json.dumps(finding.to_dict()))) == finding


def test_a_recorded_finding_without_provenance_is_refused_not_rebuilt():
    """`S-11.02.02` exists to stop an unsourced fact being returned. Rebuilding
    one with an empty source on resume would reintroduce it through the back
    door."""
    with pytest.raises(ResultSchemaError, match="no provenance"):
        Finding.from_dict({"field": "employees", "value": "42"})


# ── harness ─────────────────────────────────────────────────────────────────


class _Registry:
    def get(self, provider_id):
        if provider_id != "trusted":
            return None
        model = SimpleNamespace(id="planner", cost_per_1m_input_usd=2.0,
                                cost_per_1m_output_usd=8.0)
        return SimpleNamespace(model=lambda model_id="": model)


class _Broker:
    def __init__(self, answers):
        self.answers = list(answers)
        self.registry = _Registry()

    def plan(self, request, settings, *, provider_id=""):
        return [SimpleNamespace(id="trusted", model_id="planner", tier=TrustTier.A, cost=1.0)], []

    def call(self, request, settings, *, system_prompt, provider_id="", expect_json=False):
        if not self.answers:
            raise AssertionError("the run asked for more decisions than the test scripted")
        return SimpleNamespace(
            text=self.answers.pop(0), provider_id="trusted", provider_name="Trusted",
            model_id="planner", tier="A", policy="full",
            data_class=request.data_class.value, duration_ms=7,
            payload_fields=["instructions"], attempts=[], rejected=[], log_id="e1",
        )


class _Page:
    def __init__(self, url="https://acme.test/about"):
        self.url = url
        self.body = "Company: Acme Ltd Employees: 42"

    async def snapshot(self):
        return Snapshot(url=self.url, title="Acme",
                        nodes=[Node(handle=1, role="button", name="More", backend_id=1)])

    async def goto(self, url):
        self.url = url
        return ActionResult(action="goto", ok=True, url=url, detail=f"opened {url}")

    async def read(self, *, limit=20_000):
        return ActionResult(action="read", ok=True, url=self.url, detail="read",
                            text=self.body)

    async def click(self, handle, *, confirmed=False):
        return ActionResult(action="click", ok=True, url=self.url, detail="clicked")

    async def screenshot(self):
        return ActionResult(action="screenshot", ok=True, url=self.url, detail="shot",
                            screenshot=b"\x89PNG\r\n\x1a\nx")


def _act(action, *, record=None, **args):
    """A decision may carry a record while still acting — that is how the agent
    reports a fact as it goes, rather than saving them all for the end."""
    payload = {"state": "act", "action": action, "args": args, "reason": "step"}
    if record is not None:
        payload["record"] = record
    return json.dumps(payload)


def _done(**record):
    return json.dumps({"state": "done", "reason": "found it", "result": "found",
                       "record": record})


def _agent(page, answers, trace):
    return AgentRun(
        broker=_Broker(answers),
        settings=WorkspaceEgressSettings(workspace_id="w",
                                         enabled_models={"trusted": ("planner",)}),
        page=page, trace=trace, planner_provider_id="trusted",
    )


class _Killed(RuntimeError):
    """Stands in for the process dying. Nothing gets to tidy up."""


# ── the story ───────────────────────────────────────────────────────────────


def _interrupted_run(tmp_path, *, root):
    """Run until a fact is gathered, then die without an ending step."""
    page = _Page()
    trace = Trace.open(root)
    # The read finds the fact and the agent reports it, then the process dies
    # before the run can finish. That is the scenario this story is for.
    agent = _agent(
        page,
        [
            _act("read"),
            # Citing the read's own trace step. Ids are assigned in order, so
            # run_started is 000000, the first decision 000001, and the read
            # action 000002 — the step that carries the page capture.
            _act("click", handle=1, record={
                "employees": {
                    "value": "42",
                    "source_step_id": "step-000002",
                    "quote": "Employees: 42",
                    "kind": "observed",
                    "confidence": 0.9,
                }
            }),
        ],
        trace,
    )

    original = agent._execute_decision if hasattr(agent, "_execute_decision") else None
    real_snapshot = page.snapshot
    calls = {"n": 0}

    async def dying_snapshot():
        calls["n"] += 1
        if calls["n"] > 2:
            raise _Killed("the process went away")
        return await real_snapshot()

    page.snapshot = dying_snapshot
    with pytest.raises(_Killed):
        asyncio.run(agent.run("how many people work at Acme",
                              step_budget=10, result_schema=["employees"]))
    return trace, page


def test_a_killed_run_leaves_a_trace_that_can_be_read_back(tmp_path):
    trace, _ = _interrupted_run(tmp_path, root=tmp_path / "traces")
    state = replay(trace)

    assert isinstance(state, ResumeState)
    assert state.goal == "how many people work at Acme"
    assert state.step_budget == 10
    assert state.schema_fields == ("employees",)
    assert state.decisions >= 1
    assert state.steps_remaining < 10, "a resumed run must not get its whole budget again"


def test_resuming_continues_the_same_trace_and_marks_where(tmp_path):
    """One continuous record, not two. The second acceptance criterion."""
    root = tmp_path / "traces"
    trace, page = _interrupted_run(tmp_path, root=root)
    before = len(list(trace.read()))

    reopened = Trace.open(root, run_id=trace.run_id)
    assert len(list(reopened.read())) == before, "reopening lost or duplicated steps"

    agent = _agent(_Page(), [_done(employees="42")], reopened)
    outcome = asyncio.run(agent.resume())

    steps = list(Trace.open(root, run_id=trace.run_id).read())
    assert len(steps) > before, "the resumed half was written somewhere else"
    assert [s for s in steps if s.kind == "resumed"], "the resume point is not marked"
    assert len([s for s in steps if s.kind == "run_started"]) == 1, (
        "a resumed run started a second run inside one trace"
    )
    assert outcome.status in {"completed", "incomplete"}


def test_a_resumed_run_keeps_the_facts_it_already_gathered(tmp_path):
    """The first acceptance criterion, and the reason any of this matters."""
    root = tmp_path / "traces"
    trace, _ = _interrupted_run(tmp_path, root=root)

    state = replay(Trace.open(root, run_id=trace.run_id))
    assert "employees" in state.findings, "the fact did not survive the trace"
    assert state.findings["employees"].value == "42"
    assert state.findings["employees"].source.step_id, "the fact came back unsourced"


def test_a_resumed_run_does_not_get_its_whole_budget_again(tmp_path):
    root = tmp_path / "traces"
    trace, _ = _interrupted_run(tmp_path, root=root)
    state = replay(Trace.open(root, run_id=trace.run_id))
    assert state.steps_remaining == state.step_budget - state.decisions


def test_a_finished_run_is_not_resumed(tmp_path):
    """Appending a second ending would make the trace say two contradictory
    things about how the run turned out."""
    root = tmp_path / "traces"
    trace = Trace.open(root)
    agent = _agent(_Page(), [_done(employees="42")], trace)
    asyncio.run(agent.run("count them", step_budget=5, result_schema=["employees"]))

    again = _agent(_Page(), [], Trace.open(root, run_id=trace.run_id))
    with pytest.raises(RunRefused, match="already ended"):
        asyncio.run(again.resume())


def test_a_trace_with_no_goal_is_refused_rather_than_guessed(tmp_path):
    root = tmp_path / "traces"
    trace = Trace.open(root)
    trace.append(Step(kind="action", detail="something happened", url="https://a.test/"))
    with pytest.raises(RunRefused, match="no run_started"):
        replay(trace)


def test_a_fact_whose_artefact_is_gone_is_dropped_not_invented(tmp_path):
    """Losing a fact is recoverable. Inventing one is not."""
    root = tmp_path / "traces"
    trace, _ = _interrupted_run(tmp_path, root=root)
    reopened = Trace.open(root, run_id=trace.run_id)
    for step in reopened.read():
        if step.kind == "finding" and step.capture:
            (reopened.directory / step.capture).unlink()

    state = replay(Trace.open(root, run_id=trace.run_id))
    assert "employees" not in state.findings


def test_replay_restores_what_was_already_tried(tmp_path):
    """So a resumed run does not re-try what failed, or call a page it has
    already seen new — the two detectors from S-11.01.01 and S-11.01.02 would
    otherwise start from nothing."""
    root = tmp_path / "traces"
    trace, _ = _interrupted_run(tmp_path, root=root)
    state = replay(Trace.open(root, run_id=trace.run_id))
    assert state.visited_urls, "no page was remembered as visited"
    assert state.last_url
