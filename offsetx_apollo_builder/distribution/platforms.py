"""What each platform actually permits, and what off_CRM will not do.

The owner's brief for this campaign kind was to operate many accounts across
Instagram, Facebook, TikTok and YouTube. That is worth building, and most of the
difficulty is not code — it is that **each platform allows far less automated
posting than it looks like from the outside**, and the tools that appear to
offer more are the ones that get accounts banned.

So this module is a registry, in the same spirit as ``config/providers.yaml``
and the campaign-kind registry: a platform is a **declared thing** with stated
capabilities, stated preconditions and stated limits. A platform nobody has
described is not one off_CRM will post to.

---

**The rule.** off_CRM publishes through **official APIs only**.

Not because unofficial routes are hard — because they work until they do not,
and the failure mode is the owner's account, not an error message. Browser
automation, mobile-app endpoints and session-cookie replay all breach the terms
every one of these platforms publishes, and an account ban takes the audience
with it. That is a worse outcome than a feature that is honest about needing
setup.

The refusals are recorded per platform rather than assumed, so the answer to
"why can't it just post to my personal Instagram?" is in the product instead of
in a support conversation.

---

**On the quotas, which are the part that surprises people.**

They are small, and two of them are not per account:

- YouTube's Data API quota is **per project**, not per channel. An upload costs
  roughly 1,600 units against a default 10,000/day, so six uploads a day covers
  every channel you own until you apply for more.
- Instagram allows **25 API-published posts per account per 24 hours.**

A plan that assumes "many accounts" means "many times the throughput" is wrong
for YouTube and right for Instagram. The engine reads these numbers rather than
guessing, so a schedule that cannot be delivered is refused when it is made
instead of failing silently overnight.

---

**On watching competitors**, which the owner also asked for.

Scraping Instagram, TikTok or Facebook is against their terms, whatever the
tooling. What *is* permitted is narrower and worth knowing precisely: YouTube's
Data API serves public video and channel data under quota; Instagram's Business
Discovery returns limited public data for *business* accounts; TikTok's Research
API needs an approved application. Competitors' own websites, blogs and RSS
feeds are ordinary web pages and the discovery module's existing politeness
controls already cover them.

``reading`` below records which of those applies, so the trend side is built on
what each platform actually offers rather than on a scraper that works for a
month.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class PublishSupport(str, Enum):
    """How far off_CRM can publish to a platform today."""

    #: Fully supported through an official API.
    SUPPORTED = "supported"
    #: The API exists and off_CRM has no adapter for it yet.
    ADAPTER_MISSING = "adapter_missing"
    #: The API exists but restricts what an unapproved app may do.
    RESTRICTED = "restricted"
    #: No official route. off_CRM will not post here.
    UNAVAILABLE = "unavailable"


class ReadSupport(str, Enum):
    """How far competitor and analytics reading is permitted."""

    OFFICIAL_API = "official_api"
    LIMITED_OFFICIAL = "limited_official"
    APPROVAL_REQUIRED = "approval_required"
    NOT_PERMITTED = "not_permitted"


@dataclass(frozen=True)
class PlatformSpec:
    """One publishing destination, described honestly."""

    id: str
    label: str
    publish: PublishSupport
    read: ReadSupport
    #: The official interface, named so the owner can go and read it.
    api: str = ""
    #: What has to be true before a single post can go out.
    preconditions: tuple[str, ...] = ()
    #: Posts per account per day, 0 when the limit is not per account.
    daily_posts_per_account: int = 0
    #: Set when the real ceiling is shared across every account.
    shared_daily_budget: str = ""
    #: What off_CRM will not do here, and why.
    refuses: tuple[str, ...] = ()
    notes: str = ""

    @property
    def can_publish(self) -> bool:
        return self.publish is PublishSupport.SUPPORTED

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "label": self.label,
            "publish": self.publish.value,
            "read": self.read.value,
            "api": self.api,
            "preconditions": list(self.preconditions),
            "daily_posts_per_account": self.daily_posts_per_account,
            "shared_daily_budget": self.shared_daily_budget,
            "refuses": list(self.refuses),
            "notes": self.notes,
            "can_publish": self.can_publish,
        }


#: Refused everywhere, so the reason is stated once and applies to all.
UNIVERSAL_REFUSALS: tuple[str, ...] = (
    "Browser automation or headless-browser posting — breaches every platform's "
    "terms, and the failure mode is a banned account rather than an error.",
    "Mobile-app or other unofficial endpoints — they work until they do not, and "
    "they take the audience with them when they stop.",
    "Session-cookie or password reuse — off_CRM holds OAuth tokens for accounts "
    "you have connected, never credentials for accounts you have not.",
)

PLATFORMS: dict[str, PlatformSpec] = {
    "local_outbox": PlatformSpec(
        id="local_outbox",
        label="Local outbox",
        publish=PublishSupport.SUPPORTED,
        read=ReadSupport.OFFICIAL_API,
        api="none — writes to disk",
        notes=(
            "Posts are written to a folder instead of a platform. The same role "
            "LocalOutboxProvider plays for email: the whole pipeline runs, is "
            "reviewable and is testable without touching a real account."
        ),
    ),
    "youtube": PlatformSpec(
        id="youtube",
        label="YouTube",
        publish=PublishSupport.ADAPTER_MISSING,
        read=ReadSupport.OFFICIAL_API,
        api="YouTube Data API v3 (videos.insert) + YouTube Analytics API",
        preconditions=(
            "A Google Cloud project with the Data API enabled",
            "OAuth consent per channel you post to",
        ),
        shared_daily_budget=(
            "Quota is per API project, not per channel: an upload costs about "
            "1,600 units of a default 10,000/day, so roughly six uploads a day "
            "across every channel you own until you request more."
        ),
        notes=(
            "The most permissive of the four for reading — public video and "
            "channel data is available under the same quota, which makes it the "
            "sensible place to start on trends."
        ),
    ),
    "instagram": PlatformSpec(
        id="instagram",
        label="Instagram",
        publish=PublishSupport.ADAPTER_MISSING,
        read=ReadSupport.LIMITED_OFFICIAL,
        api="Instagram Content Publishing API",
        preconditions=(
            "A Business or Creator account — personal accounts cannot be posted "
            "to by any API, and no tool can change that",
            "A Meta app with the publishing permissions reviewed and approved",
            "OAuth per account",
        ),
        daily_posts_per_account=25,
        refuses=(
            "Posting to a personal account. There is no official route, and the "
            "unofficial ones are what get accounts banned.",
        ),
        notes=(
            "Competitor reading is Business Discovery only: limited public data "
            "about other *business* accounts. Not a general scraper, and the "
            "terms forbid building one."
        ),
    ),
    "facebook": PlatformSpec(
        id="facebook",
        label="Facebook Pages",
        publish=PublishSupport.ADAPTER_MISSING,
        read=ReadSupport.LIMITED_OFFICIAL,
        api="Facebook Pages API + Page Insights",
        preconditions=(
            "A Page, not a personal profile",
            "A reviewed Meta app with pages_manage_posts",
            "A Page access token per Page",
        ),
        notes="Analytics for your own Pages is well served; competitor data is not.",
    ),
    "tiktok": PlatformSpec(
        id="tiktok",
        label="TikTok",
        publish=PublishSupport.RESTRICTED,
        read=ReadSupport.APPROVAL_REQUIRED,
        api="TikTok Content Posting API",
        preconditions=(
            "A registered developer app",
            "Audit approval before posts can be public — until then an app may "
            "only post privately to the connecting account",
        ),
        refuses=(
            "Presenting private self-only posts as published. Until the app is "
            "audited that is all the API allows, and a campaign that counted "
            "them as reach would be lying to you.",
        ),
        notes="Competitor data needs the Research API, which is separately approved.",
    ),
    "linkedin": PlatformSpec(
        id="linkedin",
        label="LinkedIn",
        publish=PublishSupport.RESTRICTED,
        read=ReadSupport.APPROVAL_REQUIRED,
        api="LinkedIn Share on LinkedIn / Posts API",
        preconditions=("Partner-programme approval for most posting scopes",),
    ),
    "x": PlatformSpec(
        id="x",
        label="X",
        publish=PublishSupport.ADAPTER_MISSING,
        read=ReadSupport.APPROVAL_REQUIRED,
        api="X API v2",
        preconditions=("A paid tier — the free tier's write allowance is minimal",),
    ),
}


class UnknownPlatform(ValueError):
    """A platform nobody declared. Never assumed to be safe to post to."""


class PlatformNotPublishable(ValueError):
    """A declared platform off_CRM cannot publish to yet."""


def platform_spec(platform: str) -> PlatformSpec:
    key = str(platform or "").strip().lower()
    if key not in PLATFORMS:
        known = ", ".join(sorted(PLATFORMS))
        raise UnknownPlatform(f"Unknown platform {platform!r}. Known: {known}.")
    return PLATFORMS[key]


def assert_publishable(platform: str) -> PlatformSpec:
    """The gate on connecting an account or scheduling a post."""
    spec = platform_spec(platform)
    if spec.can_publish:
        return spec
    detail = {
        PublishSupport.ADAPTER_MISSING: (
            f"off_CRM has no {spec.label} adapter yet. The official route is "
            f"{spec.api}."
        ),
        PublishSupport.RESTRICTED: (
            f"{spec.label} restricts what an unapproved app may publish. "
            + "; ".join(spec.preconditions)
        ),
        PublishSupport.UNAVAILABLE: (
            f"{spec.label} offers no official publishing API, and off_CRM will "
            "not use an unofficial one."
        ),
    }[spec.publish]
    raise PlatformNotPublishable(
        f"{detail} Nothing was scheduled, because a post that cannot be "
        "delivered is worse than one that was never planned."
    )


def list_platforms() -> list[dict[str, Any]]:
    """Publishable first, then the rest alphabetically."""
    return [
        spec.to_dict()
        for spec in sorted(PLATFORMS.values(), key=lambda item: (not item.can_publish, item.id))
    ]


def publishable_platforms() -> tuple[str, ...]:
    return tuple(sorted(spec.id for spec in PLATFORMS.values() if spec.can_publish))
