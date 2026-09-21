from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from offsetx_apollo_builder.agent.companions import CompanionRegistry
from offsetx_apollo_builder.agent.routines import RoutineExecution, RoutineStore
from offsetx_apollo_builder.api.auth import WorkspaceAuthStore
from offsetx_apollo_builder.meetings.store import MeetingStore
from offsetx_apollo_builder.ai.tools import ToolRegistry
from offsetx_apollo_builder.api.app import create_app
from offsetx_apollo_builder.api.config import AppSettings
from offsetx_apollo_builder.ai.context import ContextLayer
from offsetx_apollo_builder.ai.log import EgressLog
from offsetx_apollo_builder.ai.recall import Redactor, SentMailIndex
from offsetx_apollo_builder.browser.trace import Step, Trace
from offsetx_apollo_builder.crawler_frontier import CrawlFrontier
from offsetx_apollo_builder.outreach.models import ContactInput
from offsetx_apollo_builder.outreach.store import OutreachStore
from offsetx_apollo_builder.privacy import (
    DELETE_CONFIRMATION,
    REQUIRED_PRIVACY_STORES,
    PrivacyAdapter,
    PrivacyError,
    PrivacyRecord,
    PrivacyRequestStore,
    PrivacyService,
    SubjectIdentity,
)


def _subject(email: str, url: str = "") -> SubjectIdentity:
    payload = {"emails": [email]}
    if url:
        payload["urls"] = [url]
    return SubjectIdentity.from_mapping(payload)


def _store(tmp_path: Path) -> OutreachStore:
    store = OutreachStore(tmp_path / "crm.db")
    store.initialize()
    return store


def test_subject_access_and_delete_isolate_one_contact(tmp_path):
    store = _store(tmp_path)
    try:
        alice = store.upsert_contact(ContactInput(full_name="Alice Example", email="alice@example.com"))
        bob = store.upsert_contact(ContactInput(full_name="Bob Example", email="bob@example.com"))
        campaign = store.create_campaign(name="Privacy", daily_send_limit=10)
        store.add_contact_to_campaign(campaign, alice)
        store.add_contact_to_campaign(campaign, bob)

        service = PrivacyService.for_local(store, data_dir=tmp_path / "data")
        try:
            subject = _subject("alice@example.com")
            access = service.access(subject)
            contact_records = [
                record
                for entry in access["stores"]
                for record in entry["records"]
                if record["record_class"] == "contact"
            ]
            assert contact_records[0]["items"][0]["email"] == "alice@example.com"
            assert "bob@example.com" not in str(access)

            preview = service.preview(subject)
            receipt = service.delete(
                preview["request_id"],
                subject,
                confirmation=DELETE_CONFIRMATION,
            )
            assert receipt["complete"] is True
            assert store.get_contact(alice) is None
            assert store.get_contact(bob)["email"] == "bob@example.com"
            assert "alice@example.com" not in str(receipt)
        finally:
            service.close()
    finally:
        store.close()


def test_crawler_and_trace_copies_are_removed_but_unrelated_data_remains(tmp_path):
    store = _store(tmp_path)
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    frontier_path = data_dir / "crawler_frontier.sqlite3"
    validator = lambda value: value
    with CrawlFrontier(frontier_path, validator=validator) as frontier:
        frontier.admit("https://example.com/alice", 0)
        frontier.admit("https://example.com/bob", 0)

    trace_a = Trace.open(data_dir / "agent_traces", run_id="alice-run")
    trace_a.append(Step(kind="read", detail="contact alice@example.com"))
    trace_b = Trace.open(data_dir / "agent_traces", run_id="bob-run")
    trace_b.append(Step(kind="read", detail="contact bob@example.com"))

    try:
        service = PrivacyService.for_local(store, data_dir=data_dir)
        subject = _subject("alice@example.com", "https://example.com/alice")
        preview = service.preview(subject)
        receipt = service.delete(
            preview["request_id"],
            subject,
            confirmation=DELETE_CONFIRMATION,
        )
        assert receipt["complete"] is True
        assert not (data_dir / "agent_traces" / "alice-run").exists()
        assert (data_dir / "agent_traces" / "bob-run").exists()

        with CrawlFrontier(frontier_path, validator=validator) as frontier:
            urls = {entry.url for entry in frontier.snapshot()}
        assert "https://example.com/alice" not in urls
        assert "https://example.com/bob" in urls
        service.close()
    finally:
        store.close()


class FlakyAdapter:
    name = "flaky"

    def __init__(self):
        self.calls = 0

    def find(self, subject):
        return [PrivacyRecord(self.name, "fixture", "test", [{"id": "x"}])]

    def delete(self, subject):
        self.calls += 1
        if self.calls == 1:
            raise RuntimeError("temporary failure")
        return {"fixture": 1}


class StableAdapter:
    name = "stable"

    def __init__(self):
        self.calls = 0

    def find(self, subject):
        return []

    def delete(self, subject):
        self.calls += 1
        return {"fixture": 0}


def test_failed_store_never_reports_global_success_and_retry_is_idempotent(tmp_path):
    flaky = FlakyAdapter()
    stable = StableAdapter()
    requests = PrivacyRequestStore(tmp_path / "privacy.db")
    service = PrivacyService(adapters=(flaky, stable), requests=requests)
    try:
        subject = _subject("alice@example.com")
        preview = service.preview(subject)
        first = service.delete(
            preview["request_id"], subject, confirmation=DELETE_CONFIRMATION
        )
        assert first["complete"] is False
        assert first["status"] == "partial"
        assert stable.calls == 1

        second = service.delete(
            preview["request_id"], subject, confirmation=DELETE_CONFIRMATION
        )
        assert second["complete"] is True
        assert flaky.calls == 2
        assert stable.calls == 1, "successful adapters are not repeated on retry"
    finally:
        service.close()


def test_names_are_not_accepted_as_destructive_identity():
    try:
        SubjectIdentity.from_mapping({"name": "Alice Example"})
    except PrivacyError as exc:
        assert "verified strong identifier" in str(exc)
    else:
        raise AssertionError("name-only subject identity must be refused")


def test_identity_must_match_the_preview(tmp_path):
    requests = PrivacyRequestStore(tmp_path / "privacy.db")
    service = PrivacyService(adapters=(StableAdapter(),), requests=requests)
    try:
        alice = _subject("alice@example.com")
        bob = _subject("bob@example.com")
        preview = service.preview(alice)
        try:
            service.delete(
                preview["request_id"],
                bob,
                confirmation=DELETE_CONFIRMATION,
            )
        except PrivacyError as exc:
            assert "do not match" in str(exc)
        else:
            raise AssertionError("a different subject must not reuse a deletion preview")
    finally:
        service.close()


def test_runtime_inventory_covers_all_declared_personal_data_stores(tmp_path):
    store = _store(tmp_path)
    service = PrivacyService.for_local(store, data_dir=tmp_path / "data")
    try:
        assert tuple(adapter.name for adapter in service.adapters) == REQUIRED_PRIVACY_STORES
        assert service.adapters[-1].name == "outreach_crm"
    finally:
        service.close()
        store.close()


def test_auxiliary_ai_recall_and_delivery_data_are_deleted_before_crm_anchor(tmp_path):
    store = _store(tmp_path)
    data_dir = tmp_path / "data"
    context = ContextLayer(data_dir / "ai_context.db")
    recall = SentMailIndex(data_dir / "ai_recall.db")
    egress = EgressLog(data_dir / "ai_egress.db")
    try:
        contact_id = store.upsert_contact(
            ContactInput(full_name="Alice Example", email="alice@example.com")
        )
        campaign_id = store.create_campaign(name="Privacy auxiliary", daily_send_limit=10)
        membership_id, _ = store.add_contact_to_campaign(campaign_id, contact_id)

        recall.index_message(
            {
                "id": "msg-alice",
                "direction": "outbound",
                "campaign_contact_id": membership_id,
                "subject": "Hello Alice",
                "body": "A safe sent message",
                "sent_at": "2026-09-20T00:00:00+00:00",
            },
            redactor=Redactor(),
            campaign_id=campaign_id,
        )
        context.start_task(
            title="Follow up alice@example.com",
            steps=["read public page"],
        )
        egress.record(
            provider_id="fixture",
            task_type="privacy-test",
            status="ok",
            payload={"public_fact": "alice@example.com"},
            response_text="about alice@example.com",
        )
        store.connection.execute(
            """
            INSERT INTO email_suppressions(
                email, active, reason, source, provider_event_id, created_at, updated_at
            ) VALUES(?,1,'complaint','fixture','evt-1',?,?)
            """,
            ("alice@example.com", "2026-09-20T00:00:00+00:00", "2026-09-20T00:00:00+00:00"),
        )

        service = PrivacyService.for_local(
            store,
            data_dir=data_dir,
            ai_context=context,
            ai_recall=recall,
            ai_egress=egress,
        )
        try:
            subject = _subject("alice@example.com")
            access = service.access(subject)
            stores = {item["store"]: item["count"] for item in access["stores"]}
            assert stores["sent_mail_recall"] == 1
            assert stores["ai_context"] == 1
            assert stores["ai_egress"] == 1
            assert stores["outreach_crm"] >= 2

            preview = service.preview(subject)
            receipt = service.delete(
                preview["request_id"], subject, confirmation=DELETE_CONFIRMATION
            )
            assert receipt["complete"] is True
            assert recall.connection.execute(
                "SELECT COUNT(*) AS n FROM sent_mail"
            ).fetchone()["n"] == 0
            assert context.connection.execute(
                "SELECT COUNT(*) AS n FROM ai_task_state"
            ).fetchone()["n"] == 0
            assert egress.connection.execute(
                "SELECT COUNT(*) AS n FROM ai_egress_log"
            ).fetchone()["n"] == 0
            assert store.connection.execute(
                "SELECT COUNT(*) AS n FROM email_suppressions WHERE email = ?",
                ("alice@example.com",),
            ).fetchone()["n"] == 0
            assert store.get_contact(contact_id) is None
            assert "alice@example.com" not in str(receipt)
        finally:
            service.close()
    finally:
        context.close()
        recall.close()
        egress.close()
        store.close()


def test_registered_subject_artifact_is_deleted_without_touching_other_file(tmp_path):
    store = _store(tmp_path)
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    alice_file = data_dir / "alice-report.txt"
    bob_file = data_dir / "bob-report.txt"
    alice_file.write_text("subject-specific output", encoding="utf-8")
    bob_file.write_text("unrelated output", encoding="utf-8")

    service = PrivacyService.for_local(store, data_dir=data_dir)
    try:
        alice = _subject("alice@example.com")
        service.register_artifact(alice, alice_file, record_class="generated_report")
        preview = service.preview(alice)
        receipt = service.delete(
            preview["request_id"], alice, confirmation=DELETE_CONFIRMATION
        )
        assert receipt["complete"] is True
        assert not alice_file.exists()
        assert bob_file.exists()
    finally:
        service.close()
        store.close()


class AnchorAdapter:
    name = "outreach_crm"

    def __init__(self):
        self.calls = 0

    def find(self, subject):
        return []

    def delete(self, subject):
        self.calls += 1
        return {"anchor": 1}


def test_crm_identity_anchor_waits_when_an_auxiliary_store_fails(tmp_path):
    flaky = FlakyAdapter()
    anchor = AnchorAdapter()
    service = PrivacyService(
        adapters=(flaky, anchor),
        requests=PrivacyRequestStore(tmp_path / "privacy.db"),
    )
    try:
        subject = _subject("alice@example.com")
        preview = service.preview(subject)
        first = service.delete(
            preview["request_id"], subject, confirmation=DELETE_CONFIRMATION
        )
        assert first["complete"] is False
        assert anchor.calls == 0

        second = service.delete(
            preview["request_id"], subject, confirmation=DELETE_CONFIRMATION
        )
        assert second["complete"] is True
        assert anchor.calls == 1
    finally:
        service.close()


def test_privacy_api_is_authenticated_and_requires_preview_confirmation(tmp_path):
    token = "p" * 40
    settings = AppSettings(
        project_root=Path.cwd(),
        database_path=tmp_path / "api-crm.db",
        data_dir=tmp_path / "api-data",
        export_dir=tmp_path / "exports",
        frontend_dist=tmp_path / "missing-dist",
        host="127.0.0.1",
        api_token=token,
        allowed_hosts=("testserver",),
    )
    with TestClient(create_app(settings)) as client:
        store = client.app.state.engine.store
        contact_id = store.upsert_contact(
            ContactInput(full_name="Alice Example", email="alice@example.com")
        )
        payload = {"subject": {"emails": ["alice@example.com"]}}

        assert client.post("/api/v1/privacy/subject-access", json=payload).status_code == 401
        headers = {"X-Offsetx-Token": token}

        access = client.post(
            "/api/v1/privacy/subject-access", json=payload, headers=headers
        )
        assert access.status_code == 200
        assert access.json()["total_records"] >= 1

        cross_workspace = client.post(
            "/api/v1/privacy/subject-access",
            json={"subject": {"workspace_id": "other", "emails": ["alice@example.com"]}},
            headers=headers,
        )
        assert cross_workspace.status_code == 403

        preview = client.post(
            "/api/v1/privacy/deletion-preview", json=payload, headers=headers
        )
        assert preview.status_code == 201
        request_id = preview.json()["request_id"]

        refused = client.post(
            f"/api/v1/privacy/deletions/{request_id}",
            json={**payload, "confirmation": "yes"},
            headers=headers,
        )
        assert refused.status_code == 400
        assert store.get_contact(contact_id) is not None

        deleted = client.post(
            f"/api/v1/privacy/deletions/{request_id}",
            json={**payload, "confirmation": DELETE_CONFIRMATION},
            headers=headers,
        )
        assert deleted.status_code == 200
        assert deleted.json()["complete"] is True
        assert store.get_contact(contact_id) is None


def test_csv_queue_rows_and_residual_metadata_are_removed(tmp_path):
    store = _store(tmp_path)
    data_dir = tmp_path / "data"
    export_dir = tmp_path / "exports"
    (data_dir / "poi_file_queue" / "inbox").mkdir(parents=True)
    export_dir.mkdir()

    queue = data_dir / "poi_file_queue" / "inbox" / "people.csv"
    queue.write_text(
        "name,email,url\nAlice,alice@example.com,https://example.com/alice\n"
        "Bob,bob@example.com,https://example.com/bob\n",
        encoding="utf-8",
    )
    exported = export_dir / "contacts.csv"
    exported.write_text(
        "email,status\nalice@example.com,new\nbob@example.com,new\n",
        encoding="utf-8",
    )

    campaign = store.create_campaign(name="Residual privacy", daily_send_limit=10)
    run_id = store.create_discovery_run(
        campaign_id=campaign,
        seed_urls=["https://example.com/alice"],
        allowed_domains=["example.com"],
        category="other",
        route="other",
        max_pages=1,
        max_depth=0,
        obey_robots=True,
        objective_prompt="research alice@example.com",
        plan={"source": "https://example.com/alice"},
    )
    store.add_event(
        campaign,
        "privacy_fixture",
        {"subject": "alice@example.com", "keep": "operational history"},
    )
    store.save_idempotency(
        "privacy-fixture",
        "one",
        {"email": "alice@example.com"},
    )

    service = PrivacyService.for_local(
        store, data_dir=data_dir, export_dir=export_dir
    )
    try:
        subject = _subject("alice@example.com", "https://example.com/alice")
        access = service.access(subject)
        stores = {item["store"]: item for item in access["stores"]}
        assert stores["structured_exports"]["count"] == 2

        preview = service.preview(subject)
        receipt = service.delete(
            preview["request_id"], subject, confirmation=DELETE_CONFIRMATION
        )
        assert receipt["complete"] is True

        assert "alice@example.com" not in queue.read_text(encoding="utf-8-sig")
        assert "bob@example.com" in queue.read_text(encoding="utf-8-sig")
        assert "alice@example.com" not in exported.read_text(encoding="utf-8-sig")
        assert "bob@example.com" in exported.read_text(encoding="utf-8-sig")

        run = store.connection.execute(
            "SELECT objective_prompt, seed_urls_json, plan_json FROM discovery_runs WHERE id = ?",
            (run_id,),
        ).fetchone()
        assert "alice@example.com" not in str(dict(run))
        assert "https://example.com/alice" not in str(dict(run))
        event = store.connection.execute(
            "SELECT payload_json FROM campaign_events WHERE event_type = 'privacy_fixture'"
        ).fetchone()
        assert "alice@example.com" not in str(event["payload_json"])
        assert store.connection.execute(
            "SELECT COUNT(*) AS n FROM idempotency_records WHERE scope = 'privacy-fixture'"
        ).fetchone()["n"] == 0
    finally:
        service.close()
        store.close()


def test_subject_deletion_scrubs_companion_profile_text(tmp_path):
    store = _store(tmp_path)
    data_dir = tmp_path / "data"
    tools = ToolRegistry(data_dir / "ai_tools.db")
    companions = CompanionRegistry(data_dir, tools=tools, memory_backend=store)
    alice = companions.create(
        workspace_id="local",
        name="Research companion",
        instructions="Research alice@example.com and preserve only sourced facts.",
    )
    bob = companions.create(
        workspace_id="local",
        name="Unrelated companion",
        instructions="Research public market data.",
    )

    service = PrivacyService.for_local(store, data_dir=data_dir)
    try:
        subject = _subject("alice@example.com")
        access = service.access(subject)
        companion_store = next(
            item for item in access["stores"] if item["store"] == "companion_profiles"
        )
        assert companion_store["count"] == 1

        preview = service.preview(subject)
        receipt = service.delete(
            preview["request_id"], subject, confirmation=DELETE_CONFIRMATION
        )
        assert receipt["complete"] is True

        updated_alice = companions.require(alice.id, workspace_id="local")
        unchanged_bob = companions.require(bob.id, workspace_id="local")
        assert "alice@example.com" not in updated_alice.instructions
        assert "[deleted-subject]" in updated_alice.instructions
        assert unchanged_bob.instructions == "Research public market data."
    finally:
        service.close()
        tools.close()
        store.close()



def test_privacy_deletes_subject_routines_and_result_notifications(tmp_path):
    store = _store(tmp_path)
    data_dir = tmp_path / "data"
    routines = RoutineStore(data_dir / "agent_routines.db")
    alice = routines.create(
        workspace_id="local",
        name="Alice watch",
        goal="Watch public updates about alice@example.com",
        target_url="https://example.com/alice",
        trigger_type="event",
        event_name="source.changed",
    )
    bob = routines.create(
        workspace_id="local",
        name="Market watch",
        goal="Watch public market releases",
        target_url="https://example.com/market",
        trigger_type="event",
        event_name="market.changed",
    )

    run_id = routines.begin_run(
        alice, trigger_type="event", trigger_key="fixture:alice"
    )
    assert run_id is not None
    execution = RoutineExecution(
        status="completed",
        useful=True,
        agent_run_id="agent-alice",
        summary="Useful update about alice@example.com",
    )
    routines.finish_run(run_id, execution=execution)
    routines.notify(alice, run_id, execution)

    service = PrivacyService.for_local(store, data_dir=data_dir)
    try:
        subject = _subject("alice@example.com", "https://example.com/alice")
        access = service.access(subject)
        routine_store = next(
            item for item in access["stores"] if item["store"] == "agent_routines"
        )
        assert routine_store["count"] >= 1

        preview = service.preview(subject)
        receipt = service.delete(
            preview["request_id"], subject, confirmation=DELETE_CONFIRMATION
        )
        assert receipt["complete"] is True
        assert routines.get(alice.id, workspace_id="local") is None
        assert routines.get(bob.id, workspace_id="local") is not None
        assert routines.runs(workspace_id="local", routine_id=alice.id) == []
        assert routines.notifications(workspace_id="local") == []
    finally:
        service.close()
        store.close()


def test_privacy_removes_workspace_login_when_username_is_subject_email(tmp_path):
    store = _store(tmp_path)
    data_dir = tmp_path / "data"
    auth = WorkspaceAuthStore(
        data_dir / "workspace_auth.db",
        session_secret="privacy-session-secret-" + "x" * 32,
        session_hours=8,
    )
    auth.create(
        username="alice@example.com",
        workspace_id="local",
        password="alice-password-123",
    )
    auth.create(
        username="bob@example.com",
        workspace_id="other",
        password="bob-password-456",
    )

    service = PrivacyService.for_local(store, data_dir=data_dir)
    try:
        subject = _subject("alice@example.com")
        access = service.access(subject)
        account_store = next(
            item for item in access["stores"] if item["store"] == "workspace_accounts"
        )
        assert account_store["count"] == 1

        preview = service.preview(subject)
        receipt = service.delete(
            preview["request_id"], subject, confirmation=DELETE_CONFIRMATION
        )
        assert receipt["complete"] is True
        assert auth.authenticate("alice@example.com", "alice-password-123") is None
        assert auth.authenticate("bob@example.com", "bob-password-456") is not None
    finally:
        service.close()
        store.close()



def test_privacy_deletes_matching_meeting_transcript_without_touching_other_meetings(tmp_path):
    store = _store(tmp_path)
    data_dir = tmp_path / "data"
    meetings = MeetingStore(data_dir / "meeting_transcripts.db")
    alice = meetings.create(
        workspace_id="local",
        title="Call with alice@example.com",
    )
    bob = meetings.create(
        workspace_id="local",
        title="General market call",
    )

    service = PrivacyService.for_local(store, data_dir=data_dir)
    try:
        subject = _subject("alice@example.com")
        access = service.access(subject)
        meeting_store = next(
            item for item in access["stores"]
            if item["store"] == "meeting_transcripts"
        )
        assert meeting_store["count"] == 1

        preview = service.preview(subject)
        receipt = service.delete(
            preview["request_id"], subject, confirmation=DELETE_CONFIRMATION
        )
        assert receipt["complete"] is True

        with pytest.raises(Exception):
            meetings.require(alice["id"], workspace_id="local")
        assert meetings.require(bob["id"], workspace_id="local")["title"] == "General market call"
    finally:
        service.close()
        store.close()
