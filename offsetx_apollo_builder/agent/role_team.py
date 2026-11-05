"""F-04.01.04: named agents are thin, audited adapters over existing engines.

No model-generated dispatch. A human selects one of five closed roles and an
action with typed input; workspace auth and the engines' own review gates remain
in charge. Draft != approved != published.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Mapping

from .companions import CompanionRegistry, CompanionError

ROLE_INSTRUCTIONS = {
    "Scout": (
        "Find public trends and cite sources. Do not log into a third-party "
        "site, fetch hidden customer data, or create a post."
    ),
    "Maker": (
        "Use the existing media director and assembler. Place every generated "
        "timeline into the owner review queue; never publish."
    ),
    "Poster": (
        "Prepare posts from owner-approved images using the existing draft "
        "pipeline. Do not approve, schedule or send them."
    ),
    "Analyst": (
        "Report measurable campaign totals, goals and post performance. "
        "Do not invent missing metrics or update the campaign."
    ),
    "Director": (
        "Draft a strategy for owner review using the existing GTM service. "
        "Do not apply, activate campaigns or start outreach."
    ),
}
ROLES = frozenset(ROLE_INSTRUCTIONS)


def provision_roles(
    registry: CompanionRegistry, *, workspace_id: str,
) -> list[dict[str, Any]]:
    """Owner-invoked, idempotent setup. Never replace a customized profile."""
    existing = {profile.name.casefold(): profile for profile in registry.list(workspace_id=workspace_id)}
    result = []
    for name, instructions in ROLE_INSTRUCTIONS.items():
        current = existing.get(name.casefold())
        if current is None:
            current = registry.create(
                workspace_id=workspace_id, name=name, instructions=instructions,
                granted_tool_ids=(),
            )
        result.append(current.to_dict())
    return result


@dataclass(frozen=True, slots=True)
class RoleEngines:
    trends: Any = None
    video: Any = None
    pipeline: Any = None
    distribution: Any = None
    gtm: Any = None


def execute_role(
    role: str, payload: Mapping[str, Any], *,
    engines: RoleEngines,
) -> dict[str, Any]:
    """Call existing engines only, with no separate implementation of their rules.

    The API authenticates and types values before reaching this function; this
    extra allow-list prevents accidental auto-publish in any direct caller.
    """
    if role not in ROLES:
        raise CompanionError("Unknown agent role")
    if not isinstance(payload, Mapping):
        raise CompanionError("Role parameters must be a mapping")

    campaign_id = str(payload.get("campaign_id") or "").strip()
    if role not in {"Scout", "Director"} and not campaign_id:
        raise CompanionError("Choose a campaign for this role")
    if role == "Scout":
        # Read-only observation, not crawl or image generation.
        topics = engines.trends.topics(window_hours=72, min_channels=3, limit=5)
        return {"role": role, "status": "observed", "topics": topics}
    if role == "Maker":
        topic = str(payload.get("topic") or "").strip()
        if not topic or len(topic) > 500:
            raise CompanionError("Give Maker a topic of 1-500 characters")
        project, report, direction = engines.video.direct_and_assemble(
            campaign_id, topic=topic,
        )
        # VideoEditorEngine.direct_and_assemble already queues the project for
        # owner review, as does the original video API.
        return {
            "role": role, "status": "needs_review",
            "project": project.to_dict(),
            "assembly": report.to_dict(),
            "direction": direction.to_dict(),
        }
    if role == "Poster":
        image_campaign_id = str(payload.get("image_campaign_id") or "").strip()
        account_ids = payload.get("account_ids") or []
        if not image_campaign_id or not account_ids:
            raise CompanionError("Select an image campaign and posting account")
        run = engines.pipeline.draft(
            distribution_campaign_id=campaign_id,
            image_campaign_id=image_campaign_id,
            account_ids=tuple(account_ids),
            limit=5,
        )
        return {"role": role, "status": "drafts_only", "drafts": run.to_dict()}
    if role == "Analyst":
        return {
            "role": role, "status": "read_only",
            "progress": engines.distribution.progress(campaign_id),
            "generator_performance": engines.distribution.generator_performance(campaign_id),
        }
    if role == "Director":
        values = payload.get("gtm_request")
        if not isinstance(values, dict):
            raise CompanionError("Director needs a validated GTM planning request")
        plan = engines.gtm.draft_plan(values)
        return {"role": role, "status": "draft_only", "plan": plan}
    raise CompanionError("Unknown agent role")
