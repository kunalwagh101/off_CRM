"""S-04.01.04: five role adapters use existing engines, not a second workflow."""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from offsetx_apollo_builder.ai.tools import ToolRegistry
from offsetx_apollo_builder.agent.companions import CompanionError, CompanionRegistry
from offsetx_apollo_builder.agent.role_team import (
    ROLE_INSTRUCTIONS, RoleEngines, execute_role, provision_roles, release_role_resources,
)
from offsetx_apollo_builder.api.app import create_app
from offsetx_apollo_builder.api.config import AppSettings

OWNER = "agent-team-owner-" + "a" * 35
HEADERS = {"X-Offsetx-Token": OWNER}


class EmptyMemory:
    def search_memory_items(self, *args, **kwargs):
        return [], 0


def _registry(tmp_path):
    return CompanionRegistry(
        tmp_path, tools=ToolRegistry(tmp_path / "tools.db"),
        memory_backend=EmptyMemory(),
    )


def test_five_roles_are_idempotent_and_never_override_owner_customisations(tmp_path):
    registry = _registry(tmp_path)
    original = provision_roles(registry, workspace_id="team-a")
    assert {profile["name"] for profile in original} == set(ROLE_INSTRUCTIONS)
    assert all(profile["granted_tool_ids"] == [] for profile in original)
    scout_id = next(profile["id"] for profile in original if profile["name"] == "Scout")
    registry.update(scout_id, workspace_id="team-a", instructions="Owner custom role.")
    again = provision_roles(registry, workspace_id="team-a")
    assert {profile["id"] for profile in original} == {profile["id"] for profile in again}
    assert registry.require(scout_id, workspace_id="team-a").instructions == "Owner custom role."
    assert len(registry.list(workspace_id="team-b")) == 0


def test_scout_only_reads_existing_workspace_trends():
    called = []
    trends = SimpleNamespace(topics=lambda **kw: called.append(kw) or [{"topic": "public"}])
    result = execute_role("Scout", {}, engines=RoleEngines(trends=trends))
    assert result == {"role": "Scout", "status": "observed", "topics": [{"topic": "public"}]}
    assert called == [{"window_hours": 72, "min_channels": 3, "limit": 5}]


def test_role_resources_close_workspace_watchers_only():
    closed = []
    watcher = SimpleNamespace(close=lambda: closed.append("scout"))
    poster_watcher = SimpleNamespace(close=lambda: closed.append("poster"))
    release_role_resources("Scout", RoleEngines(trends=watcher))
    release_role_resources(
        "Poster",
        RoleEngines(pipeline=SimpleNamespace(trends=poster_watcher)),
    )
    release_role_resources("Director", RoleEngines(gtm=SimpleNamespace(close=lambda: closed.append("bad"))))
    assert closed == ["scout", "poster"]


@pytest.mark.parametrize("role", ["Scout", "Poster"])
def test_role_cleanup_error_is_recorded_without_masking_a_completed_action(
    monkeypatch, role,
):
    """D-486: cleanup failure must not make owner repeat an already-created draft."""
    import offsetx_apollo_builder.agent.role_team as role_team

    errors = []
    monkeypatch.setattr(
        role_team, "report_failure",
        lambda exc, *, operation: errors.append((operation, type(exc).__name__)),
    )

    def broken_close():
        raise RuntimeError("PRIVATE-ADAPTER-DIAGNOSTIC")

    watcher = SimpleNamespace(close=broken_close)
    engines = (
        RoleEngines(trends=watcher) if role == "Scout" else
        RoleEngines(pipeline=SimpleNamespace(trends=watcher))
    )
    # A single request finishing its work must not turn into an unknown
    # 500 response merely because its private watcher failed during teardown.
    release_role_resources(role, engines)
    assert errors == [("agent.role.watcher_cleanup", "RuntimeError")]


def test_maker_reuses_existing_video_director_and_review_gated_assembler():
    called = []
    def assemble(campaign_id, *, topic):
        called.append((campaign_id, topic))
        return tuple(SimpleNamespace(to_dict=lambda i=i: {"object": i}) for i in range(3))
    result = execute_role(
        "Maker", {"campaign_id": "campaign", "topic": "Short public explainer"},
        engines=RoleEngines(video=SimpleNamespace(direct_and_assemble=assemble)),
    )
    assert result["status"] == "needs_review"
    assert result["project"] == {"object": 0}
    assert called == [("campaign", "Short public explainer")]


def test_poster_drafts_only_and_never_calls_approval_or_publish():
    called = []
    def draft(**kw):
        called.append(kw)
        return SimpleNamespace(to_dict=lambda: {"draft_ids": ["one"]})
    result = execute_role(
        "Poster",
        {"campaign_id": "dist", "image_campaign_id": "image", "account_ids": ["account"]},
        engines=RoleEngines(pipeline=SimpleNamespace(draft=draft)),
    )
    assert result["status"] == "drafts_only"
    assert result["drafts"]["draft_ids"] == ["one"]
    assert called == [{
        "distribution_campaign_id": "dist",
        "image_campaign_id": "image",
        "account_ids": ("account",), "limit": 5,
    }]


def test_analyst_reads_metrics_and_director_only_drafts_strategy():
    dist = SimpleNamespace(
        progress=lambda cid: {"campaign_id": cid, "views": 20},
        generator_performance=lambda cid: [{"provider": "test"}],
    )
    analyst = execute_role(
        "Analyst", {"campaign_id": "one"}, engines=RoleEngines(distribution=dist),
    )
    assert analyst["status"] == "read_only"
    assert analyst["progress"]["views"] == 20
    calls = []
    gtm = SimpleNamespace(draft_plan=lambda values: calls.append(values) or {"status": "draft"})
    director = execute_role(
        "Director", {"gtm_request": {"product_id": "p", "goal": "reach"}},
        engines=RoleEngines(gtm=gtm),
    )
    assert director["status"] == "draft_only"
    assert calls == [{"product_id": "p", "goal": "reach"}]


def test_no_role_can_invent_an_action_or_autopublish():
    for role, body in [
        ("Publisher", {"campaign_id": "one"}),
        ("Poster", {"campaign_id": "one", "account_ids": []}),
        ("Maker", {"campaign_id": "one", "topic": ""}),
        ("Analyst", {}),
        ("Director", {}),
    ]:
        with pytest.raises(CompanionError):
            execute_role(role, body, engines=RoleEngines())


@pytest.mark.parametrize("payload", [
    {"role": "Maker", "campaign_id": "synthetic", "topic": "Public explainer"},
    {"role": "Poster", "campaign_id": "synthetic", "image_campaign_id": "approved",
     "account_ids": ["account"]},
    {"role": "Director", "gtm_request": {"product_id": "synthetic"}},
])
def test_role_api_replays_consequential_actions_by_key_without_reexecuting(
    tmp_path, monkeypatch, payload,
):
    """D-489/A14: one owner key must not create two drafts or paid actions."""
    import offsetx_apollo_builder.agent.role_team as role_team

    calls = []
    def synthetic_action(role, values, *, engines):
        calls.append((role, values))
        return {"role": role, "status": "needs_review", "result": "synthetic"}

    monkeypatch.setattr(role_team, "execute_role", synthetic_action)
    settings = AppSettings(
        project_root=Path.cwd(), database_path=tmp_path / "crm.db",
        data_dir=tmp_path / "data", export_dir=tmp_path / "exports",
        frontend_dist=tmp_path / "missing-dist", host="127.0.0.1",
        api_token=OWNER, allowed_hosts=("testserver",),
    )
    with TestClient(create_app(settings)) as client:
        assert client.post(
            "/api/v1/agent-team/provision", headers=HEADERS,
        ).status_code == 200
        unkeyed = client.post(
            "/api/v1/agent-team/execute", json=payload, headers=HEADERS,
        )
        assert unkeyed.status_code == 422
        assert calls == []

        headers = {**HEADERS, "Idempotency-Key": "agent-role-qa-once"}
        first = client.post(
            "/api/v1/agent-team/execute", json=payload, headers=headers,
        )
        assert first.status_code == 200, first.text
        repeated = client.post(
            "/api/v1/agent-team/execute", json=payload, headers=headers,
        )
        assert repeated.status_code == 200, repeated.text
        assert repeated.json().get("idempotent_replay") is True
        assert len(calls) == 1

        changed = dict(payload)
        changed["topic"] = "Different action with the same receipt"
        conflict = client.post(
            "/api/v1/agent-team/execute", json=changed, headers=headers,
        )
        assert conflict.status_code == 409
        assert len(calls) == 1


def test_role_api_does_not_retry_uncertain_poster_action_after_error(tmp_path, monkeypatch):
    """D-489/A14: an in-progress claim survives a crashed external side effect."""
    import offsetx_apollo_builder.agent.role_team as role_team

    attempts = []

    def uncertain_post(*args, **kwargs):
        attempts.append(True)
        raise RuntimeError("PRIVATE-PROVIDER-ERROR-NEVER-ECHO")

    monkeypatch.setattr(role_team, "execute_role", uncertain_post)
    settings = AppSettings(
        project_root=Path.cwd(), database_path=tmp_path / "crm.db",
        data_dir=tmp_path / "data", export_dir=tmp_path / "exports",
        frontend_dist=tmp_path / "missing-dist", host="127.0.0.1",
        api_token=OWNER, allowed_hosts=("testserver",),
    )
    with TestClient(create_app(settings), raise_server_exceptions=False) as client:
        assert client.post("/api/v1/agent-team/provision", headers=HEADERS).status_code == 200
        headers = {**HEADERS, "Idempotency-Key": "uncertain-draft-creation"}
        payload = {"role": "Poster", "campaign_id": "campaign",
                   "image_campaign_id": "images", "account_ids": ["account"]}
        first = client.post("/api/v1/agent-team/execute", json=payload, headers=headers)
        assert first.status_code == 500
        assert "PRIVATE-PROVIDER-ERROR-NEVER-ECHO" not in first.text
        repeated = client.post("/api/v1/agent-team/execute", json=payload, headers=headers)
        assert repeated.status_code == 409, repeated.text
        assert "uncertain" in repeated.text.lower() or "in progress" in repeated.text.lower()
        assert attempts == [True], "Second click must never rerun an uncertain action"


def test_role_api_requires_owner_provision_and_denies_unauthenticated_access(tmp_path):
    settings = AppSettings(
        project_root=Path.cwd(), database_path=tmp_path / "crm.db",
        data_dir=tmp_path / "data", export_dir=tmp_path / "exports",
        frontend_dist=tmp_path / "missing-dist", host="127.0.0.1",
        api_token=OWNER, allowed_hosts=("testserver",),
    )
    with TestClient(create_app(settings)) as client:
        path = "/api/v1/agent-team/execute"
        request = {"role": "Scout"}
        assert client.post(path, json=request).status_code == 401
        assert client.post(path, json=request, headers=HEADERS).status_code == 409
        provision = client.post("/api/v1/agent-team/provision", headers=HEADERS)
        assert provision.status_code == 200, provision.text
        assert len(provision.json()["items"]) == 5
        result = client.post(path, json=request, headers=HEADERS)
        assert result.status_code == 200, result.text
        assert result.json()["role"] == "Scout"
        assert result.json()["status"] == "observed"
        assert result.json()["topics"] == []
        second = client.post("/api/v1/agent-team/provision", headers=HEADERS)
        assert second.status_code == 200
        assert {item["id"] for item in provision.json()["items"]} == {
            item["id"] for item in second.json()["items"]
        }


def test_scout_api_returns_a_result_even_when_per_request_watcher_close_fails(
    tmp_path, monkeypatch,
):
    """D-486: a completed Scout API call must not become a false retryable 500."""
    import offsetx_apollo_builder.agent.role_team as role_team
    from offsetx_apollo_builder.distribution.trends import TrendWatcher

    settings = AppSettings(
        project_root=Path.cwd(), database_path=tmp_path / "crm.db",
        data_dir=tmp_path / "data", export_dir=tmp_path / "exports",
        frontend_dist=tmp_path / "missing-dist", host="127.0.0.1",
        api_token=OWNER, allowed_hosts=("testserver",),
    )
    failures = []
    with TestClient(create_app(settings), raise_server_exceptions=False) as client:
        assert client.post(
            "/api/v1/agent-team/provision", headers=HEADERS,
        ).status_code == 200

        def broken_close(self):
            raise RuntimeError("DO-NOT-ECHO-PRIVATE-WATCHER-DETAILS")

        with monkeypatch.context() as scoped:
            scoped.setattr(TrendWatcher, "close", broken_close)
            scoped.setattr(
                role_team, "report_failure",
                lambda exc, *, operation: failures.append(
                    (operation, type(exc).__name__)
                ),
            )
            result = client.post(
                "/api/v1/agent-team/execute",
                json={"role": "Scout"}, headers=HEADERS,
            )
        assert result.status_code == 200, result.text
        assert result.json()["role"] == "Scout"
        assert result.json()["status"] == "observed"
        assert failures == [("agent.role.watcher_cleanup", "RuntimeError")]
        assert "DO-NOT-ECHO" not in result.text


def test_analyst_wrong_campaign_reports_actionable_public_reason(tmp_path):
    """D-462: content analytics must explain an email-campaign refusal safely."""
    settings = AppSettings(
        project_root=Path.cwd(), database_path=tmp_path / "crm.db",
        data_dir=tmp_path / "data", export_dir=tmp_path / "exports",
        frontend_dist=tmp_path / "missing-dist", host="127.0.0.1",
        api_token=OWNER, allowed_hosts=("testserver",),
    )
    with TestClient(create_app(settings)) as client:
        campaign_id = client.app.state.engine.store.create_campaign(
            name="Email outreach", daily_send_limit=10, kind="email",
        )
        assert client.post(
            "/api/v1/agent-team/provision", headers=HEADERS,
        ).status_code == 200
        result = client.post(
            "/api/v1/agent-team/execute",
            json={"role": "Analyst", "campaign_id": campaign_id},
            headers=HEADERS,
        )
        assert result.status_code == 409
        detail = result.json()["detail"].lower()
        assert "distribution" in detail
        assert "campaign" in detail
        assert "select" in detail
        assert campaign_id.lower() not in detail
        assert "existing engine refused" not in detail



def test_analyst_real_api_reads_distribution_campaign_without_side_effects(tmp_path):
    """F-04.01: owner can run Analyst on a real empty campaign without a model."""
    settings = AppSettings(
        project_root=Path.cwd(), database_path=tmp_path / "crm.db",
        data_dir=tmp_path / "data", export_dir=tmp_path / "exports",
        frontend_dist=tmp_path / "missing-dist", host="127.0.0.1",
        api_token=OWNER, allowed_hosts=("testserver",),
    )
    with TestClient(create_app(settings)) as client:
        campaign_id = client.app.state.engine.store.create_campaign(
            name="Distribution audit", daily_send_limit=10, kind="distribution",
        )
        provision = client.post("/api/v1/agent-team/provision", headers=HEADERS)
        assert provision.status_code == 200, provision.text
        before = client.app.state.distribution_store.list_posts(
            campaign_id=campaign_id, workspace_id="local",
        )
        result = client.post(
            "/api/v1/agent-team/execute",
            json={"role": "Analyst", "campaign_id": campaign_id},
            headers=HEADERS,
        )
        assert result.status_code == 200, result.text
        payload = result.json()
        assert payload["role"] == "Analyst"
        assert payload["status"] == "read_only"
        assert payload["progress"]["totals"]["views"] == 0
        assert isinstance(payload["generator_performance"], list)
        after = client.app.state.distribution_store.list_posts(
            campaign_id=campaign_id, workspace_id="local",
        )
        assert before == after == []
