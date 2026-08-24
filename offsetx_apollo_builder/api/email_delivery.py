from __future__ import annotations

import html
import json
from typing import Any
from urllib.parse import parse_qs

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse
from starlette.concurrency import run_in_threadpool

from ..outreach.deliverability.events import SnsVerificationError
from ..outreach.deliverability.models import valid_email
from ..outreach.deliverability.service import EmailDeliveryService
from .schemas import (
    EmailCampaignSettingsUpdate,
    EmailEnqueueRequest,
    EmailIdentityUpsert,
    EmailPermissionUpdate,
    EmailSuppressionCreate,
    EmailWorkerRequest,
)

LIVE_BULK_CONFIRMATION = "QUEUE LIVE EMAILS"


def _service(request: Request) -> EmailDeliveryService:
    return request.app.state.email_delivery


def build_email_delivery_router() -> APIRouter:
    router = APIRouter(prefix="/api/v1")

    @router.get("/email-delivery/identities")
    def identities(request: Request) -> dict[str, Any]:
        items = _service(request).store.list_identities()
        return {"items": items, "total": len(items)}

    @router.post("/email-delivery/identities", status_code=201)
    def save_identity(body: EmailIdentityUpsert, request: Request) -> dict[str, Any]:
        return _service(request).save_identity(body.model_dump())

    @router.post("/email-delivery/identities/{identity_id}/check")
    def check_identity(identity_id: str, request: Request) -> dict[str, Any]:
        return _service(request).check_identity(identity_id)

    @router.get("/campaigns/{campaign_id}/email-settings")
    def campaign_settings(campaign_id: str, request: Request) -> dict[str, Any]:
        return _service(request).store.get_campaign_settings(campaign_id)

    @router.patch("/campaigns/{campaign_id}/email-settings")
    def update_campaign_settings(
        campaign_id: str, body: EmailCampaignSettingsUpdate, request: Request
    ) -> dict[str, Any]:
        return _service(request).update_campaign_settings(
            campaign_id, body.model_dump(exclude_unset=True)
        )

    @router.get("/campaigns/{campaign_id}/email-preflight")
    def campaign_preflight(campaign_id: str, request: Request) -> dict[str, Any]:
        return _service(request).campaign_preflight(campaign_id)

    @router.post("/campaigns/{campaign_id}/email-jobs", status_code=202)
    def enqueue_campaign(
        campaign_id: str, body: EmailEnqueueRequest, request: Request
    ) -> dict[str, Any]:
        settings = _service(request).store.get_campaign_settings(campaign_id)
        if (
            settings["provider_type"] != "local"
            and body.confirmation != LIVE_BULK_CONFIRMATION
        ):
            raise ValueError(
                f"Live bulk delivery requires confirmation: {LIVE_BULK_CONFIRMATION}"
            )
        with request.app.state.campaign_locks.hold(campaign_id):
            return _service(request).enqueue_campaign(campaign_id, max_jobs=body.max_jobs)

    @router.get("/email-delivery/jobs")
    def jobs(
        request: Request,
        campaign_id: str = Query("", max_length=80),
        status: str = Query("", max_length=40),
        limit: int = Query(200, ge=1, le=1000),
        offset: int = Query(0, ge=0),
    ) -> dict[str, Any]:
        items, total = _service(request).store.list_jobs(
            campaign_id=campaign_id, status=status, limit=limit, offset=offset
        )
        return {"items": items, "total": total, "limit": limit, "offset": offset}

    @router.post("/email-delivery/jobs/{job_id}/cancel")
    def cancel_job(job_id: str, request: Request) -> dict[str, Any]:
        return _service(request).cancel_job(job_id)

    @router.post("/email-delivery/work")
    def work(body: EmailWorkerRequest, request: Request) -> dict[str, Any]:
        return _service(request).work_once(max_jobs=body.max_jobs)

    @router.get("/campaigns/{campaign_id}/email-health")
    def health(campaign_id: str, request: Request) -> dict[str, Any]:
        return _service(request).store.health(campaign_id)

    @router.post("/campaigns/{campaign_id}/email-health/resume")
    def resume(campaign_id: str, request: Request) -> dict[str, Any]:
        return _service(request).store.resume_health(campaign_id)

    @router.get("/email-delivery/permissions/{email}")
    def permission(email: str, request: Request) -> dict[str, Any]:
        if not valid_email(email):
            raise ValueError("A valid email address is required")
        return _service(request).store.get_permission(email)

    @router.patch("/email-delivery/permissions/{email}")
    def update_permission(
        email: str, body: EmailPermissionUpdate, request: Request
    ) -> dict[str, Any]:
        if not valid_email(email):
            raise ValueError("A valid email address is required")
        if body.status == "granted" and not body.basis:
            raise ValueError("A permission basis is required when permission is granted")
        if body.expires_at and body.obtained_at and body.expires_at <= body.obtained_at:
            raise ValueError("Permission expiry must be after the obtained date")
        return _service(request).store.set_permission(
            email,
            status=body.status,
            basis=body.basis,
            source=body.source,
            evidence=body.evidence,
            obtained_at=body.obtained_at,
            expires_at=body.expires_at,
        )

    @router.get("/email-delivery/suppressions")
    def suppressions(
        request: Request,
        active_only: bool = True,
        limit: int = Query(200, ge=1, le=1000),
        offset: int = Query(0, ge=0),
    ) -> dict[str, Any]:
        items, total = _service(request).store.list_suppressions(
            active_only=active_only, limit=limit, offset=offset
        )
        return {"items": items, "total": total, "limit": limit, "offset": offset}

    @router.post("/email-delivery/suppressions", status_code=201)
    def suppress(body: EmailSuppressionCreate, request: Request) -> dict[str, Any]:
        if not valid_email(body.email):
            raise ValueError("A valid email address is required")
        return _service(request).store.suppress(
            body.email, reason=body.reason, source=body.source
        )

    @router.delete("/email-delivery/suppressions/{email}")
    def unsuppress(email: str, request: Request) -> dict[str, Any]:
        return _service(request).store.unsuppress(email)

    @router.post("/email-delivery/events/ses/sns")
    async def ses_sns(request: Request) -> JSONResponse:
        raw = await request.body()
        if len(raw) > 1024 * 1024:
            raise HTTPException(413, "SNS envelope exceeds 1 MB")
        try:
            envelope = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise HTTPException(400, "SNS envelope is not valid JSON") from exc
        if not isinstance(envelope, dict):
            raise HTTPException(400, "SNS envelope must be a JSON object")
        topics = [
            row["sns_topic_arn"]
            for row in _service(request).store.list_identities()
            if row.get("sns_topic_arn")
        ]
        try:
            await run_in_threadpool(
                request.app.state.sns_verifier.verify,
                envelope,
                expected_topics=topics,
            )
        except SnsVerificationError as exc:
            raise HTTPException(403, str(exc)) from exc
        message_type = envelope.get("Type")
        if message_type == "SubscriptionConfirmation":
            await run_in_threadpool(
                request.app.state.sns_verifier.confirm_subscription, envelope
            )
            return JSONResponse(status_code=202, content={"status": "subscription_confirmed"})
        if message_type != "Notification":
            return JSONResponse(status_code=202, content={"status": "ignored"})
        payload = _service(request).events.sns_message(envelope)
        result = await run_in_threadpool(
            _service(request).events.process_ses,
            payload,
            envelope_id=str(envelope.get("MessageId", "")),
        )
        return JSONResponse(content=result)

    @router.get("/email/unsubscribe/{token}", response_class=HTMLResponse)
    def unsubscribe_page(token: str, request: Request) -> HTMLResponse:
        service = _service(request).unsubscribe
        if service is None:
            raise HTTPException(503, "Unsubscribe service is not configured")
        service.verify(token)
        safe_token = html.escape(token, quote=True)
        return HTMLResponse(
            "<!doctype html><html lang='en'><meta charset='utf-8'>"
            "<meta name='viewport' content='width=device-width,initial-scale=1'>"
            "<title>Unsubscribe</title><body><main>"
            "<h1>Stop these emails?</h1><p>This will suppress your address from future outreach.</p>"
            f"<form method='post' action='/api/v1/email/unsubscribe/{safe_token}'>"
            "<input type='hidden' name='List-Unsubscribe' value='One-Click'>"
            "<button type='submit'>Unsubscribe</button></form></main></body></html>"
        )

    @router.post("/email/unsubscribe/{token}")
    async def unsubscribe(token: str, request: Request) -> JSONResponse:
        service = _service(request).unsubscribe
        if service is None:
            raise HTTPException(503, "Unsubscribe service is not configured")
        raw = await request.body()
        if len(raw) > 4096:
            raise HTTPException(413, "Unsubscribe request is too large")
        form = parse_qs(raw.decode("utf-8", errors="strict"), keep_blank_values=True)
        if form.get("List-Unsubscribe") != ["One-Click"]:
            raise HTTPException(400, "One-click unsubscribe confirmation is required")
        result = service.unsubscribe(token)
        _service(request).store.record_delivery_event(
            {
                "provider_type": "local",
                "provider_event_id": f"unsubscribe:{result['token_id']}",
                "campaign_id": result.get("campaign_id") or None,
                "event_type": "unsubscribe",
                "recipient_email": result["email"],
                "occurred_at": result["occurred_at"],
                "raw": {"source": "one_click"},
            }
        )
        return JSONResponse(content={"status": "unsubscribed"})

    return router
