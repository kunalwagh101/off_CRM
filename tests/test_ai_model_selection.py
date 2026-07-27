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
