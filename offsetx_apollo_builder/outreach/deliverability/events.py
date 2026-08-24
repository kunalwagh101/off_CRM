from __future__ import annotations

import base64
import hashlib
import json
import re
from datetime import datetime, timezone
from typing import Any, Iterable
from urllib.parse import urlparse

import requests
from cryptography import x509
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding

from ..models import clean_text, normalize_email, to_utc_iso
from .store import DeliverabilityStore

_SNS_HOST = re.compile(r"^sns\.[a-z0-9-]+\.amazonaws\.com(?:\.cn)?$")


class SnsVerificationError(ValueError):
    pass


class SnsVerifier:
    """Verify AWS SNS envelopes before any provider event can mutate the CRM."""

    def __init__(self, *, session: Any | None = None, timeout_seconds: int = 10):
        self.session = session or requests.Session()
        self.timeout_seconds = timeout_seconds
        self._certificates: dict[str, x509.Certificate] = {}

    @staticmethod
    def _signing_text(payload: dict[str, Any]) -> bytes:
        message_type = str(payload.get("Type", ""))
        if message_type == "Notification":
            fields = ["Message", "MessageId"]
            if "Subject" in payload:
                fields.append("Subject")
            fields.extend(["Type", "Timestamp", "TopicArn"])
        elif message_type in {"SubscriptionConfirmation", "UnsubscribeConfirmation"}:
            fields = [
                "Message",
                "MessageId",
                "SubscribeURL",
                "Timestamp",
                "Token",
                "TopicArn",
                "Type",
            ]
        else:
            raise SnsVerificationError("Unsupported SNS message type")
        if any(field not in payload for field in fields):
            raise SnsVerificationError("SNS envelope is missing a signed field")
        return "".join(f"{field}\n{payload[field]}\n" for field in fields).encode("utf-8")

    @staticmethod
    def _validate_cert_url(value: str) -> str:
        parsed = urlparse(value)
        if (
            parsed.scheme != "https"
            or not parsed.hostname
            or not _SNS_HOST.fullmatch(parsed.hostname.lower())
            or parsed.port not in {None, 443}
            or parsed.username
            or parsed.password
            or parsed.query
            or parsed.fragment
            or not parsed.path.endswith(".pem")
        ):
            raise SnsVerificationError("SNS signing certificate URL is not trusted")
        return value

    def _certificate(self, url: str) -> x509.Certificate:
        if url in self._certificates:
            return self._certificates[url]
        response = self.session.get(url, timeout=self.timeout_seconds, allow_redirects=False)
        response.raise_for_status()
        if len(response.content) > 1024 * 1024:
            raise SnsVerificationError("SNS signing certificate is unexpectedly large")
        certificate = x509.load_pem_x509_certificate(response.content)
        now = datetime.now(timezone.utc)
        if hasattr(certificate, "not_valid_before_utc"):
            not_before = certificate.not_valid_before_utc
            not_after = certificate.not_valid_after_utc
        else:  # pragma: no cover - compatibility with older cryptography
            not_before = certificate.not_valid_before.replace(tzinfo=timezone.utc)
            not_after = certificate.not_valid_after.replace(tzinfo=timezone.utc)
        if not_before > now or not_after < now:
            raise SnsVerificationError("SNS signing certificate is outside its validity period")
        self._certificates[url] = certificate
        return certificate

    def verify(
        self, payload: dict[str, Any], *, expected_topics: Iterable[str]
    ) -> dict[str, Any]:
        topics = {str(item) for item in expected_topics if str(item)}
        if not topics:
            raise SnsVerificationError("No SNS topic is configured for email feedback")
        if str(payload.get("TopicArn", "")) not in topics:
            raise SnsVerificationError("SNS topic is not configured for this workspace")
        version = str(payload.get("SignatureVersion", ""))
        algorithm = hashes.SHA1() if version == "1" else hashes.SHA256() if version == "2" else None
        if algorithm is None:
            raise SnsVerificationError("Unsupported SNS signature version")
        try:
            signature = base64.b64decode(str(payload["Signature"]), validate=True)
            url = self._validate_cert_url(str(payload["SigningCertURL"]))
        except (KeyError, ValueError) as exc:
            raise SnsVerificationError("SNS envelope has an invalid signature field") from exc
        certificate = self._certificate(url)
        try:
            certificate.public_key().verify(
                signature,
                self._signing_text(payload),
                padding.PKCS1v15(),
                algorithm,
            )
        except Exception as exc:
            raise SnsVerificationError("SNS message signature is invalid") from exc
        return payload

    def confirm_subscription(self, payload: dict[str, Any]) -> None:
        """Confirm only the AWS URL contained in an already verified envelope."""
        value = str(payload.get("SubscribeURL", ""))
        parsed = urlparse(value)
        if (
            parsed.scheme != "https"
            or not parsed.hostname
            or not _SNS_HOST.fullmatch(parsed.hostname.lower())
            or parsed.port not in {None, 443}
            or parsed.username
            or parsed.password
        ):
            raise SnsVerificationError("SNS subscription URL is not trusted")
        response = self.session.get(value, timeout=self.timeout_seconds, allow_redirects=False)
        response.raise_for_status()


class SesEventParser:
    @staticmethod
    def parse(payload: dict[str, Any], *, envelope_id: str = "") -> list[dict[str, Any]]:
        kind = str(payload.get("eventType") or payload.get("notificationType") or "")
        mail = payload.get("mail") or {}
        provider_message_id = clean_text(mail.get("messageId"))
        occurred_at = str(mail.get("timestamp") or to_utc_iso())
        event_type = ""
        recipients: list[dict[str, str]] = []

        if kind == "Delivery":
            event_type = "delivered"
            delivery = payload.get("delivery") or {}
            occurred_at = str(delivery.get("timestamp") or occurred_at)
            recipients = [{"email": item, "diagnostic": ""} for item in delivery.get("recipients", [])]
        elif kind == "DeliveryDelay":
            event_type = "deferred"
            delay = payload.get("deliveryDelay") or {}
            occurred_at = str(delay.get("timestamp") or occurred_at)
            recipients = [
                {
                    "email": str(item.get("emailAddress", "")),
                    "diagnostic": str(item.get("diagnosticCode", "")),
                }
                for item in delay.get("delayedRecipients", [])
            ]
        elif kind == "Bounce":
            bounce = payload.get("bounce") or {}
            event_type = "hard_bounce" if str(bounce.get("bounceType")) == "Permanent" else "soft_bounce"
            occurred_at = str(bounce.get("timestamp") or occurred_at)
            recipients = [
                {
                    "email": str(item.get("emailAddress", "")),
                    "diagnostic": str(item.get("diagnosticCode") or item.get("status") or ""),
                }
                for item in bounce.get("bouncedRecipients", [])
            ]
        elif kind == "Complaint":
            event_type = "complaint"
            complaint = payload.get("complaint") or {}
            occurred_at = str(complaint.get("timestamp") or occurred_at)
            recipients = [
                {"email": str(item.get("emailAddress", "")), "diagnostic": "complaint"}
                for item in complaint.get("complainedRecipients", [])
            ]
        elif kind == "Reject":
            event_type = "rejected"
            diagnostic = str((payload.get("reject") or {}).get("reason", ""))
            recipients = [{"email": item, "diagnostic": diagnostic} for item in mail.get("destination", [])]
        elif kind == "Rendering Failure":
            event_type = "rendering_failed"
            diagnostic = str((payload.get("failure") or {}).get("errorMessage", ""))
            recipients = [{"email": item, "diagnostic": diagnostic} for item in mail.get("destination", [])]
        elif kind == "Send":
            event_type = "accepted"
            recipients = [{"email": item, "diagnostic": ""} for item in mail.get("destination", [])]
        else:
            return []

        if not recipients:
            recipients = [{"email": item, "diagnostic": ""} for item in mail.get("destination", [])]
        events: list[dict[str, Any]] = []
        for recipient in recipients:
            email = normalize_email(recipient.get("email"))
            unique = "|".join(
                (envelope_id, provider_message_id, event_type, email, occurred_at)
            )
            events.append(
                {
                    "provider_type": "ses",
                    "provider_event_id": hashlib.sha256(unique.encode("utf-8")).hexdigest(),
                    "provider_message_id": provider_message_id,
                    "event_type": event_type,
                    "recipient_email": email,
                    "diagnostic": clean_text(recipient.get("diagnostic")),
                    "occurred_at": occurred_at,
                    "raw": payload,
                }
            )
        return events


class DeliveryEventProcessor:
    def __init__(self, store: DeliverabilityStore):
        self.store = store

    def process_ses(
        self, payload: dict[str, Any], *, envelope_id: str = ""
    ) -> dict[str, Any]:
        inserted = 0
        duplicates = 0
        suppressions = 0
        campaigns: set[str] = set()
        for event in SesEventParser.parse(payload, envelope_id=envelope_id):
            job = self.store.find_job_by_provider_message(event["provider_message_id"])
            if job:
                event.update(
                    {
                        "job_id": job["id"],
                        "campaign_id": job["campaign_id"],
                        "identity_id": job.get("identity_id"),
                    }
                )
            if not self.store.record_delivery_event(event):
                duplicates += 1
                continue
            inserted += 1
            if event["event_type"] in {"hard_bounce", "complaint"} and event["recipient_email"]:
                self.store.suppress(
                    event["recipient_email"],
                    reason=event["event_type"],
                    source="ses_feedback",
                    provider_event_id=event["provider_event_id"],
                )
                suppressions += 1
            if event.get("campaign_id"):
                campaigns.add(str(event["campaign_id"]))

        health = []
        for campaign_id in sorted(campaigns):
            report = self.store.apply_health_pause(campaign_id)
            health.append(report)
            if report.get("auto_paused_now"):
                self.store.outreach.add_event(
                    campaign_id,
                    "email_delivery_auto_paused",
                    {"breached": report["breached"]},
                )
        return {
            "inserted": inserted,
            "duplicates": duplicates,
            "suppressions": suppressions,
            "health": health,
        }

    @staticmethod
    def sns_message(envelope: dict[str, Any]) -> dict[str, Any]:
        try:
            payload = json.loads(str(envelope["Message"]))
        except (KeyError, json.JSONDecodeError, TypeError) as exc:
            raise ValueError("SNS Message does not contain a valid SES event") from exc
        if not isinstance(payload, dict):
            raise ValueError("SNS Message does not contain a valid SES event")
        return payload
