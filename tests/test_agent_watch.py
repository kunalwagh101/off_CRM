"""Watching a run while it happens.  `S-11.04.02`

`S-11.04.01` tells you what a run did, after it did it. This is so a run heading
for the wrong page at step 4 can be seen at step 4 rather than read about at
step 40.

**It shows; it does not stop.** Interrupting is `S-02.02.03` and is not smuggled
in here — but somebody who can see a run going wrong can kill the process, and
`S-11.01.03` means resuming costs nothing.

The two things easiest to get wrong are both tested directly: that updates
arrive *during* the run rather than in a batch at the end, and that a watcher
which throws cannot take the run down with it.
"""
from __future__ import annotations

import asyncio
import io
import json
from types import SimpleNamespace

import pytest

from offsetx_apollo_builder.agent import AgentRun
from offsetx_apollo_builder.agent.watch import (
    MAX_LINE_DETAIL,
    Progress,
    console,
    observer,
)
from offsetx_apollo_builder.ai.broker import WorkspaceEgressSettings
from offsetx_apollo_builder.ai.tiers import TrustTier
from offsetx_apollo_builder.browser.page import ActionResult
from offsetx_apollo_builder.browser.perceive import Node, Snapshot
from offsetx_apollo_builder.browser.trace import Step, Trace


# ── the trace hook ──────────────────────────────────────────────────────────


def test_a_listener_hears_every_step_as_it_is_recorded(tmp_path):
    heard = []
    trace = Trace.open(tmp_path / "t")
    trace.listener = heard.append
    trace.append(Step(kind="run_started", url="https://a.test/"))
    trace.append(Step(kind="action", detail="clicked", url="https://a.test/"))
    assert [step.kind for step in heard] == ["run_started", "action"]


def test_a_listener_hears_only_what_is_already_durable(tmp_path):
    """After the write, never before. A watcher must not see a step that a
    crash would then erase."""
    trace = Trace.open(tmp_path / "t")
    seen_on_disk = []
    trace.listener = lambda step: seen_on_disk.append(
        trace.path.read_text(encoding="utf-8").count("\n")
    )
    trace.append(Step(kind="run_started"))
    trace.append(Step(kind="action"))
    assert seen_on_disk == [1, 2], "a step reached the watcher before it reached the disk"


def test_a_watcher_that_throws_cannot_take_the_trace_down(tmp_path):
    """An audit log a broken viewer can bring down is worse than no viewer."""
    trace = Trace.open(tmp_path / "t")

    def explode(_step):
        raise RuntimeError("the terminal went away")

    trace.listener = explode
    trace.append(Step(kind="run_started", url="https://a.test/"))
    assert len(list(trace.read())) == 1, "the step was lost when the watcher failed"


# ── what a watcher is told ──────────────────────────────────────────────────


def _progress(**overrides) -> Progress:
    base = dict(index=3, kind="action",
                detail="read the page [signature=read()]", url="https://a.test/x",
                ok=True, took_ms=12, cost_usd=0.0042, tokens_in=900, tokens_out=30)
    base.update(overrides)
    return Progress(**base)


def test_an_update_carries_the_action_the_url_and_the_running_cost():
    """The acceptance criterion, field by field."""
    update = _progress()
    assert update.action == "read"
    assert update.url == "https://a.test/x"
    assert update.cost_usd == 0.0042
    assert update.to_dict()["action"] == "read"


def test_only_a_step_that_was_an_action_reports_one():
    assert _progress(kind="decision", detail="read {...}").action == ""
    assert _progress(kind="completed", detail="found it").action == ""


def test_the_verb_comes_from_the_signature_not_from_the_prose():
    """A click records "clicked More". Splitting the English gives "clicked",
    which is not one of the ten verbs and matches nothing."""
    clicked = _progress(detail="clicked More [signature=click(handle=1)]")
    assert clicked.action == "click"
    typed = _progress(detail="typed into Search [signature=type(handle=2,text='hi')]")
    assert typed.action == "type"


def test_a_step_with_no_signature_reports_no_verb_rather_than_guessing():
    assert _progress(detail="something happened").action == ""


def test_a_line_is_one_terminal_can_hold():
    long = _progress(detail="x" * 5_000, url="https://a.test/" + "y" * 200)
    for line in long.line().split("\n"):
        assert len(line) <= max(MAX_LINE_DETAIL + 40, 260), line
    assert "…" in long.line(), "a long detail was not trimmed"


def test_the_line_names_the_verb_even_when_the_detail_is_cut_short():
    """The criterion asks for the action. A long detail truncates the signature
    off the end of the line, so the verb cannot live only in there."""
    line = _progress(detail="clicked " + "M" * 300 + " [signature=click(handle=1)]").line()
    assert "action click" in line
    assert "…" in line, "the detail was not long enough to test the case"


def test_a_failed_step_is_marked_so_it_can_be_spotted():
    assert _progress(ok=False).line().startswith("!")
    assert _progress(ok=True).line().startswith(" ")


def test_a_multiline_detail_does_not_break_the_layout():
    assert "\n" not in _progress(detail="a\nb\nc").line().split("\n")[0]


def test_the_running_totals_come_from_the_trace_not_from_the_watcher(tmp_path):
    """So a watcher attached to a resumed run counts the whole run and not just
    the part it was present for."""
    trace = Trace.open(tmp_path / "t")
    trace.append(Step(kind="decision", estimated_cost_usd=0.01, tokens_in=100))
    seen = []
    trace.listener = observer(trace, seen.append)
    trace.append(Step(kind="decision", estimated_cost_usd=0.02, tokens_in=50))

    assert seen[0].cost_usd == pytest.approx(0.03)
    assert seen[0].tokens_in == 150
    assert seen[0].index == 1


# ── the console watcher ─────────────────────────────────────────────────────


def test_the_console_watcher_writes_and_flushes_each_step():
    """Unflushed, it shows you the run after it has finished — the thing this
    story exists to stop."""
    flushes = {"n": 0}

    class _Stream(io.StringIO):
        def flush(self):
            flushes["n"] += 1

    stream = _Stream()
    show = console(stream)
    show(_progress(index=0))
    show(_progress(index=1, kind="completed", detail="done"))

    assert flushes["n"] == 2, "output was buffered rather than shown as it happened"
    assert "read the page" in stream.getvalue()
    assert "$0.0042" in stream.getvalue()


# ── through a real run ──────────────────────────────────────────────────────


class _Registry:
    def get(self, provider_id):
        if provider_id != "trusted":
            return None
        model = SimpleNamespace(id="planner", cost_per_1m_input_usd=2.0,
                                cost_per_1m_output_usd=8.0)
        return SimpleNamespace(model=lambda model_id="": model)


class _Broker:
    def __init__(self, answers, *, before_each=None):
        self.answers = list(answers)
        self.registry = _Registry()
        self.before_each = before_each

    def plan(self, request, settings, *, provider_id=""):
        return [SimpleNamespace(id="trusted", model_id="planner", tier=TrustTier.A, cost=1.0)], []

    def call(self, request, settings, *, system_prompt, provider_id="", expect_json=False):
        if self.before_each:
            self.before_each()
        if not self.answers:
            raise AssertionError("the run asked for more decisions than the test scripted")
        return SimpleNamespace(
            text=self.answers.pop(0), provider_id="trusted", provider_name="Trusted",
            model_id="planner", tier="A", policy="full",
            data_class=request.data_class.value, duration_ms=7,
            payload_fields=["instructions"], attempts=[], rejected=[], log_id="e1",
        )


class _Page:
    def __init__(self):
        self.url = "https://acme.test/about"

    async def snapshot(self):
        return Snapshot(url=self.url, title="Acme",
                        nodes=[Node(handle=1, role="button", name="More", backend_id=1)])

    async def read(self, *, limit=20_000):
        return ActionResult(action="read", ok=True, url=self.url, detail="read the page",
                            text="Company: Acme Ltd")

    async def click(self, handle, *, confirmed=False):
        return ActionResult(action="click", ok=True, url=self.url, detail="clicked More")

    async def screenshot(self):
        return ActionResult(action="screenshot", ok=True, url=self.url, detail="shot",
                            screenshot=b"\x89PNG\r\n\x1a\nx")


def _act(action, **args):
    return json.dumps({"state": "act", "action": action, "args": args, "reason": "step"})


def _done():
    return json.dumps({"state": "done", "reason": "finished", "result": "ok"})


def _run(tmp_path, answers, *, on_progress=None, before_each=None):
    trace = Trace.open(tmp_path / "traces")
    agent = AgentRun(
        broker=_Broker(answers, before_each=before_each),
        settings=WorkspaceEgressSettings(workspace_id="w",
                                         enabled_models={"trusted": ("planner",)}),
        page=_Page(), trace=trace, planner_provider_id="trusted",
    )
    outcome = asyncio.run(agent.run("find the address", step_budget=8,
                                    on_progress=on_progress))
    return outcome, trace


def test_a_watcher_sees_the_run_step_by_step(tmp_path):
    seen: list[Progress] = []
    outcome, trace = _run(tmp_path, [_act("read"), _act("click", handle=1), _done()],
                          on_progress=seen.append)

    assert outcome.status == "completed"
    assert [update.kind for update in seen] == [step.kind for step in trace.read()]
    assert any(update.action == "read" for update in seen)
    assert any(update.action == "click" for update in seen)


def test_a_read_answered_from_the_memo_still_reports_its_verb(tmp_path):
    """`S-11.02.04` answers a second read of a page the run has already read
    from its memo, without asking the page again. That is still an action step,
    and an action step a watcher cannot name is a hole in this criterion."""
    seen: list[Progress] = []
    _run(tmp_path, [_act("read"), _act("read"), _done()], on_progress=seen.append)

    actions = [update for update in seen if update.kind == "action"]
    assert [update.action for update in actions] == ["read", "read"]
    assert "reused the capture" in actions[1].detail, "the memo was not the one served"


def test_updates_arrive_during_the_run_not_in_a_batch_at_the_end(tmp_path):
    """The whole point. A run reported only on completion is `S-11.04.01`, which
    already exists."""
    seen: list[int] = []
    counts: list[int] = []

    def watch(update):
        seen.append(update.index)

    def before_each_decision():
        # How much had been reported by the time each decision was made?
        counts.append(len(seen))

    _run(tmp_path, [_act("read"), _act("click", handle=1), _done()],
         on_progress=watch, before_each=before_each_decision)

    assert counts[0] < counts[1] < counts[2], (
        f"nothing was reported between decisions: {counts}"
    )


def test_the_running_cost_only_goes_up(tmp_path):
    seen: list[Progress] = []
    _run(tmp_path, [_act("read"), _done()], on_progress=seen.append)
    costs = [update.cost_usd for update in seen]
    assert costs == sorted(costs)
    assert costs[-1] > 0, "a run that called a model reported no cost"


def test_a_watcher_that_throws_does_not_end_the_run(tmp_path):
    def explode(_update):
        raise RuntimeError("the terminal went away")

    outcome, _ = _run(tmp_path, [_act("read"), _done()], on_progress=explode)
    assert outcome.status == "completed"


def test_the_watcher_does_not_outlive_the_run_it_watched(tmp_path):
    """Attached for the length of one run and put back afterwards."""
    trace = Trace.open(tmp_path / "traces")
    agent = AgentRun(
        broker=_Broker([_done()]),
        settings=WorkspaceEgressSettings(workspace_id="w",
                                         enabled_models={"trusted": ("planner",)}),
        page=_Page(), trace=trace, planner_provider_id="trusted",
    )
    asyncio.run(agent.run("x", step_budget=4, on_progress=lambda _u: None))
    assert trace.listener is None, "the watcher was left attached after the run"


def test_a_run_with_nobody_watching_behaves_exactly_as_before(tmp_path):
    outcome, trace = _run(tmp_path, [_act("read"), _done()])
    assert outcome.status == "completed"
    assert trace.listener is None
