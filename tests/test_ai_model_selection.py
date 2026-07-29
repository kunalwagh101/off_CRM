"""Per-model connectors.

One API key reaches many models, and a model carries its own trust tier
independently of the company hosting it. These tests pin down both halves:
the model you choose is the model that runs, and choosing a Chinese-built model
on a US host drops the tier accordingly.

The first test here is the regression guard for a real defect: the chosen model
used to be stored and displayed, then silently discarded — every call fell back
to the provider's `default_model`, which also made the provenance cap
unreachable through the UI.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from offsetx_apollo_builder.ai import (
    DataClass,
    DataPolicy,
    EgressBroker,
    EgressLog,
    EgressRequest,
    NoPermittedProvider,
    PersonPublic,
    ProviderRegistry,
    QuotaTracker,
    TrustTier,
    WorkspaceEgressSettings,
)
from offsetx_apollo_builder.ai.discovery import discover_models
from offsetx_apollo_builder.ai.workspace import WorkspaceAISettingsStore

REPO_ROOT = Path(__file__).resolve().parents[1]

PERSON = PersonPublic(
    full_name="Ana Silva", first_name="Ana", title="Head of Trade", company="Acme GmbH"
)


@pytest.fixture()
def registry() -> ProviderRegistry:
    return ProviderRegistry(REPO_ROOT / "config" / "providers.yaml")


@pytest.fixture()
def harness(registry, tmp_path):
    """Broker whose provider stub records the model it was actually asked for."""
    calls: list[dict[str, str]] = []
    log = EgressLog(tmp_path / "egress.sqlite3")
    broker = EgressBroker(
        registry=registry,
        credential_resolver=lambda provider_id: "k",
        quota=QuotaTracker(tmp_path),
        logger=log.record,
    )

    class Stub:
        def __init__(self, provider_id: str, model_id: str) -> None:
            self.provider_id = provider_id
            self.model_id = model_id

        def generate(self, *, system_prompt: str, user_prompt: str) -> str:
            calls.append(
                {
                    "provider_id": self.provider_id,
                    "model_id": self.model_id,
                    "payload": json.loads(user_prompt),
                }
            )
            return f"{self.model_id} answered"

    broker._instantiate = lambda c: Stub(c.id, c.model_id)  # type: ignore[method-assign]
    return broker, calls, log


def _settings(**kwargs) -> WorkspaceEgressSettings:
    defaults = {"workspace_id": "local", "positioning_line": "We cut customs cost."}
    defaults.update(kwargs)
    return WorkspaceEgressSettings(**defaults)


# ── the regression: the chosen model must be the model that runs ────────────


def test_the_chosen_model_is_the_one_that_actually_runs(harness):
    """Regression guard.

    Before this was fixed, `candidates_for` resolved each provider without a
    model id, so this call went to meta/llama-3.1-70b-instruct — NVIDIA's
    default — no matter what the owner picked.
    """
    broker, calls, _ = harness
    broker.call(
        EgressRequest(task_type="t", data_class=DataClass.PUBLIC, instructions="go"),
        _settings(
            enabled_provider_ids=("nvidia",),
            enabled_models={"nvidia": ("microsoft/phi-3-medium-128k-instruct",)},
        ),
        system_prompt="w",
    )
    assert [call["model_id"] for call in calls] == ["microsoft/phi-3-medium-128k-instruct"]


def test_no_chosen_model_falls_back_to_the_provider_default(harness):
    broker, calls, _ = harness
    broker.call(
        EgressRequest(task_type="t", data_class=DataClass.PUBLIC, instructions="go"),
        _settings(enabled_provider_ids=("nvidia",)),
        system_prompt="w",
    )
    assert calls[0]["model_id"] == "meta/llama-3.1-70b-instruct"


def test_one_key_can_run_several_models_at_once(harness):
    """The point of the change: a single NVIDIA key becomes several candidates."""
    broker, _, _ = harness
    permitted, _ = broker.plan(
        EgressRequest(task_type="t", data_class=DataClass.PUBLIC, instructions="go"),
        _settings(
            enabled_provider_ids=("nvidia",),
            enabled_models={
                "nvidia": (
                    "meta/llama-3.3-70b-instruct",
                    "microsoft/phi-3-medium-128k-instruct",
                    "nvidia/llama-3.1-nemotron-70b-instruct",
                )
            },
        ),
    )
    assert len(permitted) == 3
    assert all(item.id == "nvidia" for item in permitted)
    assert len({item.model_id for item in permitted}) == 3


# ── provenance: the model's origin, not the host's ─────────────────────────


def test_a_chinese_model_on_a_us_host_drops_to_tier_c(registry):
    """NVIDIA is tier B. DeepSeek built on NVIDIA's hardware is still DeepSeek's
    model, and NVIDIA does not document pass-through, so it caps at C."""
    assert registry.resolve("nvidia", model_id="meta/llama-3.3-70b-instruct").tier is TrustTier.B
    assert registry.resolve("nvidia", model_id="deepseek-ai/deepseek-r1").tier is TrustTier.C
    assert registry.resolve("nvidia", model_id="qwen/qwen2.5-7b-instruct").tier is TrustTier.C


def test_the_tier_cap_reaches_the_broker_through_the_settings_path(harness):
    """The cap existed before but was unreachable from the UI, because the model
    never made it into resolution. This proves the whole path."""
    broker, _, _ = harness
    request = EgressRequest(
        task_type="draft_email",
        data_class=DataClass.CAMPAIGN,
        person=PERSON,
        template_text="Hi {{first_name}}",
        instructions="write",
    )
    settings = _settings(
        enabled_provider_ids=("nvidia",),
        enabled_models={"nvidia": ("deepseek-ai/deepseek-r1",)},
    )
    with pytest.raises(NoPermittedProvider) as excinfo:
        broker.plan(request, settings)
    detail = json.dumps(excinfo.value.considered)
    assert "tier_forbids_data_class" in detail
    assert "deepseek-ai/deepseek-r1" in detail


def test_two_models_on_one_key_get_different_payloads(harness):
    """A tier B and a tier C model on the same NVIDIA key, in one run: the
    template reaches one and not the other."""
    broker, calls, _ = harness
    request = EgressRequest(
        task_type="draft_email",
        data_class=DataClass.PERSON_PUBLIC,
        person=PERSON,
        template_text="Hi {{first_name}}, our customs work ...",
        instructions="write",
    )
    for model_id in ("meta/llama-3.3-70b-instruct", "deepseek-ai/deepseek-r1"):
        broker.call(
            request,
            _settings(
                enabled_provider_ids=("nvidia",), enabled_models={"nvidia": (model_id,)}
            ),
            system_prompt="w",
        )
    by_model = {call["model_id"]: call["payload"] for call in calls}
    assert "template" in by_model["meta/llama-3.3-70b-instruct"]
    assert "template" not in by_model["deepseek-ai/deepseek-r1"]
    assert by_model["deepseek-ai/deepseek-r1"]["recipient"]["full_name"] == "Ana Silva"


def test_an_unknown_model_name_is_untrusted(registry):
    """Default-deny. A model matching no origin rule cannot be placed, so it
    receives nothing rather than inheriting its host's tier."""
    assert registry.resolve("nvidia", model_id="mystery-lab/secret-9b").tier is TrustTier.D
    assert registry.classify_model("mystery-lab/secret-9b")["known"] is False


def test_longer_origin_prefixes_win(registry):
    """`meta-llama/` must not be swallowed by `meta/`."""
    assert registry.classify_model("meta-llama/Llama-3.3-70B")["origin"] == "US"
    assert registry.classify_model("deepseek-ai/deepseek-r1")["matched_prefix"] == "deepseek-ai/"


# ── discovery ──────────────────────────────────────────────────────────────


class _Response:
    def __init__(self, payload, ok=True, status_code=200):
        self._payload = payload
        self.ok = ok
        self.status_code = status_code

    def json(self):
        return self._payload


class _Session:
    def __init__(self, response):
        self._response = response
        self.calls: list[dict] = []

    def get(self, url, headers=None, timeout=None):
        self.calls.append({"url": url, "headers": headers})
        if isinstance(self._response, Exception):
            raise self._response
        return self._response


def test_discovery_classifies_live_models_using_config_rules(registry):
    session = _Session(
        _Response(
            {
                "data": [
                    {"id": "meta/llama-3.3-70b-instruct"},
                    {"id": "deepseek-ai/deepseek-v3"},
                    {"id": "mistralai/mixtral-8x22b"},
                    {"id": "unknown-lab/whatever-70b"},
                ]
            }
        )
    )
    result = discover_models(registry, "nvidia", "nvapi-key", session=session)
    assert result.source == "provider"
    by_id = {model.id: model for model in result.models}

    assert by_id["meta/llama-3.3-70b-instruct"].tier == "B"
    # Discovered, not in config, still capped by the origin rule.
    assert by_id["deepseek-ai/deepseek-v3"].tier == "C"
    assert by_id["mistralai/mixtral-8x22b"].tier == "B"
    # No rule matches, so it is untrusted and cannot be enabled.
    assert by_id["unknown-lab/whatever-70b"].known is False
    assert by_id["unknown-lab/whatever-70b"].usable is False
    assert "config/providers.yaml" in result.note


def test_discovery_sends_only_the_key_and_no_owner_data(registry):
    session = _Session(_Response({"data": [{"id": "meta/llama-3.3-70b-instruct"}]}))
    discover_models(registry, "nvidia", "nvapi-secret", session=session)
    call = session.calls[0]
    assert call["url"].endswith("/models")
    assert call["headers"] == {"Authorization": "Bearer nvapi-secret"}


def test_discovery_keeps_config_models_the_provider_did_not_mention(registry):
    session = _Session(_Response({"data": [{"id": "meta/llama-3.3-70b-instruct"}]}))
    result = discover_models(registry, "nvidia", "k", session=session)
    ids = {model.id for model in result.models}
    assert "deepseek-ai/deepseek-r1" in ids  # from config, absent from the response


def test_discovery_degrades_when_the_provider_cannot_be_reached(registry):
    result = discover_models(
        registry, "nvidia", "k", session=_Session(RuntimeError("connection refused"))
    )
    assert result.source == "config"
    assert "Could not reach" in result.error
    assert result.models, "must still show the config list rather than an empty screen"


def test_discovery_degrades_on_a_bad_key(registry):
    result = discover_models(
        registry, "nvidia", "k", session=_Session(_Response({}, ok=False, status_code=401))
    )
    assert "401" in result.error
    assert "key may be wrong" in result.error
    assert result.models


def test_discovery_without_a_key_explains_itself(registry):
    result = discover_models(registry, "nvidia", "")
    assert result.source == "config"
    assert "No API key stored" in result.note


def test_discovery_is_written_to_the_egress_log(registry, tmp_path):
    log = EgressLog(tmp_path / "egress.sqlite3")
    session = _Session(_Response({"data": [{"id": "meta/llama-3.3-70b-instruct"}]}))
    discover_models(registry, "nvidia", "k", session=session, logger=log.record)

    items, total = log.list()
    assert total == 1
    entry = log.get(items[0]["id"])
    assert entry is not None
    assert entry["task_type"] == "model_discovery"
    # No owner data left the machine, and the log says so plainly.
    assert entry["payload"] == {}
    assert "No owner data was sent" in entry["payload_summary"]["note"]


# ── storage ────────────────────────────────────────────────────────────────


def test_connecting_stores_a_model_list_and_the_broker_receives_it(tmp_path, registry):
    store = WorkspaceAISettingsStore(tmp_path, registry)
    store.connect_provider(
        "local",
        "nvidia",
        api_key="k",
        model_ids=["meta/llama-3.3-70b-instruct", "deepseek-ai/deepseek-r1"],
    )
    settings = store.egress_settings("local")
    assert settings.enabled_models["nvidia"] == (
        "meta/llama-3.3-70b-instruct",
        "deepseek-ai/deepseek-r1",
    )


def test_an_older_single_model_record_still_works(tmp_path, registry):
    """Upgrade path: records written before this change hold `model_id` only."""
    store = WorkspaceAISettingsStore(tmp_path, registry)
    store.save(
        "local",
        {"providers": {"nvidia": {"enabled": True, "model_id": "google/gemma-2-27b-it"}}},
    )
    settings = store.egress_settings("local")
    assert settings.enabled_models["nvidia"] == ("google/gemma-2-27b-it",)


def test_connecting_an_unclassifiable_model_is_refused(tmp_path, registry):
    store = WorkspaceAISettingsStore(tmp_path, registry)
    with pytest.raises(ValueError, match="model_origin_rules"):
        store.connect_provider("local", "nvidia", api_key="k", model_ids=["who-knows/model-x"])


# ── the run modes must respect the model list too ──────────────────────────


def test_compare_races_two_models_on_the_same_key(harness):
    """Regression guard.

    Compare mode had its own candidate lookup that ignored the enabled model
    list and pinned only the provider — so comparing two NVIDIA models silently
    ran that key's default model twice instead.
    """
    from offsetx_apollo_builder.ai import ModeRunner

    broker, calls, _ = harness
    result = ModeRunner(broker).run_compare(
        EgressRequest(task_type="t", data_class=DataClass.PUBLIC, instructions="go"),
        _settings(
            enabled_provider_ids=("nvidia",),
            enabled_models={
                "nvidia": (
                    "meta/llama-3.3-70b-instruct",
                    "microsoft/phi-3-medium-128k-instruct",
                )
            },
        ),
        system_prompt="w",
    )
    ran = {call["model_id"] for call in calls}
    assert ran == {"meta/llama-3.3-70b-instruct", "microsoft/phi-3-medium-128k-instruct"}
    assert {branch.model_id for branch in result.branches} == ran


def test_compare_lets_a_restricted_model_join_public_work(harness):
    """Public tasks are exactly where a tier C model earns its keep — the
    failover chain excludes it, compare deliberately does not."""
    from offsetx_apollo_builder.ai import ModeRunner

    broker, calls, _ = harness
    ModeRunner(broker).run_compare(
        EgressRequest(task_type="t", data_class=DataClass.PUBLIC, instructions="go"),
        _settings(
            enabled_provider_ids=("nvidia",),
            enabled_models={
                "nvidia": ("meta/llama-3.3-70b-instruct", "deepseek-ai/deepseek-r1")
            },
        ),
        system_prompt="w",
    )
    assert "deepseek-ai/deepseek-r1" in {call["model_id"] for call in calls}


def test_a_restricted_model_on_a_trusted_key_still_cannot_lead_a_plan(harness):
    """One key can hold a tier B and a tier C model. Only the trusted one may
    plan — the tier belongs to the model, not to the key."""
    from offsetx_apollo_builder.ai import ModeRunner
    from offsetx_apollo_builder.ai import PolicyViolation as PV

    broker, _, _ = harness
    settings = _settings(
        enabled_provider_ids=("nvidia",),
        enabled_models={"nvidia": ("deepseek-ai/deepseek-r1",)},
    )
    with pytest.raises((NoPermittedProvider, PV)):
        ModeRunner(broker).run_orchestrated(
            EgressRequest(task_type="t", data_class=DataClass.PUBLIC, instructions="go"),
            settings,
            system_prompt="w",
        )


# ── per-model request options ──────────────────────────────────────────────


def test_model_request_options_reach_the_http_payload(registry, tmp_path):
    """A reasoning model needs max_tokens and its thinking settings. Storing
    them in config is only useful if they actually go over the wire.
    """
    from offsetx_apollo_builder.outreach.providers import OpenAICompatibleProvider

    sent: dict = {}

    class _Session:
        def post(self, url, headers=None, json=None, timeout=None):
            sent["url"] = url
            sent["payload"] = json

            class _R:
                ok = True
                status_code = 200

                @staticmethod
                def json():
                    return {"choices": [{"message": {"content": "hello"}}]}

            return _R()

    broker = EgressBroker(
        registry=registry, credential_resolver=lambda p: "nvapi-test", quota=QuotaTracker(tmp_path)
    )
    candidate = registry.resolve("nvidia", model_id="nvidia/nemotron-3-ultra-550b-a55b")
    provider = broker._instantiate(candidate)
    assert isinstance(provider, OpenAICompatibleProvider)
    provider.session = _Session()
    provider.generate(system_prompt="s", user_prompt="u")

    payload = sent["payload"]
    assert payload["model"] == "nvidia/nemotron-3-ultra-550b-a55b"
    assert payload["max_tokens"] == 16384
    assert payload["temperature"] == 1
    assert payload["top_p"] == 0.95
    assert payload["chat_template_kwargs"] == {"enable_thinking": True}
    assert payload["reasoning_budget"] == 16384
    assert sent["url"].endswith("/chat/completions")


def test_a_model_without_options_sends_a_plain_payload(registry, tmp_path):
    """Options are opt-in per model; nothing is invented for models that do not
    declare any."""
    from offsetx_apollo_builder.outreach.providers import OpenAICompatibleProvider

    sent: dict = {}

    class _Session:
        def post(self, url, headers=None, json=None, timeout=None):
            sent["payload"] = json

            class _R:
                ok = True
                status_code = 200

                @staticmethod
                def json():
                    return {"choices": [{"message": {"content": "hi"}}]}

            return _R()

    broker = EgressBroker(
        registry=registry, credential_resolver=lambda p: "k", quota=QuotaTracker(tmp_path)
    )
    provider = broker._instantiate(
        registry.resolve("nvidia", model_id="meta/llama-3.3-70b-instruct")
    )
    assert isinstance(provider, OpenAICompatibleProvider)
    provider.session = _Session()
    provider.generate(system_prompt="s", user_prompt="u")
    assert set(sent["payload"].keys()) == {"model", "messages"}


def test_a_reasoning_model_that_only_returned_its_thinking_still_answers():
    """Reasoning models put their working in `reasoning_content`. Returning that
    beats raising 'no content' at the user."""
    from offsetx_apollo_builder.outreach.models import ProviderConfig
    from offsetx_apollo_builder.outreach.providers import OpenAICompatibleProvider

    class _Session:
        def post(self, url, headers=None, json=None, timeout=None):
            class _R:
                ok = True
                status_code = 200

                @staticmethod
                def json():
                    return {
                        "choices": [
                            {"message": {"content": "", "reasoning_content": "I thought about it."}}
                        ]
                    }

            return _R()

    provider = OpenAICompatibleProvider(
        ProviderConfig(provider_type="openai_compatible", model="m", base_url="https://x.test/v1"),
        api_key="k",
        session=_Session(),
    )
    assert provider.generate(system_prompt="s", user_prompt="u") == "I thought about it."


def test_running_out_of_tokens_says_how_to_fix_it():
    """A truncated reasoning model used to surface as 'did not contain message
    content', which tells the owner nothing actionable."""
    from offsetx_apollo_builder.outreach.models import ProviderConfig
    from offsetx_apollo_builder.outreach.providers import OpenAICompatibleProvider, ProviderError

    class _Session:
        def post(self, url, headers=None, json=None, timeout=None):
            class _R:
                ok = True
                status_code = 200

                @staticmethod
                def json():
                    return {"choices": [{"message": {"content": ""}, "finish_reason": "length"}]}

            return _R()

    provider = OpenAICompatibleProvider(
        ProviderConfig(provider_type="openai_compatible", model="m", base_url="https://x.test/v1"),
        api_key="k",
        session=_Session(),
    )
    with pytest.raises(ProviderError, match="max_tokens"):
        provider.generate(system_prompt="s", user_prompt="u")


# ── image models ───────────────────────────────────────────────────────────


def test_image_models_are_kept_apart_from_chat_models(registry):
    """A picture model cannot answer a chat task and vice versa — different
    endpoints, different return type."""
    entry = registry.require("nvidia")
    images = [m.id for m in entry.models if m.is_image]
    assert "black-forest-labs/flux.1-dev" in images
    assert not entry.model("meta/llama-3.3-70b-instruct").is_image

    chat, _ = registry.candidates_for(
        DataClass.PUBLIC,
        enabled_ids=("nvidia",),
        enabled_models={"nvidia": ("meta/llama-3.3-70b-instruct", "black-forest-labs/flux.1-dev")},
        kind="chat",
    )
    assert [c.model_id for c in chat] == ["meta/llama-3.3-70b-instruct"]

    drawing, _ = registry.candidates_for(
        DataClass.PUBLIC,
        enabled_ids=("nvidia",),
        enabled_models={"nvidia": ("meta/llama-3.3-70b-instruct", "black-forest-labs/flux.1-dev")},
        kind="image",
    )
    assert [c.model_id for c in drawing] == ["black-forest-labs/flux.1-dev"]


def test_image_model_makers_are_classified_by_origin(registry):
    """FLUX is German, Stable Diffusion is British — origin rules cover them the
    same way they cover text models."""
    assert registry.classify_model("black-forest-labs/flux.1-dev")["origin"] == "EU"
    assert registry.classify_model("stabilityai/stable-diffusion-xl")["origin"] == "GB"


def test_drawing_a_picture_goes_through_the_same_gate(registry, tmp_path):
    """The prompt is text. Everything protective applies unchanged."""
    log = EgressLog(tmp_path / "egress.sqlite3")
    broker = EgressBroker(
        registry=registry,
        credential_resolver=lambda p: "k",
        quota=QuotaTracker(tmp_path),
        logger=log.record,
    )

    sent: dict = {}

    class _Stub:
        def generate_images(self, *, prompt: str) -> list[str]:
            sent["prompt"] = prompt
            return ["data:image/png;base64,AAAA"]

    broker._instantiate = lambda c, adapter_override="": _Stub()  # type: ignore[method-assign]

    result = broker.call_image(
        EgressRequest(
            task_type="image_generation",
            data_class=DataClass.PUBLIC,
            instructions="a cargo ship at a European port",
        ),
        _settings(
            enabled_provider_ids=("nvidia",),
            enabled_models={"nvidia": ("black-forest-labs/flux.1-dev",)},
        ),
    )
    assert result.images == ["data:image/png;base64,AAAA"]
    assert result.model_id == "black-forest-labs/flux.1-dev"
    assert sent["prompt"] == "a cargo ship at a European port"

    # Logged like any other call — but the picture itself is not stored, because
    # the log exists to show what left, and what left was the prompt.
    items, total = log.list()
    assert total == 1
    entry = log.get(items[0]["id"])
    assert entry is not None
    assert entry["task_type"] == "image_generation"
    assert "cargo ship" in json.dumps(entry["payload"])
    assert entry["response_text"] == "[1 image(s) returned]"
    assert "base64" not in entry["response_text"]


def test_an_image_prompt_carrying_an_owner_domain_is_blocked(registry, tmp_path):
    broker = EgressBroker(
        registry=registry,
        credential_resolver=lambda p: "k",
        quota=QuotaTracker(tmp_path),
        logger=EgressLog(tmp_path / "e.sqlite3").record,
    )
    broker._instantiate = lambda c, adapter_override="": pytest.fail("provider was called")  # type: ignore[method-assign]

    from offsetx_apollo_builder.ai import EgressBlocked

    with pytest.raises(EgressBlocked):
        broker.call_image(
            EgressRequest(
                task_type="image_generation",
                data_class=DataClass.PUBLIC,
                instructions="a logo for offsetx.example",
            ),
            _settings(
                enabled_provider_ids=("nvidia",),
                enabled_models={"nvidia": ("black-forest-labs/flux.1-dev",)},
                owner_domains=("offsetx.example",),
            ),
        )


def test_no_image_model_switched_on_says_where_to_go(registry, tmp_path):
    broker = EgressBroker(
        registry=registry, credential_resolver=lambda p: "k", quota=QuotaTracker(tmp_path)
    )
    with pytest.raises(NoPermittedProvider) as excinfo:
        broker.call_image(
            EgressRequest(
                task_type="image_generation", data_class=DataClass.PUBLIC, instructions="a ship"
            ),
            _settings(
                enabled_provider_ids=("nvidia",),
                enabled_models={"nvidia": ("meta/llama-3.3-70b-instruct",)},
            ),
        )
    assert "Connectors" in str(excinfo.value)


def test_the_image_adapter_asks_for_base64_not_a_link():
    """A provider URL can expire or be fetched from elsewhere. Base64 keeps the
    picture in off_CRM's hands."""
    from offsetx_apollo_builder.outreach.models import ProviderConfig
    from offsetx_apollo_builder.outreach.providers import OpenAIImageProvider

    sent: dict = {}

    class _Session:
        def post(self, url, headers=None, json=None, timeout=None):
            sent["url"] = url
            sent["payload"] = json

            class _R:
                ok = True
                status_code = 200

                @staticmethod
                def json():
                    return {"data": [{"b64_json": "QUJD"}]}

            return _R()

    provider = OpenAIImageProvider(
        ProviderConfig(
            provider_type="openai_image",
            model="black-forest-labs/flux.1-dev",
            base_url="https://integrate.api.nvidia.com/v1",
            extra={"request": {"size": "1024x1024", "n": 1}},
        ),
        api_key="k",
        session=_Session(),
    )
    images = provider.generate_images(prompt="a ship")

    assert images == ["data:image/png;base64,QUJD"]
    assert sent["url"].endswith("/images/generations")
    assert sent["payload"]["response_format"] == "b64_json"
    assert sent["payload"]["size"] == "1024x1024"
