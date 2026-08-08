"""The verify loop: cheap generate, deterministic check, repair, strong review.

The properties that matter:

* the loop actually repairs — a bad first draft becomes a good one;
* **the best attempt wins, not the last** — repair can make things worse;
* the deterministic checks are the gate, and a model review only advises;
* the round cap is real, so a non-converging task cannot burn the budget;
* nothing widens what a model receives, including on repair rounds.
"""
from __future__ import annotations

import ast
import json
from pathlib import Path

import pytest

from offsetx_apollo_builder.ai import (
    Attempt,
    DataClass,
    DataPolicy,
    EgressBroker,
    EgressLog,
    EgressRequest,
    ModeRunner,
    PersonPublic,
    ProviderRegistry,
    QuotaTracker,
    RunMode,
    VerifiedResult,
    VerifyLoop,
    WorkspaceEgressSettings,
    checks_for,
)
from offsetx_apollo_builder.ai.verify import (
    DEFAULT_MAX_ROUNDS,
    HARD_ROUND_CAP,
    build_repair_instructions,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
SUITE_PATH = REPO_ROOT / "config" / "evals.yaml"
PACKAGE_ROOT = REPO_ROOT / "offsetx_apollo_builder"

EMAIL_CHECKS = checks_for("email_first_contact", SUITE_PATH)

GOOD_EMAIL = (
    "Subject: The new EU customs codes\n\n"
    "You spoke about the new customs rules at the trade summit last month. "
    "The tariff codes landing next quarter reclassify a lot of ambient stock, "
    "and most importers we work with are finding it out late. "
    "We cut that cost for exporters in your position. "
    "Would fifteen minutes next week be useful to you?"
)
BAD_EMAIL = "Certainly! Here is your email:\n\nHi {{first_name}}, reach me at bob@acme.com."

PERSON = PersonPublic(
    full_name="Ana Silva",
    first_name="Ana",
    title="Head of Trade",
    company="Meridian Foods",
    category="importer",
    public_hook="spoke at the EU trade summit",
)


class SequenceProvider:
    """Returns a scripted sequence, so a repair round can be made to succeed."""

    def __init__(self, replies: list[str], seen: list[str]) -> None:
        self.replies = replies
        self.seen = seen
        self.index = 0

    def generate(self, *, system_prompt: str, user_prompt: str) -> str:
        self.seen.append(user_prompt)
        reply = self.replies[min(self.index, len(self.replies) - 1)]
        self.index += 1
        return reply


@pytest.fixture()
def registry() -> ProviderRegistry:
    return ProviderRegistry(REPO_ROOT / "config" / "providers.yaml")


@pytest.fixture()
def harness(registry, tmp_path):
    """Broker whose every provider replays a scripted list, and the payloads seen."""
    log = EgressLog(tmp_path / "egress.sqlite3")
    broker = EgressBroker(
        registry=registry,
        credential_resolver=lambda provider_id: "k",
        quota=QuotaTracker(tmp_path),
        logger=log.record,
    )
    script: dict[str, list[str]] = {}
    seen: list[str] = []
    providers: dict[str, SequenceProvider] = {}

    def instantiate(candidate):
        if candidate.id not in providers:
            providers[candidate.id] = SequenceProvider(
                script.get(candidate.id, [GOOD_EMAIL]), seen
            )
        return providers[candidate.id]

    broker._instantiate = instantiate  # type: ignore[method-assign]
    return broker, script, seen


def _settings(**kwargs) -> WorkspaceEgressSettings:
    defaults = {
        "workspace_id": "local",
        "owner_domains": ("offsetx.example",),
        "positioning_line": "We help exporters cut customs cost.",
    }
    defaults.update(kwargs)
    return WorkspaceEgressSettings(**defaults)


def _request(**kwargs) -> EgressRequest:
    defaults = {
        "task_type": "draft_email",
        "data_class": DataClass.PERSON_PUBLIC,
        "person": PERSON,
        "instructions": "Write a first-contact email opening on the public hook.",
        "positioning_line": "We help exporters cut customs cost.",
    }
    defaults.update(kwargs)
    return EgressRequest(**defaults)


# ── the loop repairs ────────────────────────────────────────────────────────


def test_a_bad_first_draft_is_repaired_into_a_good_one(harness):
    broker, script, _ = harness
    script["mistral"] = [BAD_EMAIL, GOOD_EMAIL]

    result = VerifyLoop(broker).run(
        _request(),
        _settings(enabled_provider_ids=("mistral",)),
        system_prompt="write",
        checks=EMAIL_CHECKS,
        review=False,
    )
    assert result.rounds == 2
    assert result.passed is True
    assert result.text == GOOD_EMAIL
    assert result.attempts[0].passed is False
    assert result.attempts[0].score < result.attempts[1].score


def test_a_good_first_draft_stops_immediately_and_costs_one_call(harness):
    """No repair round when nothing is wrong. The loop must not spend money
    proving something already passed."""
    broker, script, _ = harness
    script["mistral"] = [GOOD_EMAIL, GOOD_EMAIL, GOOD_EMAIL]

    result = VerifyLoop(broker).run(
        _request(),
        _settings(enabled_provider_ids=("mistral",)),
        system_prompt="write",
        checks=EMAIL_CHECKS,
        review=False,
    )
    assert result.rounds == 1
    assert result.calls == 1
    assert result.passed is True


def test_the_repair_prompt_names_the_specific_failures(harness):
    """A repair round that says only "try again" wastes the round."""
    broker, script, seen = harness
    script["mistral"] = [BAD_EMAIL, GOOD_EMAIL]

    VerifyLoop(broker).run(
        _request(),
        _settings(enabled_provider_ids=("mistral",)),
        system_prompt="write",
        checks=EMAIL_CHECKS,
        review=False,
    )
    repair_payload = json.loads(seen[1])
    instructions = repair_payload["instructions"]
    assert "previous attempt was rejected" in instructions
    assert "no_unfilled_placeholder" in instructions
    assert "no_assistant_preamble" in instructions


# ── the best attempt wins, not the last ─────────────────────────────────────


def test_a_repair_that_makes_things_worse_does_not_win(harness):
    """The core correctness property. A model told to fix one thing will
    cheerfully break another, and returning the final attempt would ship it."""
    broker, script, _ = harness
    nearly_good = GOOD_EMAIL.replace("Subject: The new EU customs codes\n\n", "")
    script["mistral"] = [nearly_good, BAD_EMAIL, BAD_EMAIL]

    result = VerifyLoop(broker).run(
        _request(),
        _settings(enabled_provider_ids=("mistral",)),
        system_prompt="write",
        checks=EMAIL_CHECKS,
        max_rounds=3,
        review=False,
    )
    assert result.rounds == 3
    assert result.passed is False, "none of the drafts passed everything"
    # The first draft only missed the subject line; the later ones are far worse.
    assert result.text == nearly_good
    assert result.best.round == 1
    assert any("was the best of" in note for note in result.notes)


def test_a_tie_prefers_the_earlier_round(harness):
    """A later round that only matched the earlier one cost money for nothing."""
    broker, script, _ = harness
    no_subject = GOOD_EMAIL.replace("Subject: The new EU customs codes\n\n", "")
    script["mistral"] = [no_subject, no_subject]

    result = VerifyLoop(broker).run(
        _request(),
        _settings(enabled_provider_ids=("mistral",)),
        system_prompt="write",
        checks=EMAIL_CHECKS,
        max_rounds=2,
        review=False,
    )
    assert result.best.round == 1


# ── budget ──────────────────────────────────────────────────────────────────


def test_a_never_passing_task_stops_at_the_round_cap(harness):
    broker, script, _ = harness
    script["mistral"] = [BAD_EMAIL] * 20

    result = VerifyLoop(broker).run(
        _request(),
        _settings(enabled_provider_ids=("mistral",)),
        system_prompt="write",
        checks=EMAIL_CHECKS,
        max_rounds=3,
        review=False,
    )
    assert result.rounds == 3
    assert result.calls == 3
    assert result.passed is False
    assert result.remaining_failures


def test_a_caller_cannot_ask_for_more_rounds_than_the_hard_cap(harness):
    """A loop that can run twenty times is a way to spend twenty times the
    money on a task that is not converging."""
    broker, script, _ = harness
    script["mistral"] = [BAD_EMAIL] * 50

    result = VerifyLoop(broker).run(
        _request(),
        _settings(enabled_provider_ids=("mistral",)),
        system_prompt="write",
        checks=EMAIL_CHECKS,
        max_rounds=99,
        review=False,
    )
    assert result.rounds == HARD_ROUND_CAP


def test_zero_or_negative_rounds_still_runs_once(harness):
    broker, script, _ = harness
    script["mistral"] = [GOOD_EMAIL]
    result = VerifyLoop(broker).run(
        _request(),
        _settings(enabled_provider_ids=("mistral",)),
        system_prompt="write",
        checks=EMAIL_CHECKS,
        max_rounds=0,
        review=False,
    )
    assert result.rounds == 1


def test_a_refusal_stops_the_loop_rather_than_retrying_it(harness):
    """Retrying a policy refusal produces the identical refusal. Spending three
    rounds to learn that twice more is pure waste."""
    broker, _, _ = harness
    result = VerifyLoop(broker).run(
        _request(data_class=DataClass.CAMPAIGN),
        _settings(enabled_provider_ids=("deepseek",)),  # tier C cannot hold campaign
        system_prompt="write",
        checks=EMAIL_CHECKS,
        max_rounds=3,
        review=False,
    )
    assert result.rounds == 1
    assert result.calls == 1
    assert result.passed is False
    assert result.attempts[0].error
    assert any("Stopped early" in note for note in result.notes)


# ── checks are the gate; the model only advises ────────────────────────────


def test_with_no_checks_nothing_is_verified_and_it_says_so(harness):
    """Silently returning "passed" with no checks would be a lie."""
    broker, script, _ = harness
    script["mistral"] = [BAD_EMAIL]
    result = VerifyLoop(broker).run(
        _request(),
        _settings(enabled_provider_ids=("mistral",)),
        system_prompt="write",
        checks=(),
        review=False,
    )
    assert result.passed is False
    assert result.rounds == 1
    assert any("nothing was verified" in note for note in result.notes)


def test_a_reviewer_saying_NO_NOTES_does_not_trigger_a_rewrite(harness):
    broker, script, _ = harness
    script["mistral"] = [GOOD_EMAIL]
    script["local"] = ["NO NOTES"]

    result = VerifyLoop(broker).run(
        _request(),
        _settings(enabled_provider_ids=("mistral", "local")),
        system_prompt="write",
        checks=EMAIL_CHECKS,
        provider_id="mistral",  # pin the writer so `local` is left to review
        review=True,
    )
    assert result.rounds == 1, "a clean review must not cost a repair round"
    assert result.review_notes == "NO NOTES"
    assert result.reviewer == "local", "a second opinion beats self-review"


def test_a_model_review_cannot_turn_a_failing_draft_into_a_passing_one(harness):
    """The reviewer advises. Only the deterministic checks decide."""
    broker, script, _ = harness
    script["mistral"] = [BAD_EMAIL, BAD_EMAIL, BAD_EMAIL]
    script["local"] = ["This draft is excellent, ship it."]

    result = VerifyLoop(broker).run(
        _request(),
        _settings(enabled_provider_ids=("mistral", "local")),
        system_prompt="write",
        checks=EMAIL_CHECKS,
        max_rounds=2,
        provider_id="mistral",
        review=True,
    )
    assert result.passed is False, "a glowing review must not override the rules"
    assert result.remaining_failures


# ── the loop does not widen what a model receives ──────────────────────────


def test_a_repair_round_to_a_restricted_model_stays_pseudonymous(harness):
    """The repair prompt carries the previous draft. That must not become a
    route for identity to reach a tier C provider."""
    broker, script, seen = harness
    leaky = "Certainly! Hi Ana Silva at Meridian Foods, reach me at a@b.com."
    script["deepseek"] = [leaky, GOOD_EMAIL]

    VerifyLoop(broker).run(
        _request(),
        _settings(enabled_provider_ids=("deepseek",)),
        system_prompt="write",
        checks=EMAIL_CHECKS,
        max_rounds=2,
        review=False,
    )
    repair = json.loads(seen[1])
    blob = json.dumps(repair)
    assert "Ana Silva" not in blob
    assert "Meridian Foods" not in blob
    assert "PERSON_1" in blob


def test_the_repair_payload_never_gains_the_template_at_a_lower_tier(harness):
    broker, script, seen = harness
    script["deepseek"] = [BAD_EMAIL, GOOD_EMAIL]

    VerifyLoop(broker).run(
        _request(template_text="Our margin is 40 percent.", campaign_notes="Series B."),
        _settings(enabled_provider_ids=("deepseek",)),
        system_prompt="write",
        checks=EMAIL_CHECKS,
        max_rounds=2,
        review=False,
    )
    for raw in seen:
        payload = json.loads(raw)
        assert "template" not in payload
        assert "campaign_notes" not in payload


def test_build_repair_instructions_includes_reviewer_notes_when_present():
    attempt = Attempt(round=1, text="draft text", checks=[])
    with_notes = build_repair_instructions("do the thing", attempt, "- the ask is vague")
    assert "Reviewer notes:" in with_notes
    assert "- the ask is vague" in with_notes
    # "NO NOTES" is the reviewer's way of saying nothing, not a note.
    clean = build_repair_instructions("do the thing", attempt, "NO NOTES")
    assert "Reviewer notes:" not in clean


# ── as a run mode ───────────────────────────────────────────────────────────


def test_verified_is_a_run_mode_and_reports_its_rounds(harness):
    broker, script, _ = harness
    script["mistral"] = [BAD_EMAIL, GOOD_EMAIL]

    result = ModeRunner(broker).run_verified(
        _request(),
        _settings(enabled_provider_ids=("mistral",)),
        system_prompt="write",
        checks=EMAIL_CHECKS,
        review=False,
    )
    assert result.mode == RunMode.VERIFIED.value
    assert result.first_permitted_text == GOOD_EMAIL
    assert any("generation round" in note for note in result.notes)


def test_the_eval_harness_can_score_verified_mode(harness):
    """Closing the loop: the mode that enforces the checks can be measured by
    the harness that defines them."""
    from offsetx_apollo_builder.ai import EvalRunner, load_suites

    broker, script, _ = harness
    script["mistral"] = [BAD_EMAIL, GOOD_EMAIL, GOOD_EMAIL, GOOD_EMAIL, GOOD_EMAIL, GOOD_EMAIL]

    suite = load_suites(SUITE_PATH)["email_first_contact"]
    report = EvalRunner(broker).run_mode(
        suite,
        _settings(enabled_provider_ids=("mistral",)),
        mode="verified",
        runner=ModeRunner(broker),
    )
    assert report.subject == "verified"
    assert report.errors == 0
    assert report.score > 0


# ── structural ──────────────────────────────────────────────────────────────


def test_the_verify_module_reaches_a_model_only_through_the_broker():
    source = (PACKAGE_ROOT / "ai" / "verify.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module)
            imported.update(f"{node.module}.{alias.name}" for alias in node.names)
        elif isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
    banned = {"requests", "httpx", "urllib", "urllib.request", "socket", "openai"}
    assert not (imported & banned)
    assert not any("create_provider" in name for name in imported)


def test_the_default_round_count_is_low_on_purpose():
    """Rounds 1-2 capture most of the gain. A high default is a quiet way to
    triple everyone's bill."""
    assert DEFAULT_MAX_ROUNDS <= 3
    assert HARD_ROUND_CAP <= 5
