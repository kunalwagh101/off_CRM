"""Bounded, on-demand provider balance checks; never a model call.

Only documented, hard-coded HTTPS endpoints are allowed. The registry can
describe support but must not provide arbitrary URLs for a customer's API key.
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Any

import requests


ENDPOINTS = {
    "openrouter": "https://openrouter.ai/api/v1/key",
    "deepseek": "https://api.deepseek.com/user/balance",
}
MAX_RESPONSE_BYTES = 16 * 1024


class UsageReportError(ValueError):
    """A provider's real balance could not be checked."""


def _amount(value: object) -> str:
    if value is None or isinstance(value, bool):
        raise UsageReportError("Provider did not supply an available numeric balance")
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise UsageReportError("Provider supplied an invalid balance") from exc
    if not amount.is_finite() or amount < 0:
        raise UsageReportError("Provider supplied an invalid balance")
    return str(amount)


def fetch_provider_balance(
    provider_id: str, api_key: str, *, session: Any = None
) -> dict[str, Any]:
    """Check a key's reported remaining amount, with no prompts or customer data."""
    url = ENDPOINTS.get(provider_id)
    if not url:
        raise UsageReportError("This provider has no supported balance endpoint")
    if not api_key:
        raise UsageReportError("Connect the provider key before checking its balance")
    client = session if session is not None else requests.Session()
    own_client = session is None
    if own_client:
        client.trust_env = False  # do not send a key through ambient proxies
    try:
        response = client.get(
            url,
            headers={"Authorization": f"Bearer {api_key}", "Accept": "application/json"},
            timeout=(3, 8),
            allow_redirects=False,
            stream=True,
        )
        try:
            if response.status_code != 200:
                raise UsageReportError(
                    "The provider did not accept the balance check; verify the connected key"
                )
            chunks: list[bytes] = []
            size = 0
            for chunk in response.iter_content(chunk_size=4096):
                size += len(chunk)
                if size > MAX_RESPONSE_BYTES:
                    raise UsageReportError("Provider balance response is too large")
                chunks.append(chunk)
            try:
                payload = json.loads(b"".join(chunks))
            except (json.JSONDecodeError, UnicodeDecodeError) as exc:
                raise UsageReportError("Provider returned an invalid balance response") from exc
        finally:
            response.close()
    except requests.RequestException as exc:
        raise UsageReportError("Provider balance check could not connect securely") from exc
    finally:
        if own_client:
            client.close()
    checked_at = datetime.now(timezone.utc).isoformat()
    if not isinstance(payload, dict):
        raise UsageReportError("Provider returned an invalid balance response")
    if provider_id == "openrouter":
        data = payload.get("data")
        if not isinstance(data, dict):
            raise UsageReportError("Provider returned an invalid balance response")
        if data.get("limit_remaining") is None:
            return {
                "provider_id": provider_id, "source": "provider_reported",
                "kind": "key_spend_limit", "available": False, "remaining": None,
                "unit": "USD", "checked_at": checked_at,
                "description": "No per-key spend limit reported; not an account credit balance",
            }
        remaining = _amount(data["limit_remaining"])
        kind = "key_spend_limit"
        unit = "USD"
    else:
        infos = payload.get("balance_infos")
        if not isinstance(infos, list) or not infos:
            raise UsageReportError("Provider returned no balance entries")
        selected = next((row for row in infos if isinstance(row, dict)
                         and row.get("currency") == "USD"), infos[0])
        if not isinstance(selected, dict):
            raise UsageReportError("Provider returned an invalid balance response")
        unit = str(selected.get("currency", ""))
        if unit not in {"USD", "CNY"}:
            raise UsageReportError("Provider returned an unknown balance currency")
        remaining = _amount(selected.get("total_balance"))
        kind = "account_balance"
    return {
        "provider_id": provider_id,
        "source": "provider_reported",
        "kind": kind,
        "available": True,
        "remaining": remaining,
        "unit": unit,
        "checked_at": checked_at,
    }
