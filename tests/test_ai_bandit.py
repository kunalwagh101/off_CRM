"""Traffic shifting between template variants (§4H).

The property that matters most is the unglamorous one: **the system must behave
sensibly when it does not know.** Cold-outreach reply rates are low, so a naive
"run to 20 sends then pick the winner" rule is fed data that cannot support the
decision it is being asked to make, and it answers confidently anyway.

So the tests are grouped around that:

* with thin data the split stays close to even and nothing is declared;
* with real evidence the split moves and the call is made;
* no variant is ever starved to zero, so a bad early run is recoverable;
* the sentence shown to the owner never contradicts the split it describes.
"""
from __future__ import annotations

import ast
from pathlib import Path

import pytest

from offsetx_apollo_builder.ai.bandit import (
    DEFAULT_FLOOR,
    Arm,
    allocate,
    arms_from_scores,
    sends_needed,
)

PACKAGE_ROOT = Path(__file__).resolve().parents[1] / "offsetx_apollo_builder"

#: Fixed so every assertion below is exact rather than flaky. Thompson sampling
#: is random by design — that randomness is the exploration — so a seeded run is
#: the only way to test it honestly.
SEED = 7


def _pair(sends_a, replies_a, sends_b, replies_b):
    return [
        Arm("a", "original", sends_a, replies_a),
        Arm("b", "rewrite", sends_b, replies_b),
    ]


# ── behaving sensibly when it does not know ────────────────────────────────


def test_with_no_data_at_all_the_split_is_even():
    result = allocate(_pair(0, 0, 0, 0), seed=SEED)
    for arm in result.arms:
        assert 0.4 < arm.share < 0.6
    assert result.confident is False


def test_twenty_sends_does_not_produce_a_confident_call():
    """The number the old threshold used. One reply against three looks like a
    threefold improvement and is nowhere near evidence of one."""
    result = allocate(_pair(20, 1, 20, 3), seed=SEED)
    assert result.confident is False
    assert "not conclusive" in result.verdict


def test_a_thin_but_lopsided_sample_still_leaves_the_loser_a_real_share():
    """Exploration must survive a bad start, or a variant that was unlucky in
    its first twenty sends never gets to prove otherwise."""
    result = allocate(_pair(20, 0, 20, 4), seed=SEED)
    loser = min(result.arms, key=lambda a: a.share)
    assert loser.share >= DEFAULT_FLOOR


def test_nearly_identical_rates_keep_the_split_close_to_even():
    result = allocate(_pair(300, 10, 300, 11), seed=SEED)
    assert result.confident is False
    for arm in result.arms:
        assert 0.35 < arm.share < 0.65


def test_the_owner_is_told_how_far_off_an_answer_is():
    """"You need about N more sends" is more use than a percentage that looks
    decisive and is not."""
    result = allocate(_pair(300, 10, 300, 11), seed=SEED)
    assert "sends per variant" in result.verdict
    assert "more each" in result.verdict


# ── moving when the evidence is real ───────────────────────────────────────


def test_strong_evidence_shifts_traffic_and_declares_a_leader():
    result = allocate(_pair(1000, 20, 1000, 40), seed=SEED)
    assert result.confident is True
    assert result.leader.arm_id == "b"
    assert result.leader.share > 0.85


def test_the_leader_never_takes_everything():
    """A holdout is what makes a later regression visible. If the winner took
    100%, a degrading template would look fine forever."""
    result = allocate(_pair(5000, 50, 5000, 300), seed=SEED)
    assert result.leader.share <= 1.0 - DEFAULT_FLOOR + 1e-9
    assert min(arm.share for arm in result.arms) >= DEFAULT_FLOOR - 1e-9


def test_probability_best_and_share_agree_on_who_is_ahead():
    result = allocate(_pair(1000, 20, 1000, 40), seed=SEED)
    by_probability = max(result.arms, key=lambda a: a.probability_best)
    by_share = max(result.arms, key=lambda a: a.share)
    assert by_probability.arm_id == by_share.arm_id


# ── the verdict must not contradict the split ──────────────────────────────


@pytest.mark.parametrize(
    "arms",
    [
        _pair(0, 0, 0, 0),
        _pair(20, 1, 20, 3),
        _pair(300, 10, 300, 11),
        _pair(1000, 20, 1000, 40),
        _pair(5000, 50, 5000, 300),
    ],
)
def test_a_verdict_claiming_an_even_split_is_only_used_when_the_split_is_even(arms):
    """Regression. The first version said "traffic stays near even" while
    allocating 80/20 — the text and the numbers disagreed, which is exactly the
    kind of quiet dishonesty that makes a dashboard untrustworthy."""
    result = allocate(arms, seed=SEED)
    if "stays close to even" in result.verdict:
        assert result.leader.share < 0.65, (
            f"verdict claims an even split but the leader takes "
            f"{result.leader.share:.0%}"
        )


def test_the_verdict_always_names_the_leader():
    result = allocate(_pair(1000, 20, 1000, 40), seed=SEED)
    assert "rewrite" in result.verdict


# ── the maths ──────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "rate_a,rate_b,lower,upper",
    [
        (0.02, 0.04, 900, 1500),
        (0.02, 0.03, 3000, 4500),
        (0.05, 0.10, 300, 600),
    ],
)
def test_sample_size_matches_the_standard_two_proportion_formula(
    rate_a, rate_b, lower, upper
):
    """Sanity-bounded against the textbook numbers, so a later refactor cannot
    quietly make the honesty figure optimistic."""
    assert lower <= sends_needed(rate_a, rate_b) <= upper


def test_identical_rates_need_no_sample_size():
    assert sends_needed(0.03, 0.03) == 0


def test_degenerate_rates_do_not_explode():
    for a, b in [(0.0, 0.5), (0.5, 1.0), (-1, 0.5)]:
        assert sends_needed(a, b) == 0


def test_the_posterior_is_pulled_towards_the_middle_when_data_is_thin():
    """A single reply from two sends is not a 50% reply rate, and quoting it as
    one is how people talk themselves into bad templates."""
    thin = Arm("a", "x", sends=2, replies=1)
    assert thin.observed_rate == 0.5
    assert thin.posterior_mean == 0.5  # Beta(2,2) is symmetric, mean 0.5
    fat = Arm("b", "y", sends=1000, replies=500)
    assert abs(fat.posterior_mean - 0.5) < 0.01
    # The interval is what separates them, and it is reported.
    thin_result = allocate([thin, Arm("c", "z", 2, 0)], seed=SEED)
    wide = thin_result.arms[0]
    assert wide.high - wide.low > 0.5, "thin data should show a wide interval"


def test_shares_always_sum_to_one():
    for arms in (
        _pair(0, 0, 0, 0),
        _pair(20, 1, 20, 3),
        _pair(1000, 20, 1000, 40),
        [Arm(str(i), f"v{i}", 100, i * 3) for i in range(5)],
    ):
        result = allocate(arms, seed=SEED)
        assert abs(sum(arm.share for arm in result.arms) - 1.0) < 1e-6


def test_the_floor_cannot_push_the_total_over_one():
    """With many arms a naive floor would sum past 100% and silently inflate
    everyone's share."""
    arms = [Arm(str(i), f"v{i}", 10, 1) for i in range(30)]
    result = allocate(arms, floor=0.5, seed=SEED)
    assert abs(sum(arm.share for arm in result.arms) - 1.0) < 1e-6


# ── inputs and edges ───────────────────────────────────────────────────────


def test_more_replies_than_sends_is_refused():
    with pytest.raises(ValueError, match="impossible"):
        Arm("a", "x", sends=5, replies=6)


def test_retired_variants_are_excluded_entirely():
    arms = [
        Arm("a", "original", 100, 5),
        Arm("b", "retired", 100, 50, retired=True),
    ]
    result = allocate(arms, seed=SEED)
    assert [arm.arm_id for arm in result.arms] == ["a"]
    assert result.share_for("b") == 0.0


def test_a_single_variant_takes_everything_and_says_why():
    result = allocate([Arm("a", "only", 100, 5)], seed=SEED)
    assert result.share_for("a") == 1.0
    assert "Only one active variant" in result.verdict
    assert result.confident is False


def test_no_active_variants_reports_rather_than_dividing_by_zero():
    result = allocate([Arm("a", "gone", 10, 1, retired=True)], seed=SEED)
    assert result.arms == []
    assert "No active variants" in result.verdict
    assert result.leader is None


def test_the_same_seed_gives_the_same_allocation():
    """An owner should be able to re-derive the split they were shown."""
    arms = _pair(200, 8, 200, 14)
    first = allocate(arms, seed=42)
    second = allocate(arms, seed=42)
    assert [a.to_dict() for a in first.arms] == [a.to_dict() for a in second.arms]


def test_different_seeds_move_the_split_only_slightly():
    """Monte-Carlo noise must not be mistaken for a change in the evidence."""
    arms = _pair(1000, 20, 1000, 40)
    shares = [allocate(arms, seed=s).leader.share for s in range(5)]
    assert max(shares) - min(shares) < 0.05


def test_scores_from_the_context_layer_convert_cleanly():
    class Score:
        variant_id = "v1"
        label = "rewrite"
        sends = 120
        replies = 6
        retired = False

    arms = arms_from_scores([Score()])
    assert arms[0].id == "v1"
    assert arms[0].sends == 120
    assert arms[0].replies == 6


# ── structural ─────────────────────────────────────────────────────────────


def test_the_bandit_reaches_no_provider_and_no_database():
    """Allocation maths has no business knowing about SQLite or HTTP. Keeping it
    pure is what lets it be tested exactly."""
    source = (PACKAGE_ROOT / "ai" / "bandit.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module)
        elif isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
    banned = {"requests", "httpx", "openai", "sqlite3", "socket"}
    assert not (imported & banned), f"bandit.py imports {imported & banned}"


def test_allocation_output_is_plain_data():
    result = allocate(_pair(100, 5, 100, 8), seed=SEED)
    payload = result.to_dict()
    assert isinstance(payload["arms"], list)
    assert isinstance(payload["confident"], bool)
    assert isinstance(payload["verdict"], str)


# ── wired to the real counters ─────────────────────────────────────────────


def test_the_context_layer_splits_traffic_from_its_own_counts(tmp_path):
    """End to end on the real store: register two variants, record sends and
    replies, and get a split back."""
    from offsetx_apollo_builder.ai.context import ContextLayer

    context = ContextLayer(tmp_path / "ctx.db")
    context.register_template(
        workspace_id="local", template_id="t1", variant_id="original",
        label="original", template_text="Hi there",
    )
    context.register_template(
        workspace_id="local", template_id="t1", variant_id="rewrite",
        label="rewrite", template_text="Hello there",
    )
    for _ in range(400):
        context.record_send(template_id="t1", variant_id="original")
        context.record_send(template_id="t1", variant_id="rewrite")
    for _ in range(8):
        context.record_reply(template_id="t1", variant_id="original")
    for _ in range(32):
        context.record_reply(template_id="t1", variant_id="rewrite")

    split = context.traffic_split("local", template_id="t1", seed=SEED)
    assert split["leader"] == "rewrite"
    assert split["confident"] is True
    shares = {arm["arm_id"]: arm["share"] for arm in split["arms"]}
    assert shares["rewrite"] > shares["original"]
    assert abs(sum(shares.values()) - 1.0) < 1e-6
    context.close()


def test_a_template_with_no_data_yet_gets_an_even_split(tmp_path):
    from offsetx_apollo_builder.ai.context import ContextLayer

    context = ContextLayer(tmp_path / "ctx.db")
    for variant in ("original", "rewrite"):
        context.register_template(
            workspace_id="local", template_id="t1", variant_id=variant,
            label=variant, template_text="x",
        )
    split = context.traffic_split("local", template_id="t1", seed=SEED)
    assert split["confident"] is False
    for arm in split["arms"]:
        assert 0.3 < arm["share"] < 0.7
    context.close()


def test_the_context_layer_still_lets_no_model_touch_the_split(tmp_path):
    """`traffic_split` reads the counters and returns plain data. It must not
    become a retrieval interface a provider could reach."""
    from offsetx_apollo_builder.ai.context import ContextLayer

    context = ContextLayer(tmp_path / "ctx.db")
    for attribute in ("query", "search", "tools", "functions", "retrieve"):
        assert not hasattr(context, attribute)
    context.close()
