from __future__ import annotations

import base64
import json
from datetime import datetime, timedelta, timezone
from email import policy
from email.parser import BytesParser
from pathlib import Path

import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.x509.oid import NameOID
from fastapi.testclient import TestClient

from offsetx_apollo_builder.api.app import create_app
from offsetx_apollo_builder.api.config import AppSettings
from offsetx_apollo_builder.outreach.deliverability.domain_auth import DomainAuthChecker
from offsetx_apollo_builder.outreach.deliverability.events import (
    DeliveryEventProcessor,
    SnsVerifier,
)
from offsetx_apollo_builder.outreach.deliverability.models import AmbiguousDeliveryError
from offsetx_apollo_builder.outreach.deliverability.service import EmailDeliveryService
from offsetx_apollo_builder.outreach.deliverability.ses import SesMailProvider
from offsetx_apollo_builder.outreach.deliverability.store import DeliverabilityStore
from offsetx_apollo_builder.outreach.deliverability.unsubscribe import UnsubscribeService
from offsetx_apollo_builder.outreach.engine import OutreachEngine
from offsetx_apollo_builder.outreach.gmail import LocalOutboxProvider
from offsetx_apollo_builder.outreach.models import (
    INITIAL,
    IncomingMessage,
    to_utc_iso,
    utc_now,
)


CONTACTS = (
    "Full Name,Email,Company,Title,Category,Public Hook,Hook Source,Tension\n"
    "Anita Rao,anita@example.com,Example Exports,Climate Lead,CBAM,"
    "Published a supplier emissions brief,https://example.com/anita,Supplier evidence handoff\n"
)


def _campaign(engine: OutreachEngine, tmp_path: Path) -> str:
    contacts = tmp_path / "contacts.csv"
    contacts.write_text(CONTACTS, encoding="utf-8")
    campaign_id = engine.create_campaign(name="Delivery", daily_send_limit=25)
    assert engine.import_contacts(campaign_id, contacts)["added"] == 1
    assert engine.generate_drafts(campaign_id, stages=[INITIAL])["generated"] == 1
    assert engine.approve_drafts(campaign_id, stages=[INITIAL])["approved"] == 1
    return campaign_id


def _service(
    engine: OutreachEngine,
    tmp_path: Path,
    *,
    provider_factory=None,
) -> EmailDeliveryService:
    delivery_store = DeliverabilityStore(engine.store)
    unsubscribe = UnsubscribeService(
        delivery_store,
        secret=b"test-unsubscribe-secret-that-is-long-enough",
        public_base_url="https://crm.example",
    )
    return EmailDeliveryService(
        engine,
        unsubscribe=unsubscribe,
        provider_factory=provider_factory
        or (lambda _job, _identity: LocalOutboxProvider(tmp_path / "mail")),
    )


def test_permission_marketing_fails_closed_and_suppression_is_global(tmp_path):
    engine = OutreachEngine(tmp_path / "outreach.db")
    try:
        campaign_id = _campaign(engine, tmp_path)
        service = _service(engine, tmp_path)
        identity = service.save_identity(
            {
                "name": "Marketing lane",
                "provider_type": "ses",
                "stream": "permission_marketing",
                "from_email": "news@example.com",
                "ses_identity": "example.com",
                "aws_region": "us-east-1",
                "configuration_set": "feedback",
                "mail_from_domain": "mail.example.com",
                "sns_topic_arn": "arn:aws:sns:us-east-1:123456789012:feedback",
            }
        )
        with pytest.raises(ValueError, match="isolated subdomain"):
            service.save_identity(
                {
                    "name": "Outreach lane",
                    "provider_type": "local",
                    "stream": "targeted_outreach",
                    "from_email": "outreach@example.com",
                }
            )
        service.store.update_identity_check(
            identity["id"],
            provider_verified=True,
            spf_status="pass",
            dkim_status="pass",
            dmarc_status="pass",
            alignment_status="pass",
            dmarc_policy="reject",
            details={},
        )
        service.update_campaign_settings(
            campaign_id,
            {
                "stream": "permission_marketing",
                "provider_type": "ses",
                "identity_id": identity["id"],
            },
        )
        with pytest.raises(ValueError, match="cannot disable unsubscribe"):
            service.update_campaign_settings(
                campaign_id, {"require_unsubscribe": False}
            )

        unknown = service.preflight.check(campaign_id, "anita@example.com")
        assert not unknown.allowed
        assert "permission_required" in {item.code for item in unknown.blockers}

        service.store.set_permission(
            "anita@example.com",
            status="granted",
            basis="explicit_consent",
            source="signup_form",
            evidence="consent-record-1",
            obtained_at=utc_now(),
        )
        service.store.update_identity_check(
            identity["id"],
            provider_verified=True,
            spf_status="pass",
            dkim_status="pass",
            dmarc_status="pass",
            alignment_status="pass",
            dmarc_policy="reject",
            details={},
            checked_at=utc_now() - timedelta(days=8),
        )
        assert "authentication_check_stale" in {
            item.code
            for item in service.preflight.check(
                campaign_id, "anita@example.com"
            ).blockers
        }
        service.store.update_identity_check(
            identity["id"],
            provider_verified=True,
            spf_status="pass",
            dkim_status="pass",
            dmarc_status="pass",
            alignment_status="pass",
            dmarc_policy="reject",
            details={},
        )
        assert service.preflight.check(campaign_id, "anita@example.com").allowed
        unavailable = EmailDeliveryService(
            engine,
            unsubscribe=None,
            provider_factory=lambda _job, _identity: LocalOutboxProvider(
                tmp_path / "closed-mail"
            ),
        ).preflight.check(campaign_id, "anita@example.com")
        assert "unsubscribe_unavailable" in {
            item.code for item in unavailable.blockers
        }

        service.store.suppress(
            "anita@example.com", reason="operator_request", source="test"
        )
        suppressed = service.preflight.check(campaign_id, "anita@example.com")
        assert not suppressed.allowed
        assert "suppressed" in {item.code for item in suppressed.blockers}
    finally:
        engine.close()


def test_durable_local_job_is_snapshotted_claimed_once_and_recorded(tmp_path):
    engine = OutreachEngine(tmp_path / "outreach.db")
    try:
        campaign_id = _campaign(engine, tmp_path)
        service = _service(engine, tmp_path)
        assert service.store.get_campaign_settings(campaign_id)["daily_limit"] == 25
        assert service.update_campaign_settings(campaign_id, {"daily_limit": 12})[
            "daily_limit"
        ] == 12
        assert engine.store.get_campaign(campaign_id)["daily_send_limit"] == 12
        now = datetime.now(timezone.utc) + timedelta(minutes=1)
        queued = service.enqueue_campaign(campaign_id, max_jobs=10, now=now)
        assert queued["queued_count"] == 1
        job = service.store.get_job(queued["queued"][0]["job_id"])
        assert job["status"] == "queued"
        assert "Manage email preferences:" in job["body"]
        draft = engine.store.get_draft_by_id(campaign_id, job["draft_id"])
        assert draft["approval_status"] == "queued"
        with pytest.raises(ValueError, match="queued"):
            engine.edit_draft(
                campaign_id,
                job["draft_id"],
                subject=draft["subject"],
                body=draft["body"] + " changed",
            )

        result = service.work_once(max_jobs=10, now=now)
        assert result["accepted"] == 1
        assert service.work_once(max_jobs=10, now=now)["processed"] == 0
        accepted = service.store.get_job(job["id"])
        assert accepted["status"] == "accepted"
        outgoing = engine.store.last_outgoing(job["campaign_contact_id"])
        assert outgoing and outgoing["body"] == job["body"]
        outbox = list((tmp_path / "mail" / "outbox").glob("*.json"))
        assert len(outbox) == 1
    finally:
        engine.close()


def test_ambiguous_delivery_is_quarantined_and_never_retried(tmp_path):
    class AmbiguousProvider:
        provider_type = "local"

        def send_message(self, **_):
            raise AmbiguousDeliveryError("connection ended after upload")

    engine = OutreachEngine(tmp_path / "outreach.db")
    try:
        campaign_id = _campaign(engine, tmp_path)
        service = _service(
            engine,
            tmp_path,
            provider_factory=lambda _job, _identity: AmbiguousProvider(),
        )
        now = datetime.now(timezone.utc) + timedelta(minutes=1)
        job_id = service.enqueue_campaign(campaign_id, now=now)["queued"][0]["job_id"]
        result = service.work_once(max_jobs=1, now=now)
        assert result["items"][0]["status"] == "delivery_unknown"
        assert service.store.get_job(job_id)["attempt_count"] == 1
        assert service.work_once(max_jobs=1, now=now + timedelta(hours=1))["processed"] == 0
    finally:
        engine.close()


def test_stale_claim_without_a_recorded_message_becomes_delivery_unknown(tmp_path):
    engine = OutreachEngine(tmp_path / "outreach.db")
    try:
        campaign_id = _campaign(engine, tmp_path)
        service = _service(engine, tmp_path)
        now = datetime.now(timezone.utc) + timedelta(minutes=1)
        job_id = service.enqueue_campaign(campaign_id, now=now)["queued"][0]["job_id"]
        assert service.store.claim_next(now=now, lease_seconds=10)["id"] == job_id
        recovered = service.store.recover_stale(now=now + timedelta(seconds=11))
        assert recovered == {"recovered": 0, "delivery_unknown": 1}
        assert service.store.get_job(job_id)["status"] == "delivery_unknown"
    finally:
        engine.close()


def test_direct_sender_checks_global_suppression_before_provider_call(tmp_path):
    engine = OutreachEngine(tmp_path / "outreach.db")
    try:
        campaign_id = _campaign(engine, tmp_path)
        engine.deliverability_store.suppress(
            "anita@example.com", reason="unsubscribe", source="test"
        )
        result = engine.run_due(
            campaign_id,
            mail_provider=LocalOutboxProvider(tmp_path / "mail"),
            own_email="owner@example.com",
            now=datetime.now(timezone.utc) + timedelta(minutes=1),
            sync_replies_first=False,
        )
        assert result["sent_count"] == 0
        assert result["skipped"][0]["reason"] == "suppressed"
        assert not list((tmp_path / "mail" / "outbox").glob("*.json"))
    finally:
        engine.close()


def test_ses_feedback_is_idempotent_suppresses_and_auto_pauses(tmp_path):
    engine = OutreachEngine(tmp_path / "outreach.db")
    try:
        campaign_id = _campaign(engine, tmp_path)
        service = _service(engine, tmp_path)
        service.update_campaign_settings(
            campaign_id,
            {
                "health_sample_size": 1,
                "max_hard_bounce_rate": 0,
                "max_complaint_rate": 1,
            },
        )
        now = datetime.now(timezone.utc) + timedelta(minutes=1)
        job_id = service.enqueue_campaign(campaign_id, now=now)["queued"][0]["job_id"]
        service.work_once(max_jobs=1, now=now)
        job = service.store.get_job(job_id)
        payload = {
            "eventType": "Bounce",
            "mail": {
                "messageId": job["provider_message_id"],
                "timestamp": to_utc_iso(now),
                "destination": [job["to_email"]],
            },
            "bounce": {
                "bounceType": "Permanent",
                "timestamp": to_utc_iso(now),
                "bouncedRecipients": [
                    {
                        "emailAddress": job["to_email"],
                        "diagnosticCode": "smtp; 550 user unknown",
                    }
                ],
            },
        }
        first = DeliveryEventProcessor(service.store).process_ses(payload, envelope_id="sns-1")
        second = DeliveryEventProcessor(service.store).process_ses(payload, envelope_id="sns-1")
        later_payload = json.loads(json.dumps(payload))
        later_payload["bounce"]["timestamp"] = to_utc_iso(now + timedelta(seconds=1))
        DeliveryEventProcessor(service.store).process_ses(
            later_payload, envelope_id="sns-2"
        )
        assert first["inserted"] == 1 and first["suppressions"] == 1
        assert second["duplicates"] == 1
        assert service.store.is_suppressed(job["to_email"])["reason"] == "hard_bounce"
        assert engine.store.get_campaign(campaign_id)["status"] == "paused"
        assert service.store.health(campaign_id)["status"] == "paused"
        events, _ = engine.store.list_events(campaign_id)
        pause_events = [
            event for event in events if event["event_type"] == "email_delivery_auto_paused"
        ]
        assert len(pause_events) == 1
        assert service.store.get_job(job_id)["status"] == "failed"
        resumed = service.store.resume_health(campaign_id)
        assert resumed["status"] == "review"
        assert engine.store.get_campaign(campaign_id)["status"] == "active"
    finally:
        engine.close()


def test_job_cancellation_is_terminal_and_only_allowed_before_claim(tmp_path):
    engine = OutreachEngine(tmp_path / "outreach.db")
    try:
        campaign_id = _campaign(engine, tmp_path)
        service = _service(engine, tmp_path)
        now = datetime.now(timezone.utc) + timedelta(minutes=1)
        job_id = service.enqueue_campaign(campaign_id, now=now)["queued"][0]["job_id"]
        cancelled = service.cancel_job(job_id)
        assert cancelled["status"] == "cancelled"
        with pytest.raises(ValueError, match="Only queued or waiting"):
            service.cancel_job(job_id)
        assert service.work_once(max_jobs=1, now=now)["processed"] == 0
    finally:
        engine.close()


def test_reply_cancels_an_already_queued_email_before_delivery(tmp_path):
    engine = OutreachEngine(tmp_path / "outreach.db")
    try:
        campaign_id = _campaign(engine, tmp_path)
        service = _service(engine, tmp_path)
        now = datetime.now(timezone.utc) + timedelta(minutes=1)
        job_id = service.enqueue_campaign(campaign_id, now=now)["queued"][0]["job_id"]
        job = service.store.get_job(job_id)
        updated = engine.store.record_reply(
            campaign_id,
            IncomingMessage(
                provider_message_id="reply-1",
                thread_id="",
                from_email="anita@example.com",
                subject="Re: hello",
                body_preview="Please stop",
                received_at=now,
            ),
        )
        assert updated == [job["campaign_contact_id"]]
        assert service.store.get_job(job_id)["status"] == "cancelled"
        assert engine.store.get_draft_by_id(campaign_id, job["draft_id"])[
            "approval_status"
        ] == "cancelled_reply"
        assert service.work_once(max_jobs=1, now=now)["processed"] == 0
    finally:
        engine.close()


def test_worker_defers_outside_send_window_without_spending_a_provider_attempt(tmp_path):
    engine = OutreachEngine(tmp_path / "outreach.db")
    try:
        campaign_id = _campaign(engine, tmp_path)
        engine.store.update_campaign(
            campaign_id,
            {"send_window_start": "09:00", "send_window_end": "17:00"},
        )
        service = _service(engine, tmp_path)
        queue_time = (utc_now() + timedelta(days=1)).replace(
            hour=10, minute=0, second=0, microsecond=0
        )
        job_id = service.enqueue_campaign(campaign_id, now=queue_time)["queued"][0][
            "job_id"
        ]
        result = service.work_once(
            max_jobs=1,
            now=queue_time.replace(hour=18),
        )
        assert result["retry_wait"] == 1
        deferred = service.store.get_job(job_id)
        assert deferred["status"] == "retry_wait"
        assert deferred["attempt_count"] == 0
        assert not list((tmp_path / "mail" / "outbox").glob("*.json"))
    finally:
        engine.close()


def test_transactional_lane_requires_relationship_basis_not_marketing_consent(tmp_path):
    engine = OutreachEngine(tmp_path / "outreach.db")
    try:
        campaign_id = _campaign(engine, tmp_path)
        service = _service(engine, tmp_path)
        service.update_campaign_settings(
            campaign_id,
            {
                "stream": "transactional",
                "provider_type": "local",
                "require_unsubscribe": False,
            },
        )
        service.store.set_permission(
            "anita@example.com", status="granted", basis="explicit_consent"
        )
        assert "relationship_required" in {
            issue.code
            for issue in service.preflight.check(
                campaign_id, "anita@example.com"
            ).blockers
        }
        service.store.set_permission(
            "anita@example.com", status="granted", basis="existing_customer"
        )
        assert service.preflight.check(campaign_id, "anita@example.com").allowed
    finally:
        engine.close()


def test_domain_auth_uses_dns_and_ses_identity_evidence():
    class Resolver:
        def query(self, name: str, record_type: str) -> list[str]:
            records = {
                ("mail.example.com", "TXT"): ['"v=spf1 include:amazonses.com -all"'],
                ("_dmarc.example.com", "TXT"): ['"v=DMARC1; p=reject"'],
            }
            return records.get((name, record_type), [])

    result = DomainAuthChecker(Resolver()).check(
        {
            "provider_type": "ses",
            "from_email": "news@example.com",
            "domain": "example.com",
            "mail_from_domain": "mail.example.com",
            "ses_identity": "example.com",
            "dkim_selector": "",
        },
        provider_details={
            "VerifiedForSendingStatus": True,
            "DkimAttributes": {"Status": "SUCCESS"},
        },
    )
    assert result["provider_verified"] is True
    assert result["spf_status"] == "pass"
    assert result["dkim_status"] == "pass"
    assert result["dmarc_status"] == "pass"
    assert result["alignment_status"] == "pass"
    assert result["dmarc_policy"] == "reject"


def test_ses_provider_builds_raw_mime_with_one_click_headers():
    class Client:
        def __init__(self):
            self.request = None

        def send_email(self, **kwargs):
            self.request = kwargs
            return {"MessageId": "ses-message-1", "ResponseMetadata": {"HTTPStatusCode": 200}}

    client = Client()
    provider = SesMailProvider(
        region="us-east-1", configuration_set="feedback", client=client
    )
    result = provider.send_message(
        to_email="person@example.net",
        from_email="news@example.com",
        from_name="Example",
        reply_to="help@example.com",
        subject="Update",
        body="Hello",
        headers={
            "List-Unsubscribe": "<https://crm.example/u/token>",
            "List-Unsubscribe-Post": "List-Unsubscribe=One-Click",
        },
        tags={"off_crm_campaign": "campaign-1"},
    )
    assert result.provider_message_id == "ses-message-1"
    assert client.request["ConfigurationSetName"] == "feedback"
    message = BytesParser(policy=policy.default).parsebytes(
        client.request["Content"]["Raw"]["Data"]
    )
    assert message["List-Unsubscribe-Post"] == "List-Unsubscribe=One-Click"
    assert message["Reply-To"] == "help@example.com"
    assert message.get_body(preferencelist=("plain",)).get_content().strip() == "Hello"


def test_sns_envelope_signature_is_verified_before_parsing():
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "sns.amazonaws.com")])
    now = datetime.now(timezone.utc)
    certificate = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(minutes=1))
        .not_valid_after(now + timedelta(days=1))
        .sign(key, hashes.SHA256())
    )
    cert_bytes = certificate.public_bytes(serialization.Encoding.PEM)

    class Response:
        content = cert_bytes

        @staticmethod
        def raise_for_status():
            return None

    class Session:
        @staticmethod
        def get(_url, timeout, allow_redirects):
            assert timeout == 10
            assert allow_redirects is False
            return Response()

    envelope = {
        "Type": "Notification",
        "MessageId": "message-1",
        "TopicArn": "arn:aws:sns:us-east-1:123456789012:ses-feedback",
        "Message": "{}",
        "Timestamp": to_utc_iso(now),
        "SignatureVersion": "2",
        "SigningCertURL": "https://sns.us-east-1.amazonaws.com/SimpleNotificationService-test.pem",
    }
    signing_text = SnsVerifier._signing_text(envelope)
    envelope["Signature"] = base64.b64encode(
        key.sign(signing_text, padding.PKCS1v15(), hashes.SHA256())
    ).decode("ascii")
    verified = SnsVerifier(session=Session()).verify(
        envelope, expected_topics=[envelope["TopicArn"]]
    )
    assert verified["MessageId"] == "message-1"


def _settings(tmp_path: Path) -> AppSettings:
    return AppSettings(
        project_root=Path.cwd(),
        database_path=tmp_path / "outreach.db",
        data_dir=tmp_path / "data",
        export_dir=tmp_path / "exports",
        frontend_dist=tmp_path / "missing-dist",
        public_base_url="http://testserver",
        unsubscribe_secret="test-unsubscribe-secret-that-is-long-enough",
    )


def test_email_delivery_api_and_public_one_click_unsubscribe(tmp_path):
    with TestClient(create_app(_settings(tmp_path))) as client:
        campaign_id = client.post("/api/v1/campaigns", json={"name": "API delivery"}).json()["id"]
        imported = client.post(
            f"/api/v1/campaigns/{campaign_id}/contacts/import",
            files={"file": ("contacts.csv", CONTACTS.encode(), "text/csv")},
        )
        assert imported.json()["added"] == 1
        client.post(
            f"/api/v1/campaigns/{campaign_id}/drafts/generate",
            json={"campaign_contact_ids": [], "stages": ["initial"], "provider": None},
        )
        client.post(
            f"/api/v1/campaigns/{campaign_id}/drafts/approve",
            json={"draft_ids": [], "stages": ["initial"]},
        )
        preflight = client.get(
            f"/api/v1/campaigns/{campaign_id}/email-preflight"
        ).json()
        assert preflight["allowed"] == 1
        queued = client.post(
            f"/api/v1/campaigns/{campaign_id}/email-jobs", json={"max_jobs": 10}
        )
        assert queued.status_code == 202
        assert queued.json()["queued_count"] == 1
        worked = client.post("/api/v1/email-delivery/work", json={"max_jobs": 10})
        assert worked.json()["accepted"] == 1
        assert client.get(
            f"/api/v1/email-delivery/jobs?campaign_id={campaign_id}"
        ).json()["total"] == 1

        payload = json.loads(next((tmp_path / "data" / "mail" / "outbox").glob("*.json")).read_text())
        url = payload["body"].split("Manage email preferences: ", 1)[1].strip()
        path = url.removeprefix("http://testserver")
        page = client.get(path)
        assert page.status_code == 200
        assert "Stop these emails?" in page.text
        unsubscribed = client.post(path, data={"List-Unsubscribe": "One-Click"})
        assert unsubscribed.status_code == 200
        assert unsubscribed.json() == {"status": "unsubscribed"}
        suppressions = client.get("/api/v1/email-delivery/suppressions").json()
        assert suppressions["total"] == 1
        assert suppressions["items"][0]["email"] == "anita@example.com"


def test_public_feedback_paths_bypass_login_but_still_verify_their_tokens(tmp_path):
    settings = _settings(tmp_path)
    settings.api_token = "x" * 32
    with TestClient(create_app(settings)) as client:
        assert client.get("/api/v1/dashboard").status_code == 401
        invalid_unsubscribe = client.get("/api/v1/email/unsubscribe/not-a-token")
        assert invalid_unsubscribe.status_code == 422
        invalid_sns = client.post(
            "/api/v1/email-delivery/events/ses/sns", content=b"{}"
        )
        assert invalid_sns.status_code == 403


def test_live_ses_queue_requires_exact_operator_confirmation(tmp_path):
    with TestClient(create_app(_settings(tmp_path))) as client:
        campaign_id = client.post("/api/v1/campaigns", json={"name": "Live delivery"}).json()["id"]
        client.post(
            f"/api/v1/campaigns/{campaign_id}/contacts/import",
            files={"file": ("contacts.csv", CONTACTS.encode(), "text/csv")},
        )
        client.post(
            f"/api/v1/campaigns/{campaign_id}/drafts/generate",
            json={"campaign_contact_ids": [], "stages": ["initial"], "provider": None},
        )
        client.post(
            f"/api/v1/campaigns/{campaign_id}/drafts/approve",
            json={"draft_ids": [], "stages": ["initial"]},
        )
        identity = client.post(
            "/api/v1/email-delivery/identities",
            json={
                "name": "Marketing",
                "provider_type": "ses",
                "stream": "permission_marketing",
                "from_email": "news@example.com",
                "ses_identity": "example.com",
                "aws_region": "us-east-1",
                "configuration_set": "feedback",
                "mail_from_domain": "mail.example.com",
                "sns_topic_arn": "arn:aws:sns:us-east-1:123456789012:feedback",
            },
        ).json()
        client.app.state.email_delivery.store.update_identity_check(
            identity["id"],
            provider_verified=True,
            spf_status="pass",
            dkim_status="pass",
            dmarc_status="pass",
            alignment_status="pass",
            dmarc_policy="reject",
            details={},
        )
        client.patch(
            f"/api/v1/campaigns/{campaign_id}/email-settings",
            json={
                "stream": "permission_marketing",
                "provider_type": "ses",
                "identity_id": identity["id"],
            },
        )
        client.patch(
            "/api/v1/email-delivery/permissions/anita@example.com",
            json={
                "status": "granted",
                "basis": "explicit_consent",
                "source": "signup",
                "evidence": "record-1",
            },
        )

        rejected = client.post(
            f"/api/v1/campaigns/{campaign_id}/email-jobs",
            json={"max_jobs": 1, "confirmation": "SEND"},
        )
        accepted = client.post(
            f"/api/v1/campaigns/{campaign_id}/email-jobs",
            json={"max_jobs": 1, "confirmation": "QUEUE LIVE EMAILS"},
        )
        assert rejected.status_code == 422
        assert accepted.status_code == 202
        assert accepted.json()["queued_count"] == 1
