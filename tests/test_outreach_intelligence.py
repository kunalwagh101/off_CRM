from __future__ import annotations

from datetime import datetime, timezone

from fastapi.testclient import TestClient

from offsetx_apollo_builder.api.app import create_app
from offsetx_apollo_builder.api.config import AppSettings
from offsetx_apollo_builder.outreach.engine import OutreachEngine, campaign_send_window
from offsetx_apollo_builder.outreach.providers import (
    FallbackAIProvider,
    PolicyAIProvider,
    ProviderError,
    apply_data_policy,
)


CSV = """Full Name,Email,Company,Title,Category,Public Hook,Hook Source,Tension
Anita Rao,anita@example.com,Example Exports,Climate Lead,CBAM,Published a supplier evidence brief,https://example.com/anita,Supplier evidence handoff
"""


class _Provider:
    def __init__(self, value: str = '{"subject":"Hello","body":"Useful body"}', error: Exception | None = None):
        self.value = value
        self.error = error
        self.calls = 0

    def generate(self, **_kwargs):
        self.calls += 1
        if self.error:
            raise self.error
        return self.value


def _engine_with_drafts(tmp_path):
    source = tmp_path / "contacts.csv"
    source.write_text(CSV, encoding="utf-8")
    engine = OutreachEngine(tmp_path / "crm.db")
    campaign_id = engine.create_campaign(name="Intelligence", variants=["A"])
    engine.import_contacts(campaign_id, source)
    assert engine.generate_drafts(campaign_id)["generated"] == 3
    return engine, campaign_id


def test_minimal_data_policy_removes_recipient_identity_and_direct_data():
    prompt = '{"stage":"initial","recipient":{"first_name":"Anita","company":"Example Exports","category":"CBAM","email":"anita@example.com"},"template_blueprint":{"body":"Hi Anita at Example Exports. See https://example.com/anita"}}'
    minimized = apply_data_policy(prompt, "minimal")
    assert "Anita" not in minimized
    assert "Example Exports" not in minimized
    assert "anita@example.com" not in minimized
    assert "https://example.com" not in minimized
    assert "CBAM" in minimized


def test_policy_provider_records_metadata_without_payload_body():
    calls = []
    provider = PolicyAIProvider(
        _Provider(),
        profile_id="primary",
        provider_type="openai",
        model="test-model",
        data_policy="minimal",
        audit_payloads=False,
        audit_callback=lambda **values: calls.append(values),
    )
    provider.generate(system_prompt="system", user_prompt='{"stage":"initial"}')
    assert calls[0]["status"] == "succeeded"
    assert calls[0]["request_payload"] == {
        "payload_logging": "disabled",
        "user_prompt_chars": len('{"stage": "initial", "recipient": {}}'),
    }
    assert "text" not in calls[0]["response_payload"]


def test_multi_provider_strategies_support_round_robin_and_parallel_failover():
    first = _Provider()
    second = _Provider()
    router = FallbackAIProvider([("first", first), ("second", second)], strategy="round_robin")
    router.generate(system_prompt="s", user_prompt="u")
    assert router.last_run["selected_profile_id"] == "first"
    router.generate(system_prompt="s", user_prompt="u")
    assert router.last_run["selected_profile_id"] == "second"

    failed = _Provider(error=ProviderError("offline"))
    parallel = FallbackAIProvider([("failed", failed), ("healthy", _Provider())], strategy="parallel")
    parallel.generate(system_prompt="s", user_prompt="u")
    assert parallel.last_run["selected_profile_id"] == "healthy"


def test_campaign_send_window_evaluates_in_campaign_timezone():
    campaign = {
        "timezone": "Asia/Kolkata",
        "send_window_start": "09:00",
        "send_window_end": "17:00",
        "send_weekdays": [0, 1, 2, 3, 4],
    }
    monday_open = datetime(2026, 7, 20, 5, 0, tzinfo=timezone.utc)
    monday_closed = datetime(2026, 7, 20, 14, 0, tzinfo=timezone.utc)
    assert campaign_send_window(campaign, monday_open)["allowed"] is True
    assert campaign_send_window(campaign, monday_closed)["allowed"] is False


def test_human_edit_creates_approved_deidentified_memory(tmp_path):
    engine, campaign_id = _engine_with_drafts(tmp_path)
    draft = engine.store.list_drafts(campaign_id, limit=10, stage="initial")[0][0]
    engine.edit_draft(
        campaign_id,
        draft["id"],
        subject=draft["subject"],
        body=draft["body"].replace("practical", "specific"),
    )
    items, total = engine.store.search_memory_items("correction", approved_only=True)
    assert total == 1
    assert items[0]["kind"] == "human_correction"
    assert "Anita Rao" not in items[0]["content"]
    assert "anita@example.com" not in items[0]["content"]
    assert items[0]["approved"] is True
    engine.close()


def test_bulk_correction_preview_apply_and_schedule_are_audited(tmp_path):
    engine, campaign_id = _engine_with_drafts(tmp_path)
    draft = engine.store.list_drafts(campaign_id, limit=10, stage="initial")[0][0]
    preview = engine.bulk_replace_drafts(
        campaign_id,
        find="OffsetX",
        replace="OffsetX platform",
        draft_ids=[draft["id"]],
        preview_only=True,
    )
    assert preview["matched_drafts"] == 1
    applied = engine.bulk_replace_drafts(
        campaign_id,
        find="OffsetX",
        replace="OffsetX platform",
        draft_ids=[draft["id"]],
        preview_only=False,
    )
    assert applied["changed"] == 1
    scheduled = datetime(2026, 7, 21, 6, 30, tzinfo=timezone.utc)
    assert engine.schedule_drafts(campaign_id, draft_ids=[draft["id"]], scheduled_at=scheduled) == {"scheduled": 1}
    updated = engine.store.get_draft_by_id(campaign_id, draft["id"])
    assert updated["scheduled_at"] == "2026-07-21T06:30:00+00:00"
    engine.close()


def test_api_exposes_memory_provider_audit_and_experiment_contract(tmp_path):
    settings = AppSettings(
        project_root=tmp_path,
        database_path=tmp_path / "crm.db",
        data_dir=tmp_path / "data",
        export_dir=tmp_path / "exports",
        frontend_dist=tmp_path / "missing",
    )
    with TestClient(create_app(settings)) as client:
        campaign = client.post(
            "/api/v1/campaigns",
            json={
                "name": "Experiment",
                "variants": ["A", "B"],
                "experiment_hypothesis": "Specific hooks increase replies",
                "experiment_min_sample": 25,
                "send_window_start": "09:00",
                "send_window_end": "17:00",
                "send_weekdays": [0, 1, 2, 3, 4],
            },
        ).json()
        assert campaign["experiment_min_sample"] == 25
        assert campaign["send_weekdays"] == [0, 1, 2, 3, 4]
        created = client.post(
            "/api/v1/memory",
            json={"content": "Prefer one precise CTA", "kind": "playbook", "scope": "global", "tags": ["cta"]},
        )
        assert created.status_code == 201
        assert created.json()["approved"] is True
        client.app.state.engine.store.record_provider_call(
            profile_id="p1",
            provider_type="openai",
            model="test",
            data_policy="minimal",
            status="succeeded",
            request_payload={"payload_logging": "disabled"},
        )
        calls = client.get("/api/v1/provider-calls").json()
        assert calls["total"] == 1
        assert calls["items"][0]["data_policy"] == "minimal"
        assert client.get("/api/v1/memory/stats").json()["approved"] == 1
