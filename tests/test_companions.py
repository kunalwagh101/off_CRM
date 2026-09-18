from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from offsetx_apollo_builder.agent.companions import (
    CompanionError,
    CompanionStore,
    approved_memory_loader,
)
from offsetx_apollo_builder.api.app import create_app
from offsetx_apollo_builder.api.config import AppSettings


def test_companion_profile_persists_and_names_are_workspace_scoped(tmp_path: Path) -> None:
    path = tmp_path / "companions.db"
    store = CompanionStore(path)
    scout = store.create(
        workspace_id="alpha",
        name="Scout",
        instructions="Research before acting.",
        memory_scope="campaign:carbon",
        granted_tools=("goto", "read"),
    )
    with pytest.raises(CompanionError, match="already exists"):
        store.create(
            workspace_id="alpha",
            name=" scout ",
            instructions="duplicate",
            memory_scope="global",
            granted_tools=(),
        )
    other = store.create(
        workspace_id="beta",
        name="Scout",
        instructions="Different workspace.",
        memory_scope="global",
        granted_tools=("read",),
    )
    assert other.id != scout.id
    store.close()

    reopened = CompanionStore(path)
    loaded = reopened.require(scout.id, workspace_id="alpha")
    assert loaded.name == "Scout"
    assert loaded.instructions == "Research before acting."
    assert loaded.memory_scope == "campaign:carbon"
    assert loaded.granted_tools == ("goto", "read")
    assert reopened.get(scout.id, workspace_id="beta") is None
    reopened.close()


def test_companion_refuses_undeclared_browser_tools(tmp_path: Path) -> None:
    store = CompanionStore(tmp_path / "companions.db")
    with pytest.raises(CompanionError, match="unknown browser tool"):
        store.create(
            workspace_id="local",
            name="Unsafe",
            instructions="",
            memory_scope="global",
            granted_tools=("read", "evaluate"),
        )


def test_runtime_loads_only_the_declared_memory_scope(tmp_path: Path) -> None:
    store = CompanionStore(tmp_path / "companions.db")
    profile = store.create(
        workspace_id="alpha",
        name="Analyst",
        instructions="Summarise evidence.",
        memory_scope="campaign:one",
        granted_tools=("read",),
    )
    calls: list[tuple[str, str]] = []

    def loader(workspace_id: str, scope: str) -> str:
        calls.append((workspace_id, scope))
        return "memory for one"

    runtime = store.runtime(
        profile.id,
        workspace_id="alpha",
        memory_loader=loader,
    )
    assert calls == [("alpha", "campaign:one")]
    assert runtime.memory_context == "memory for one"

    with pytest.raises(CompanionError, match="not found"):
        store.runtime(profile.id, workspace_id="beta", memory_loader=loader)
    assert calls == [("alpha", "campaign:one")]


def _settings(tmp_path: Path) -> AppSettings:
    return AppSettings(
        project_root=Path.cwd(),
        database_path=tmp_path / "outreach.db",
        data_dir=tmp_path / "data",
        export_dir=tmp_path / "exports",
        frontend_dist=tmp_path / "missing-dist",
        allow_unauthenticated=True,
    )


def test_companion_api_is_typed_persisted_and_owner_editable(tmp_path: Path) -> None:
    app = create_app(_settings(tmp_path))
    with TestClient(app) as client:
        created = client.post(
            "/api/v1/ai/companions",
            json={
                "name": "Poster",
                "instructions": "Prepare the post but do not publish.",
                "memory_scope": "campaign:launch",
                "granted_tools": ["goto", "read", "screenshot"],
            },
        )
        assert created.status_code == 201
        companion_id = created.json()["id"]

        listed = client.get("/api/v1/ai/companions").json()
        assert listed["total"] == 1
        assert listed["items"][0]["name"] == "Poster"
        assert set(listed["browser_tools"]) >= {"goto", "read", "click"}

        updated = client.patch(
            f"/api/v1/ai/companions/{companion_id}",
            json={"granted_tools": ["read"], "enabled": False},
        )
        assert updated.status_code == 200
        assert updated.json()["granted_tools"] == ["read"]
        assert updated.json()["enabled"] is False

        active = client.get("/api/v1/ai/companions?include_disabled=false").json()
        assert active["items"] == []

        bad = client.post(
            "/api/v1/ai/companions",
            json={
                "name": "Bad Tool",
                "memory_scope": "global",
                "granted_tools": ["shell"],
            },
        )
        assert bad.status_code == 422

        deleted = client.delete(f"/api/v1/ai/companions/{companion_id}")
        assert deleted.status_code == 200
        assert deleted.json() == {"deleted": True}
        assert client.get(f"/api/v1/ai/companions/{companion_id}").status_code == 404


def test_approved_memory_loader_never_reads_outside_scope_or_unapproved_items() -> None:
    calls = []

    class Backend:
        def search_memory_items(self, query="", **filters):
            calls.append((query, filters))
            return ([{"content": "approved fact"}], 1)

    loader = approved_memory_loader(Backend(), limit=25)
    assert loader("alpha", "campaign:one") == "approved fact"
    assert calls == [
        (
            "",
            {
                "workspace_id": "alpha",
                "scope": "campaign:one",
                "approved_only": True,
                "include_global": False,
                "limit": 25,
                "offset": 0,
            },
        )
    ]


def test_real_memory_backend_can_exclude_global_and_unapproved_items(tmp_path: Path) -> None:
    app = create_app(_settings(tmp_path))
    with TestClient(app) as client:
        backend = app.state.engine.store
        backend.add_memory_item(
            workspace_id="local",
            scope="global",
            kind="manual",
            content="GLOBAL SHOULD NOT APPEAR",
            tags=[],
            metadata={},
            confidence=1.0,
            approved=True,
            source_type="manual",
        )
        backend.add_memory_item(
            workspace_id="local",
            scope="campaign:one",
            kind="manual",
            content="SCOPED APPROVED",
            tags=[],
            metadata={},
            confidence=1.0,
            approved=True,
            source_type="manual",
        )
        backend.add_memory_item(
            workspace_id="local",
            scope="campaign:one",
            kind="manual",
            content="SCOPED UNAPPROVED",
            tags=[],
            metadata={},
            confidence=1.0,
            approved=False,
            source_type="manual",
        )

        loaded = approved_memory_loader(backend)("local", "campaign:one")
        assert loaded == "SCOPED APPROVED"
        assert "GLOBAL SHOULD NOT APPEAR" not in loaded
        assert "SCOPED UNAPPROVED" not in loaded


def test_companion_store_serializes_concurrent_worker_threads(tmp_path: Path) -> None:
    store = CompanionStore(tmp_path / "companions.db")

    def create(index: int) -> str:
        return store.create(
            workspace_id="local",
            name=f"Worker {index}",
            instructions="",
            memory_scope=f"scope:{index}",
            granted_tools=("read",),
        ).id

    with ThreadPoolExecutor(max_workers=8) as pool:
        ids = list(pool.map(create, range(24)))

    assert len(set(ids)) == 24
    assert len(store.list(workspace_id="local")) == 24
    store.close()
