from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from ..models import parse_datetime, utc_now
from .models import (
    PERMISSION_MARKETING,
    TARGETED_OUTREACH,
    TRANSACTIONAL,
    PreflightReport,
    unsubscribe_required,
    valid_email,
)
from .store import DeliverabilityStore

_TRANSACTIONAL_BASES = {"existing_customer", "service_request", "contract"}


class PreflightService:
    """Explainable send policy. It never calls a model and never guesses."""

    def __init__(
        self,
        store: DeliverabilityStore,
        *,
        unsubscribe_available: bool = False,
    ):
        self.store = store
        self.unsubscribe_available = unsubscribe_available

    def check(
        self,
        campaign_id: str,
        email: str,
        *,
        provider_type: str | None = None,
        identity_id: str | None = None,
        now: datetime | None = None,
    ) -> PreflightReport:
        now = now or utc_now()
        report = PreflightReport()
        campaign = self.store.outreach.get_campaign(campaign_id)
        settings = self.store.get_campaign_settings(campaign_id)
        provider = provider_type or str(settings["provider_type"])
        selected_identity = identity_id if identity_id is not None else settings.get("identity_id")
        stream = str(settings["stream"])

        report.checks.update(
            {
                "campaign_status": campaign["status"],
                "stream": stream,
                "provider_type": provider,
                "identity_id": selected_identity or "",
            }
        )
        if campaign["status"] != "active":
            report.block("campaign_inactive", "Campaign must be active before email can be sent.")
        from ..engine import campaign_send_window

        window = campaign_send_window(campaign, now)
        report.checks["send_window"] = window
        if not window["allowed"]:
            report.block(
                "outside_campaign_send_window",
                "Campaign is outside its configured local send window.",
                "send_window",
            )
        if settings.get("paused_reason"):
            report.block(
                "deliverability_paused",
                str(settings["paused_reason"]),
                "campaign_id",
            )

        if not valid_email(email, ascii_only=provider == "ses"):
            message = "SES requires a valid ASCII recipient address." if provider == "ses" else "A valid recipient email is required."
            report.block("invalid_email", message, "email")
            return report

        suppression = self.store.is_suppressed(email)
        report.checks["suppressed"] = bool(suppression)
        if suppression:
            report.block(
                "suppressed",
                f"Recipient is globally suppressed: {suppression['reason']}",
                "email",
            )

        permission = self.store.get_permission(email)
        permission_expiry = parse_datetime(permission.get("expires_at"))
        permission_active = permission["status"] == "granted" and (
            permission_expiry is None or permission_expiry > now
        )
        relationship_active = permission_active and permission.get("basis") in _TRANSACTIONAL_BASES
        report.checks["permission"] = {
            "status": permission["status"],
            "basis": permission.get("basis", ""),
            "expires_at": permission.get("expires_at"),
            "active": permission_active,
            "relationship_active": relationship_active,
        }
        if permission["status"] == "denied":
            report.block("permission_denied", "Recipient has denied email permission.", "email")
        elif stream == PERMISSION_MARKETING and not permission_active:
            report.block(
                "permission_required",
                "Permission marketing requires an active, recorded grant for this address.",
                "permission",
            )
        elif stream == TRANSACTIONAL and not relationship_active:
            report.block(
                "relationship_required",
                "Transactional email requires a recorded customer, contract, or service-request relationship.",
                "permission",
            )
        elif stream == TARGETED_OUTREACH and permission["status"] == "unknown":
            report.warn(
                "permission_unknown",
                "No permission grant is recorded. Keep this as targeted outreach; do not treat it as subscribed marketing.",
                "permission",
            )

        recent = self.store.recent_send_count(
            email, since=now - timedelta(days=int(settings["frequency_cap_days"]))
        )
        report.checks["frequency"] = {
            "recent_sends": recent,
            "days": int(settings["frequency_cap_days"]),
            "maximum": int(settings["frequency_cap_max"]),
        }
        if recent >= int(settings["frequency_cap_max"]):
            report.block(
                "frequency_cap",
                f"Recipient already received {recent} emails in the last {settings['frequency_cap_days']} days.",
                "frequency_cap_max",
            )

        requires_unsubscribe = unsubscribe_required(
            stream=stream,
            provider_type=provider,
            configured=bool(settings["require_unsubscribe"]),
        )
        report.checks["unsubscribe"] = {
            "required": requires_unsubscribe,
            "available": self.unsubscribe_available,
        }
        if requires_unsubscribe and (
            stream == PERMISSION_MARKETING or provider == "ses"
        ) and not self.unsubscribe_available:
            report.block(
                "unsubscribe_unavailable",
                "Permission marketing and SES bulk outreach require a public one-click unsubscribe URL.",
                "public_base_url",
            )
        elif requires_unsubscribe and not self.unsubscribe_available:
            report.warn(
                "unsubscribe_unavailable",
                "Configure a public base URL before using this campaign for scaled outreach.",
                "public_base_url",
            )

        identity: dict[str, Any] | None = None
        if selected_identity:
            try:
                identity = self.store.get_identity(str(selected_identity))
            except KeyError:
                report.block("identity_missing", "The selected sending identity no longer exists.", "identity_id")
            else:
                report.checks["identity"] = {
                    "status": identity["status"],
                    "stream": identity["stream"],
                    "provider_type": identity["provider_type"],
                    "from_email": identity["from_email"],
                    "provider_verified": identity["provider_verified"],
                    "spf": identity["spf_status"],
                    "dkim": identity["dkim_status"],
                    "dmarc": identity["dmarc_status"],
                    "alignment": identity["alignment_status"],
                    "last_checked_at": identity["last_checked_at"],
                }
                if identity["status"] != "active":
                    report.block("identity_inactive", "The sending identity is not active.", "identity_id")
                if identity["stream"] != stream:
                    report.block(
                        "traffic_not_separated",
                        "The sending identity belongs to a different email stream.",
                        "identity_id",
                    )
                if identity["provider_type"] != provider:
                    report.block(
                        "provider_mismatch",
                        "Campaign provider and sending identity provider do not match.",
                        "provider_type",
                    )
                if not valid_email(identity["from_email"], ascii_only=provider == "ses"):
                    report.block("invalid_from_email", "Sending identity needs a valid From address.", "from_email")

        if provider == "ses":
            if identity is None:
                report.block("identity_required", "Amazon SES requires a sending identity.", "identity_id")
            else:
                checked_at = parse_datetime(identity.get("last_checked_at"))
                auth_fresh = bool(checked_at and checked_at > now - timedelta(days=7))
                report.checks["identity"]["authentication_fresh"] = auth_fresh
                if not auth_fresh:
                    report.block(
                        "authentication_check_stale",
                        "Run the SES/domain authentication check within seven days of sending.",
                        "last_checked_at",
                    )
                if not identity.get("configuration_set"):
                    report.block(
                        "feedback_configuration_required",
                        "SES bulk delivery requires a configuration set for provider feedback.",
                        "configuration_set",
                    )
                if not identity.get("sns_topic_arn"):
                    report.block(
                        "feedback_topic_required",
                        "SES bulk delivery requires an expected SNS feedback topic ARN.",
                        "sns_topic_arn",
                    )
                if not identity["provider_verified"]:
                    report.block(
                        "provider_identity_unverified",
                        "Amazon SES has not verified this sending identity.",
                        "identity_id",
                    )
                if identity["dkim_status"] != "pass":
                    report.block("dkim_required", "DKIM must pass before SES sending is enabled.", "dkim")
                for field, label in (
                    ("spf_status", "SPF"),
                    ("dmarc_status", "DMARC"),
                    ("alignment_status", "DMARC alignment"),
                ):
                    if identity[field] != "pass":
                        if stream == PERMISSION_MARKETING:
                            report.block(
                                f"{field.removesuffix('_status')}_required",
                                f"{label} must pass for permission marketing.",
                                field,
                            )
                        else:
                            report.warn(
                                f"{field.removesuffix('_status')}_not_ready",
                                f"{label} is not confirmed. Deliverability will be weaker.",
                                field,
                            )
        elif stream == PERMISSION_MARKETING:
            report.block(
                "bulk_provider_required",
                "Permission marketing must use the SES bulk lane so bounces and complaints are measurable.",
                "provider_type",
            )
        elif provider == "gmail":
            report.warn(
                "gmail_small_outreach_only",
                "Gmail is retained for small targeted outreach, not high-volume campaigns.",
                "provider_type",
            )
        else:
            report.warn(
                "local_delivery_only",
                "Local mode writes a test message to disk and does not contact the recipient.",
                "provider_type",
            )
        return report

    def campaign_report(
        self,
        campaign_id: str,
        *,
        provider_type: str | None = None,
        identity_id: str | None = None,
        now: datetime | None = None,
        limit: int = 5000,
    ) -> dict[str, Any]:
        rows = self.store.outreach.send_queue(campaign_id, now=now or utc_now())[:limit]
        items: list[dict[str, Any]] = []
        allowed = 0
        for row in rows:
            if (
                not row.get("draft_id")
                or not row.get("is_due")
                or row.get("status") in {"replied", "stopped", "completed"}
                or row.get("approval_status") != "approved"
                or not row.get("sendable")
            ):
                continue
            report = self.check(
                campaign_id,
                str(row.get("email", "")),
                provider_type=provider_type,
                identity_id=identity_id,
                now=now,
            )
            allowed += int(report.allowed)
            items.append(
                {
                    "campaign_contact_id": row["campaign_contact_id"],
                    "draft_id": row["draft_id"],
                    "email": row.get("email", ""),
                    **report.to_dict(),
                }
            )
        blocker_counts: dict[str, int] = {}
        for item in items:
            for blocker in item["blockers"]:
                blocker_counts[blocker["code"]] = blocker_counts.get(blocker["code"], 0) + 1
        return {
            "campaign_id": campaign_id,
            "allowed": allowed,
            "blocked": len(items) - allowed,
            "evaluated": len(items),
            "blocker_counts": blocker_counts,
            "items": items,
        }
