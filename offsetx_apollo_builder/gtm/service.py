"""GtmService — the one stateful orchestrator of the GTM engine.

Everything it needs from the rest of off_CRM arrives as a callable the API
builds per request: the sending identities, the connected social accounts,
whether Apollo is set up, and ``ask`` — the one model call. It reads no table it
does not own (the seam rule, ``GTM_ENGINE.md`` §3), which is what lets the tests
drive it with plain functions and what would let it be lifted out later.
"""

from __future__ import annotations

from typing import Any, Callable, Mapping, Sequence

from .. import campaigns
from .store import GtmStore
from .strategy import (
    ASSUMED_REPLY_RATE,
    COLD_EMAILS_PER_IDENTITY_PER_DAY,
    Envelope,
    ModelUnavailable,
    ParsedPlan,
    PlanRefused,
    baseline_plan,
    build_prompt,
    envelope_from,
    feasibility,
    parse_plan,
    request_fields,
    validate_request,
    vocabulary,
)

#: Policies below `standard` do not carry campaign notes (`ai/payload.py`), so a
#: model answering under one saw the one-liner and nothing else of the product.
_THIN_POLICIES = frozenset({"strict", "pseudonymous", "minimal"})


class GtmService:
    def __init__(
        self,
        store: GtmStore,
        *,
        workspace_id: str,
        identities: Callable[[], Sequence[Mapping[str, Any]]],
        accounts: Callable[[], Sequence[Mapping[str, Any]]],
        apollo_ready: Callable[[], bool],
        ask: Callable[..., Any] | None = None,
    ) -> None:
        self.store = store
        self.workspace_id = workspace_id
        self.identities = identities
        self.accounts = accounts
        self.apollo_ready = apollo_ready
        #: ``ask(*, system_prompt, task_type, positioning_line, campaign_notes,
        #: instructions)`` -> a result with ``text``, ``provider_id``,
        #: ``model_id`` and ``policy``; raises ``ModelUnavailable`` when no
        #: permitted model can answer. ``None`` means rules only.
        self.ask = ask

    # ── capacity and vocabulary ─────────────────────────────────────────────

    def envelope(self, *, per_identity_cap: int = COLD_EMAILS_PER_IDENTITY_PER_DAY) -> Envelope:
        return envelope_from(
            identities=list(self.identities()),
            accounts=list(self.accounts()),
            apollo_ready=bool(self.apollo_ready()),
            per_identity_cap=per_identity_cap,
        )

    def describe(self) -> dict[str, Any]:
        """What the Strategy screen shows before a plan exists."""
        return {
            "envelope": self.envelope().to_dict(),
            "vocabulary": vocabulary(),
            "defaults": {
                "assumed_reply_rate": ASSUMED_REPLY_RATE,
                "per_identity_daily_cap": COLD_EMAILS_PER_IDENTITY_PER_DAY,
                "horizon_days": 30,
            },
        }

    # ── plans ───────────────────────────────────────────────────────────────

    def _with_staleness(self, plan: dict[str, Any]) -> dict[str, Any]:
        try:
            current = self.store.get_product(plan["product_id"], self.workspace_id)
            plan["product_stale"] = int(current["version"]) != int(plan["product_version"])
            plan["product_deleted"] = False
        except KeyError:
            plan["product_stale"] = True
            plan["product_deleted"] = True
        return plan

    def draft_plan(self, values: Mapping[str, Any]) -> dict[str, Any]:
        """A goal in, a stored draft plan out. Never a stack trace for "no model"."""
        request = validate_request(values, implemented=campaigns.implemented_kinds())
        product = self.store.get_product(request.product_id, self.workspace_id)
        envelope = self.envelope(per_identity_cap=request.per_identity_daily_cap)

        parsed: ParsedPlan | None = None
        fallback_reason = ""
        meta = {"provider_id": "", "model_id": "", "policy": ""}
        if not request.use_model:
            fallback_reason = "You asked for the rules-based plan."
        elif self.ask is None:
            fallback_reason = "No model is wired to this screen, so this is the rules-based plan."
        else:
            try:
                result = self.ask(
                    system_prompt=build_prompt(),
                    task_type="gtm_plan",
                    **request_fields(product, request, envelope),
                )
                parsed = parse_plan(
                    str(getattr(result, "text", "") or ""),
                    request=request,
                    envelope=envelope,
                    product=product,
                )
                meta = {
                    "provider_id": str(getattr(result, "provider_id", "") or ""),
                    "model_id": str(getattr(result, "model_id", "") or ""),
                    "policy": str(getattr(result, "policy", "") or ""),
                }
                if meta["policy"] in _THIN_POLICIES:
                    parsed.notes.insert(
                        0,
                        f"This plan was written by a model that saw only your one-liner, "
                        f"because the data policy for {meta['provider_id'] or 'that provider'} "
                        f"is {meta['policy']}. Raise it to standard in Connectors for a plan "
                        "written against the whole product.",
                    )
            except ModelUnavailable as exc:
                fallback_reason = f"No model could write this plan: {exc} This is the rules-based plan."
            except PlanRefused as exc:
                fallback_reason = f"The model's plan was refused: {exc} This is the rules-based plan."

        if parsed is None:
            parsed = baseline_plan(request=request, envelope=envelope, product=product)
            parsed.notes.insert(0, fallback_reason)

        stored = self.store.create_plan(
            self.workspace_id,
            product=product,
            request=request.to_dict(),
            envelope=envelope.to_dict(),
            plan=parsed.to_dict(),
            feasibility=feasibility(parsed, request),
            notes=parsed.notes,
            source=parsed.source,
            **meta,
        )
        return self._with_staleness(stored)

    def get_plan(self, plan_id: str) -> dict[str, Any]:
        return self._with_staleness(self.store.get_plan(plan_id, self.workspace_id))

    def list_plans(self, *, product_id: str = "") -> list[dict[str, Any]]:
        return [
            self._with_staleness(plan)
            for plan in self.store.list_plans(self.workspace_id, product_id=product_id)
        ]

    def discard_plan(self, plan_id: str) -> dict[str, Any]:
        self.store.move_plan(plan_id, self.workspace_id, allowed_from=("draft",), to="discarded")
        return self.get_plan(plan_id)
