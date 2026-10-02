"""S-06.03.01: every store off_CRM keeps is known, with where it lives.

On Render's free plan the data folder is wiped on every deploy, restart and
spin-down, so the list of what lives there is what `F-06.03` has to move. It is
checked against the running app, not kept by hand: a service added to start-up,
or a file written under the data folder, fails here until it is classified.
"""
from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from offsetx_apollo_builder import db_cli
from offsetx_apollo_builder.api.app import create_app
from offsetx_apollo_builder.api.config import AppSettings
from offsetx_apollo_builder.db import inventory

API = "/api/v1"
TOKEN = "inventory-install-token-" + "x" * 24
DOC = Path(__file__).resolve().parents[1] / "docs" / "architecture" / "HOSTED_STORAGE.md"


@pytest.fixture
def running(tmp_path, monkeypatch):
    monkeypatch.delenv("OFFSETX_DATABASE_URL", raising=False)
    monkeypatch.delenv("OFFSETX_SECRETS_KEY", raising=False)
    data = tmp_path / "data"
    settings = AppSettings(
        project_root=Path.cwd(),
        database_path=data / "offsetx_outreach.db",
        data_dir=data,
        export_dir=data / "exports",
        frontend_dist=tmp_path / "no-frontend",
        host="127.0.0.1",
        api_token=TOKEN,
        allowed_hosts=("testserver",),
    )
    app = create_app(settings)
    with TestClient(app, headers={"X-Offsetx-Token": TOKEN}) as client:
        yield app, client, data


def _files(data: Path) -> list[str]:
    return sorted(p.relative_to(data).as_posix() for p in data.rglob("*") if p.is_file())


def test_every_service_the_app_opens_is_classified(running):
    app, _, _ = running
    opened = set(vars(app.state)["_state"])
    named = {thing.service for thing in inventory.STORES if thing.service} | inventory.NOT_STORES
    assert sorted(opened - named) == [], "add these to db/inventory.py, as a store or as keeping nothing"
    assert sorted(named - opened) == [], "the inventory names services the app no longer opens"


def test_every_file_the_app_writes_belongs_to_a_store(running):
    app, client, data = running
    # The stores the hosted database takes first write lazily: make each write.
    connected = client.post(f"{API}/ai/providers/nvidia/connect", json={
        "api_key": "nvapi-inventory", "model_ids": ["nvidia/nemotron-3-ultra-550b-a55b"],
        "requests_per_day": 200, "max_spend_usd_per_day": 5,
    })
    assert connected.status_code == 200, connected.text
    trusted = client.post(f"{API}/ai/providers/nvidia/trust", json={"tier": "D"})
    assert trusted.status_code == 200, trusted.text
    made = client.post(f"{API}/workspaces", json={
        "username": "colleague", "workspace_id": "beta", "password": "beta-password-1"})
    assert made.status_code == 201, made.text
    app.state.ai_quota.record("nvidia", spend_usd=0.01)
    app.state.ai_egress_log.record(provider_id="nvidia", status="ok")
    written = _files(data)
    for name in ("ai_workspaces.json", "ai_provider_keys.enc", "ai_quota.json", "workspace_auth.db", "ai_egress.db"):
        assert name in written
    assert [name for name in written if inventory.owner_of(name) is None] == []


def test_the_design_document_shows_the_inventory_as_generated():
    text = DOC.read_text(encoding="utf-8")
    start, end = "<!-- inventory:start -->", "<!-- inventory:end -->"
    assert start in text and end in text, "HOSTED_STORAGE.md has no generated inventory table"
    shown = text[text.index(start) + len(start):text.index(end)].strip()
    assert shown == inventory.markdown_table(), "regenerate it: offsetx-db inventory --markdown"


def test_the_inventory_command_reports_each_store_and_what_it_holds_on_disk(tmp_path, capsys):
    (tmp_path / "ai_workspaces.json").write_text("{" + " " * 2046 + "}", encoding="utf-8")
    (tmp_path / "workspace_auth.db").write_bytes(b"\0" * 4096)
    assert db_cli.main(["inventory", "--data-dir", str(tmp_path)]) == 0
    printed = capsys.readouterr().out
    rows = {line.split("  ")[0].strip(): line for line in printed.splitlines() if "  " in line}
    assert "2.0 KB" in rows["AI settings and trust"]
    assert "4.0 KB" in rows["Workspace logins"]
    assert "hosted database" in rows["Workspace logins"]
    assert db_cli.main(["inventory", "--markdown"]) == 0
    assert capsys.readouterr().out.strip() == inventory.markdown_table()


def test_every_file_the_code_names_in_the_data_folder_belongs_to_a_store():
    """D-215: a file a store writes only later — the Gmail token on refresh — or
    a command-line tool writes was in no entry, and the run above cannot see it.
    So the code itself is read: every name joined onto a data folder."""
    import re

    package = Path(__file__).resolve().parents[1] / "offsetx_apollo_builder"
    joined = re.compile(r"\bdata_dir(?:\([^)]*\))?\s*/\s*\"([^\"]+)\"")
    named = set()
    for source in package.rglob("*.py"):
        named.update(joined.findall(source.read_text(encoding="utf-8")))
    assert named, "the pattern no longer finds the data folder's files"
    assert sorted(name for name in named if inventory.owner_of(name) is None) == []
