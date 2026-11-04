"""A10: priced provider calls must not become free because receipt data is bad."""
from __future__ import annotations

from pathlib import Path

import pytest

from offsetx_apollo_builder.ai.broker import EgressBroker, WorkspaceEgressSettings, measure
from offsetx_apollo_builder.ai.errors import NoPermittedProvider
from offsetx_apollo_builder.ai.payload import EgressRequest
from offsetx_apollo_builder.ai.quota import QuotaLimits, QuotaTracker
from offsetx_apollo_builder.ai.registry import ModelEntry, ProviderRegistry
from offsetx_apollo_builder.ai.tiers import DataClass
from offsetx_apollo_builder.outreach.providers import read_usage


class _PaidProvider:
    """Controlled external boundary: records transport, not a fake success claim."""

    def __init__(self, receipt, calls):
        self.last_usage = receipt
        self.calls = calls

    def generate(self, *, system_prompt, user_prompt):
        self.calls.append((system_prompt, len(user_prompt)))
        return "A priced response, not a free result."


def _settings(usd_cap):
    return WorkspaceEgressSettings(
        workspace_id="a10-cost-audit",
        enabled_provider_ids=("mistral",),
        quota_limits={"mistral": QuotaLimits(max_spend_usd_per_day=usd_cap)},
    )


def _broker(tmp_path: Path, receipt, calls):
    broker = EgressBroker(
        registry=ProviderRegistry(Path(__file__).resolve().parents[1] / "config" / "providers.yaml"),
        credential_resolver=lambda _: "synthetic-paid-key-never-sent",
        quota=QuotaTracker(tmp_path / "quota"),
        max_retries=0,
    )
    broker._instantiate = lambda _: _PaidProvider(receipt, calls)
    return broker


def _request():
    # A substantial input ensures fallback accounting cannot round down to $0.
    return EgressRequest(
        task_type="a10-regression",
        data_class=DataClass.PUBLIC,
        instructions="public test content " * 600,
    )


def _usage_on_reopen(broker, tmp_path, settings):
    candidates, rejected = broker.plan(_request(), settings)
    assert candidates, rejected
    candidate = candidates[0]
    return QuotaTracker(tmp_path / "quota").usage(
        "mistral",
        settings.quota_limits["mistral"],
        scope_id=broker._quota_scope_id(candidate, settings.workspace_id),
        workspace_scope_id=broker._quota_workspace_scope("mistral", settings.workspace_id),
    )


def test_A10_valid_provider_receipt_is_charged_and_survives_restart(tmp_path):
    """A10: a paid call consumes the configured daily USD allowance."""
    wire = []
    settings = _settings(0.80)  # $0.768 context reservation fits once.
    broker = _broker(tmp_path, {"tokens_in": 10000, "tokens_out": 20000}, wire)
    result = broker.call(_request(), settings, system_prompt="plain public answer")
    assert result.provider_id == "mistral"
    assert result.usage_source == "provider"
    assert (result.tokens_in, result.tokens_out) == (10000, 20000)
    assert result.cost_usd == pytest.approx(0.14)
    assert len(wire) == 1

    observed = _usage_on_reopen(broker, tmp_path, settings)
    assert observed["day_spend_usd"] == pytest.approx(0.14)
    assert observed["day_reserved_usd"] == pytest.approx(0.0)

    restarted = _broker(tmp_path, {"tokens_in": 10000, "tokens_out": 20000}, wire)
    with pytest.raises(NoPermittedProvider, match="spend|quota|cost|limit"):
        restarted.call(_request(), settings, system_prompt="plain public answer")
    assert len(wire) == 1, "restarting must never restore a spent daily allowance"


@pytest.mark.parametrize("receipt", [
    {"tokens_in": 0, "tokens_out": 0},
    {"tokens_in": "invalid", "tokens_out": 3},
    {"tokens_in": float("nan"), "tokens_out": 3},
    {"tokens_in": -2, "tokens_out": -3},
], ids=["all-zero", "malformed", "nonfinite", "negative"])
def test_A10_invalid_receipt_estimates_nonzero_spend_and_refuses_next_transport(tmp_path, receipt):
    """A10: invalid usage cannot become a confirmed free bill or a post-send 500."""
    wire = []
    settings = _settings(0.769)
    broker = _broker(tmp_path, receipt, wire)
    result = broker.call(_request(), settings, system_prompt="plain public answer")
    assert result.usage_source == "estimated"
    assert result.tokens_in > 0 and result.tokens_out > 0
    assert result.cost_usd > 0.001
    assert len(wire) == 1

    restarted = _broker(tmp_path, receipt, wire)
    with pytest.raises(NoPermittedProvider, match="spend|quota|cost|limit"):
        restarted.call(_request(), settings, system_prompt="plain public answer")
    assert len(wire) == 1


@pytest.mark.parametrize("raw", [
    {"input_tokens": 0, "output_tokens": 0},
    {"input_tokens": float("inf"), "output_tokens": 20},
    {"input_tokens": True, "output_tokens": 20},
])
def test_A10_bad_provider_usage_blocks_cannot_look_like_valid_receipts(raw):
    """A10: raw adapter usage must not throw or call its invalid numbers a receipt."""
    assert read_usage({"usage": raw}) == {}


def test_A10_legitimate_zero_output_keeps_the_input_token_receipt():
    """An input-only paid request is not the same as a fabricated all-zero bill."""
    assert read_usage({"usage": {"input_tokens": 100, "output_tokens": 0}}) == {
        "tokens_in": 100, "tokens_out": 0,
    }
    priced = ModelEntry(id="m", cost_per_1m_input_usd=2, cost_per_1m_output_usd=6)
    assert measure(priced, reported={"tokens_in": 100, "tokens_out": 0},
                   sent="request", received="")[3] == "provider"
