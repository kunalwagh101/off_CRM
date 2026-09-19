from __future__ import annotations

from pathlib import Path

from offsetx_apollo_builder.browser.trace import Step, Trace
from offsetx_apollo_builder.crawler_frontier import CrawlFrontier
from offsetx_apollo_builder.outreach.models import ContactInput
from offsetx_apollo_builder.outreach.store import OutreachStore
from offsetx_apollo_builder.privacy import (
    DELETE_CONFIRMATION,
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
