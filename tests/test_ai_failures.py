"""Failure classification, and what the broker does with it.

Before this, every provider failure was treated identically: record it, move to
the next candidate, cool the model off after two. That is correct for exactly
one kind of failure — a provider having a bad day — and wrong for the rest.

The three that cost real money:

- **A broken API key looked like a busy provider.** A 401 failed over silently
  to the next model, which worked, so nobody found out.
- **A payload we built wrong took out healthy providers.** A 400 is our bug;
  another model rejects it identically, and the circuit breaker opened on each
  one on the way past.
- **A rate limit fell through to another provider's quota**, which is the
  expensive answer to a problem that a short wait solves for free.

So the tests here are in two halves: the classifier maps a message to a kind,
and the broker turns a kind into the right *action* — including refusing to
fail over when failing over is what hid the problem.
"""
from __future__ import annotations

import time
from pathlib import Path

import pytest

from offsetx_apollo_builder.ai.broker import EgressBroker
from offsetx_apollo_builder.ai.errors import NoPermittedProvider, ProviderFailure
from offsetx_apollo_builder.ai.failures import (
    PROVIDER_HEALTH_KINDS,
    Failure,
    FailureAction,
    FailureKind,
    classify,
    describe_kinds,
)
from offsetx_apollo_builder.ai.log import EgressLog
from offsetx_apollo_builder.ai.payload import EgressRequest, PersonPublic
from offsetx_apollo_builder.ai.quota import QuotaTracker
from offsetx_apollo_builder.ai.registry import ProviderRegistry
from offsetx_apollo_builder.ai.tiers import DataClass

REPO_ROOT = Path(__file__).resolve().parents[1]

PERSON = PersonPublic.from_contact(
    {
        "full_name": "Ana Rao",
        "company": "Meridian Foods",
        "title": "Head of Trade",
        "category": "importer",
        "public_hook": "spoke at the EU trade summit",
    }
)


# ─────────────────────────────────────────────────────────────────────────────
# Classification
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "message,kind",
    [
        ("AI provider returned 401: invalid api key", FailureKind.AUTH),
        ("AI provider returned 403: forbidden", FailureKind.AUTH),
        ("AI provider returned 402: insufficient credit", FailureKind.PAYMENT),
        ("AI provider returned 404: model meta/llama-9 does not exist", FailureKind.MODEL_NOT_FOUND),
        ("AI provider returned 429: rate limit exceeded", FailureKind.RATE_LIMITED),
        ("AI provider returned 500: internal error", FailureKind.SERVER_ERROR),
        ("AI provider returned 503: upstream overloaded", FailureKind.OVERLOADED),
        ("AI provider returned 400: context length exceeded", FailureKind.CONTEXT_LENGTH),
        ("The model ran out of room. Raise max_tokens", FailureKind.TRUNCATED),
        ("did not contain message content (finish_reason: content_filter)", FailureKind.CONTENT_FILTER),
        ("OpenAI response did not contain text output", FailureKind.EMPTY_RESPONSE),
        ("AI provider returned a non-JSON response", FailureKind.MALFORMED_RESPONSE),
        ("ConnectionError(Connection refused)", FailureKind.CONNECTION),
        ("the request timed out", FailureKind.TIMEOUT),
        ("something nobody has ever seen before", FailureKind.UNKNOWN),
    ],
)
def test_real_provider_messages_are_classified(message, kind):
    assert classify(message).kind is kind


def test_connection_refused_is_not_a_content_filter():
    """The regression that made the case for precise patterns.

    `refus` as a pattern matched "Connection refused" and filed a dead network
    as a content filter — which would fail over politely instead of reporting
    that nothing could be reached. Patterns on an error path are exercised by
    text nobody chose, so each alternative has to be wrong about only what it
    is for.
    """
    assert classify("ConnectionError(Connection refused)").kind is FailureKind.CONNECTION
    assert classify("the model refused to answer").kind is FailureKind.CONTENT_FILTER


def test_a_retry_after_hint_is_read_and_bounded():
    """Waiting the time the server named beats guessing, but not indefinitely."""
    assert classify("429: rate limited, retry-after 12").retry_after == 12.0
    assert classify("429: retry after 99999").retry_after == 300.0
    assert classify("429: no hint given").retry_after is None


def test_a_status_is_only_read_from_the_shape_providers_actually_use():
    """`ProviderError` is a plain RuntimeError; the status lives in the text.

    Only `returned NNN` is trusted. A bare three-digit number elsewhere is far
    more likely to be part of the provider's prose than its status code.
    """
    assert classify("AI provider returned 429: slow down").status_code == 429
    assert classify("the model produced 404 words of nonsense").status_code is None


def test_an_unknown_error_fails_over_but_does_not_retry():
    """Default-deny applied to spending.

    An error nobody has classified, retried three times, costs three times as
    much with no particular reason to succeed.
    """
    failure = classify("something nobody has ever seen before")
    assert failure.kind is FailureKind.UNKNOWN
    assert failure.action is FailureAction.FAILOVER


@pytest.mark.parametrize(
    "kind",
    [FailureKind.AUTH, FailureKind.PAYMENT, FailureKind.MODEL_NOT_FOUND, FailureKind.TRUNCATED],
)
def test_configuration_failures_stop_rather_than_fail_over(kind):
    """Failing over is what made these invisible."""
    entry = next(item for item in describe_kinds() if item["kind"] == kind.value)
    assert entry["action"] == FailureAction.STOP_CONFIG.value
    assert entry["owner_action"], "a stop must tell the owner what to do"


def test_request_failures_stop_because_another_model_fails_identically():
    for kind in (FailureKind.BAD_REQUEST, FailureKind.CONTEXT_LENGTH):
        entry = next(item for item in describe_kinds() if item["kind"] == kind.value)
        assert entry["action"] == FailureAction.STOP_REQUEST.value


def test_only_provider_health_counts_against_a_provider():
    """A payload we built wrong says nothing about their service.

    Letting it open the circuit breaker means one malformed request can take
    every model in the tier out of service for a minute.
    """
    assert FailureKind.BAD_REQUEST not in PROVIDER_HEALTH_KINDS
    assert FailureKind.CONTEXT_LENGTH not in PROVIDER_HEALTH_KINDS
    assert FailureKind.AUTH not in PROVIDER_HEALTH_KINDS
    assert FailureKind.SERVER_ERROR in PROVIDER_HEALTH_KINDS
    assert FailureKind.TIMEOUT in PROVIDER_HEALTH_KINDS


def test_every_kind_has_an_action():
    kinds = {item["kind"] for item in describe_kinds()}
    assert kinds == {kind.value for kind in FailureKind}
    for item in describe_kinds():
        assert item["action"] in {action.value for action in FailureAction}


def test_classifying_never_raises():
    """This runs on the error path.

    A classifier that raises while classifying replaces a useful message with a
    useless one.
    """
    for value in (None, "", 0, object(), ValueError("x"), b"bytes"):
        assert isinstance(classify(value), Failure)


# ─────────────────────────────────────────────────────────────────────────────
# What the broker does with it
# ─────────────────────────────────────────────────────────────────────────────


class _Boom:
    """A provider that fails a fixed number of times, then succeeds."""

    def __init__(self, message: str, *, fail_times: int = 99) -> None:
        self.message = message
        self.fail_times = fail_times
        self.calls = 0

    def generate(self, *, system_prompt: str, user_prompt: str) -> str:
        self.calls += 1
        if self.calls <= self.fail_times:
            raise RuntimeError(self.message)
        return "Subject: Hello\n\nA good draft."


@pytest.fixture()
def broker(tmp_path, monkeypatch):
    """A broker whose every provider raises whatever the test scripts."""
    registry = ProviderRegistry(REPO_ROOT / "config" / "providers.yaml")
    log = EgressLog(tmp_path / "egress.sqlite3")
    made = EgressBroker(
        registry=registry,
        credential_resolver=lambda provider_id: "k",
        quota=QuotaTracker(tmp_path),
        logger=log.record,
        deadline_seconds=5.0,
    )
    made._log_store = log  # type: ignore[attr-defined]
    return made


def _settings(**overrides):
    from offsetx_apollo_builder.ai.broker import WorkspaceEgressSettings

    fields = dict(
        workspace_id="local",
        # Both United States, so both are tier B. Failover never crosses a
        # tier boundary, so two candidates means two providers of the *same*
        # tier — an earlier draft of this test used mistral (A) and nvidia (B)
        # and got exactly one candidate, which is the rule working.
        enabled_provider_ids=("openai", "anthropic"),
        owner_domains=(),
        owner_addresses=(),
    )
    fields.update(overrides)
    return WorkspaceEgressSettings(**fields)


def _request():
    return EgressRequest(
        task_type="draft_email", data_class=DataClass.PERSON_PUBLIC, person=PERSON
    )


def _script(broker, provider):
    monkeyed = {}

    def instantiate(candidate):
        monkeyed.setdefault(candidate.id, provider)
        return provider

    broker._instantiate = instantiate  # type: ignore[assignment]
    return monkeyed


def test_a_rejected_key_stops_instead_of_quietly_using_another_model(broker):
    """The failure that motivated the whole module.

    Failing over here worked — which is exactly why nobody noticed the key was
    broken, while every call ran on a model the owner had not chosen.
    """
    provider = _Boom("AI provider returned 401: invalid api key")
    _script(broker, provider)

    with pytest.raises(ProviderFailure) as exc:
        broker.call(_request(), _settings(), system_prompt="write")

    assert exc.value.failure.kind is FailureKind.AUTH
    assert "Connectors" in str(exc.value), "the message must say what to do"
    assert provider.calls == 1, "it must not have tried the second provider"


def test_a_payload_we_built_wrong_stops_and_blames_us(broker):
    provider = _Boom("AI provider returned 400: context length exceeded")
    _script(broker, provider)

    with pytest.raises(ProviderFailure) as exc:
        broker.call(_request(), _settings(), system_prompt="write")

    assert exc.value.failure.kind is FailureKind.CONTEXT_LENGTH
    assert exc.value.failure.action is FailureAction.STOP_REQUEST
    assert provider.calls == 1


def test_a_bad_request_does_not_open_the_circuit_on_a_healthy_provider(broker):
    """One malformed payload must not take the whole tier out of service."""
    provider = _Boom("AI provider returned 400: context length exceeded")
    _script(broker, provider)
    for _ in range(3):
        with pytest.raises(ProviderFailure):
            broker.call(_request(), _settings(), system_prompt="write")
    assert broker._open_until == {}, "no provider was cooled down"
    assert not any(broker._failures.values())


def test_a_server_error_does_fail_over_and_does_count(broker):
    provider = _Boom("AI provider returned 503: upstream overloaded")
    _script(broker, provider)

    with pytest.raises(NoPermittedProvider) as exc:
        broker.call(_request(), _settings(), system_prompt="write")

    assert provider.calls >= 2, "it should have tried more than one provider"
    assert any(broker._failures.values()), "an unhealthy provider is counted"
    assert "overloaded" in str(exc.value).lower() or "503" in str(exc.value)


def test_a_rate_limit_waits_and_retries_the_same_provider(broker):
    """Waiting beats spending another provider's quota on a free problem."""
    provider = _Boom("AI provider returned 429: rate limited, retry-after 0", fail_times=1)
    _script(broker, provider)

    result = broker.call(_request(), _settings(), system_prompt="write")
    assert result.text.startswith("Subject:")
    assert provider.calls == 2, "the same provider was asked again"
    used = [item for item in result.attempts if item.get("status") == "used"]
    assert used and used[0]["provider_id"] == result.provider_id


def test_the_failure_kind_reaches_the_egress_log(broker):
    """Classification is only useful if the pattern is visible later.

    "This provider has been returning auth errors for a week" is a question the
    log can answer with a kind column and cannot answer with a pile of
    500-character strings.
    """
    provider = _Boom("AI provider returned 503: upstream overloaded")
    _script(broker, provider)
    with pytest.raises(NoPermittedProvider):
        broker.call(_request(), _settings(), system_prompt="write")

    log = broker._log_store  # type: ignore[attr-defined]
    kinds = {row["failure_kind"] for row in log.list(limit=50)[0]}
    assert FailureKind.OVERLOADED.value in kinds

    by_failure = {row["failure_kind"]: row["calls"] for row in log.stats()["by_failure"]}
    assert by_failure.get(FailureKind.OVERLOADED.value, 0) >= 1


def test_the_whole_chain_is_bounded_by_a_deadline(broker):
    """The owner's question: does retrying take a lot of time?

    Not more than the deadline. Every attempt, retry and failover shares one
    wall clock, so a slow failure cannot become an unbounded wait.
    """
    broker.deadline_seconds = 0.5

    class Slow:
        calls = 0

        def generate(self, *, system_prompt: str, user_prompt: str) -> str:
            Slow.calls += 1
            time.sleep(0.3)
            raise RuntimeError("AI provider returned 503: upstream overloaded")

    _script(broker, Slow())
    started = time.monotonic()
    with pytest.raises(NoPermittedProvider) as exc:
        broker.call(_request(), _settings(), system_prompt="write")
    elapsed = time.monotonic() - started

    assert elapsed < 3.0, f"took {elapsed:.1f}s despite a 0.5s deadline"
    assert "deadline" in str(exc.value).lower() or Slow.calls >= 1
