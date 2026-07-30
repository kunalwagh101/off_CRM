"""The context layer.

Two safety rules matter more than any feature here, and both get their own test:

* No model can read this store. It has no query path a provider could use.
* Only code writes to it. No field is filled in by an AI.

Plus the learning loop: counting is deterministic, and a rewrite request carries
the template wording and two numbers — nothing about any real person.
"""
from __future__ import annotations

import ast
import io
import json
import tokenize
from pathlib import Path

import pytest

from offsetx_apollo_builder.ai import ContextLayer, DataClass
from offsetx_apollo_builder.ai.context import (
    MIN_SENDS_TO_JUDGE,
    WEAK_REPLY_RATE,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
CONTEXT_SOURCE = REPO_ROOT / "offsetx_apollo_builder" / "ai" / "context.py"


def _code_only(source: str) -> str:
    """The source with comments and docstrings dropped.

    The prose in this module *describes* the interfaces it deliberately does not
    have ("no retrieval tool"), so a plain substring search over the whole file
    would flag the very sentence promising the absence.  Strip the writing and
    search the code.
    """
    docstrings = {
        node.body[0].value
        for node in ast.walk(ast.parse(source))
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef))
        and node.body
        and isinstance(node.body[0], ast.Expr)
        and isinstance(node.body[0].value, ast.Constant)
        and isinstance(node.body[0].value.value, str)
    }
    docstring_spans = {(node.lineno, node.col_offset) for node in docstrings}
    kept: list[str] = []
    for token in tokenize.generate_tokens(io.StringIO(source).readline):
        if token.type == tokenize.COMMENT:
            continue
        if token.type == tokenize.STRING and token.start in docstring_spans:
            continue
        kept.append(token.string)
    return "\n".join(kept)


@pytest.fixture()
def layer(tmp_path) -> ContextLayer:
    return ContextLayer(tmp_path / "context.db")


# ── job 1: keeping the job's place ──────────────────────────────────────────


def test_a_job_remembers_its_steps_and_what_comes_next(layer):
    task = layer.start_task(title="EU importers", steps=["Find leads", "Write", "Send"])
    assert task.total_steps == 3
    assert task.done_count == 0
    assert task.next_step["name"] == "Find leads"

    task = layer.finish_step(task.id, 0, note="42 leads")
    assert task.done_count == 1
    assert task.next_step["name"] == "Write"


def test_a_decision_survives_so_a_later_model_cannot_undo_it(layer):
    """The point of the layer: swap models mid-job and the choices still hold."""
    task = layer.start_task(title="Campaign", steps=["Write"])
    layer.record_decision(task.id, "Keep emails under 100 words")
    layer.record_decision(task.id, "No exclamation marks")

    resumed = layer.get_task(task.id)
    assert resumed is not None
    texts = [decision["text"] for decision in resumed.decisions]
    assert "Keep emails under 100 words" in texts
    assert "No exclamation marks" in texts
    # And they appear in the summary a model is handed.
    assert "under 100 words" in resumed.summary


def test_the_summary_is_built_by_code_not_by_a_model(layer):
    """A rolling summary written by an AI would cost a call per update and could
    quietly drift. This one is assembled from stored fields."""
    task = layer.start_task(title="Big job", steps=["One", "Two"])
    layer.finish_step(task.id, 0)
    layer.record_decision(task.id, "Short subject lines")
    task = layer.remember_fact(task.id, "leads", 42)

    assert "Big job" in task.summary
    assert "1 of 2 steps done" in task.summary
    assert "Short subject lines" in task.summary
    assert "leads: 42" in task.summary
    # Same inputs, same summary — no model in the loop means no randomness.
    again = layer.get_task(task.id)
    assert again is not None and again.summary == task.summary


def test_facts_are_structured_fields_not_free_text(layer):
    task = layer.start_task(title="Job")
    layer.remember_fact(task.id, "leads_found", 42)
    layer.remember_fact(task.id, "sector", "customs")
    resumed = layer.get_task(task.id)
    assert resumed is not None
    assert resumed.facts == {"leads_found": 42, "sector": "customs"}


def test_open_jobs_are_listed_and_closing_removes_them(layer):
    first = layer.start_task(title="One")
    layer.start_task(title="Two")
    assert len(layer.open_tasks()) == 2
    layer.close_task(first.id)
    assert [task.title for task in layer.open_tasks()] == ["Two"]


# ── job 2: counting what works ──────────────────────────────────────────────


def test_reply_rate_is_plain_counting(layer):
    for _ in range(40):
        layer.record_send(template_id="t1")
    for _ in range(6):
        layer.record_reply(template_id="t1")
    score = layer.score_for("local", "t1")
    assert score is not None
    assert score.sends == 40
    assert score.replies == 6
    assert score.reply_rate == 15.0


def test_a_template_is_not_judged_until_it_has_enough_sends(layer):
    """One lucky reply out of two sends is not a 50% success rate."""
    layer.record_send(template_id="lucky")
    layer.record_send(template_id="lucky")
    layer.record_reply(template_id="lucky")
    score = layer.score_for("local", "lucky")
    assert score is not None
    assert score.reply_rate == 50.0
    assert score.judged is False
    assert score.weak is False  # cannot be called weak either — too early

    for _ in range(MIN_SENDS_TO_JUDGE):
        layer.record_send(template_id="lucky")
    score = layer.score_for("local", "lucky")
    assert score is not None and score.judged is True


def test_a_weak_template_is_flagged_and_a_good_one_is_not(layer):
    for _ in range(30):
        layer.record_send(template_id="formal")
    layer.record_reply(template_id="formal")  # 3.3%

    for _ in range(25):
        layer.record_send(template_id="direct")
    for _ in range(5):
        layer.record_reply(template_id="direct")  # 20%

    weak = {score.template_id for score in layer.weak_templates()}
    assert weak == {"formal"}
    assert layer.winner().template_id == "direct"


def test_the_winner_must_have_earned_it(layer):
    """A template with 1 send and 1 reply is 100% — and must not win."""
    layer.record_send(template_id="fluke")
    layer.record_reply(template_id="fluke")
    for _ in range(30):
        layer.record_send(template_id="real")
    for _ in range(3):
        layer.record_reply(template_id="real")

    assert layer.winner().template_id == "real"


def test_only_sends_and_replies_can_be_counted(layer):
    """Guards the counting path against being used for anything else."""
    with pytest.raises(ValueError):
        layer._bump("local", "t1", "", "opens")


# ── job 3: the rewrite request ──────────────────────────────────────────────


def test_a_rewrite_request_carries_no_person_data(layer):
    """The whole learning loop in one assertion: wording plus two numbers.

    No recipient, no name, no address, no campaign. That is why it runs as
    public work and why it leaks nothing.
    """
    layer.register_template(
        template_id="formal",
        label="Formal",
        template_text="Dear {{first_name}}, I am writing regarding customs.",
    )
    for _ in range(30):
        layer.record_send(template_id="formal")
    layer.record_reply(template_id="formal")

    score = layer.score_for("local", "formal")
    assert score is not None
    request = layer.rewrite_request(score)

    assert request.data_class is DataClass.PUBLIC
    assert request.person is None
    assert request.template_text == ""
    assert "30 times" in request.instructions
    assert "1 replies" in request.instructions
    assert "{{first_name}}" in request.instructions  # placeholder must survive
    # Nothing that identifies anybody.
    assert "@" not in request.instructions


def test_the_winner_is_offered_as_a_reference_to_beat(layer):
    """The owner asked for this: the best template is shown to other models as
    something they may follow or improve on."""
    layer.register_template(
        template_id="best", label="Direct", template_text="Hi {{first_name}}, quick one."
    )
    layer.register_template(
        template_id="poor", label="Formal", template_text="Dear Sir or Madam,"
    )
    for _ in range(30):
        layer.record_send(template_id="best")
        layer.record_send(template_id="poor")
    for _ in range(9):
        layer.record_reply(template_id="best")
    layer.record_reply(template_id="poor")

    poor = layer.score_for("local", "poor")
    assert poor is not None
    request = layer.rewrite_request(poor, winner=layer.winner())
    assert "Hi {{first_name}}, quick one." in request.instructions
    assert "or do better" in request.instructions

    reference = layer.reference_for_models()
    assert "Hi {{first_name}}, quick one." in reference
    assert "%" in reference


def test_there_is_no_reference_before_anything_has_been_earned(layer):
    assert layer.reference_for_models() == ""


# ── the two safety rules ────────────────────────────────────────────────────


def test_no_model_can_query_this_store():
    """A model that can *ask* for data has access. This store gives a model no
    way to ask: no tool, no function, no retrieval interface, no connection.

    off_CRM reads it and builds a payload. A model only receives that payload.
    """
    source = CONTEXT_SOURCE.read_text(encoding="utf-8")
    code = _code_only(source)
    for marker in ("tool_choice", '"tools"', "function_call", "mcp", "retrieval"):
        assert marker not in code, f"context layer must not expose {marker} to a model"

    # It also must not be able to call a provider itself. The only thing it
    # produces is an EgressRequest, which the broker then decides about.
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            assert not node.module.endswith("providers"), (
                "the context layer must never import a provider — it hands an "
                "EgressRequest to the broker instead"
            )
        if isinstance(node, ast.Import):
            for alias in node.names:
                assert alias.name != "requests", "the context layer makes no network calls"


def test_nothing_here_is_written_by_a_model():
    """Every stored field is set by Python. If an AI ever wrote into this store,
    the reply numbers would stop being facts.
    """
    code = _code_only(CONTEXT_SOURCE.read_text(encoding="utf-8"))
    # No call path that would run a model and store its answer.
    assert ".generate(" not in code
    assert "broker" not in code.lower()


def test_a_reply_is_counted_without_reading_it(layer):
    """Detecting that a reply arrived is a fact. Reading what it says would mean
    sending mailbox content to a provider, which is never allowed.

    So the counter takes no reply text — there is nowhere to put it.
    """
    import inspect

    signature = inspect.signature(layer.record_reply)
    assert set(signature.parameters) == {"workspace_id", "template_id", "variant_id"}
    assert "body" not in signature.parameters
    assert "text" not in signature.parameters


def test_thresholds_are_sensible():
    assert MIN_SENDS_TO_JUDGE >= 10
    assert 0 < WEAK_REPLY_RATE < 50


# ── the wiring: counters that nothing feeds are just zeroes ─────────────────


def test_the_real_send_path_feeds_the_counter(tmp_path):
    """The scoreboard is only worth having if sending actually fills it in.

    This drives a real send and a real reply through ``OutreachEngine`` — no
    stubbed counting — and asserts the numbers land against the template that
    went out.
    """
    from datetime import datetime, timedelta, timezone

    from offsetx_apollo_builder.outreach.engine import OutreachEngine
    from offsetx_apollo_builder.outreach.gmail import LocalOutboxProvider

    contacts = tmp_path / "contacts.csv"
    contacts.write_text(
        "Full Name,Email,Company,Title,Category,Public Hook,Hook Source,Tension\n"
        "Anita Rao,anita@example.com,Example Exports,Climate Lead,CBAM,"
        "Published a supplier emissions brief,https://example.com/anita,"
        "Supplier evidence handoff\n",
        encoding="utf-8",
    )

    layer = ContextLayer(tmp_path / "context.db")
    engine = OutreachEngine(tmp_path / "outreach.db", template_counter=layer)
    campaign_id = engine.create_campaign(name="Pilot")
    engine.import_contacts(campaign_id, contacts)
    engine.generate_drafts(campaign_id)
    engine.approve_drafts(campaign_id, stages=["initial"])

    mail = LocalOutboxProvider(tmp_path / "mail")
    now = datetime.now(timezone.utc) + timedelta(minutes=1)
    assert engine.run_due(
        campaign_id, mail_provider=mail, own_email="owner@example.com", now=now
    )["sent_count"] == 1

    scores = layer.scoreboard()
    assert len(scores) == 1, "one send should create exactly one template row"
    assert scores[0].sends == 1
    assert scores[0].replies == 0

    contact = next(
        item for item in engine.store.campaign_contacts(campaign_id) if item["sent_count"]
    )
    outgoing = engine.store.last_outgoing(contact["id"])
    assert outgoing is not None
    # The row must be the template that actually went out, not the stage.
    assert scores[0].template_id == (outgoing["template_id"] or outgoing["stage"])
    assert scores[0].variant_id == outgoing["variant_id"]

    (tmp_path / "mail" / "inbox" / "reply.json").write_text(
        json.dumps(
            {
                "id": "reply-1",
                "thread_id": outgoing["thread_id"],
                "from": contact["email"],
                "subject": "Re: evidence",
                "body": "Happy to discuss.",
                "received_at": (now + timedelta(hours=1)).isoformat(),
            }
        ),
        encoding="utf-8",
    )
    engine.sync_replies(
        campaign_id,
        mail_provider=mail,
        own_email="owner@example.com",
        now=now + timedelta(hours=2),
    )

    scores = layer.scoreboard()
    assert len(scores) == 1, "the reply belongs to the template that was sent"
    assert scores[0].sends == 1 and scores[0].replies == 1
    engine.close()


def test_a_broken_counter_never_costs_a_send(tmp_path):
    """A send that already left the building must not be reported as failed
    because a scoreboard write went wrong. Counting is the optional half."""
    from datetime import datetime, timedelta, timezone

    from offsetx_apollo_builder.outreach.engine import OutreachEngine
    from offsetx_apollo_builder.outreach.gmail import LocalOutboxProvider

    class BrokenCounter:
        def record_send(self, **_: object) -> None:
            raise RuntimeError("disk on fire")

        def record_reply(self, **_: object) -> None:
            raise RuntimeError("disk on fire")

    contacts = tmp_path / "contacts.csv"
    contacts.write_text(
        "Full Name,Email,Company,Title,Category,Public Hook,Hook Source,Tension\n"
        "Anita Rao,anita@example.com,Example Exports,Climate Lead,CBAM,"
        "Published a supplier emissions brief,https://example.com/anita,"
        "Supplier evidence handoff\n",
        encoding="utf-8",
    )
    engine = OutreachEngine(tmp_path / "outreach.db", template_counter=BrokenCounter())
    campaign_id = engine.create_campaign(name="Pilot")
    engine.import_contacts(campaign_id, contacts)
    engine.generate_drafts(campaign_id)
    engine.approve_drafts(campaign_id, stages=["initial"])
    result = engine.run_due(
        mail_provider=LocalOutboxProvider(tmp_path / "mail"),
        campaign_id=campaign_id,
        own_email="owner@example.com",
        now=datetime.now(timezone.utc) + timedelta(minutes=1),
    )
    assert result["sent_count"] == 1 and result["failed"] == []
    engine.close()


def test_counting_is_optional(tmp_path):
    """No counter wired in must not be a crash — the engine ships without one."""
    from offsetx_apollo_builder.outreach.engine import OutreachEngine

    engine = OutreachEngine(tmp_path / "outreach.db")
    assert engine.template_counter is None
    engine._count_send({"template_id": "t", "variant_id": "A"})
    engine._count_reply({"template_id": "t", "variant_id": "A"})
    engine.close()
