"""The eval harness and the champion/challenger gate.

Two properties under test throughout:

* **Scoring is deterministic.** Same output text, same score, every time. If
  that stops being true the whole harness is decoration.
* **The gate is conservative.** A challenger is promoted only when it is better
  on the mean, better case-by-case beyond chance, and affordable. Every other
  path keeps the champion.
"""
from __future__ import annotations

import ast
import json
import math
from pathlib import Path

import pytest

from offsetx_apollo_builder.ai import (
    CHECKS,
    DataClass,
    DataPolicy,
    EgressBroker,
    EgressLog,
    EvalReport,
    EvalRunner,
    ModeRunner,
    PersonPublic,
    ProviderRegistry,
    QuotaTracker,
    Scoreboard,
    TrustTier,
    WorkspaceEgressSettings,
    best_of,
    compare,
    load_suites,
    run_checks,
    sign_test_p_value,
    suite_summary,
)
from offsetx_apollo_builder.ai.evals import CaseResult

REPO_ROOT = Path(__file__).resolve().parents[1]
SUITE_PATH = REPO_ROOT / "config" / "evals.yaml"
PACKAGE_ROOT = REPO_ROOT / "offsetx_apollo_builder"


# ── fixtures ────────────────────────────────────────────────────────────────


@pytest.fixture()
def registry() -> ProviderRegistry:
    return ProviderRegistry(REPO_ROOT / "config" / "providers.yaml")


class ScriptedProvider:
    """Returns a fixed reply, so a score is a property of the checks alone."""

    def __init__(self, reply: str) -> None:
        self.reply = reply

    def generate(self, *, system_prompt: str, user_prompt: str) -> str:
        return self.reply


@pytest.fixture()
def harness(registry, tmp_path):
    log = EgressLog(tmp_path / "egress.sqlite3")
    broker = EgressBroker(
        registry=registry,
        credential_resolver=lambda provider_id: "k",
        quota=QuotaTracker(tmp_path),
        logger=log.record,
    )
    replies: dict[str, str] = {}

    def instantiate(candidate):
        return ScriptedProvider(replies.get(candidate.id, "Subject: Hi\n\nHello there."))

    broker._instantiate = instantiate  # type: ignore[method-assign]
    return broker, replies


def _settings(**kwargs) -> WorkspaceEgressSettings:
    defaults = {
        "workspace_id": "local",
        "owner_domains": ("offsetx.example",),
        "positioning_line": "We help exporters cut customs cost.",
    }
    defaults.update(kwargs)
    return WorkspaceEgressSettings(**defaults)


def _report(subject: str, scores: dict[str, float], *, kind: str = "model") -> EvalReport:
    return EvalReport(
        subject=subject,
        subject_kind=kind,
        suite_id="s1",
        results=[CaseResult(case_id=cid, score=sc) for cid, sc in scores.items()],
    )


# ── checks are deterministic and complete ──────────────────────────────────


GOOD_EMAIL = (
    "Subject: The new EU customs codes\n\n"
    "You spoke about the new customs rules at the trade summit last month. "
    "The tariff codes landing next quarter reclassify a lot of ambient stock, "
    "and most importers we work with are finding it out late. "
    "We cut that cost for exporters in your position. "
    "Would fifteen minutes next week be useful to you?"
)


def test_a_good_email_passes_every_default_check():
    suites = load_suites(SUITE_PATH)
    case = suites["email_first_contact"].cases[0]
    results = run_checks(GOOD_EMAIL, case.checks)
    failed = [item for item in results if not item.passed]
    assert not failed, f"unexpected failures: {[(f.name, f.detail) for f in failed]}"


@pytest.mark.parametrize(
    "text,failing_check",
    [
        ("Certainly! Here is the email:\n\nSubject: Hi\n\n" + "word " * 50,
         "no_assistant_preamble"),
        ("Subject: Hi\n\nHello {{first_name}}, " + "word " * 50,
         "no_unfilled_placeholder"),
        ("Subject: Hi\n\nReach me at bob@example.com. " + "word " * 50,
         "invented_no_address"),
        ("Subject: Hi\n\nToo short.", "length_is_sane"),
        ("No subject at all here. " + "word " * 50, "has_subject_line"),
        ("Subject: Hi\n\nI hope this email finds you well. " + "word " * 50,
         "no_ai_tells"),
    ],
)
def test_each_default_check_catches_its_own_failure(text, failing_check):
    """One bad output per rule, so a rule that silently stops working is caught
    rather than quietly passing everything."""
    suites = load_suites(SUITE_PATH)
    case = suites["email_first_contact"].cases[0]
    results = {item.name: item.passed for item in run_checks(text, case.checks)}
    assert results[failing_check] is False, f"{failing_check} did not fire"


def test_scoring_is_deterministic():
    suites = load_suites(SUITE_PATH)
    case = suites["email_first_contact"].cases[0]
    first = [(i.name, i.passed) for i in run_checks(GOOD_EMAIL, case.checks)]
    for _ in range(5):
        assert [(i.name, i.passed) for i in run_checks(GOOD_EMAIL, case.checks)] == first


def test_an_unknown_check_kind_fails_rather_than_passing():
    """A typo in a check name must not inflate every score that uses it."""
    results = run_checks("anything", [{"kind": "does_not_exist", "name": "typo"}])
    assert results[0].passed is False
    assert "Unknown check kind" in results[0].detail


def test_a_malformed_regex_fails_the_check_instead_of_crashing_the_suite():
    results = run_checks("x", [{"kind": "requires_pattern", "pattern": "([unclosed"}])
    assert results[0].passed is False
    assert "bad pattern" in results[0].detail


def test_valid_python_check_accepts_a_fenced_block_and_rejects_prose():
    ok = run_checks("```python\ndef f():\n    return 1\n```", [{"kind": "valid_python"}])
    assert ok[0].passed is True
    bad = run_checks("Here is how you would write it, in words.", [{"kind": "valid_python"}])
    assert bad[0].passed is False


def test_json_checks_tolerate_a_code_fence():
    text = '```json\n{"a": 1, "b": null}\n```'
    results = run_checks(
        text, [{"kind": "valid_json"}, {"kind": "json_has_keys", "keys": ["a", "b"]}]
    )
    assert all(item.passed for item in results)


def test_every_check_kind_in_the_shipped_suite_is_registered():
    """The config and the code cannot drift apart silently."""
    suites = load_suites(SUITE_PATH)
    used = {
        str(check.get("kind"))
        for suite in suites.values()
        for case in suite.cases
        for check in case.checks
    }
    unknown = used - set(CHECKS)
    assert not unknown, f"config uses unregistered check kinds: {unknown}"


# ── the suite file itself ───────────────────────────────────────────────────


def test_the_shipped_suite_loads_and_every_case_has_checks():
    suites = load_suites(SUITE_PATH)
    assert suites
    for suite in suites.values():
        for case in suite.cases:
            assert case.checks, f"{suite.id}/{case.id} has no checks and would score 1.0 for free"


def test_a_missing_suite_file_says_so_rather_than_returning_nothing():
    with pytest.raises(Exception) as excinfo:
        load_suites(Path("/nonexistent/evals.yaml"))
    assert "No eval suite file" in str(excinfo.value)


# ── the runner goes through the broker like any other caller ───────────────


def test_running_a_case_uses_the_broker_and_respects_tier_rules(harness):
    """An eval is not a privileged caller. A person_public case cannot reach a
    provider that may not hold that class."""
    broker, _ = harness
    runner = EvalRunner(broker)
    suites = load_suites(SUITE_PATH)
    suite = suites["email_first_contact"]

    # openrouter is an aggregator, tier D: it receives nothing.
    report = runner.run_model(
        suite, _settings(enabled_provider_ids=("openrouter",)), provider_id="openrouter"
    )
    assert report.score == 0.0
    assert report.errors == len(suite.cases)
    assert all("openrouter" in r.error.lower() or r.error for r in report.results)


def test_a_refusal_scores_zero_instead_of_crashing_the_suite(harness):
    broker, _ = harness
    runner = EvalRunner(broker)
    suites = load_suites(SUITE_PATH)
    report = runner.run_model(
        suites["email_first_contact"],
        _settings(enabled_provider_ids=("deepseek",)),
        provider_id="deepseek",
    )
    # DeepSeek is tier C and may hold person_public, so this should actually run.
    assert len(report.results) == 3
    assert report.errors == 0


def test_the_score_reflects_the_output_quality(harness):
    broker, replies = harness
    runner = EvalRunner(broker)
    suites = load_suites(SUITE_PATH)
    suite = suites["email_first_contact"]

    replies["mistral"] = GOOD_EMAIL
    good = runner.run_model(
        suite, _settings(enabled_provider_ids=("mistral",)), provider_id="mistral"
    )

    replies["mistral"] = "Certainly! Here is your email:\n\nHi {{first_name}}!"
    bad = runner.run_model(
        suite, _settings(enabled_provider_ids=("mistral",)), provider_id="mistral"
    )

    assert good.score > bad.score
    assert good.score > 0.7
    assert bad.score < 0.5


def test_suite_summary_ranks_best_first():
    rows = suite_summary([
        _report("weak", {"a": 0.2}),
        _report("strong", {"a": 0.9}),
        _report("middle", {"a": 0.5}),
    ])
    assert [row["subject"] for row in rows] == ["strong", "middle", "weak"]


# ── the sign test ───────────────────────────────────────────────────────────


def test_sign_test_matches_hand_computed_binomial_values():
    # P(X >= 8 | n=10, p=0.5) = (C(10,8)+C(10,9)+C(10,10)) / 2^10 = 56/1024
    assert sign_test_p_value(8, 2) == pytest.approx(56 / 1024)
    # A clean sweep of 10.
    assert sign_test_p_value(10, 0) == pytest.approx(1 / 1024)
    # An even split is the least surprising result there is.
    assert sign_test_p_value(5, 5) > 0.5


def test_sign_test_reports_no_evidence_when_nothing_is_decided():
    """All ties must not look significant."""
    assert sign_test_p_value(0, 0) == 1.0


def test_ties_are_excluded_rather_than_counted_as_losses():
    """A case both sides score identically says nothing about which is better."""
    assert sign_test_p_value(6, 0) == sign_test_p_value(6, 0)
    assert sign_test_p_value(6, 0) < sign_test_p_value(6, 2)


# ── the champion/challenger gate ────────────────────────────────────────────


def _paired(champion_scores, challenger_scores):
    return _report("mistral", champion_scores), _report(
        "compare", challenger_scores, kind="mode"
    )


def test_a_clear_significant_win_is_promoted():
    champ, chall = _paired(
        {f"c{i}": 0.5 for i in range(12)},
        {f"c{i}": 0.9 for i in range(12)},
    )
    verdict = compare(champ, chall, cost_multiple=3.0)
    assert verdict.promoted is True
    assert verdict.wins == 12 and verdict.losses == 0
    assert verdict.p_value < 0.01
    assert "Promoted" in verdict.reason


def test_a_higher_mean_from_a_lucky_split_is_not_promoted():
    """Six wins to four losses is noise, however the means fall. This is the
    case a naive `>` comparison gets wrong."""
    champ_scores = {f"c{i}": 0.5 for i in range(10)}
    chall_scores = {f"c{i}": (0.9 if i < 6 else 0.45) for i in range(10)}
    champ, chall = _paired(champ_scores, chall_scores)
    verdict = compare(champ, chall, cost_multiple=3.0)
    assert verdict.challenger_score > verdict.champion_score
    assert verdict.wins == 6 and verdict.losses == 4
    assert verdict.promoted is False
    assert "luck" in verdict.reason


def test_a_lower_mean_is_never_promoted_however_many_cases_it_wins():
    """Winning many cases narrowly while losing a few catastrophically is not an
    improvement to the output the owner actually reads."""
    champ_scores = {f"c{i}": (0.5 if i < 8 else 1.0) for i in range(10)}
    chall_scores = {f"c{i}": (0.55 if i < 8 else 0.0) for i in range(10)}
    champ, chall = _paired(champ_scores, chall_scores)
    verdict = compare(champ, chall, cost_multiple=1.0)
    assert verdict.wins == 8 and verdict.losses == 2
    assert verdict.challenger_score < verdict.champion_score
    assert verdict.promoted is False
    assert "Not an improvement" in verdict.reason


def test_an_unaffordable_win_is_refused_with_the_cost_named():
    champ, chall = _paired(
        {f"c{i}": 0.5 for i in range(12)},
        {f"c{i}": 0.9 for i in range(12)},
    )
    verdict = compare(champ, chall, cost_multiple=9.0)
    assert verdict.promoted is False
    assert "9.0x" in verdict.reason
    assert "ceiling" in verdict.reason


def test_the_cost_ceiling_can_be_raised_deliberately():
    champ, chall = _paired(
        {f"c{i}": 0.5 for i in range(12)},
        {f"c{i}": 0.9 for i in range(12)},
    )
    assert compare(champ, chall, cost_multiple=9.0, max_cost_multiple=10.0).promoted


def test_comparing_runs_with_no_shared_cases_refuses_rather_than_guessing():
    champ = _report("mistral", {"a": 0.9})
    chall = _report("compare", {"b": 0.1}, kind="mode")
    verdict = compare(champ, chall)
    assert verdict.promoted is False
    assert "share no cases" in verdict.reason


def test_comparing_across_different_suites_raises():
    champ = _report("mistral", {"a": 0.5})
    chall = _report("compare", {"a": 0.9}, kind="mode")
    chall.suite_id = "a_different_suite"
    with pytest.raises(ValueError, match="across suites"):
        compare(champ, chall)


def test_best_of_picks_the_highest_score_and_breaks_ties_on_speed():
    slow = _report("slow", {"a": 0.8})
    slow.duration_ms = 9000
    fast = _report("fast", {"a": 0.8})
    fast.duration_ms = 100
    assert best_of([slow, fast]).subject == "fast"
    assert best_of([]) is None


# ── the scoreboard ──────────────────────────────────────────────────────────


def test_scoreboard_records_and_reads_back(tmp_path):
    board = Scoreboard(tmp_path / "evals.sqlite3")
    board.record(_report("mistral", {"a": 0.8, "b": 0.6}))
    history = board.history(suite_id="s1")
    assert len(history) == 1
    assert history[0]["subject"] == "mistral"
    assert history[0]["score"] == pytest.approx(0.7)


def test_leaderboard_shows_the_latest_score_per_subject(tmp_path):
    board = Scoreboard(tmp_path / "evals.sqlite3")
    board.record(_report("mistral", {"a": 0.4}))
    board.record(_report("deepseek", {"a": 0.9}))
    rows = board.leaderboard(suite_id="s1")
    assert [row["subject"] for row in rows] == ["deepseek", "mistral"]


def test_an_unmeasured_system_routes_to_one_model_not_an_ensemble(tmp_path):
    """The safe default. Nothing has been checked, so do the cheap thing."""
    board = Scoreboard(tmp_path / "evals.sqlite3")
    assert board.route_for(suite_id="never_run") == "simple"


def test_a_promoted_mode_changes_the_route(tmp_path):
    board = Scoreboard(tmp_path / "evals.sqlite3")
    board.set_champion(
        suite_id="s1", subject="compare", subject_kind="mode", score=0.9, reason="won"
    )
    assert board.route_for(suite_id="s1") == "compare"


def test_a_champion_that_is_a_single_model_leaves_the_route_on_simple(tmp_path):
    board = Scoreboard(tmp_path / "evals.sqlite3")
    board.set_champion(
        suite_id="s1", subject="mistral", subject_kind="model", score=0.9
    )
    assert board.route_for(suite_id="s1") == "simple"


def test_setting_a_champion_twice_replaces_rather_than_duplicates(tmp_path):
    board = Scoreboard(tmp_path / "evals.sqlite3")
    board.set_champion(suite_id="s1", subject="a", subject_kind="model", score=0.5)
    board.set_champion(suite_id="s1", subject="b", subject_kind="model", score=0.7)
    assert board.champion(suite_id="s1")["subject"] == "b"
    assert board.stats()["champions"] == 1


# ── structural safety, same technique as the egress wall ───────────────────


def test_no_model_can_reach_the_scoreboard_or_the_eval_store():
    """The numbers must be facts. A store a model can write to is a store that
    tells you what the model wants you to hear."""
    for module in ("scoreboard.py", "evals.py"):
        source = (PACKAGE_ROOT / "ai" / module).read_text(encoding="utf-8")
        tree = ast.parse(source)
        imported: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module)
                for alias in node.names:
                    imported.add(f"{node.module}.{alias.name}")
            elif isinstance(node, ast.Import):
                imported.update(alias.name for alias in node.names)
        banned = {"requests", "httpx", "urllib", "urllib.request", "socket", "openai"}
        assert not (imported & banned), f"{module} imports transport: {imported & banned}"
        assert not any(
            "create_provider" in name for name in imported
        ), f"{module} imports a provider constructor"


def test_the_eval_runner_has_no_retrieval_interface_for_a_provider(harness):
    """Same rule as the context layer: a model receives a payload, never a way
    to ask for one."""
    broker, _ = harness
    runner = EvalRunner(broker)
    for attribute in ("query", "search", "fetch", "tools", "functions", "retrieve"):
        assert not hasattr(runner, attribute)


# ── end to end: a real verdict from a real run ─────────────────────────────


def test_a_full_run_produces_a_leaderboard_and_a_verdict(harness, tmp_path):
    """The whole pipeline: score models, score a mode, compare, record, route.

    Mistral is scripted to answer well and DeepSeek badly, so the champion is
    known in advance and the verdict is checkable rather than decorative.
    """
    broker, replies = harness
    replies["mistral"] = GOOD_EMAIL
    replies["deepseek"] = "Certainly! Here you go: Hi {{first_name}}!"

    suites = load_suites(SUITE_PATH)
    suite = suites["email_first_contact"]
    settings = _settings(enabled_provider_ids=("mistral", "deepseek"))
    runner = EvalRunner(broker)
    board = Scoreboard(tmp_path / "evals.sqlite3")

    reports = [
        runner.run_model(suite, settings, provider_id=pid) for pid in ("mistral", "deepseek")
    ]
    for report in reports:
        board.record(report)

    champion = best_of(reports)
    assert champion.subject == "mistral", "the better-scripted model should win"

    # Compare mode fans out to both models, but its single-string answer is
    # taken from the highest trust tier — which is Mistral, the champion. So it
    # returns *the same text* at three times the cost. The gate must see that
    # for what it is.
    mode_report = runner.run_mode(
        suite, settings, mode="compare", runner=ModeRunner(broker)
    )
    board.record(mode_report)
    assert mode_report.score == pytest.approx(champion.score), (
        "compare mode should tie the champion here, because its single answer "
        "IS the champion's answer"
    )

    verdict = compare(champion, mode_report, cost_multiple=3.0)
    assert verdict.promoted is False, "a tie must not promote a 3x more expensive mode"
    assert verdict.wins == 0 and verdict.losses == 0
    assert "Not an improvement" in verdict.reason

    top = board.leaderboard(suite_id=suite.id)
    assert top[0]["score"] == pytest.approx(champion.score)
    assert {row["subject"] for row in top} == {"mistral", "deepseek", "compare"}
    assert min(row["score"] for row in top) < champion.score  # deepseek scored worse

    board.set_champion(
        suite_id=suite.id,
        subject=champion.subject,
        subject_kind="model",
        score=champion.score,
        reason=verdict.reason,
    )
    assert board.route_for(suite_id=suite.id) == "simple"


def test_compare_mode_running_across_tiers_still_scores_honestly(harness):
    """Compare reaches tier C, which now gets a pseudonymous payload. The score
    must reflect what that model actually produced, not what a better-informed
    one would have."""
    broker, replies = harness
    replies["deepseek"] = "Subject: Hi\n\nHello PERSON_1 at COMPANY_1. " + "word " * 60
    suites = load_suites(SUITE_PATH)
    report = EvalRunner(broker).run_model(
        suites["email_first_contact"],
        _settings(enabled_provider_ids=("deepseek",)),
        provider_id="deepseek",
    )
    assert 0.0 < report.score < 1.0
    assert report.errors == 0


# ── the CLI ─────────────────────────────────────────────────────────────────


def test_cli_list_names_every_suite(capsys):
    from offsetx_apollo_builder.ai.eval_cli import main

    assert main(["list"]) == 0
    out = capsys.readouterr().out
    for suite_id in load_suites(SUITE_PATH):
        assert suite_id in out


def test_cli_warns_when_a_suite_is_too_small_to_trust(capsys):
    from offsetx_apollo_builder.ai.eval_cli import main

    main(["list"])
    assert "too few to detect a small difference" in capsys.readouterr().out


def test_cli_rejects_an_unknown_suite(capsys, tmp_path):
    from offsetx_apollo_builder.ai.eval_cli import main

    assert main(["--data-dir", str(tmp_path), "run", "--suite", "nope"]) == 2
    assert "No suite named" in capsys.readouterr().out


def test_cli_dry_run_sends_nothing(capsys, tmp_path, monkeypatch):
    """The plan and the call count, without spending tokens."""
    from offsetx_apollo_builder.ai import eval_cli

    def exploding_broker(*args, **kwargs):
        raise AssertionError("a dry run must not construct a call path")

    store = eval_cli.WorkspaceAISettingsStore(tmp_path, eval_cli.ProviderRegistry())
    store.connect_provider("local", "mistral", api_key="k")
    monkeypatch.setattr(eval_cli.EvalRunner, "run_model", exploding_broker)

    code = eval_cli.main(
        ["--data-dir", str(tmp_path), "run", "--suite", "email_first_contact", "--dry-run"]
    )
    out = capsys.readouterr().out
    assert code == 0
    assert "Dry run. Nothing was sent." in out
    assert "calls     : ~" in out


def test_cli_champion_explains_itself_when_nothing_is_measured(capsys, tmp_path):
    from offsetx_apollo_builder.ai.eval_cli import main

    assert main(["--data-dir", str(tmp_path), "champion", "--suite", "s1"]) == 0
    out = capsys.readouterr().out
    assert "Nothing measured" in out
    assert "offsetx-evals run" in out
