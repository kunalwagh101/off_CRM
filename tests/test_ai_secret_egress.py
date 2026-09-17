"""Acceptance tests for S-06.02.01: no credential reaches model-visible egress."""
from __future__ import annotations

import ast
import inspect
import json
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


ROOT = Path(__file__).resolve().parents[1]
BROKER_PATH = ROOT / "offsetx_apollo_builder" / "ai" / "broker.py"


@pytest.fixture()
def registry() -> ProviderRegistry:
    return ProviderRegistry(ROOT / "config" / "providers.yaml")


@pytest.fixture()
def broker(registry: ProviderRegistry) -> EgressBroker:
    return EgressBroker(
        registry=registry,
        credential_resolver=lambda _provider_id: "test-key",
    )


def _settings() -> WorkspaceEgressSettings:
    return WorkspaceEgressSettings(
        workspace_id="local",
        enabled_provider_ids=("mistral",),
    )


def test_system_prompt_secret_is_blocked_before_provider_instantiation(broker, monkeypatch):
    """D-51: system_prompt used to bypass the payload-only scanner entirely."""
    monkeypatch.setattr(
        broker,
        "_instantiate",
        lambda _candidate, **_kwargs: pytest.fail("provider instantiated before preflight"),
    )
    request = EgressRequest(
        task_type="write_code",
        data_class=DataClass.PUBLIC,
        public_text="Explain stable sorting.",
    )

    with pytest.raises(EgressBlocked) as excinfo:
        broker.call(
            request,
            _settings(),
            system_prompt="Follow the task. OPENAI_API_KEY=opaque-secret-value-12345",
        )

    assert any(item["kind"] == "credential" for item in excinfo.value.findings)
    assert any(item["location"] == "$.system_prompt" for item in excinfo.value.findings)


def test_blocked_system_prompt_never_writes_the_secret_to_the_egress_log(registry):
    rows: list[dict] = []
    broker = EgressBroker(
        registry=registry,
        credential_resolver=lambda _provider_id: "test-key",
        logger=lambda **record: rows.append(record) or "log-1",
    )
    secret = "client_secret=never-store-this-secret-value"
    request = EgressRequest(
        task_type="write_code",
        data_class=DataClass.PUBLIC,
        public_text="Explain stable sorting.",
    )

    with pytest.raises(EgressBlocked):
        broker.call(request, _settings(), system_prompt=f"Rules: {secret}")

    assert rows and rows[-1]["status"] == "blocked"
    assert secret not in json.dumps(rows[-1])
    assert "never-store-this-secret-value" not in json.dumps(rows[-1])


@pytest.mark.parametrize(
    "text",
    [
        "api_key=opaque-secret-value-12345",
        "OPENAI_API_KEY=opaque-secret-value-12345",
        "Authorization: Basic QWxhZGRpbjpPcGVuU2VzYW1l",
        "https://alice:supers3cret@example.com/private",
        "oauth_token=opaque-oauth-token-value",
    ],
)
def test_generic_credential_shapes_are_blocked_even_without_provider_prefixes(text):
    report = scan_payload({"text": text}, policy=DataPolicy.FULL, allow_addresses=True)
    assert not report.clean, text
    assert any(item.kind == "credential" for item in report.findings), text


def test_credential_shaped_field_name_is_blocked_even_when_value_is_opaque():
    report = scan_payload(
        {"nested": {"client_secret": "not-a-recognisable-provider-prefix"}},
        policy=DataPolicy.FULL,
        allow_addresses=True,
    )
    assert any(item.kind == "credential" for item in report.findings)


def test_transcription_metadata_is_inside_the_same_preflight_wall(broker):
    request = EgressRequest(
        task_type="transcribe",
        data_class=DataClass.PUBLIC,
        instructions="Transcribe this recording.",
    )
    candidates, _ = broker.plan(request, _settings())
    candidate = candidates[0]

    with pytest.raises(EgressBlocked) as excinfo:
        broker._preflight(
            settings=_settings(),
            candidate=candidate,
            request=request,
            payload={"instructions": "Transcribe this recording."},
            provider_text={"filename": "client_secret=opaque-secret-value.webm"},
        )

    assert any(item["location"] == "$.filename" for item in excinfo.value.findings)
    assert any(item["kind"] == "credential" for item in excinfo.value.findings)


def test_every_broker_provider_instantiation_is_preceded_by_preflight():
    """Future provider paths join the wall by construction, not by memory.

    Any EgressBroker method that instantiates a provider is an outbound seam. If
    a fourth seam is added later without `_preflight`, this test fails even if
    nobody remembered to add a hand-written case for its method name.
    """
    tree = ast.parse(BROKER_PATH.read_text(encoding="utf-8"), filename=str(BROKER_PATH))
    broker_class = next(
        node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "EgressBroker"
    )
    guarded: set[str] = set()

    for function in broker_class.body:
        if not isinstance(function, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        instantiate_lines = [
            node.lineno
            for node in ast.walk(function)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == "self"
            and node.func.attr == "_instantiate"
        ]
        if not instantiate_lines:
            continue
        preflight_lines = [
            node.lineno
            for node in ast.walk(function)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == "self"
            and node.func.attr == "_preflight"
        ]
        assert preflight_lines, f"EgressBroker.{function.name} can instantiate without preflight"
        assert min(preflight_lines) < min(instantiate_lines), (
            f"EgressBroker.{function.name} preflight runs after provider instantiation"
        )
        guarded.add(function.name)

    assert {"call", "call_image", "call_transcript"} <= guarded


def test_image_path_has_no_raw_request_prompt_fallback():
    """Only the prompt that survived build + scan may reach image generation."""
    source = inspect.getsource(EgressBroker.call_image)
    assert "request.instructions" not in source
    assert 'payload.get("instructions")' in source
