"""S-06.02.34 — provider-reported amounts are not local quota guesses."""
from __future__ import annotations

import json
from unittest.mock import MagicMock

import pytest

from offsetx_apollo_builder.ai.provider_usage import UsageReportError, fetch_provider_balance


def response(payload, status=200):
    result = MagicMock()
    result.status_code = status
    result.iter_content.return_value = [json.dumps(payload).encode("utf-8")]
    return result


@pytest.mark.parametrize(
    ("provider", "payload", "expected"),
    [
        ("openrouter", {"data": {"limit_remaining": 74.5}}, ("74.5", "USD")),
        ("deepseek", {"is_available": True, "balance_infos": [
            {"currency": "CNY", "total_balance": "110.00"}]}, ("110.00", "CNY")),
    ],
)
def test_documented_provider_balances_are_labeled_and_timestamped(provider, payload, expected):
    sess = MagicMock()
    sess.get.return_value = response(payload)
    value = fetch_provider_balance(provider, "test-key", session=sess)
    assert (value["remaining"], value["unit"]) == expected
    assert value["source"] == "provider_reported"
    assert value["checked_at"].endswith("+00:00")
    options = sess.get.call_args.kwargs
    assert options["allow_redirects"] is False
    assert options["stream"] is True
    assert options["headers"]["Authorization"] == "Bearer test-key"
    assert sess.get.call_args.args[0].startswith("https://")
    sess.get.return_value.close.assert_called_once()


def test_no_key_spend_cap_is_not_presented_as_unlimited_account_credit():
    sess = MagicMock()
    sess.get.return_value = response({"data": {"limit_remaining": None}})
    value = fetch_provider_balance("openrouter", "test-key", session=sess)
    assert value["remaining"] is None
    assert value["available"] is False


@pytest.mark.parametrize("payload", [{"data": {"limit_remaining": -5}},
                                      {"data": {"limit_remaining": "NaN"}},
                                      {"data": {"limit_remaining": "not-a-number"}}])
def test_malformed_balances_do_not_create_fake_amounts(payload):
    sess = MagicMock()
    sess.get.return_value = response(payload)
    with pytest.raises(UsageReportError):
        fetch_provider_balance("openrouter", "test-key", session=sess)


def test_no_arbitrary_provider_or_endpoint_is_contacted():
    sess = MagicMock()
    with pytest.raises(UsageReportError):
        fetch_provider_balance("unknown", "test-key", session=sess)
    sess.get.assert_not_called()


def test_provider_http_error_does_not_leak_provider_body_or_key():
    sess = MagicMock()
    sess.get.return_value = response({"error": "private-key-content"}, status=401)
    with pytest.raises(UsageReportError) as caught:
        fetch_provider_balance("deepseek", "test-key", session=sess)
    assert "private-key-content" not in str(caught.value)
    assert "test-key" not in str(caught.value)


def test_balance_responses_are_size_limited():
    sess = MagicMock()
    sess.get.return_value = response({})
    sess.get.return_value.iter_content.return_value = [b"x" * 17000]
    with pytest.raises(UsageReportError, match="too large"):
        fetch_provider_balance("deepseek", "test-key", session=sess)
