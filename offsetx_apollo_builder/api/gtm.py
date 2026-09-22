"""HTTP surface for the GTM engine — epic E-12.

The contract is ``docs/architecture/GTM_ENGINE.md`` §9. Every refusal is
``{"error": code, "message": sentence}`` with 404, 409 or 422 — never a stack
trace, and never the app-wide ``ValueError`` handler's bare string, because the
product form needs to know *which field* to point at.
"""

from __future__ import annotations

from typing import Any, Callable

from fastapi import APIRouter, Body, HTTPException, Request

from ..gtm.products import ProductInvalid
from ..gtm.store import GtmStore, ProductConflict

#: How the router learns the workspace. Passed in rather than decided here, so
#: this surface follows whatever rule the rest of the API uses.
WorkspaceOf = Callable[[Request], str]


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


def _object(body: Any) -> dict[str, Any]:
    if not isinstance(body, dict):
        raise _invalid(ProductInvalid("product", "A product must be an object of named fields."))
    return body


def build_gtm_router(*, workspace_of: WorkspaceOf) -> APIRouter:
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

    return router
