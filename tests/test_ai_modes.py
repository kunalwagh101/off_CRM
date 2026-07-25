"""Run modes: simple, compare, orchestrated.

The safety property under test throughout: a mode changes *how many* models run
and *who decides*, never *what a model is allowed to see*.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from offsetx_apollo_builder.ai import (
    DataClass,
    DataPolicy,
    EgressBroker,
    EgressLog,
    EgressRequest,
    ModeRunner,
    NoPermittedProvider,
    PersonPublic,
    PolicyViolation,
    ProviderRegistry,
    QuotaTracker,
    RunMode,
    TrustTier,
    WorkspaceEgressSettings,
)

REPO_ROOT = Path(__file__).resolve().parents[1]

PERSON = PersonPublic(
    full_name="Ana Silva",
    first_name="Ana",
    title="Head of Trade",
    company="Acme GmbH",
    category="importer",
    public_hook="spoke at the EU trade summit",
)


class Sink(dict):
    """Records every call, not just the last one per provider.

    A provider can legitimately be called twice in one run — Mistral often
    writes the plan and then also does a step — so keeping only the latest
    payload per provider would test the wrong call.
    """

    def __init__(self) -> None:
        super().__init__()
        self.calls: list[tuple[str, dict]] = []

    def record(self, provider_id: str, payload: dict) -> None:
        self.calls.append((provider_id, payload))
        self[provider_id] = payload

    def first_for(self, provider_id: str) -> dict:
        for called_id, payload in self.calls:
            if called_id == provider_id:
                return payload
        raise AssertionError(f"{provider_id} was never called")


class RecordingProvider:
    """Stands in for a real provider and remembers what it was sent."""

    def __init__(self, sink: Sink, name: str, reply: str = "answer") -> None:
        self.sink = sink
        self.name = name
        self.reply = reply

    def generate(self, *, system_prompt: str, user_prompt: str) -> str:
        self.sink.record(self.name, json.loads(user_prompt))
        return self.reply


@pytest.fixture()
def registry() -> ProviderRegistry:
    return ProviderRegistry(REPO_ROOT / "config" / "providers.yaml")


@pytest.fixture()
def harness(registry, tmp_path):
    """Broker with every provider stubbed, plus the payloads each one saw."""
    sink = Sink()
    replies: dict = {}
    log = EgressLog(tmp_path / "egress.sqlite3")
    broker = EgressBroker(
        registry=registry,
        credential_resolver=lambda provider_id: "k",
        quota=QuotaTracker(tmp_path),
        logger=log.record,
    )

    def instantiate(candidate):
        return RecordingProvider(sink, candidate.id, replies.get(candidate.id, f"{candidate.id} says hi"))

    broker._instantiate = instantiate  # type: ignore[method-assign]
    return broker, sink, replies, log


def _settings(**kwargs) -> WorkspaceEgressSettings:
    defaults = {
        "workspace_id": "local",
        "owner_domains": ("offsetx.example",),
        "positioning_line": "We help exporters cut customs cost.",
    }
    defaults.update(kwargs)
    return WorkspaceEgressSettings(**defaults)


# ── compare mode ────────────────────────────────────────────────────────────


def test_compare_runs_every_permitted_model_at_once(harness):
    broker, sink, _, _ = harness
    runner = ModeRunner(broker)
    request = EgressRequest(
        task_type="draft_email",
        data_class=DataClass.PERSON_PUBLIC,
        person=PERSON,
        instructions="Write a first-contact email.",
    )
    result = runner.run_compare(
        request,
        _settings(enabled_provider_ids=("mistral", "groq", "deepseek")),
        system_prompt="write",
    )
    assert result.mode == RunMode.COMPARE.value
    assert {branch.provider_id for branch in result.branches} == {"mistral", "groq", "deepseek"}
    assert all(branch.ok for branch in result.branches)
    # Every branch was actually called.
    assert set(sink.keys()) == {"mistral", "groq", "deepseek"}


def test_compare_gives_each_model_only_what_its_own_tier_allows(harness):
    """The point of compare mode: you get a restricted model's answer without
    giving it more than it should have."""
    broker, sink, _, _ = harness
    runner = ModeRunner(broker)
    request = EgressRequest(
        task_type="draft_email",
        data_class=DataClass.PERSON_PUBLIC,
        person=PERSON,
        instructions="Write a first-contact email.",
        template_text="Hi {{first_name}}, our customs work ...",
    )
    runner.run_compare(
        request,
        _settings(enabled_provider_ids=("mistral", "deepseek")),
        system_prompt="write",
    )

    # Mistral is tier A at `standard`: it sees the template.
    assert "template" in sink["mistral"]
    # DeepSeek is tier C, clamped to `minimal`: no template, but it still gets
    # the person's public identity so it can personalise.
    assert "template" not in sink["deepseek"]
    assert sink["deepseek"]["recipient"]["full_name"] == "Ana Silva"
    assert sink["deepseek"]["recipient"]["company"] == "Acme GmbH"


def test_compare_still_excludes_a_provider_that_may_not_hold_the_data(harness):
    broker, sink, _, _ = harness
    runner = ModeRunner(broker)
    request = EgressRequest(
        task_type="draft_email",
        data_class=DataClass.CAMPAIGN,
        person=PERSON,
        template_text="Hi there",
        instructions="Improve this template.",
    )
    result = runner.run_compare(
        request,
        _settings(enabled_provider_ids=("mistral", "deepseek", "openrouter")),
        system_prompt="write",
    )
    assert {branch.provider_id for branch in result.branches} == {"mistral"}
    assert "deepseek" not in sink
    assert "openrouter" not in sink
    reasons = {item["provider_id"]: item["reason"] for item in result.excluded}
    assert reasons["deepseek"] == "tier_forbids_data_class"
    assert reasons["openrouter"] == "tier_forbids_data_class"


def test_compare_warns_when_answers_came_from_different_trust_levels(harness):
    broker, _, _, _ = harness
    result = ModeRunner(broker).run_compare(
        EgressRequest(
            task_type="t", data_class=DataClass.PERSON_PUBLIC, person=PERSON, instructions="go"
        ),
        _settings(enabled_provider_ids=("mistral", "deepseek")),
        system_prompt="w",
    )
    assert any("different trust levels" in note for note in result.notes)


def test_compare_survives_one_model_failing(harness):
    broker, sink, _, _ = harness
    original = broker._instantiate

    def flaky(candidate):
        if candidate.id == "groq":
            raise RuntimeError("provider is down")
        return original(candidate)

    broker._instantiate = flaky  # type: ignore[method-assign]
    result = ModeRunner(broker).run_compare(
        EgressRequest(task_type="t", data_class=DataClass.PUBLIC, instructions="go"),
        _settings(enabled_provider_ids=("mistral", "groq")),
        system_prompt="w",
    )
    by_id = {branch.provider_id: branch for branch in result.branches}
    assert by_id["mistral"].ok
    assert not by_id["groq"].ok
    assert by_id["groq"].error


def test_compare_with_nothing_connected_explains_what_to_do(harness):
    broker, _, _, _ = harness
    with pytest.raises(NoPermittedProvider) as excinfo:
        ModeRunner(broker).run_compare(
            EgressRequest(task_type="t", data_class=DataClass.PUBLIC, instructions="go"),
            _settings(enabled_provider_ids=()),
            system_prompt="w",
        )
    assert "Connectors" in str(excinfo.value)


def test_compare_is_capped_so_a_question_cannot_burn_every_quota(harness):
    broker, sink, _, _ = harness
    everything = tuple(entry.id for entry in broker.registry.all())
    result = ModeRunner(broker).run_compare(
        EgressRequest(task_type="t", data_class=DataClass.PUBLIC, instructions="go"),
        _settings(enabled_provider_ids=everything),
        system_prompt="w",
        max_branches=3,
    )
    assert len(result.branches) == 3


# ── orchestrated mode ───────────────────────────────────────────────────────

PLAN = json.dumps(
    {
        "steps": [
            {"title": "Research", "instructions": "Summarise the sector.", "needs": "public", "tags": ["reasoning"]},
            {"title": "Draft", "instructions": "Write the email.", "needs": "person_public", "tags": ["writing"]},
        ]
    }
)


def test_orchestrated_run_plans_then_dispatches_each_step(harness):
    broker, sink, replies, _ = harness
    replies["mistral"] = PLAN
    result = ModeRunner(broker).run_orchestrated(
        EgressRequest(
            task_type="campaign",
            data_class=DataClass.PERSON_PUBLIC,
            person=PERSON,
            instructions="Build a first-contact campaign for EU importers.",
        ),
        _settings(enabled_provider_ids=("mistral", "groq", "deepseek")),
        system_prompt="do the step",
    )
    assert result.planner_provider_id == "mistral"
    assert result.planner_tier == "A"
    assert [step.title for step in result.steps] == ["Research", "Draft"]
    assert all(step.assigned_provider_id for step in result.steps)


def test_a_restricted_tier_model_can_never_be_the_planner(harness):
    """Deciding who does what means seeing the whole job. Tier C models may do
    steps, never lead."""
    broker, _, _, _ = harness
    with pytest.raises(PolicyViolation) as excinfo:
        ModeRunner(broker).run_orchestrated(
            EgressRequest(task_type="t", data_class=DataClass.PUBLIC, instructions="go"),
            _settings(enabled_provider_ids=("mistral", "deepseek")),
            system_prompt="w",
            planner_provider_id="deepseek",
        )
    assert "cannot lead a plan" in str(excinfo.value)


def test_orchestration_refuses_when_only_restricted_models_are_connected(harness):
    broker, _, _, _ = harness
    with pytest.raises(NoPermittedProvider) as excinfo:
        ModeRunner(broker).run_orchestrated(
            EgressRequest(task_type="t", data_class=DataClass.PUBLIC, instructions="go"),
            _settings(enabled_provider_ids=("deepseek", "moonshot")),
            system_prompt="w",
        )
    message = str(excinfo.value)
    assert "Highest or Default trust" in message
    assert "One model" in message


def test_the_planner_is_told_worker_names_but_never_the_data(harness):
    """The plan brief describes shape, not content."""
    broker, sink, replies, _ = harness
    replies["mistral"] = PLAN
    ModeRunner(broker).run_orchestrated(
        EgressRequest(
            task_type="campaign",
            data_class=DataClass.PERSON_PUBLIC,
            person=PERSON,
            instructions="Build a campaign.",
            template_text="Hi {{first_name}}, secret internal template",
        ),
        _settings(enabled_provider_ids=("mistral", "deepseek")),
        system_prompt="w",
    )
    # The planning call is the first one Mistral received.
    brief = json.dumps(sink.first_for("mistral"))
    assert "DeepSeek" in brief  # worker names, so it can allocate
    assert "Ana Silva" not in brief  # never the person
    assert "secret internal template" not in brief  # never the template


def test_a_plan_cannot_widen_its_own_reach(harness):
    """Model output is untrusted input. A step asking for more than the caller
    offered is clamped down, not honoured."""
    broker, sink, replies, _ = harness
    replies["mistral"] = json.dumps(
        {
            "steps": [
                {"title": "Sneaky", "instructions": "Read the mailbox.", "needs": "mailbox"},
                {"title": "Also sneaky", "instructions": "Dump the CRM.", "needs": "internal"},
                {"title": "Greedy", "instructions": "Use the template.", "needs": "campaign"},
            ]
        }
    )
    result = ModeRunner(broker).run_orchestrated(
        EgressRequest(
            task_type="t",
            data_class=DataClass.PERSON_PUBLIC,  # ceiling the plan cannot exceed
            person=PERSON,
            instructions="go",
        ),
        _settings(enabled_provider_ids=("mistral",)),
        system_prompt="w",
    )
    classes = {step.data_class for step in result.steps}
    assert DataClass.MAILBOX not in classes
    assert DataClass.INTERNAL not in classes
    assert DataClass.CAMPAIGN not in classes
    assert classes <= {DataClass.PUBLIC, DataClass.PERSON_PUBLIC}


def test_a_public_request_keeps_every_step_public(harness):
    broker, _, replies, _ = harness
    replies["mistral"] = PLAN
    result = ModeRunner(broker).run_orchestrated(
        EgressRequest(task_type="t", data_class=DataClass.PUBLIC, instructions="go"),
        _settings(enabled_provider_ids=("mistral", "deepseek")),
        system_prompt="w",
    )
    assert all(step.data_class is DataClass.PUBLIC for step in result.steps)


def test_an_unusable_plan_falls_back_to_a_single_step(harness):
    broker, _, replies, _ = harness
    replies["mistral"] = "I would rather write you a poem about trade."
    result = ModeRunner(broker).run_orchestrated(
        EgressRequest(task_type="t", data_class=DataClass.PUBLIC, instructions="Do the job"),
        _settings(enabled_provider_ids=("mistral",)),
        system_prompt="w",
    )
    assert len(result.steps) == 1
    assert any("single step" in note for note in result.notes)


def test_plan_length_is_capped(harness):
    broker, _, replies, _ = harness
    replies["mistral"] = json.dumps(
        {"steps": [{"title": f"S{i}", "instructions": f"do {i}", "needs": "public"} for i in range(20)]}
    )
    result = ModeRunner(broker).run_orchestrated(
        EgressRequest(task_type="t", data_class=DataClass.PUBLIC, instructions="go"),
        _settings(enabled_provider_ids=("mistral",)),
        system_prompt="w",
    )
    assert len(result.steps) <= 6


# ── every mode is logged the same way ───────────────────────────────────────


def test_all_modes_write_to_the_egress_log(harness):
    broker, _, replies, log = harness
    runner = ModeRunner(broker)
    replies["mistral"] = PLAN
    settings = _settings(enabled_provider_ids=("mistral", "groq"))

    runner.run_simple(
        EgressRequest(task_type="t1", data_class=DataClass.PUBLIC, instructions="a"),
        settings,
        system_prompt="w",
    )
    runner.run_compare(
        EgressRequest(task_type="t2", data_class=DataClass.PUBLIC, instructions="b"),
        settings,
        system_prompt="w",
    )
    _, total = log.list()
    # 1 simple + 2 compare branches, at minimum.
    assert total >= 3
    for row, _ in [(row, None) for row in log.list(limit=50)[0]]:
        assert row["provider_id"]
        assert row["tier"]
