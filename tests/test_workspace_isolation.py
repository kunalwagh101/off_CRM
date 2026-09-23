from __future__ import annotations

from pathlib import Path
import json
import threading

from fastapi.testclient import TestClient
import pytest

from offsetx_apollo_builder.ai.registry import ProviderRegistry
from offsetx_apollo_builder.ai.workspace import WorkspaceAISettingsStore
from offsetx_apollo_builder.api.app import create_app
from offsetx_apollo_builder.api.auth import WorkspaceAuthError, WorkspaceAuthStore
from offsetx_apollo_builder.api.config import AppSettings
from offsetx_apollo_builder.browser.vault import SessionVault


SESSION_SECRET = "workspace-session-secret-" + "x" * 32
ADMIN_TOKEN = "workspace-admin-token-" + "y" * 32


def _settings(tmp_path: Path) -> AppSettings:
    return AppSettings(
        project_root=Path.cwd(),
        database_path=tmp_path / "crm.db",
        data_dir=tmp_path / "data",
        export_dir=tmp_path / "exports",
        frontend_dist=tmp_path / "missing-dist",
        host="127.0.0.1",
        api_token=ADMIN_TOKEN,
        session_secret=SESSION_SECRET,
        allowed_hosts=("testserver",),
    )


def test_two_workspace_logins_resolve_to_different_workspace_ids(tmp_path):
    auth = WorkspaceAuthStore(
        tmp_path / "auth.db",
        session_secret=SESSION_SECRET,
        session_hours=8,
    )
    alice = auth.create(
        username="alice",
        workspace_id="alpha",
        password="alice-password-123",
    )
    bob = auth.create(
        username="bob",
        workspace_id="beta",
        password="bob-password-456",
    )

    alice_login = auth.authenticate("alice", "alice-password-123")
    bob_login = auth.authenticate("bob", "bob-password-456")
    assert alice_login is not None and alice_login.workspace_id == "alpha"
    assert bob_login is not None and bob_login.workspace_id == "beta"
    assert auth.verify(auth.issue(alice)).workspace_id == "alpha"
    assert auth.verify(auth.issue(bob)).workspace_id == "beta"


@pytest.mark.parametrize("username", ["nora", "xavier", "user0"])
def test_workspace_username_validation_accepts_normal_characters(tmp_path, username):
    auth = WorkspaceAuthStore(
        tmp_path / f"{username}.db",
        session_secret=SESSION_SECRET,
        session_hours=8,
    )
    identity = auth.create(
        username=username,
        workspace_id=f"ws-{username}".replace("_", "-"),
        password="valid-password-123",
    )

    assert identity.username == username
    assert auth.authenticate(username, "valid-password-123") is not None


@pytest.mark.parametrize("username", ["bad\nname", "bad\x00name"])
def test_workspace_username_validation_refuses_control_characters(tmp_path, username):
    auth = WorkspaceAuthStore(
        tmp_path / "invalid-user.db",
        session_secret=SESSION_SECRET,
        session_hours=8,
    )

    with pytest.raises(WorkspaceAuthError, match="username"):
        auth.create(
            username=username,
            workspace_id="valid-workspace",
            password="valid-password-123",
        )


def test_password_rotation_invalidates_existing_workspace_sessions(tmp_path):
    auth = WorkspaceAuthStore(
        tmp_path / "auth.db",
        session_secret=SESSION_SECRET,
        session_hours=8,
    )
    identity = auth.create(
        username="alice",
        workspace_id="alpha",
        password="alice-password-123",
    )
    old_cookie = auth.issue(identity)
    assert auth.verify(old_cookie) is not None

    auth.set_password("alice", "alice-new-password-789")

    assert auth.verify(old_cookie) is None
    assert auth.authenticate("alice", "alice-password-123") is None
    assert auth.authenticate("alice", "alice-new-password-789") is not None


def test_provider_keys_are_encrypted_and_workspace_isolated(tmp_path):
    store = WorkspaceAISettingsStore(tmp_path / "ai", ProviderRegistry())
    store.set_key("alpha", "mistral", "ALPHA-PROVIDER-SECRET")
    store.set_key("beta", "mistral", "BETA-PROVIDER-SECRET")

    assert store.key_for("alpha", "mistral") == "ALPHA-PROVIDER-SECRET"
    assert store.key_for("beta", "mistral") == "BETA-PROVIDER-SECRET"
    assert store.key_for("alpha", "openai") == ""

    raw = b"".join(
        path.read_bytes()
        for path in (tmp_path / "ai").rglob("*")
        if path.is_file()
    )
    assert b"ALPHA-PROVIDER-SECRET" not in raw
    assert b"BETA-PROVIDER-SECRET" not in raw


def test_independent_workspace_stores_do_not_lose_concurrent_provider_updates(
    tmp_path, monkeypatch
):
    data_dir = tmp_path / "ai"
    first = WorkspaceAISettingsStore(data_dir, ProviderRegistry())
    second = WorkspaceAISettingsStore(data_dir, ProviderRegistry())
    barrier = threading.Barrier(2)
    errors = []

    def synchronize_the_old_two_read_path(store):
        original = store._document
        state = {"calls": 0}
        guard = threading.Lock()

        def wrapped():
            document = original()
            with guard:
                state["calls"] += 1
                call_number = state["calls"]
            # Before the fix connect_provider() performed one read via raw()
            # and a second read inside save(). Force both stores to take that
            # second snapshot before either replaces the shared document.
            if call_number == 2:
                barrier.wait(timeout=5)
            return document

        monkeypatch.setattr(store, "_document", wrapped)
        return original

    first_document = synchronize_the_old_two_read_path(first)
    second_document = synchronize_the_old_two_read_path(second)

    def connect(store, workspace_id, key):
        try:
            store.connect_provider(
                workspace_id,
                "mistral",
                api_key=key,
                model_id="mistral-small-latest",
            )
        except BaseException as exc:
            errors.append(exc)

    one = threading.Thread(
        target=connect, args=(first, "alpha", "ALPHA-CONCURRENT-KEY")
    )
    two = threading.Thread(
        target=connect, args=(second, "beta", "BETA-CONCURRENT-KEY")
    )
    one.start()
    two.start()
    one.join(timeout=10)
    two.join(timeout=10)

    assert not one.is_alive() and not two.is_alive()
    assert errors == []
    monkeypatch.setattr(first, "_document", first_document)
    monkeypatch.setattr(second, "_document", second_document)
    assert first.raw("alpha")["providers"]["mistral"]["enabled"] is True
    assert first.raw("beta")["providers"]["mistral"]["enabled"] is True
    assert first.key_for("alpha", "mistral") == "ALPHA-CONCURRENT-KEY"
    assert first.key_for("beta", "mistral") == "BETA-CONCURRENT-KEY"


def test_browser_sessions_are_workspace_isolated_for_the_same_platform(tmp_path, monkeypatch):
    from offsetx_apollo_builder.browser import vault as vault_module

    monkeypatch.setattr(vault_module, "_keychain_master", lambda create: (None, ""))
    vault = SessionVault(
        tmp_path / "vault",
        passphrase="workspace-vault-passphrase-long-enough",
    )
    vault.seal(
        "alpha",
        "linkedin",
        {"cookies": [{"name": "li_at", "value": "ALPHA-COOKIE", "domain": ".linkedin.com"}]},
    )
    vault.seal(
        "beta",
        "linkedin",
        {"cookies": [{"name": "li_at", "value": "BETA-COOKIE", "domain": ".linkedin.com"}]},
    )

    assert vault.unseal("alpha", "linkedin")["cookies"][0]["value"] == "ALPHA-COOKIE"
    assert vault.unseal("beta", "linkedin")["cookies"][0]["value"] == "BETA-COOKIE"
    assert vault.inspect("alpha", "linkedin").key_id != vault.inspect("beta", "linkedin").key_id


def test_authenticated_workspace_selects_only_its_provider_keys(tmp_path):
    settings = _settings(tmp_path)
    with TestClient(create_app(settings)) as admin:
        headers = {"X-Offsetx-Token": ADMIN_TOKEN}
        for username, workspace, password in (
            ("alice", "alpha", "alice-password-123"),
            ("bob", "beta", "bob-password-456"),
        ):
            response = admin.post(
                "/api/v1/workspaces",
                headers=headers,
                json={
                    "username": username,
                    "workspace_id": workspace,
                    "password": password,
                },
            )
            assert response.status_code == 201

        alice = TestClient(admin.app)
        login = alice.post(
            "/api/v1/auth/login",
            json={"username": "alice", "password": "alice-password-123"},
        )
        assert login.status_code == 200
        assert login.json()["workspace_id"] == "alpha"
        connected = alice.post(
            "/api/v1/ai/providers/mistral/connect",
            json={"api_key": "ALPHA-KEY", "model_id": "mistral-small-latest"},
        )
        assert connected.status_code == 200
        assert connected.json()["workspace"] == "alpha"

        bob = TestClient(admin.app)
        login = bob.post(
            "/api/v1/auth/login",
            json={"username": "bob", "password": "bob-password-456"},
        )
        assert login.status_code == 200
        assert login.json()["workspace_id"] == "beta"
        providers = bob.get("/api/v1/ai/providers")
        assert providers.status_code == 200
        assert providers.json()["workspace_id"] == "beta"
        mistral = next(item for item in providers.json()["providers"] if item["id"] == "mistral")
        assert mistral["has_key"] is False

        # The install-level API token is backward-compatible and deliberately
        # remains the local workspace rather than impersonating a team member.
        local = admin.get("/api/v1/auth/session", headers=headers)
        assert local.status_code == 200
        assert local.json()["workspace_id"] == "local"


def test_workspace_admin_routes_are_not_available_to_a_workspace_session(tmp_path):
    settings = _settings(tmp_path)
    with TestClient(create_app(settings)) as client:
        headers = {"X-Offsetx-Token": ADMIN_TOKEN}
        assert client.post(
            "/api/v1/workspaces",
            headers=headers,
            json={
                "username": "alice",
                "workspace_id": "alpha",
                "password": "alice-password-123",
            },
        ).status_code == 201

        assert client.post(
            "/api/v1/auth/login",
            json={"username": "alice", "password": "alice-password-123"},
        ).status_code == 200

        response = client.post(
            "/api/v1/workspaces",
            json={
                "username": "mallory",
                "workspace_id": "mallory",
                "password": "mallory-password-123",
            },
        )
        assert response.status_code == 403


def test_a_workspace_login_cannot_export_or_restore_the_whole_install(tmp_path):
    """A backup holds every workspace at once — each login, each provider key,
    the install token and the key that signs every session — and a restore
    replaces all of them. Both answered any login (D-124): a workspace could
    export, read the install token out of its own archive, and administer."""
    settings = _settings(tmp_path)
    admin = {"X-Offsetx-Token": ADMIN_TOKEN}
    with TestClient(create_app(settings)) as client:
        assert client.post(
            "/api/v1/workspaces",
            headers=admin,
            json={"username": "alice", "workspace_id": "alpha", "password": "alice-password-123"},
        ).status_code == 201
        assert client.post(
            "/api/v1/auth/login",
            json={"username": "alice", "password": "alice-password-123"},
        ).status_code == 200

        exported = client.post("/api/v1/backups/export", json={"passphrase": "alpha-chose-this-phrase"})
        assert exported.status_code == 403
        assert "owner" in exported.json()["detail"]
        # Refused before the upload is even validated: a 422 here would mean the
        # check ran after the archive was opened with the caller's passphrase.
        restored = client.post(
            "/api/v1/backups/restore",
            files={"file": ("w.oxbackup", b"not a backup")},
            data={"passphrase": "alpha-chose-this-phrase"},
        )
        assert restored.status_code == 403

        client.cookies.clear()
        owner = client.post(
            "/api/v1/backups/export", headers=admin, json={"passphrase": "owner-chose-this-phrase"}
        )
        assert owner.status_code == 200


SHARED_CONTACTS = b"""Full Name,Email,Company,Title,Category,Public Hook,Hook Source,Tension
Anita Rao,anita@example.com,Example Exports,Climate Lead,CBAM,Published a supplier emissions brief,https://example.com/anita,Supplier evidence handoff
"""
ACME_OFFER = "ACME-PRIVATE pricing: 40% off for the first 3 months"


def _two_workspaces_and_a_shared_campaign(client, app) -> tuple[str, str]:
    """acme links its private product to a campaign every login can see.

    Campaigns, contacts, drafts and templates are install-wide; a product is
    its workspace's. Returns (campaign id, product id)."""
    admin = {"X-Offsetx-Token": ADMIN_TOKEN}
    for workspace in ("acme", "beta"):
        assert client.post(
            "/api/v1/workspaces",
            headers=admin,
            json={"username": f"{workspace}-user", "workspace_id": workspace, "password": f"{workspace}-password-1"},
        ).status_code == 201
    campaign = client.post(
        "/api/v1/campaigns", headers=admin, json={"name": "Shared", "daily_send_limit": 2}
    ).json()["id"]
    assert client.post(
        f"/api/v1/campaigns/{campaign}/contacts/import",
        headers=admin,
        files={"file": ("c.csv", SHARED_CONTACTS, "text/csv")},
        data={"default_category": "Sustainability / ESG / Climate"},
    ).status_code == 200
    store = app.state.engine.store
    for template in store.list_templates(limit=1000)[0]:
        template = dict(template)
        template["body_template"] += "\n\nWe offer {product_offer}."
        store.upsert_template(template)
    _login(client, "acme")
    product = client.post(
        "/api/v1/gtm/products",
        json={
            "name": "Acme product",
            "one_liner": "Freight invoice reconciliation for finance teams",
            "audience": "Finance leads at logistics companies",
            "problem": "Carriers overbill and nobody checks every invoice",
            "offer": ACME_OFFER,
            "proof": [],
            "forbidden_claims": [],
        },
    ).json()
    assert client.put(
        f"/api/v1/gtm/products/{product['id']}/campaigns", json={"campaign_ids": [campaign]}
    ).status_code == 200
    return campaign, product["id"]


def _login(client, workspace: str) -> None:
    client.cookies.clear()
    assert client.post(
        "/api/v1/auth/login",
        json={"username": f"{workspace}-user", "password": f"{workspace}-password-1"},
    ).status_code == 200


def _generate(client, campaign: str) -> list[dict]:
    generated = client.post(
        f"/api/v1/campaigns/{campaign}/drafts/generate",
        json={"campaign_contact_ids": [], "stages": ["initial"], "provider": None},
    )
    assert generated.status_code == 200, generated.text
    return client.get(f"/api/v1/campaigns/{campaign}/drafts").json()["items"]


def test_a_workspace_cannot_draft_another_workspaces_product(tmp_path):
    """beta cannot read acme's product at /gtm, and could not before — but it
    could draft acme's campaign and read the offer out of the drafts, or add
    every product placeholder to the install-wide templates and read them all
    (D-125). The reader now asks with the caller's workspace."""
    app = create_app(_settings(tmp_path))
    with TestClient(app) as client:
        campaign, product_id = _two_workspaces_and_a_shared_campaign(client, app)
        _login(client, "beta")
        assert client.get(f"/api/v1/gtm/products/{product_id}").status_code == 404

        drafts = _generate(client, campaign)
        assert drafts
        assert ACME_OFFER not in json.dumps(drafts)
        # Blocked with the reason, not sent without its product's checks.
        assert all("another workspace" in json.dumps(draft) for draft in drafts)


def test_the_linking_workspace_still_drafts_its_own_product(tmp_path):
    """The other half: acme's own login drafts with its product (D-109)."""
    app = create_app(_settings(tmp_path))
    with TestClient(app) as client:
        campaign, _ = _two_workspaces_and_a_shared_campaign(client, app)
        drafts = _generate(client, campaign)
        assert drafts and all(ACME_OFFER in draft["body"] for draft in drafts)


def test_only_the_install_owner_runs_or_configures_the_content_timer(tmp_path):
    """The timer acts for the install, on the owner's keys and egress policy.
    Any login could run it now, or reconfigure what it runs (D-125)."""
    app = create_app(_settings(tmp_path))
    with TestClient(app) as client:
        _two_workspaces_and_a_shared_campaign(client, app)
        _login(client, "beta")
        assert client.post("/api/v1/content-automation/run").status_code == 403
        assert client.patch("/api/v1/content-automation", json={"enabled": False}).status_code == 403
        assert client.get("/api/v1/content-automation").status_code == 200

        client.cookies.clear()
        owner = {"X-Offsetx-Token": ADMIN_TOKEN}
        assert client.patch(
            "/api/v1/content-automation", headers=owner, json={"enabled": False}
        ).status_code == 200
        assert client.post("/api/v1/content-automation/run", headers=owner).status_code == 200


def test_the_demo_login_is_the_install_owner_and_keeps_its_backups(tmp_path):
    """On Render the owner signs in with the demo login and has no install
    token — one is made only when no login is configured. On the free plan a
    backup is how that owner keeps data across a deploy, so the owner check
    must not lock them out."""
    settings = _settings(tmp_path)
    settings.api_token = ""
    settings.demo_username = "owner"
    settings.demo_password = "owner-password-123"
    with TestClient(create_app(settings)) as client:
        assert client.post(
            "/api/v1/auth/login",
            json={"username": "owner", "password": "owner-password-123"},
        ).status_code == 200
        exported = client.post("/api/v1/backups/export", json={"passphrase": "owner-chose-this-phrase"})
        assert exported.status_code == 200


def test_backup_restores_workspace_keys_logins_and_routines_together(tmp_path):
    settings = _settings(tmp_path)
    headers = {"X-Offsetx-Token": ADMIN_TOKEN}
    passphrase = "workspace-recovery-passphrase"

    with TestClient(create_app(settings)) as client:
        created = client.post(
            "/api/v1/workspaces",
            headers=headers,
            json={
                "username": "alice",
                "workspace_id": "alpha",
                "password": "alice-password-123",
            },
        )
        assert created.status_code == 201

        client.app.state.ai_workspaces.set_key(
            "alpha", "mistral", "ALPHA-KEY-BEFORE-BACKUP"
        )
        routine = client.app.state.agent_routine_store.create(
            workspace_id="alpha",
            name="alpha-release-watch",
            goal="Watch the public release page.",
            target_url="https://example.com/releases",
            trigger_type="event",
            event_name="release.changed",
        )

        backup = client.post(
            "/api/v1/backups/export",
            headers=headers,
            json={"passphrase": passphrase},
        )
        assert backup.status_code == 200

        assert client.patch(
            "/api/v1/workspaces/alice",
            headers=headers,
            json={"password": "alice-password-after-backup"},
        ).status_code == 200
        client.app.state.ai_workspaces.set_key(
            "alpha", "mistral", "ALPHA-KEY-AFTER-BACKUP"
        )
        assert client.app.state.agent_routine_store.delete(
            routine.id, workspace_id="alpha"
        )

        restored = client.post(
            "/api/v1/backups/restore",
            headers=headers,
            files={
                "file": (
                    "workspace.oxbackup",
                    backup.content,
                    "application/octet-stream",
                )
            },
            data={"passphrase": passphrase},
        )
        assert restored.status_code == 200

        auth = WorkspaceAuthStore(
            settings.data_dir / "workspace_auth.db",
            session_secret=settings.session_secret,
            session_hours=settings.session_hours,
        )
        assert auth.authenticate("alice", "alice-password-123") is not None
        assert auth.authenticate("alice", "alice-password-after-backup") is None
        assert (
            client.app.state.ai_workspaces.key_for("alpha", "mistral")
            == "ALPHA-KEY-BEFORE-BACKUP"
        )
        assert client.app.state.agent_routine_store.get(
            routine.id, workspace_id="alpha"
        ) is not None



def test_bound_brokers_never_share_workspace_credentials_under_concurrency(
    tmp_path, monkeypatch
):
    from offsetx_apollo_builder.ai.broker import EgressBroker
    from offsetx_apollo_builder.ai.quota import QuotaTracker
    from offsetx_apollo_builder.ai.registry import ProviderRegistry
    from offsetx_apollo_builder.ai import broker as broker_module

    base = EgressBroker(
        registry=ProviderRegistry(Path.cwd() / "config" / "providers.yaml"),
        credential_resolver=lambda _provider_id: "",
        quota=QuotaTracker(tmp_path / "quota"),
    )
    alpha = base.with_credential_resolver(
        lambda provider_id: "ALPHA-KEY" if provider_id == "mistral" else ""
    )
    beta = base.with_credential_resolver(
        lambda provider_id: "BETA-KEY" if provider_id == "mistral" else ""
    )

    candidate = base.registry.resolve("mistral")
    barrier = threading.Barrier(2)
    seen: list[str] = []
    seen_lock = threading.Lock()

    def fake_create_provider(config, *, environ):
        barrier.wait(timeout=5)
        key = str(environ.get(config.api_key_env) or "")
        with seen_lock:
            seen.append(key)
        return object()

    monkeypatch.setattr(broker_module, "create_provider", fake_create_provider)

    failures: list[BaseException] = []

    def instantiate(bound):
        try:
            bound._instantiate(candidate)
        except BaseException as exc:
            failures.append(exc)

    left = threading.Thread(target=instantiate, args=(alpha,))
    right = threading.Thread(target=instantiate, args=(beta,))
    left.start()
    right.start()
    left.join(timeout=10)
    right.join(timeout=10)

    assert not failures
    assert sorted(seen) == ["ALPHA-KEY", "BETA-KEY"]
    assert base.credential_resolver("mistral") == ""
    assert alpha.credential_resolver("mistral") == "ALPHA-KEY"
    assert beta.credential_resolver("mistral") == "BETA-KEY"

    # Operational protection is shared even though credentials are not.
    assert alpha._lock is base._lock
    assert beta._lock is base._lock
    assert alpha._failures is base._failures
    assert beta._open_until is base._open_until


def test_api_never_mutates_the_shared_ai_broker_credential_resolver():
    from offsetx_apollo_builder.api import app as app_module

    source = Path(app_module.__file__).read_text(encoding="utf-8")
    assert ".credential_resolver =" not in source
    assert "with_credential_resolver(" in source


def test_a_session_secret_alone_is_a_valid_install_but_half_a_demo_login_is_not(tmp_path):
    """The secret signs workspace logins too. Refusing it without a demo
    username and password stopped every workspace-login install from starting."""
    _settings(tmp_path).validate()

    half_demo = _settings(tmp_path)
    half_demo.demo_username = "owner"
    with pytest.raises(ValueError, match="Demo login requires"):
        half_demo.validate()
