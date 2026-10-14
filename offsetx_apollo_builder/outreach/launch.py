"""Read-only launch readiness for email campaigns, never a send authorisation.

A green result means the current CRM state contains at least one review
candidate and no obvious local blocker. It does not verify external mail
credentials, recipient consent or delivery-provider preflight.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from .engine import local_day_bounds
from .models import utc_now
from .store import OutreachStore


def launch_readiness(store: OutreachStore, campaign_id: str, *, now: datetime | None = None) -> dict[str, Any]:
    now = now or utc_now()
    campaign = store.get_campaign(campaign_id)
    if campaign["kind"] != "email":
        return {
            "campaign_id": campaign_id, "kind": campaign["kind"],
            "eligible_for_local_review": False,
            "checks": [{
                "id": "campaign_kind", "passed": False,
                "message": "This campaign is not an email campaign; use its own runner.",
                "screen": "campaigns",
            }],
            "candidate_count": 0, "remaining_today": None,
            "external_delivery_verified": False,
        }
    queue = store.send_queue_view(campaign_id, now=now, limit=1)
    counts = queue["counts"]
    start, end = local_day_bounds(now, str(campaign["timezone"]))
    sent_today = store.sent_count_between(campaign_id, start, end)
    remaining = max(0, int(campaign["daily_send_limit"]) - sent_today)
    checks = [
        {
            "id": "active", "passed": campaign["status"] == "active",
            "message": "Campaign is active" if campaign["status"] == "active"
            else "Campaign is paused or archived. Activate it deliberately before a run.",
            "screen": "campaigns",
        },
        {
            "id": "audience", "passed": counts["all"] > 0,
            "message": f"{counts['all']} contacts in this campaign" if counts["all"]
            else "Add contacts before preparing outreach.",
            "screen": "contacts",
        },
        {
            "id": "approved_due", "passed": counts["ready"] > 0,
            "message": f"{counts['ready']} approved, sendable drafts are due for review" if counts["ready"]
            else "No approved sendable draft is due. Generate, audit, approve or check scheduling.",
            "screen": "drafts",
        },
        {
            "id": "daily_cap", "passed": remaining > 0,
            "message": f"{remaining} of the campaign's daily message allowance remain" if remaining
            else "The campaign's daily message allowance is exhausted.",
            "screen": "queue",
        },
    ]
    return {
        "campaign_id": campaign_id,
        "kind": "email",
        "eligible_for_local_review": all(item["passed"] for item in checks),
        "checks": checks,
        "candidate_count": counts["ready"],
        "needs_approval": counts["approval"],
        "remaining_today": remaining,
        "sent_today": sent_today,
        "external_delivery_verified": False,
        "limitations": (
            "This is not an authorization to send. Recipient validation, suppression, "
            "deliverability, mailbox credentials, send window and provider-specific "
            "preflight run separately when sending."
        ),
    }
