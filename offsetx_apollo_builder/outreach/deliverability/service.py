from __future__ import annotations

import hashlib
import re
import threading
from datetime import datetime, timedelta
from typing import Any, Callable

from ..models import FOLLOWUP_1, INITIAL, clean_text, to_utc_iso, utc_now
from .domain_auth import DomainAuthChecker
from .events import DeliveryEventProcessor
from .models import (
    EMAIL_STREAMS,
    MAIL_PROVIDERS,
    PERMISSION_MARKETING,
    AmbiguousDeliveryError,
    DeliveryProvider,
    PermanentDeliveryError,
    RetryableDeliveryError,
    unsubscribe_required,
    valid_email,
)
from .preflight import PreflightService
from .store import DeliverabilityStore
from .unsubscribe import UnsubscribeService

ProviderFactory = Callable[[dict[str, Any], dict[str, Any] | None], DeliveryProvider]

_AWS_REGION = re.compile(r"^[a-z]{2}(?:-gov)?-[a-z]+-\d$")
_CONFIGURATION_SET = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
_SNS_TOPIC_ARN = re.compile(
    r"^arn:(?:aws|aws-cn|aws-us-gov):sns:([a-z0-9-]+):\d{12}:[A-Za-z0-9_-]{1,256}$"
)


class EmailDeliveryService:
    """Application boundary for protected, durable email delivery."""

    def __init__(
        self,
        engine: Any,
        *,
        unsubscribe: UnsubscribeService | None = None,
        domain_checker: DomainAuthChecker | None = None,
        provider_factory: ProviderFactory | None = None,
    ):
        self.engine = engine
        self.store = DeliverabilityStore(engine.store)
        self.unsubscribe = unsubscribe
        self.preflight = PreflightService(
            self.store,
            unsubscribe_available=bool(unsubscribe and unsubscribe.available),
        )
        self.domain_checker = domain_checker or DomainAuthChecker()
        self.provider_factory = provider_factory
        self.events = DeliveryEventProcessor(self.store)
        self._worker_lock = threading.Lock()

    # Configuration ------------------------------------------------------

    def save_identity(self, values: dict[str, Any]) -> dict[str, Any]:
        provider = clean_text(values.get("provider_type"))
        stream = clean_text(values.get("stream"))
        from_email = clean_text(values.get("from_email")).lower()
        if not clean_text(values.get("name")):
            raise ValueError("Sending identity name is required")
        if provider not in MAIL_PROVIDERS:
            raise ValueError("Email provider must be local, gmail, or ses")
        if stream not in EMAIL_STREAMS:
            raise ValueError("Unknown email stream")
        if not valid_email(from_email, ascii_only=provider == "ses"):
            raise ValueError("Sending identity requires a valid From address")
        domain = from_email.rsplit("@", 1)[1]
        supplied_domain = clean_text(values.get("domain")).lower()
        if supplied_domain and supplied_domain != domain:
            raise ValueError("Sending identity domain must match the From address")
        if values.get("reply_to") and not valid_email(values["reply_to"], ascii_only=provider == "ses"):
            raise ValueError("Reply-To address is invalid")
        rate = float(values.get("max_per_second", 1))
        batch_size = int(values.get("max_batch_size", 25))
        if not 0 < rate <= 1000:
            raise ValueError("Messages per second must be above 0 and at most 1000")
        if not 1 <= batch_size <= 500:
            raise ValueError("Worker batch size must be between 1 and 500")
        if provider == "ses" and not clean_text(values.get("aws_region")):
            raise ValueError("Amazon SES region is required")
        if provider == "ses":
            region = clean_text(values.get("aws_region"))
            if not _AWS_REGION.fullmatch(region):
                raise ValueError("Amazon SES region is invalid")
            configuration_set = clean_text(values.get("configuration_set"))
            if configuration_set and not _CONFIGURATION_SET.fullmatch(configuration_set):
                raise ValueError("Amazon SES configuration-set name is invalid")
            topic = clean_text(values.get("sns_topic_arn"))
            match = _SNS_TOPIC_ARN.fullmatch(topic) if topic else None
            if topic and (not match or match.group(1) != region):
                raise ValueError("SNS topic ARN must be valid and use the SES region")
        identity_id = clean_text(values.get("id"))
        for existing in self.store.list_identities():
            if existing["id"] != identity_id and existing["from_email"] == from_email:
                raise ValueError("An active sending identity already uses this From address")
            if (
                existing["id"] != identity_id
                and existing["domain"] == domain
                and existing["stream"] != stream
            ):
                raise ValueError(
                    "Sending domain already belongs to a different email stream; use an isolated subdomain"
                )
        payload = {**values, "domain": domain}
        return self.store.upsert_identity(payload)

    def check_identity(self, identity_id: str) -> dict[str, Any]:
        identity = self.store.get_identity(identity_id)
        provider_details: dict[str, Any] = {}
        if identity["provider_type"] == "ses":
            if self.provider_factory is None:
                raise RuntimeError("Email delivery provider factory is not configured")
            provider = self.provider_factory(
                {
                    "provider_type": "ses",
                    "identity_id": identity_id,
                    "campaign_id": "",
                },
                identity,
            )
            identity_status = getattr(provider, "identity_status", None)
            if not callable(identity_status):
                raise RuntimeError("SES provider cannot check identity status")
            provider_details = identity_status(identity["ses_identity"] or identity["domain"])
        result = self.domain_checker.check(identity, provider_details=provider_details)
        return self.store.update_identity_check(identity_id, **result)

    def update_campaign_settings(
        self, campaign_id: str, values: dict[str, Any]
    ) -> dict[str, Any]:
        current = self.store.get_campaign_settings(campaign_id)
        merged = {**current, **values}
        if merged["stream"] not in EMAIL_STREAMS:
            raise ValueError("Unknown email stream")
        if merged["provider_type"] not in MAIL_PROVIDERS:
            raise ValueError("Email provider must be local, gmail, or ses")
        if merged["stream"] == PERMISSION_MARKETING and not merged["require_unsubscribe"]:
            raise ValueError("Permission marketing cannot disable unsubscribe")
        identity_id = merged.get("identity_id")
        if identity_id:
            identity = self.store.get_identity(str(identity_id))
            if identity["stream"] != merged["stream"]:
                raise ValueError("Sending identity belongs to a different email stream")
            if identity["provider_type"] != merged["provider_type"]:
                raise ValueError("Sending identity belongs to a different provider")
        elif merged["provider_type"] == "ses":
            raise ValueError("Amazon SES campaigns require a sending identity")
        return self.store.update_campaign_settings(campaign_id, values)

    # Preflight and enqueue ---------------------------------------------

    def campaign_preflight(self, campaign_id: str) -> dict[str, Any]:
        settings = self.store.get_campaign_settings(campaign_id)
        return self.preflight.campaign_report(
            campaign_id,
            provider_type=str(settings["provider_type"]),
            identity_id=settings.get("identity_id"),
        )

    def enqueue_campaign(
        self, campaign_id: str, *, max_jobs: int = 5000, now: datetime | None = None
    ) -> dict[str, Any]:
        now = now or utc_now()
        settings = self.store.get_campaign_settings(campaign_id)
        identity = (
            self.store.get_identity(str(settings["identity_id"]))
            if settings.get("identity_id")
            else None
        )
        provider = str(settings["provider_type"])
        if provider == "gmail":
            raise ValueError(
                "Gmail is the small-outreach lane. Use the confirmed Gmail action in Send queue; durable bulk jobs use SES."
            )
        queued: list[dict[str, str]] = []
        blocked: list[dict[str, Any]] = []
        replayed = 0
        for item in self.engine.store.send_queue(campaign_id, now=now):
            if len(queued) >= max_jobs:
                break
            if item.get("status") in {"replied", "stopped", "completed"}:
                continue
            if not item.get("is_due") or item.get("approval_status") != "approved" or not item.get("sendable"):
                continue
            draft_id = clean_text(item.get("draft_id"))
            if not draft_id:
                continue
            report = self.preflight.check(
                campaign_id,
                str(item.get("email", "")),
                provider_type=provider,
                identity_id=settings.get("identity_id"),
                now=now,
            )
            if not report.allowed:
                blocked.append(
                    {
                        "campaign_contact_id": item["campaign_contact_id"],
                        "draft_id": draft_id,
                        **report.to_dict(),
                    }
                )
                continue
            draft = self.engine.store.get_draft_by_id(campaign_id, draft_id)
            body = str(draft["body"])
            headers: dict[str, str] = {}
            stream = str(settings["stream"])
            needs_unsubscribe = unsubscribe_required(
                stream=stream,
                provider_type=provider,
                configured=bool(settings["require_unsubscribe"]),
            )
            if self.unsubscribe and self.unsubscribe.available and needs_unsubscribe:
                url = self.unsubscribe.issue(
                    email=str(item["email"]), campaign_id=campaign_id, stream=stream
                )
                body, headers = self.unsubscribe.prepare_content(
                    body,
                    url=url,
                    include_list_headers=stream == PERMISSION_MARKETING,
                )
            idempotency_key = hashlib.sha256(
                ":".join(
                    (
                        campaign_id,
                        draft_id,
                        str(draft["revision"]),
                        provider,
                        str(settings.get("identity_id") or ""),
                    )
                ).encode("utf-8")
            ).hexdigest()
            lane_key = f"{provider}:{settings.get('identity_id') or campaign_id}"
            job, created = self.store.enqueue_job(
                {
                    "campaign_id": campaign_id,
                    "campaign_contact_id": item["campaign_contact_id"],
                    "draft_id": draft_id,
                    "draft_revision": int(draft["revision"]),
                    "identity_id": settings.get("identity_id"),
                    "stream": stream,
                    "provider_type": provider,
                    "lane_key": lane_key,
                    "to_email": item["email"],
                    "from_email": identity["from_email"] if identity else "",
                    "subject": draft["subject"],
                    "body": body,
                    "headers": headers,
                    "idempotency_key": idempotency_key,
                    "available_at": to_utc_iso(now),
                }
            )
            replayed += int(not created)
            queued.append(
                {
                    "job_id": str(job["id"]),
                    "draft_id": draft_id,
                    "to": str(job["to_email"]),
                }
            )
        result = {
            "campaign_id": campaign_id,
            "queued": queued,
            "queued_count": len(queued),
            "blocked": blocked,
            "blocked_count": len(blocked),
            "idempotent_replays": replayed,
        }
        self.engine.store.add_event(campaign_id, "email_jobs_enqueued", result)
        return result

    # Worker -------------------------------------------------------------

    def work_once(self, *, max_jobs: int = 25, now: datetime | None = None) -> dict[str, Any]:
        if self.provider_factory is None:
            raise RuntimeError("Email delivery provider factory is not configured")
        if not self._worker_lock.acquire(blocking=False):
            raise RuntimeError("An email delivery worker cycle is already running")
        now = now or utc_now()
        try:
            recovered = self.store.recover_stale(now=now)
            results: list[dict[str, Any]] = []
            lane_counts: dict[str, int] = {}
            for _ in range(max_jobs):
                job = self.store.claim_next(now=now, lane_counts=lane_counts)
                if job is None:
                    break
                lane = str(job["lane_key"])
                lane_counts[lane] = lane_counts.get(lane, 0) + 1
                results.append(self._send_job(job, now=now))
            return {
                "processed": len(results),
                "accepted": sum(item["status"] == "accepted" for item in results),
                "retry_wait": sum(item["status"] == "retry_wait" for item in results),
                "failed": sum(item["status"] in {"failed", "blocked", "delivery_unknown"} for item in results),
                "recovery": recovered,
                "items": results,
            }
        finally:
            self._worker_lock.release()

    def _send_job(self, job: dict[str, Any], *, now: datetime) -> dict[str, Any]:
        contact = self.engine.store.get_campaign_contact(
            str(job["campaign_id"]), str(job["campaign_contact_id"])
        )
        if contact["status"] in {"replied", "stopped", "completed"}:
            self.store.cancel_for_reply(str(job["id"]))
            return {
                "job_id": job["id"],
                "status": "cancelled",
                "error": "Recipient is no longer eligible after a reply or stop.",
            }
        report = self.preflight.check(
            str(job["campaign_id"]),
            str(job["to_email"]),
            provider_type=str(job["provider_type"]),
            identity_id=job.get("identity_id"),
            now=now,
        )
        if not report.allowed:
            reason = "; ".join(item.message for item in report.blockers)
            temporal = {
                "campaign_inactive",
                "outside_campaign_send_window",
                "deliverability_paused",
            }
            if {item.code for item in report.blockers}.issubset(temporal):
                self.store.defer_without_attempt(
                    str(job["id"]),
                    reason=reason,
                    available_at=now + timedelta(minutes=15),
                )
                return {
                    "job_id": job["id"],
                    "status": "retry_wait",
                    "retry_after_seconds": 900,
                    "error": reason,
                }
            self.store.mark_terminal(str(job["id"]), status="blocked", error=reason)
            return {"job_id": job["id"], "status": "blocked", "error": reason}
        identity = (
            self.store.get_identity(str(job["identity_id"])) if job.get("identity_id") else None
        )
        if identity and str(identity["from_email"]) != str(job["from_email"]):
            reason = "Sending identity changed after the job was queued; enqueue a new job."
            self.store.mark_terminal(str(job["id"]), status="blocked", error=reason)
            return {"job_id": job["id"], "status": "blocked", "error": reason}
        provider = self.provider_factory(job, identity)
        last = self.engine.store.last_outgoing(str(job["campaign_contact_id"])) or {}
        try:
            result = provider.send_message(
                to_email=str(job["to_email"]),
                from_email=str(job["from_email"]),
                from_name=str(identity["name"]) if identity else "",
                reply_to=str(identity["reply_to"]) if identity else "",
                subject=str(job["subject"]),
                body=str(job["body"]),
                headers=job.get("headers") or {},
                tags={
                    "off_crm_job": str(job["id"]),
                    "off_crm_campaign": str(job["campaign_id"]),
                    "off_crm_stream": str(job["stream"]),
                },
                thread_id=clean_text(last.get("thread_id")),
                in_reply_to=clean_text(last.get("internet_message_id")),
                references=clean_text(last.get("internet_message_id")),
                idempotency_key=str(job["idempotency_key"]),
            )
        except RetryableDeliveryError as exc:
            if int(job["attempt_count"]) >= 5:
                self.store.mark_terminal(
                    str(job["id"]), status="failed", error=f"Retry limit reached: {exc}"
                )
                return {"job_id": job["id"], "status": "failed", "error": str(exc)}
            delay = exc.retry_after_seconds or min(3600, 5 * (2 ** max(0, int(job["attempt_count"]) - 1)))
            self.store.mark_retry(
                str(job["id"]), error=str(exc), available_at=now + timedelta(seconds=delay)
            )
            return {
                "job_id": job["id"],
                "status": "retry_wait",
                "retry_after_seconds": delay,
                "error": str(exc),
            }
        except PermanentDeliveryError as exc:
            self.store.mark_terminal(str(job["id"]), status="failed", error=str(exc))
            return {"job_id": job["id"], "status": "failed", "error": str(exc)}
        except AmbiguousDeliveryError as exc:
            self.store.mark_terminal(
                str(job["id"]), status="delivery_unknown", error=str(exc)
            )
            return {"job_id": job["id"], "status": "delivery_unknown", "error": str(exc)}
        except Exception as exc:
            # Unknown provider exceptions are ambiguous. Retrying automatically
            # could contact the same person twice.
            message = f"Provider state is unknown: {str(exc)[:900]}"
            self.store.mark_terminal(
                str(job["id"]), status="delivery_unknown", error=message
            )
            return {"job_id": job["id"], "status": "delivery_unknown", "error": message}

        campaign = self.engine.store.get_campaign(str(job["campaign_id"]))
        draft = self.engine.store.get_draft_by_id(str(job["campaign_id"]), str(job["draft_id"]))
        from ..engine import add_working_days

        stage = str(draft["stage"])
        if stage == INITIAL:
            next_action = add_working_days(
                now, int(campaign["followup1_working_days"]), str(campaign["timezone"])
            )
            final_status = "waiting_followup"
        elif stage == FOLLOWUP_1:
            next_action = add_working_days(
                now, int(campaign["followup2_working_days"]), str(campaign["timezone"])
            )
            final_status = "waiting_followup"
        else:
            next_action = None
            final_status = "completed"
        self.engine.store.record_sent(
            campaign_contact_id=str(job["campaign_contact_id"]),
            draft=draft,
            result=result,
            to_email=str(job["to_email"]),
            sent_at=now,
            next_action_at=next_action,
            final_status=final_status,
            idempotency_key=str(job["idempotency_key"]),
            sent_subject=str(job["subject"]),
            sent_body=str(job["body"]),
        )
        self.store.mark_accepted(
            str(job["id"]), provider_message_id=result.provider_message_id
        )
        self.store.record_delivery_event(
            {
                "provider_type": job["provider_type"],
                "provider_event_id": f"accepted:{job['id']}",
                "job_id": job["id"],
                "campaign_id": job["campaign_id"],
                "identity_id": job.get("identity_id"),
                "provider_message_id": result.provider_message_id,
                "event_type": "accepted",
                "recipient_email": job["to_email"],
                "occurred_at": now.isoformat(),
                "raw": {"source": "worker"},
            }
        )
        self.engine._count_send(draft)
        if self.engine.mail_archive is not None:
            self.engine._archive_send(
                str(job["campaign_id"]),
                str(job["campaign_contact_id"]),
                str(job["from_email"]),
                self.engine.store.campaign_contacts(str(job["campaign_id"])),
            )
        return {
            "job_id": job["id"],
            "status": "accepted",
            "provider_message_id": result.provider_message_id,
        }

    def cancel_job(self, job_id: str) -> dict[str, Any]:
        return self.store.cancel_queued_job(job_id)
