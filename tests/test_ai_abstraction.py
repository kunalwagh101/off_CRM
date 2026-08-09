"""Abstraction: hiding the shape of a request, not just the names in it.

Tokenisation answers "who is this about". These rules answer a question no PII
scrubber asks: **what does this reveal about how the business works?**

Three properties under test:

* the leak this exists to close is actually closed;
* every rule only ever **widens** — none can make text more revealing, which is
  what makes running it twice safe;
* a rule never lies. Widening that inverts the meaning would produce worse copy
  for no privacy gain, and one shipped rule did exactly that before it was
  caught here.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

from offsetx_apollo_builder.ai import DataClass, DataPolicy, EgressRequest, PersonPublic
from offsetx_apollo_builder.ai.abstraction import (
    Abstractor,
    Rule,
    abstractor_for,
    load_rules,
)
from offsetx_apollo_builder.ai.errors import RegistryError
from offsetx_apollo_builder.ai.payload import build_payload

REPO_ROOT = Path(__file__).resolve().parents[1]
RULES_PATH = REPO_ROOT / "config" / "abstraction.yaml"


@pytest.fixture()
def abstractor() -> Abstractor:
    return Abstractor(load_rules(RULES_PATH))


#: The exact sentence from the design discussion. Every identifier is already
#: gone and it still gives away most of a go-to-market strategy.
THE_LEAK = (
    "Third follow-up to a CTO at a 180-person Series B fintech in Berlin who "
    "opened twice and never replied. ICP: Series B fintechs, 100-250 staff. "
    "Our margin is 40% and we close 1 in 8."
)


# ── the leak this exists to close ──────────────────────────────────────────


def test_the_motivating_leak_is_closed(abstractor):
    out = abstractor.abstract(THE_LEAK).text
    for secret in (
        "180-person",   # company size
        "Series B",     # funding stage
        "40%",          # gross margin
        "1 in 8",       # close rate
        "100-250",      # ICP size band
        "Third follow-up",  # sequence length
        "opened twice",     # engagement telemetry
    ):
        assert secret not in out, f"{secret!r} survived abstraction"


def test_a_margin_figure_does_not_survive(abstractor):
    """Regression. The percentage rule originally ended in `\\b`, and since `%`
    is not a word character that boundary can never match — so the single most
    commercially sensitive number in a payload passed through untouched."""
    assert "40%" not in abstractor.abstract("Our margin is 40% this year.").text
    assert "40 %" not in abstractor.abstract("Our margin is 40 % this year.").text
    assert "40 percent" not in abstractor.abstract("Our margin is 40 percent.").text


def test_a_trailing_word_boundary_after_a_symbol_can_never_match():
    """The bug in isolation, so nobody reintroduces the shape of it."""
    broken = re.compile(r"\b\d{1,3}\s?%\b")
    assert broken.search("margin is 40% and") is None
    fixed = re.compile(r"\b\d{1,3}\s?%")
    assert fixed.search("margin is 40% and") is not None


# ── rules must not lie ─────────────────────────────────────────────────────


def test_a_first_email_is_left_alone_and_not_called_a_later_one(abstractor):
    """Caught by an existing test when this rule shipped: "a warm first email"
    became "a later message in the sequence", which inverts the meaning.

    It is also unnecessary. Every sequence has a first message, so the word
    leaks nothing — it is the high ordinals that disclose how many steps exist.
    """
    text = "Write a warm first email to the CTO."
    assert abstractor.abstract(text).text == text
    assert abstractor.abstract("This is email 1 of the sequence.").applied == {}


def test_high_ordinals_are_still_widened(abstractor):
    for phrase in ("Third follow-up", "seventh touch", "email 7", "step 4"):
        result = abstractor.abstract(f"Send the {phrase} now.")
        assert result.changed, f"{phrase!r} should have been widened"
        assert "later message" in result.text


def test_widening_never_asserts_a_position_it_cannot_know(abstractor):
    """"Later" is only claimed where the input actually said second or beyond."""
    assert "later" not in abstractor.abstract("the first touch").text


# ── only ever widens ───────────────────────────────────────────────────────


def test_applying_the_rules_twice_changes_nothing_further(abstractor):
    """Idempotence follows from every rule being a widening. If a second pass
    kept changing things, some rule would be rewriting its own output."""
    once = abstractor.abstract(THE_LEAK).text
    twice = abstractor.abstract(once).text
    assert once == twice


def test_ordinary_copy_instructions_pass_through_untouched(abstractor):
    """The cost of this protection must be near zero on normal work."""
    for benign in (
        "Write a warm intro email about customs software.",
        "Keep it under 120 words and end with a question.",
        "Mention their talk at the trade summit.",
        "",
    ):
        result = abstractor.abstract(benign)
        assert result.text == benign
        assert result.applied == {}


def test_the_result_reports_which_rules_fired(abstractor):
    """The owner should be able to see what was changed rather than trust it."""
    result = abstractor.abstract(THE_LEAK)
    assert result.changed is True
    assert "percentages" in result.applied
    assert "headcount" in result.applied
    assert all(count > 0 for count in result.applied.values())


# ── number banding ─────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "headcount,expected",
    [
        ("a 4-person team", "a very small company"),
        ("a 40 person company", "a small company"),
        ("a 180-person fintech", "a mid-size company"),
        ("a 900 employee firm", "a large company"),
        ("a 40,000 employee firm", "an enterprise"),
    ],
)
def test_headcount_lands_in_the_right_band(abstractor, headcount, expected):
    assert expected in abstractor.abstract(headcount).text


def test_a_band_label_does_not_produce_a_double_article(abstractor):
    """Regression: bucket labels begin with an article, so "a 180-person" became
    "a a mid-size company" until the pattern learned to swallow the article."""
    out = abstractor.abstract("a 180-person fintech").text
    assert "a a " not in out
    assert "an an " not in out
    assert out.startswith("a mid-size company")


def test_a_size_range_is_recognised_before_a_single_number(abstractor):
    """Regression: `headcount` was listed first and consumed the right-hand
    number of "100-250 staff", so the range rule never saw it. The more specific
    pattern must run first."""
    out = abstractor.abstract("targeting 100-250 staff companies").text
    assert "a company size band" in out
    assert "250" not in out


# ── config integrity ───────────────────────────────────────────────────────


def test_the_shipped_rules_load_and_every_one_has_a_note():
    """A rule nobody can explain is a rule nobody can review."""
    rules = load_rules(RULES_PATH)
    assert rules
    for rule in rules:
        assert rule.note, f"rule {rule.id!r} has no note explaining why it exists"


def test_rule_ids_are_unique():
    ids = [rule.id for rule in load_rules(RULES_PATH)]
    assert len(ids) == len(set(ids))


def test_an_unknown_kind_is_refused_rather_than_ignored(tmp_path):
    """A rule that silently does nothing is worse than no rule: it looks like
    protection."""
    path = tmp_path / "bad.yaml"
    path.write_text("rules:\n  - id: x\n    kind: not_a_kind\n    pattern: 'a'\n")
    with pytest.raises(RegistryError, match="unknown kind"):
        load_rules(path)


def test_a_bucket_rule_without_an_open_ended_band_is_refused(tmp_path):
    """Without a `max: null` bucket a large value falls through the bottom of
    the ladder and the number leaks."""
    path = tmp_path / "bad.yaml"
    path.write_text(
        "rules:\n"
        "  - id: x\n"
        "    kind: bucket_number\n"
        "    pattern: '(?P<value>\\d+) widgets'\n"
        "    buckets:\n"
        "      - {max: 10, label: 'a few'}\n"
    )
    with pytest.raises(RegistryError, match="open-ended bucket"):
        load_rules(path)


def test_a_bucket_rule_without_a_value_group_is_refused(tmp_path):
    path = tmp_path / "bad.yaml"
    path.write_text(
        "rules:\n"
        "  - id: x\n"
        "    kind: bucket_number\n"
        "    pattern: '\\d+ widgets'\n"
        "    buckets:\n"
        "      - {max: null, label: 'some'}\n"
    )
    with pytest.raises(RegistryError, match="named group"):
        load_rules(path)


def test_a_malformed_pattern_is_refused_at_load_time(tmp_path):
    path = tmp_path / "bad.yaml"
    path.write_text("rules:\n  - id: x\n    kind: replace_pattern\n    pattern: '([unclosed'\n")
    with pytest.raises(RegistryError, match="bad pattern"):
        load_rules(path)


def test_a_missing_rules_file_says_so(tmp_path):
    with pytest.raises(RegistryError, match="No abstraction rules"):
        load_rules(tmp_path / "nope.yaml")


def test_a_non_numeric_match_is_left_alone_rather_than_mislabelled():
    """A bucket rule whose captured group is not a number must not invent a
    band. Returning the original is the only safe answer."""
    rule = Rule(
        id="x",
        kind="bucket_number",
        pattern=re.compile(r"(?P<value>[\d.]+) widgets"),
        buckets=(),
    )
    text, count = rule.apply("1.2.3 widgets")
    assert text == "1.2.3 widgets"
    assert count == 0


# ── wired into the payload ─────────────────────────────────────────────────


def _request(**kwargs) -> EgressRequest:
    defaults = {
        "task_type": "draft_email",
        "data_class": DataClass.CAMPAIGN,
        "person": PersonPublic(full_name="Ana Silva", first_name="Ana", title="CTO"),
        "instructions": THE_LEAK,
        "campaign_notes": "ICP: Series B fintechs, 100-250 staff. Margin 40%.",
    }
    defaults.update(kwargs)
    return EgressRequest(**defaults)


def test_a_standard_payload_no_longer_carries_the_business_shape():
    payload = build_payload(_request(), DataPolicy.STANDARD)
    blob = str(payload)
    for secret in ("180-person", "Series B", "40%", "1 in 8", "100-250"):
        assert secret not in blob, f"{secret!r} reached a tier B payload"


def test_campaign_notes_are_widened_as_well_as_instructions():
    """Notes are the densest source: an ICP line and a margin often share a
    sentence."""
    payload = build_payload(_request(), DataPolicy.STANDARD)
    assert "Series B" not in payload["campaign_notes"]
    assert "40%" not in payload["campaign_notes"]


def test_full_policy_sends_the_text_verbatim():
    """At `full` the owner has explicitly trusted one provider with everything,
    and widening there would only degrade the copy."""
    payload = build_payload(_request(), DataPolicy.FULL)
    assert "180-person" in payload["instructions"]
    assert "40%" in payload["campaign_notes"]


def test_abstraction_can_be_switched_off_for_a_call():
    payload = build_payload(_request(), DataPolicy.STANDARD, abstract_shape=False)
    assert "180-person" in payload["instructions"]


def test_the_default_is_the_safe_one():
    """A caller that forgets the argument gets protection, not a leak."""
    assert "180-person" not in str(build_payload(_request(), DataPolicy.STANDARD))


def test_abstraction_runs_after_identity_scrubbing_not_instead_of_it():
    """Both protections apply. They guard different things and neither
    substitutes for the other."""
    payload = build_payload(
        _request(instructions="Ana Silva runs a 180-person Series B fintech."),
        DataPolicy.PSEUDONYMOUS,
    )
    text = payload["instructions"]
    assert "Ana Silva" not in text          # tokenisation did its job
    assert "PERSON_1" in text
    assert "180-person" not in text         # abstraction did its job
    assert "Series B" not in text


def test_a_broken_rules_file_does_not_stop_a_send(monkeypatch):
    """Failing to widen must not become failing to send. The gap is visible in
    the payload rather than taking the feature down."""
    def explode(text):
        raise RegistryError("rules are broken")

    monkeypatch.setattr(
        "offsetx_apollo_builder.ai.abstraction.abstract_text", explode
    )
    payload = build_payload(_request(), DataPolicy.STANDARD)
    assert payload["instructions"], "the send should still have happened"


def test_the_shared_abstractor_is_reused_rather_than_recompiled():
    """A dozen regexes recompiled on every payload build would be a silly cost
    for something that never changes within a process."""
    assert abstractor_for(RULES_PATH) is abstractor_for(RULES_PATH)


# ── the workspace switch ───────────────────────────────────────────────────


def test_the_broker_widens_by_default_and_the_owner_can_stop_it(tmp_path):
    """End to end through the real broker, not just the builder."""
    from offsetx_apollo_builder.ai import (
        EgressBroker,
        EgressLog,
        ProviderRegistry,
        QuotaTracker,
        WorkspaceEgressSettings,
    )

    seen: list[dict] = []

    class Recorder:
        def generate(self, *, system_prompt, user_prompt):
            import json as _json

            seen.append(_json.loads(user_prompt))
            return "ok"

    broker = EgressBroker(
        registry=ProviderRegistry(REPO_ROOT / "config" / "providers.yaml"),
        credential_resolver=lambda provider_id: "k",
        quota=QuotaTracker(tmp_path),
        logger=EgressLog(tmp_path / "e.db").record,
    )
    broker._instantiate = lambda candidate: Recorder()

    def settings(**kw):
        base = {
            "workspace_id": "local",
            "enabled_provider_ids": ("mistral",),
            "owner_domains": ("offsetx.example",),
        }
        base.update(kw)
        return WorkspaceEgressSettings(**base)

    broker.call(_request(), settings(), system_prompt="w")
    assert "180-person" not in str(seen[-1]), "the default must protect"

    broker.call(
        _request(), settings(abstract_business_shape=False), system_prompt="w"
    )
    assert "180-person" in str(seen[-1]), "the owner must be able to switch it off"
