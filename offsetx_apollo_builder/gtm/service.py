"""GtmService — the one stateful orchestrator of the GTM engine.

Everything it needs from the rest of off_CRM arrives as a callable the API
builds per request: the sending identities, the connected social accounts,
whether Apollo is set up, and ``ask`` — the one model call. It reads no table it
does not own (the seam rule, ``GTM_ENGINE.md`` §3), which is what lets the tests
drive it with plain functions and what would let it be lifted out later.
"""

from __future__ import annotations

from contextlib import AbstractContextManager
from datetime import date, timedelta
from typing import Any, Callable, Mapping, Sequence

from .. import campaigns
from .store import GtmStore, PlanStateError
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

#: The CRM's own ceiling on a campaign's daily limit (`api/schemas.py`
#: `CampaignCreate`). A plan across many mailboxes can exceed it; Apply caps
#: the campaign and says so rather than writing a row the API would refuse.
CAMPAIGN_DAILY_LIMIT = 500
CAMPAIGN_NAME_LIMIT = 120


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
        create_campaign: Callable[..., str] | None = None,
        update_campaign: Callable[[str, dict[str, Any]], Any] | None = None,
        set_goal: Callable[..., Any] | None = None,
        goals_of: Callable[[str], Sequence[Mapping[str, Any]]] | None = None,
        lock: Callable[[str], AbstractContextManager[Any]] | None = None,
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
        #: Apply's hands on the CRM and the distribution store — the engine's
        #: own `create_campaign` and the store's `update_campaign`, `set_goal`
        #: and `list_goals` — plus a per-key lock that refuses a second
        #: operation on the same plan while one is running.
        self.create_campaign = create_campaign
        self.update_campaign = update_campaign
        self.set_goal = set_goal
        self.goals_of = goals_of
        self.lock = lock

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

    # ── apply (S-12.02.02) ─────────────────────────────────────────────────

    def _apply_ready(self) -> None:
        missing = [
            name
            for name in ("create_campaign", "update_campaign", "set_goal", "goals_of", "lock")
            if getattr(self, name) is None
        ]
        if missing:
            raise RuntimeError(f"Apply is not wired: {', '.join(missing)} missing.")

    def apply_plan(self, plan_id: str) -> dict[str, Any]:
        """A draft becomes paused campaigns. Nothing is imported, spent or sent.

        The campaigns live in the CRM store and the links here, and the two
        cannot share a transaction. So Apply is **idempotent per channel**: a
        channel whose campaign already exists for this plan's line is updated,
        not created again, and the plan becomes ``applied`` only once every
        channel is done. A half-finished apply is resumed by applying again.
        The lock refuses a second apply of the same plan while one runs.
        """
        self._apply_ready()
        with self.lock(f"gtm-plan:{plan_id}"):
            plan = self.store.get_plan(plan_id, self.workspace_id)
            if plan["status"] != "draft":
                raise PlanStateError(
                    f"This plan is {plan['status']}, so it cannot be applied. Only a draft can."
                )
            try:
                self.store.get_product(plan["product_id"], self.workspace_id)
            except KeyError:
                raise PlanStateError(
                    "The product this plan was written for has been deleted, so its "
                    "campaigns would speak for nothing. Draft a new plan for a product "
                    "that exists."
                ) from None
            product = plan["product_snapshot"]
            request = plan["request"]
            existing = self.store.line_links(plan["root_id"], self.workspace_id)
            notes: list[str] = []
            created: list[dict[str, Any]] = []
            for channel in plan["plan"]["channels"]:
                created.append(self._apply_channel(plan, product, request, channel, existing, notes))
            # A revision that dropped a channel pauses its campaign, never deletes it.
            kept = {item["kind"] for item in plan["plan"]["channels"]}
            for kind, campaign_id in existing.items():
                if kind not in kept:
                    self.update_campaign(campaign_id, {"status": "paused"})
                    notes.append(f"This version has no {kind} channel, so its campaign was paused.")
            self.store.move_plan(plan_id, self.workspace_id, allowed_from=("draft",), to="applied")
            if plan["parent_id"]:
                self._supersede_earlier(plan)
        return {
            "plan": self.get_plan(plan_id),
            "campaigns": created,
            "next_steps": _next_steps(plan),
            "notes": notes,
        }

    def _apply_channel(
        self,
        plan: Mapping[str, Any],
        product: Mapping[str, Any],
        request: Mapping[str, Any],
        channel: Mapping[str, Any],
        existing: Mapping[str, str],
        notes: list[str],
    ) -> dict[str, Any]:
        kind = str(channel["kind"])
        settings: dict[str, Any] = {}
        if kind == "email":
            volume = int(channel.get("daily_volume") or 1)
            if volume > CAMPAIGN_DAILY_LIMIT:
                notes.append(
                    f"The plan carries {volume} emails a day, but one campaign's limit is "
                    f"{CAMPAIGN_DAILY_LIMIT}; the email campaign was set to {CAMPAIGN_DAILY_LIMIT}."
                )
                volume = CAMPAIGN_DAILY_LIMIT
            window = channel.get("send_window") or ["09:00", "17:00"]
            settings = {
                "daily_send_limit": volume,
                "send_window_start": window[0],
                "send_window_end": window[1],
                "send_weekdays": [0, 1, 2, 3, 4] if channel.get("weekdays") != "all" else list(range(7)),
                "experiment_hypothesis": str(channel.get("hypothesis") or "")[:1000],
            }
            if channel.get("timezone"):
                settings["timezone"] = channel["timezone"]
        elif kind == "distribution":
            settings = {"daily_send_limit": max(1, min(int(channel.get("daily_volume") or 1),
                                                       CAMPAIGN_DAILY_LIMIT))}
        else:
            settings = {"daily_send_limit": 1}

        campaign_id = existing.get(kind, "")
        if campaign_id:
            self.update_campaign(campaign_id, dict(settings))
            action = "updated"
        else:
            name = f"{product.get('name', 'Product')} · {kind} · {request['goal_target']} {request['goal_kind']}"
            create = {
                "name": name[:CAMPAIGN_NAME_LIMIT],
                "kind": kind,
                "daily_send_limit": settings["daily_send_limit"],
                "approval_mode": "each_message",
            }
            if kind == "email":
                create.update(
                    send_window_start=settings["send_window_start"],
                    send_window_end=settings["send_window_end"],
                    send_weekdays=settings["send_weekdays"],
                    experiment_hypothesis=settings["experiment_hypothesis"],
                )
                if "timezone" in settings:
                    create["timezone_name"] = settings["timezone"]
            campaign_id = self.create_campaign(**create)
            # Linked straight away, so a failure after this point resumes
            # rather than making the campaign again.
            self.store.link_campaign(
                campaign_id, str(product["id"]), self.workspace_id,
                plan_id=str(plan["id"]), channel=kind,
            )
            action = "created"
        self.update_campaign(campaign_id, {"status": "paused"})
        if kind == "distribution" and request["goal_kind"] == "views":
            self._ensure_views_goal(plan, request, campaign_id)
        return {"kind": kind, "campaign_id": campaign_id, "action": action}

    def _ensure_views_goal(
        self, plan: Mapping[str, Any], request: Mapping[str, Any], campaign_id: str
    ) -> None:
        # Anchored on the day the goal was stated, so a revision (which carries
        # the remaining days) keeps the same deadline instead of pushing it out.
        deadline = (
            date.fromisoformat(str(plan["created_at"])[:10]) + timedelta(days=int(request["horizon_days"]))
        ).isoformat()
        target = int(request["goal_target"])
        goals = [goal for goal in self.goals_of(campaign_id) if goal.get("metric") == "views"]
        latest = goals[-1] if goals else None
        if latest and int(latest.get("target") or 0) == target and str(latest.get("deadline")) == deadline:
            return
        self.set_goal(campaign_id=campaign_id, metric="views", target=target, deadline=deadline)

    def _supersede_earlier(self, plan: Mapping[str, Any]) -> None:
        for other in self.store.list_plans(self.workspace_id, product_id=str(plan["product_id"])):
            if other["root_id"] == plan["root_id"] and other["id"] != plan["id"] and other["status"] == "applied":
                self.store.move_plan(other["id"], self.workspace_id, allowed_from=("applied",),
                                     to="superseded")


def _next_steps(plan: Mapping[str, Any]) -> list[dict[str, str]]:
    """What the owner does next, each on a screen that already does it."""
    kinds = {item["kind"] for item in plan["plan"]["channels"]}
    audience = plan["plan"]["audience"]
    envelope = plan["envelope"]
    steps: list[dict[str, str]] = []
    if "email" in kinds:
        who = audience.get("description") or "the audience in the plan"
        if audience.get("source") in ("apollo_search", "public_discovery"):
            steps.append({
                "page": "discovery",
                "label": "Find the people this plan is for",
                "why": f"Apply spends no credits and imports nobody. Look for: {who.rstrip('.')}.",
            })
        steps.append({
            "page": "contacts",
            "label": "Add contacts to the email campaign",
            "why": "The email campaign starts empty, so it cannot send to anyone yet.",
        })
        if not envelope.get("email_identities") or envelope.get("email_unverified"):
            steps.append({
                "page": "deliverability",
                "label": "Set up a sending identity that passes its checks",
                "why": "Preflight refuses mail from an identity without passing SPF, DKIM and DMARC.",
            })
        steps.append({
            "page": "drafts",
            "label": "Write and approve the drafts",
            "why": "Every email waits for your approval before it can send.",
        })
    if "distribution" in kinds:
        steps.append({
            "page": "posting",
            "label": "Connect an account and set its daily cap" if not envelope.get("platforms")
            else "Check each account's daily cap",
            "why": "Posts go out only through accounts you connected, never above your cap.",
        })
    if "image" in kinds:
        steps.append({
            "page": "imagereview",
            "label": "Keep or skip pictures as they arrive",
            "why": "Nothing is posted until you keep it.",
        })
    steps.append({
        "page": "campaigns",
        "label": "Resume each campaign when you are ready",
        "why": "Apply left every campaign paused, so nothing has sent.",
    })
    return steps

