"""HTTP surface for the GTM engine — epic E-12.

The contract is ``docs/architecture/GTM_ENGINE.md`` §9. Every refusal is
``{"error": code, "message": sentence}`` with 404, 409 or 422 — never a stack
trace, and never the app-wide ``ValueError`` handler's bare string, because the
product form needs to know *which field* to point at.
"""

from __future__ import annotations

from typing import Any, Callable

from fastapi import APIRouter, Body, HTTPException, Query, Request

from ..gtm.products import ProductInvalid
from ..gtm.service import GtmService
from ..gtm.store import GtmStore, PlanStateError, ProductConflict
from ..gtm.strategy import RequestInvalid

#: How the router learns the workspace. Passed in rather than decided here, so
#: this surface follows whatever rule the rest of the API uses.
WorkspaceOf = Callable[[Request], str]

#: How the router reads a campaign: raises ``KeyError`` when there is none.
#: Campaigns live in the CRM store, which this module does not own.
CampaignOf = Callable[[Request, str], dict[str, Any]]

#: The strategy brain for a request's workspace, built by the app with the
#: readers and the one model call it needs.
ServiceOf = Callable[[Request], GtmService]

#: A checklist longer than this is not a person ticking boxes.
MAX_LINKS = 200


def resolve_angle(store: GtmStore, workspace_id: str, campaign_id: str, explicit: str) -> str:
    """The angle a post pipeline runs with: the owner's, else the product's.

    One rule for the HTTP endpoints and the automation timer. It must run
    **before** the pipeline is built, because the pipeline chooses its data
    class from whether an angle is present — the owner's positioning is not
    public, and tier C and D must never see it under a public label.
    """
    chosen = str(explicit or "").strip()
    if chosen:
        return chosen
    product = store.product_for_campaign(campaign_id, workspace_id)
    return str(product["one_liner"]) if product else ""


def _store(request: Request) -> GtmStore:
    return request.app.state.gtm_store


def _sentence(text: str) -> str:
    text = text.strip().strip("'\"")
    return text if text.endswith((".", "?", "!")) else f"{text}."


def _not_found(exc: KeyError) -> HTTPException:
    return HTTPException(
        404, detail={"error": "not_found", "message": _sentence(str(exc))}
    )


def _invalid(exc: ProductInvalid) -> HTTPException:
    return HTTPException(
        422,
        detail={"error": "invalid_product", "field": exc.field, "message": _sentence(str(exc))},
    )


def _conflict(exc: Exception) -> HTTPException:
    return HTTPException(409, detail={"error": "conflict", "message": _sentence(str(exc))})


def _wrong_state(exc: PlanStateError) -> HTTPException:
    return HTTPException(409, detail={"error": "wrong_state", "message": _sentence(str(exc))})


def _invalid_request(exc: RequestInvalid) -> HTTPException:
    return HTTPException(
        422,
        detail={"error": "invalid_request", "field": exc.field, "message": _sentence(str(exc))},
    )


def _object(body: Any) -> dict[str, Any]:
    if not isinstance(body, dict):
        raise _invalid(ProductInvalid("product", "A product must be an object of named fields."))
    return body


def _link_view(request: Request, campaign_of: CampaignOf, campaign_id: str) -> dict[str, Any]:
    try:
        campaign = campaign_of(request, campaign_id)
    except KeyError:
        # Deleted from the CRM after it was linked. Shown, not hidden, so the
        # owner can see it and unlink it.
        return {"campaign_id": campaign_id, "name": "", "kind": "", "exists": False}
    return {
        "campaign_id": campaign_id,
        "name": str(campaign.get("name") or ""),
        "kind": str(campaign.get("kind") or ""),
        "exists": True,
    }


def build_gtm_router(
    *, workspace_of: WorkspaceOf, campaign_of: CampaignOf, service_of: ServiceOf
) -> APIRouter:
    router = APIRouter(prefix="/api/v1/gtm")

    # ── products (S-12.01.01) ───────────────────────────────────────────────

    @router.get("/products")
    def list_products(request: Request) -> dict[str, Any]:
        return {"items": _store(request).list_products(workspace_of(request))}

    @router.post("/products", status_code=201)
    def create_product(request: Request, body: Any = Body(...)) -> dict[str, Any]:
        try:
            return _store(request).create_product(workspace_of(request), _object(body))
        except ProductInvalid as exc:
            raise _invalid(exc) from exc

    @router.get("/products/{product_id}")
    def get_product(product_id: str, request: Request) -> dict[str, Any]:
        try:
            return _store(request).get_product(product_id, workspace_of(request))
        except KeyError as exc:
            raise _not_found(exc) from exc

    @router.patch("/products/{product_id}")
    def update_product(product_id: str, request: Request, body: Any = Body(...)) -> dict[str, Any]:
        try:
            return _store(request).update_product(
                product_id, workspace_of(request), _object(body)
            )
        except KeyError as exc:
            raise _not_found(exc) from exc
        except ProductInvalid as exc:
            raise _invalid(exc) from exc
        except ProductConflict as exc:
            raise _conflict(exc) from exc

    @router.delete("/products/{product_id}")
    def delete_product(product_id: str, request: Request) -> dict[str, bool]:
        try:
            _store(request).delete_product(product_id, workspace_of(request))
        except KeyError as exc:
            raise _not_found(exc) from exc
        return {"deleted": True}

    # ── campaign links (S-12.01.02) ─────────────────────────────────────────

    @router.get("/products/{product_id}/campaigns")
    def product_campaigns(product_id: str, request: Request) -> dict[str, Any]:
        store, workspace = _store(request), workspace_of(request)
        try:
            store.get_product(product_id, workspace)
        except KeyError as exc:
            raise _not_found(exc) from exc
        return {
            "items": [
                _link_view(request, campaign_of, campaign_id)
                for campaign_id in store.linked_campaigns(product_id, workspace)
            ]
        }

    @router.put("/products/{product_id}/campaigns")
    def set_product_campaigns(
        product_id: str, request: Request, body: Any = Body(...)
    ) -> dict[str, Any]:
        ids = body.get("campaign_ids") if isinstance(body, dict) else None
        if not isinstance(ids, list) or not all(isinstance(item, str) for item in ids):
            raise HTTPException(
                422,
                detail={
                    "error": "invalid_links",
                    "message": "Send {\"campaign_ids\": [...]} — a list of campaign ids.",
                },
            )
        if len(ids) > MAX_LINKS:
            raise HTTPException(
                422,
                detail={
                    "error": "invalid_links",
                    "message": f"{len(ids)} campaigns is more than {MAX_LINKS} in one list.",
                },
            )
        for campaign_id in ids:
            try:
                campaign_of(request, campaign_id)
            except KeyError:
                raise HTTPException(
                    422,
                    detail={
                        "error": "unknown_campaign",
                        "message": f"There is no campaign {campaign_id!r}. Nothing was linked.",
                    },
                ) from None
        store, workspace = _store(request), workspace_of(request)
        try:
            linked = store.set_links(product_id, workspace, ids)
        except KeyError as exc:
            raise _not_found(exc) from exc
        return {"items": [_link_view(request, campaign_of, campaign_id) for campaign_id in linked]}

    # ── the strategy brain (S-12.02.01) ─────────────────────────────────────

    @router.get("/envelope")
    def envelope(request: Request) -> dict[str, Any]:
        """Capacity, vocabulary and defaults — what a plan will be fitted inside."""
        return service_of(request).describe()

    @router.post("/plans", status_code=201)
    def draft_plan(request: Request, body: Any = Body(...)) -> dict[str, Any]:
        if not isinstance(body, dict):
            raise _invalid_request(
                RequestInvalid("request", "A plan request must be an object of named fields.")
            )
        try:
            return service_of(request).draft_plan(body)
        except RequestInvalid as exc:
            raise _invalid_request(exc) from exc
        except KeyError as exc:
            raise _not_found(exc) from exc

    @router.get("/plans")
    def list_plans(request: Request, product_id: str = Query("", max_length=64)) -> dict[str, Any]:
        return {"items": service_of(request).list_plans(product_id=product_id)}

    @router.get("/plans/{plan_id}")
    def get_plan(plan_id: str, request: Request) -> dict[str, Any]:
        try:
            return service_of(request).get_plan(plan_id)
        except KeyError as exc:
            raise _not_found(exc) from exc

    @router.post("/plans/{plan_id}/apply")
    def apply_plan(plan_id: str, request: Request) -> dict[str, Any]:
        """The draft becomes paused campaigns. Nothing is imported, spent or sent."""
        try:
            return service_of(request).apply_plan(plan_id)
        except KeyError as exc:
            raise _not_found(exc) from exc
        except PlanStateError as exc:
            raise _wrong_state(exc) from exc

    @router.post("/plans/{plan_id}/discard")
    def discard_plan(plan_id: str, request: Request) -> dict[str, Any]:
        try:
            return service_of(request).discard_plan(plan_id)
        except KeyError as exc:
            raise _not_found(exc) from exc
        except PlanStateError as exc:
            raise _wrong_state(exc) from exc

    # ── review (S-12.02.03) ────────────────────────────────────────────────

    @router.post("/plans/{plan_id}/review", status_code=201)
    def review_plan(plan_id: str, request: Request, body: Any = Body(default=None)) -> dict[str, Any]:
        """Measure an applied plan and say, per channel, what is wrong. Changes nothing."""
        if body is not None and not isinstance(body, dict):
            raise _invalid_request(
                RequestInvalid("request", "A review request must be an object, such as {}.")
            )
        try:
            return service_of(request).review_plan(plan_id, body or {})
        except RequestInvalid as exc:
            raise _invalid_request(exc) from exc
        except KeyError as exc:
            raise _not_found(exc) from exc
        except PlanStateError as exc:
            raise _wrong_state(exc) from exc

    # ── revise (S-12.02.04) ────────────────────────────────────────────────

    @router.post("/plans/{plan_id}/revise", status_code=201)
    def revise_plan(plan_id: str, request: Request, body: Any = Body(default=None)) -> dict[str, Any]:
        """The next version of an applied plan, from its latest review. A draft: nothing changes yet."""
        if body is not None and not isinstance(body, dict):
            raise _invalid_request(
                RequestInvalid("request", "A revise request must be an object, such as {}.")
            )
        try:
            return service_of(request).revise_plan(plan_id, body or {})
        except RequestInvalid as exc:
            raise _invalid_request(exc) from exc
        except KeyError as exc:
            raise _not_found(exc) from exc
        except PlanStateError as exc:
            raise _wrong_state(exc) from exc

    return router
