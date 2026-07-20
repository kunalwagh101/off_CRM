from __future__ import annotations

import pytest

from offsetx_apollo_builder.outreach.models import ProviderConfig
from offsetx_apollo_builder.outreach.providers import (
    FallbackAIProvider,
    ProviderError,
    _validate_http_url,
    create_provider,
)


class _FixedProvider:
    def __init__(self, value=None, error=None):
        self.value = value
        self.error = error
        self.calls = 0

    def generate(self, **_kwargs):
        self.calls += 1
        if self.error:
            raise self.error
        return self.value


class _Response:
    ok = True
    status_code = 200
    text = ""

    def json(self):
        return {"output_text": "provider output"}


class _Session:
    def __init__(self):
        self.calls = []

    def post(self, url, **kwargs):
        self.calls.append((url, kwargs))
        return _Response()


def test_provider_credentials_are_read_from_named_environment_only():
    session = _Session()
    provider = create_provider(
        ProviderConfig(
            provider_type="openai",
            model="test-model",
            api_key_env="MY_TEST_KEY",
        ),
        environ={"MY_TEST_KEY": "secret"},
        session=session,
    )
    assert provider.generate(system_prompt="system", user_prompt="user") == "provider output"
    assert session.calls[0][0] == "https://api.openai.com/v1/responses"
    assert session.calls[0][1]["headers"]["Authorization"] == "Bearer secret"


def test_provider_url_validation_blocks_plain_remote_http_and_embedded_credentials():
    assert _validate_http_url("http://127.0.0.1:8080/v1") == "http://127.0.0.1:8080/v1"
    with pytest.raises(ProviderError, match="loopback"):
        _validate_http_url("http://example.com/v1")
    with pytest.raises(ProviderError, match="embedded credentials"):
        _validate_http_url("https://user:pass@example.com/v1")


def test_missing_provider_key_fails_before_network_call():
    with pytest.raises(ProviderError, match="Missing AI credential"):
        create_provider(
            ProviderConfig(
                provider_type="anthropic",
                model="test-model",
                api_key_env="ANTHROPIC_API_KEY",
            ),
            environ={},
        )


def test_fallback_provider_uses_next_provider_after_outage():
    failed = _FixedProvider(error=ProviderError("rate limited"))
    healthy = _FixedProvider(value='{"subject":"Hello","body":"Useful body"}')
    router = FallbackAIProvider([("primary", failed), ("fallback", healthy)])

    result = router.generate(system_prompt="system", user_prompt="user")

    assert '"schema_version": 1' in result
    assert failed.calls == 1
    assert healthy.calls == 1
    assert router.last_run["selected_profile_id"] == "fallback"


def test_fallback_provider_rejects_malformed_output_and_continues():
    malformed = _FixedProvider(value="not json")
    healthy = _FixedProvider(value='{"subject":"Valid","body":"Valid body"}')
    router = FallbackAIProvider([("malformed", malformed), ("healthy", healthy)])

    result = router.generate(system_prompt="system", user_prompt="user")

    assert '"subject": "Valid"' in result
    assert router.last_run["attempts"][0]["status"] == "failed"
