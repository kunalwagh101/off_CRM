"""Regression tests for defects found by the 2026-11-13 live end-to-end sweep.

Every test here was written RED first against `develop` at 2177e05, from a
failure seen on a real local server talking to the real NVIDIA API. The full
evidence is in docs/evidence/2026-11-13-live-e2e-sweep.md.
"""
from __future__ import annotations

from pathlib import Path

import yaml

from offsetx_apollo_builder.ai.failures import FailureAction, FailureKind, classify
from offsetx_apollo_builder.ai.payload import tokenise_addresses
from offsetx_apollo_builder.ai.registry import ProviderRegistry
from offsetx_apollo_builder.ai.tiers import TrustTier

REPO = Path(__file__).resolve().parents[1]
CONFIG = REPO / "config" / "providers.yaml"
PACKAGED = REPO / "offsetx_apollo_builder" / "ai" / "providers.yaml"

#: Answered NVIDIA with 410 Gone or 404 for a valid key on 2026-11-13. Keeping
#: any of these as a configured model offers the owner a dead choice; keeping
#: one as the default makes every fresh NVIDIA connection fail (D-440).
RETIRED_NVIDIA_MODELS = {
    "meta/llama-3.1-70b-instruct",
    "meta/llama-3.3-70b-instruct",
    "nvidia/llama-3.1-nemotron-70b-instruct",
    "microsoft/phi-3-medium-128k-instruct",
    "google/gemma-2-27b-it",
    "ibm/granite-3.0-8b-instruct",
    "mistralai/mistral-large-2-instruct",
    "deepseek-ai/deepseek-r1",
    "qwen/qwen2.5-coder-32b-instruct",
    "qwen/qwen2.5-7b-instruct",
    "stabilityai/stable-diffusion-xl",
}


def _nvidia(path: Path) -> dict:
    doc = yaml.safe_load(path.read_text(encoding="utf-8"))
    return next(p for p in doc["providers"] if p["id"] == "nvidia")


# ── D-440: dead NVIDIA catalogue ────────────────────────────────────────────
def test_nvidia_default_model_is_not_a_retired_model():
    assert _nvidia(CONFIG)["default_model"] not in RETIRED_NVIDIA_MODELS


def test_nvidia_lists_no_retired_model():
    listed = {m["id"] for m in _nvidia(CONFIG)["models"]}
    assert not listed & RETIRED_NVIDIA_MODELS, sorted(listed & RETIRED_NVIDIA_MODELS)


def test_nvidia_default_model_is_one_of_its_listed_chat_models():
    nvidia = _nvidia(CONFIG)
    chat = {m["id"] for m in nvidia["models"] if m.get("kind", "chat") == "chat"}
    assert nvidia["default_model"] in chat


def test_packaged_registry_matches_the_config_copy():
    # A pip install reads the packaged copy; drift means a fix that never ships.
    assert CONFIG.read_bytes() == PACKAGED.read_bytes()


# ── D-441: a retired model is reported as "our bug" ─────────────────────────
NVIDIA_410 = (
    'AI provider returned 410: {"type":"about:blank","title":"Gone","status":410,'
    '"detail":"The model \'meta/llama-3.1-70b-instruct\' has reached its end of life '
    'on 2026-08-26T09:00:00Z and is no longer available."}'
)


def test_a_retired_model_410_is_model_not_found_not_bad_request():
    failure = classify(NVIDIA_410)
    assert failure.kind is FailureKind.MODEL_NOT_FOUND
    assert failure.action is FailureAction.STOP_CONFIG


def test_a_retired_model_tells_the_owner_to_pick_another_model():
    advice = classify(NVIDIA_410).owner_action.lower()
    assert "off_crm bug" not in advice
    assert "retired" in advice or "no longer" in advice
    assert "connectors" in advice


def test_end_of_life_wording_without_a_status_is_still_recognised():
    assert classify("The model has reached its end of life and is no longer available").kind is (
        FailureKind.MODEL_NOT_FOUND
    )


# ── D-442: phone numbers left in clear text ─────────────────────────────────
def test_phone_numbers_in_owner_text_are_tokenised():
    text = "My client is jane@acme.example, phone +1 415 555 0199. Reply OK."
    out = tokenise_addresses(text)
    assert "555 0199" not in out
    assert "jane@acme.example" not in out


def test_common_phone_shapes_are_tokenised():
    for phone in ("+44 20 7946 0958", "(415) 555-0199", "415.555.0199", "+91-98765-43210", "+4930123456789"):
        assert phone not in tokenise_addresses(f"call {phone} today"), phone


def test_dates_money_years_and_versions_are_left_alone():
    for text in (
        "Report due 2026-11-13 at 10:00",
        "Budget is 1,500,000 EUR for 2026",
        "CBAM phase 2026-2034",
        "Version 3.12.1 released",
        "Order 12345",
        "Server 192.168.100.100 is internal",
    ):
        assert tokenise_addresses(text) == text, text


# ── D-447: Chinese labs on NVIDIA's live catalogue not classified ───────────
def test_chinese_labs_on_the_nvidia_catalogue_are_capped_at_tier_c():
    registry = ProviderRegistry(CONFIG)
    for model in ("z-ai/glm-5.3-flash", "minimaxai/minimax-m3", "stepfun-ai/step-3"):
        known, cap = registry.model_origin("nvidia", model)
        assert known, model
        assert cap is TrustTier.C, (model, cap)


# ── D-443: privacy tokens could reach a real inbox ──────────────────────────
def _audit(body: str):
    from offsetx_apollo_builder.outreach.email_expert import OFFSETX_SIGNATURE, audit_draft
    from offsetx_apollo_builder.locked_categories import LOCKED_CATEGORIES

    return audit_draft(
        stage="initial", route="future_client_discovery", category=sorted(LOCKED_CATEGORIES)[0],
        public_hook="Acme opened a CBAM desk.", hook_source="https://acme.example/n",
        subject="Quick question", body=body + "\n\n" + OFFSETX_SIGNATURE,
    )


def test_a_draft_still_holding_a_privacy_token_is_not_sendable():
    for token in ("<RECIPIENT_1>", "RECIPIENT_1", "PERSON_1", "COMPANY_1", "<PHONE>"):
        audit = _audit(f"Hi there, write to {token} about the desk?")
        assert any("privacy token" in e.lower() for e in audit.errors), (token, audit.errors)


def test_a_normal_draft_has_no_privacy_token_error():
    audit = _audit("Hi Ana, saw the CBAM desk news. Is the evidence trail a pain today?")
    assert not any("privacy token" in e.lower() for e in audit.errors), audit.errors


# ── D-444: NVIDIA images were sent to an endpoint NVIDIA does not serve ─────
def _genai_provider(session, *, genai_url="https://ai.api.nvidia.com/v1/genai/black-forest-labs/flux.1-schnell",
                    base_url="https://integrate.api.nvidia.com/v1"):
    from offsetx_apollo_builder.outreach.models import ProviderConfig
    from offsetx_apollo_builder.outreach.providers import OpenAIImageProvider

    return OpenAIImageProvider(
        ProviderConfig(
            provider_type="openai_image",
            model="black-forest-labs/flux.1-schnell",
            base_url=base_url,
            extra={"request": {"genai_url": genai_url, "width": 1024, "height": 1024, "steps": 4, "seed": 0}},
        ),
        api_key="k",
        session=session,
    )


class _GenaiSession:
    def __init__(self, body):
        self.body, self.sent = body, {}

    def post(self, url, headers=None, json=None, timeout=None):
        self.sent.update(url=url, payload=json, headers=headers)
        body = self.body

        class _R:
            ok = True
            status_code = 200

            @staticmethod
            def json():
                return body

        return _R()


def test_nvidia_genai_image_uses_the_genai_url_and_body():
    session = _GenaiSession({"artifacts": [{"base64": "QUJD", "finishReason": "SUCCESS", "seed": 0}]})
    images = _genai_provider(session).generate_images(prompt="a ship")
    assert images == ["data:image/jpeg;base64,QUJD"]
    assert session.sent["url"] == "https://ai.api.nvidia.com/v1/genai/black-forest-labs/flux.1-schnell"
    assert session.sent["payload"] == {"prompt": "a ship", "width": 1024, "height": 1024, "steps": 4, "seed": 0}
    assert "model" not in session.sent["payload"] and "genai_url" not in session.sent["payload"]


def test_nvidia_genai_content_filtered_image_is_an_error_not_a_picture():
    import pytest
    from offsetx_apollo_builder.outreach.providers import ProviderError

    session = _GenaiSession({"artifacts": [{"base64": "QUJD", "finishReason": "CONTENT_FILTERED"}]})
    with pytest.raises(ProviderError, match="filter"):
        _genai_provider(session).generate_images(prompt="x")


def test_the_genai_url_must_be_on_the_providers_own_domain():
    import pytest
    from offsetx_apollo_builder.outreach.providers import ProviderError

    session = _GenaiSession({"artifacts": []})
    with pytest.raises(ProviderError, match="domain"):
        _genai_provider(session, genai_url="https://evil.example/v1/genai/x").generate_images(prompt="x")
    assert not session.sent  # the key never left


def test_nvidia_image_models_point_at_the_genai_endpoint():
    for model in _nvidia(CONFIG)["models"]:
        if model.get("kind") == "image":
            url = model["request_options"].get("genai_url", "")
            assert url.startswith("https://ai.api.nvidia.com/v1/genai/"), model["id"]
            assert url.endswith(model["id"]), model["id"]


# ── API-level findings ─────────────────────────────────────────────────────
import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402


@pytest.fixture()
def api(tmp_path):
    from offsetx_apollo_builder.api.app import create_app
    from offsetx_apollo_builder.api.config import AppSettings

    token = "e2e-findings-" + "t" * 40
    app = create_app(AppSettings(project_root=Path.cwd(), database_path=tmp_path / "crm.db",
        data_dir=tmp_path / "data", export_dir=tmp_path / "exports", frontend_dist=tmp_path / "missing",
        api_token=token, allowed_hosts=("testserver",)))
    with TestClient(app) as client:
        client.headers.update({"X-Offsetx-Token": token})
        yield client


# D-446: a pasted API key was saved as an approved memory and fed to prompts.
@pytest.mark.parametrize("content", [
    "my api_key=sk-abcdefghijklmnopqrstuvwxyz123456",
    "use nvapi-AbCdEfGhIjKlMnOpQrStUvWxYz0123456789 for NVIDIA",
    "password: hunter2-very-secret",
])
def test_a_memory_holding_a_credential_is_refused_with_a_next_step(api, content):
    response = api.post("/api/v1/memory", json={"content": content})
    assert response.status_code == 422, response.text
    message = response.json()["detail"].lower()
    assert "credential" in message and "connectors" in message
    assert api.get("/api/v1/memory").json()["items"] == []


def test_an_ordinary_memory_is_still_saved(api):
    assert api.post("/api/v1/memory", json={"content": "We file CBAM reports in two days."}).status_code == 201


def test_a_companion_memory_holding_a_credential_is_refused(api):
    companion = api.post("/api/v1/companions", json={"name": "Writer", "instructions": "Write short."}).json()
    response = api.post(f"/api/v1/companions/{companion['id']}/memory",
                        json={"content": "token=abcdefghijklmnop1234567890", "approved": True})
    assert response.status_code == 422, response.text


# D-445: a row with no email was imported silently into an email campaign.
def test_import_warns_about_a_row_that_cannot_be_emailed(api):
    campaign = api.post("/api/v1/campaigns", json={"name": "Import warn"}).json()["id"]
    csv = b"full_name,email,company\nAna Silva,ana@acme.example,Acme\nNo Mail,,X\n"
    result = api.post(f"/api/v1/campaigns/{campaign}/contacts/import",
                      files={"file": ("c.csv", csv, "text/csv")}).json()
    assert result["added"] == 2
    assert any(w["row"] == 3 and "email" in w["warning"].lower() for w in result.get("warnings", [])), result


# D-448: refusal named an internal setting and gave no next step.
def test_companion_on_public_data_says_what_to_choose(api):
    companion = api.post("/api/v1/companions", json={"name": "Writer2", "instructions": "Write short."}).json()
    chat = api.post("/api/v1/ai/chats", json={"title": "c"}).json()
    response = api.post(f"/api/v1/ai/chats/{chat['id']}/messages",
                        json={"content": "hi", "companion_id": companion["id"], "data_class": "public"})
    assert response.status_code == 400
    detail = str(response.json()["detail"]).lower()
    assert "campaign" in detail and ("choose" in detail or "switch" in detail)


# D-449: FastAPI's default Swagger OAuth page was served without login.
def test_swagger_oauth_redirect_page_is_not_public(api):
    anonymous = TestClient(api.app)
    assert anonymous.get("/docs/oauth2-redirect").status_code in (401, 404)


# ── D-450: an uncertain call (read timeout) was repeated automatically ──────
class _FlakySession:
    def __init__(self, first_error):
        self.first_error, self.calls = first_error, 0

    def post(self, url, headers=None, json=None, timeout=None):
        self.calls += 1
        if self.calls == 1:
            raise self.first_error

        class _R:
            ok = True
            status_code = 200

            @staticmethod
            def json():
                return {"artifacts": [{"base64": "QUJD", "finishReason": "SUCCESS"}]}

        return _R()


def test_a_read_timeout_is_not_retried_because_the_call_may_have_run():
    import requests
    from offsetx_apollo_builder.outreach.providers import ProviderError

    session = _FlakySession(requests.exceptions.ReadTimeout("read timed out"))
    with pytest.raises(ProviderError, match="may already have run"):
        _genai_provider(session).generate_images(prompt="x")
    assert session.calls == 1


def test_a_connection_failure_is_still_retried_because_nothing_was_sent(monkeypatch):
    import requests

    monkeypatch.setattr("offsetx_apollo_builder.outreach.providers.time.sleep", lambda s: None)
    session = _FlakySession(requests.exceptions.ConnectionError("connection refused"))
    assert _genai_provider(session).generate_images(prompt="x") == ["data:image/jpeg;base64,QUJD"]
    assert session.calls == 2
