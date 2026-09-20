from __future__ import annotations

import inspect
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
    build_payload,
)
from offsetx_apollo_builder.ai.scanner import scan_model_input


ROOT = Path(__file__).resolve().parents[1]


def _broker(tmp_path):
    return EgressBroker(
        registry=ProviderRegistry(ROOT / "config" / "providers.yaml"),
        credential_resolver=lambda _provider_id: "transport-key-that-is-not-a-prompt",
    )


def _settings(provider_id: str) -> WorkspaceEgressSettings:
    return WorkspaceEgressSettings(
        workspace_id="local",
        enabled_provider_ids=(provider_id,),
        cross_tier_public_routing=False,
    )


@pytest.mark.parametrize("policy", list(DataPolicy))
def test_representative_safe_payload_scans_clean_after_construction(policy):
    request = EgressRequest(
        task_type="summarise",
        data_class=DataClass.PUBLIC,
        instructions="Summarise the public release notes.",
        public_text="Version 2 improves import speed and error messages.",
        task_tags=("release",),
    )
    payload = build_payload(request, policy)
    report = scan_model_input(
        payload,
        system_prompt="Return a short factual summary.",
        policy=policy,
        allow_addresses=policy is DataPolicy.FULL,
    )
    assert report.clean, report.summary()


def test_credential_shaped_field_surviving_full_payload_is_still_blocked():
    request = EgressRequest(
        task_type="debug",
        data_class=DataClass.PUBLIC,
        unrestricted={"access_token": "opaque-but-secret-value"},
    )
    payload = build_payload(request, DataPolicy.FULL)
    report = scan_model_input(
        payload,
        policy=DataPolicy.FULL,
        allow_addresses=True,
    )
    assert not report.clean
    assert any(item.kind == "credential" for item in report.findings)


def test_secret_in_system_prompt_blocks_before_provider_instantiation(tmp_path, monkeypatch):
    broker = _broker(tmp_path)
    monkeypatch.setattr(
        broker,
        "_instantiate",
        lambda candidate, **kwargs: pytest.fail("provider was instantiated"),
    )
    request = EgressRequest(
        task_type="write_code",
        data_class=DataClass.PUBLIC,
        public_text="Write a safe hello-world function.",
    )

    with pytest.raises(EgressBlocked) as excinfo:
        broker.call(
            request,
            _settings("mistral"),
            system_prompt="Authorization: Bearer abcdefghijklmnopqrstuvwxyz123456",
        )

    assert any(item["kind"] == "credential" for item in excinfo.value.findings)
    assert any("system_prompt" in item["location"] for item in excinfo.value.findings)


def test_secret_in_image_prompt_blocks_before_image_provider_instantiation(tmp_path, monkeypatch):
    broker = _broker(tmp_path)
    monkeypatch.setattr(
        broker,
        "_instantiate",
        lambda candidate, **kwargs: pytest.fail("image provider was instantiated"),
    )
    request = EgressRequest(
        task_type="image",
        data_class=DataClass.PUBLIC,
        instructions="Draw a diagram. token=abcdefghijklmnop1234567890",
    )

    with pytest.raises(EgressBlocked):
        broker.call_image(request, _settings("nvidia"), provider_id="nvidia")


@pytest.mark.parametrize(
    "metadata",
    [
        {"filename": "password=supersecret-recording.wav"},
        {"language": "Bearer abcdefghijklmnopqrstuvwxyz123456"},
        {"media_type": "token=abcdefghijklmnop1234567890"},
    ],
)
def test_secret_in_transcription_metadata_blocks_before_provider_instantiation(
    tmp_path, monkeypatch, metadata
):
    broker = _broker(tmp_path)
    monkeypatch.setattr(
        broker,
        "_instantiate",
        lambda candidate, **kwargs: pytest.fail("transcription provider was instantiated"),
    )
    request = EgressRequest(
        task_type="transcribe",
        data_class=DataClass.PUBLIC,
        instructions="Transcribe this public recording.",
    )
    arguments = {
        "audio": b"not-real-audio-but-the-provider-must-never-see-it",
        "filename": "audio.webm",
        "media_type": "audio/webm",
        "language": "en",
        **metadata,
    }

    with pytest.raises(EgressBlocked) as excinfo:
        broker.call_transcript(
            request,
            _settings("openai"),
            provider_id="openai",
            **arguments,
        )

    assert any(item["kind"] == "credential" for item in excinfo.value.findings)
    assert any("transport_text" in item["location"] for item in excinfo.value.findings)


def test_every_provider_prompt_path_scans_before_provider_io():
    for method_name, provider_marker in (
        ("call", "provider.generate("),
        ("call_image", "provider.generate_images("),
        ("call_transcript", "provider.transcribe("),
    ):
        source = inspect.getsource(getattr(EgressBroker, method_name))
        assert "scan_model_input(" in source, method_name
        assert source.index("scan_model_input(") < source.index(provider_marker), method_name


def test_transport_api_key_is_not_added_to_model_visible_input():
    key = "sk-transport-only-abcdefghijklmnopqrstuvwxyz"
    request = EgressRequest(
        task_type="write_code",
        data_class=DataClass.PUBLIC,
        public_text="Return the number one.",
    )
    payload = build_payload(request, DataPolicy.MINIMAL)
    report = scan_model_input(payload, system_prompt="Answer briefly.")

    assert key not in repr(payload)
    assert report.clean
