"""Acceptance tests for S-06.02.01: no secret may enter a model prompt.

The important boundary is the provider call, not an individual payload builder.
A credential is blocked whether it appears in structured user payload, the
separate system prompt, or text metadata sent beside an audio transcription.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from offsetx_apollo_builder.ai import (
    DataClass,
    DataPolicy,
    EgressBlocked,
    EgressBroker,
    EgressRequest,
    ProviderRegistry,
    WorkspaceEgressSettings,
    scan_payload,
)

REPO_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture()
def broker() -> EgressBroker:
    return EgressBroker(
        registry=ProviderRegistry(REPO_ROOT / "config" / "providers.yaml"),
        credential_resolver=lambda provider_id: "test-provider-key",
    )


def _settings(provider_id: str, *, policy: DataPolicy | None = None) -> WorkspaceEgressSettings:
    policies = {provider_id: policy} if policy is not None else {}
    return WorkspaceEgressSettings(
        workspace_id="security-test",
        enabled_provider_ids=(provider_id,),
        default_policy_by_provider=policies,
    )


def _must_not_instantiate(*args, **kwargs):  # pragma: no cover - failure path only
    pytest.fail("provider was instantiated after the secret gate should have blocked")


def test_chat_system_prompt_secret_is_blocked_before_provider_instantiation(
    broker: EgressBroker, monkeypatch: pytest.MonkeyPatch
) -> None:
    """D-51: the system prompt is a second provider-bound string.

    Scanning only the JSON user payload is insufficient because providers receive
    both strings.  A credential in either one must stop before the adapter exists.
    """
    monkeypatch.setattr(broker, "_instantiate", _must_not_instantiate)
    request = EgressRequest(task_type="security-test", data_class=DataClass.PUBLIC)

    with pytest.raises(EgressBlocked) as excinfo:
        broker.call(
            request,
            _settings("mistral"),
            system_prompt="Use sk-abcdefghijklmnop1234567890 to call the tool.",
        )

    assert any(item["kind"] == "credential" for item in excinfo.value.findings)
    assert any(item.get("location") == "$.system_prompt" for item in excinfo.value.findings)


def test_full_policy_never_relaxes_system_prompt_credentials(
    broker: EgressBroker, monkeypatch: pytest.MonkeyPatch
) -> None:
    """FULL may widen business fields; it never authorises credentials."""
    monkeypatch.setattr(broker, "_instantiate", _must_not_instantiate)
    request = EgressRequest(task_type="security-test", data_class=DataClass.PUBLIC)

    with pytest.raises(EgressBlocked):
        broker.call(
            request,
            _settings("mistral", policy=DataPolicy.FULL),
            system_prompt="Authorization: Bearer abcdefghijklmnopqrstuvwxyz123456",
        )


def test_secret_field_names_are_canonicalised_before_matching() -> None:
    """D-52: naming style must not decide whether a secret is recognised."""
    variants = (
        "clientSecret",
        "client-secret",
        "client_secret",
        "secretAccessKey",
        "x-api-key",
        "AuthorizationHeader",
    )
    for field_name in variants:
        report = scan_payload({field_name: "opaque-value-with-no-special-shape"})
        assert not report.clean, field_name
        assert any(item.kind == "credential" for item in report.findings), field_name


def test_common_secret_assignment_and_basic_auth_shapes_are_blocked() -> None:
    for text in (
        "client_secret=opaque-but-private-value",
        "api-key: opaque-but-private-value",
        "Authorization: Basic QWxhZGRpbjpvcGVuIHNlc2FtZQ==",
    ):
        report = scan_payload({"instructions": text})
        assert not report.clean, text
        assert any(item.kind == "credential" for item in report.findings), text


def test_off_crm_environment_variable_names_are_blocked() -> None:
    report = scan_payload({"instructions": "read OFF_CRM_MASTER_KEY before continuing"})
    assert not report.clean
    assert any(item.kind == "environment_variable" for item in report.findings)


def test_transcription_metadata_is_scanned_before_provider_instantiation(
    broker: EgressBroker, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Filename/language/media-type leave outside the normal payload object.

    They are still text crossing the provider boundary, so they receive the same
    pre-flight treatment as the vocabulary prompt.
    """
    monkeypatch.setattr(broker, "_instantiate", _must_not_instantiate)
    request = EgressRequest(task_type="transcribe", data_class=DataClass.PUBLIC)

    with pytest.raises(EgressBlocked) as excinfo:
        broker.call_transcript(
            request,
            _settings("groq"),
            audio=b"not-sent-because-metadata-blocks-first",
            filename="password=supersecret.webm",
        )

    assert any(item["kind"] == "credential" for item in excinfo.value.findings)
    assert any(item.get("location") == "$.filename" for item in excinfo.value.findings)


def test_image_prompt_never_falls_back_to_unscanned_request_text(
    broker: EgressBroker, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The provider receives only the prompt that survived payload construction.

    A future payload policy may deliberately omit instructions.  The image path
    must not then reach back to the raw request and bypass the scanner.
    """
    from offsetx_apollo_builder.ai import broker as broker_module

    sent: list[str] = []

    class _ImageProvider:
        def generate_images(self, *, prompt: str) -> list[str]:
            sent.append(prompt)
            return ["image"]

    monkeypatch.setattr(
        broker_module,
        "build_payload",
        lambda request, policy, **kwargs: {
            "schema_version": 1,
            "task": "image",
            "recipient_token": "RECIPIENT_1",
            "sender_token": "SENDER",
        },
    )
    monkeypatch.setattr(
        broker,
        "_instantiate",
        lambda candidate, adapter_override="": _ImageProvider(),
    )

    request = EgressRequest(
        task_type="image",
        data_class=DataClass.PUBLIC,
        instructions="api_key=opaque-but-private-value",
    )
    image_settings = WorkspaceEgressSettings(
        workspace_id="security-test",
        enabled_provider_ids=("nvidia",),
        enabled_models={"nvidia": ("black-forest-labs/flux.1-dev",)},
    )
    result = broker.call_image(request, image_settings)

    assert result.prompt == ""
    assert sent == [""]


def test_secret_samples_are_masked_in_findings() -> None:
    secret = "sk-abcdefghijklmnop1234567890"
    report = scan_payload({"instructions": f"use {secret}"})
    assert not report.clean
    rendered = str(report.to_dict())
    assert secret not in rendered
    assert "sk-a" in rendered
