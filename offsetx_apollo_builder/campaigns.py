"""Campaign kinds — what a campaign *is*, before anything decides how to run it.

Until now every campaign was an email campaign, and the schema said so: a
`campaigns` row is nothing but send limits, follow-up gaps, a send window and a
reply-rate metric. The product is a CRM with an AI layer that runs campaigns
itself, and email is one kind of several (see
``docs/architecture/CAMPAIGN_TYPES.md``). A table that can only describe email
blocks every other one.

This module is the registry. A kind is a **declared thing** with a name, a unit
of output and an owner, not a free-text string someone types into a column.

---

**On declaring kinds that do not work yet.**

``distribution`` is in the registry and marked ``implemented=False``. Nothing
runs it, and :func:`assert_runnable` refuses to create one. (``image`` was in
the same position until its runner was built.)

That refusal is the point. The failure mode of adding a ``kind`` column early is
a database full of campaigns no runner will ever pick up — rows that look alive
in a list, have contacts attached, and simply never send. A kind that is
declared but not implemented says so at creation time, in a sentence naming what
is missing, instead of failing silently for a week.

The alternative — leaving them out until they work — loses the thing worth
having, which is that ``kind`` means something checkable from the day it exists.

---

**On the settings blob.**

``CAMPAIGN_TYPES.md`` proposed ``kind`` plus a per-kind settings blob. Only the
column is here. Email's settings live in real columns that are validated and
indexed, and no other kind can be created yet, so a ``settings_json`` column
today would be an unvalidated blob with no writer — a dumping ground waiting to
be filled by whoever needs a field in a hurry.

Adding a column to SQLite is additive and costs exactly the same later as now.
The validator is the part that has to exist before the blob does, and it cannot
be written until there is a kind whose settings are known.

---

**The safety property this module exists to make testable.**

Each runner must only touch campaigns of its own kind. That is the real risk of
this column: without the check, ``run_due`` would happily try to send an image
campaign as mail. :func:`assert_kind` is the check, and both
``OutreachEngine`` and ``ImageCampaignEngine`` apply it at every entry point.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

#: What every existing row is, and what a row without a kind means. Chosen
#: rather than inferred: every campaign in every database predating this column
#: was an email campaign, because nothing else existed.
DEFAULT_KIND = "email"


class CampaignKindError(ValueError):
    """Base for every refusal in this module.

    A ``ValueError`` so the API's existing handler turns it into a 422 carrying
    the message, and a common base so callers that want to present these
    nicely — the CLI prints them without a traceback — can catch one thing.
    """


class UnknownCampaignKind(CampaignKindError):
    """A kind that is not in the registry. Never assumed to be safe."""


class CampaignKindNotImplemented(CampaignKindError):
    """A declared kind that nothing can run yet."""


class WrongCampaignKind(CampaignKindError):
    """A runner was handed a campaign belonging to a different kind."""


@dataclass(frozen=True)
class CampaignKindSpec:
    """One kind of campaign.

    ``implemented`` is the honest field. It is what stops the registry from
    becoming a list of promises.
    """

    id: str
    label: str
    #: What one unit of output is: an email, a picture, a post.
    unit: str
    #: The module that runs it, empty when nothing does.
    runner: str
    implemented: bool
    summary: str
    #: What is missing before it can run. Only meaningful when not implemented,
    #: and required in that case — "not implemented" without a next step is a
    #: shrug rather than an answer.
    missing: str = ""
    #: Whether the email-shaped columns on ``campaigns`` mean anything for it.
    uses_email_columns: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "label": self.label,
            "unit": self.unit,
            "runner": self.runner,
            "implemented": self.implemented,
            "summary": self.summary,
            "missing": self.missing,
            "uses_email_columns": self.uses_email_columns,
        }


KINDS: dict[str, CampaignKindSpec] = {
    "email": CampaignKindSpec(
        id="email",
        label="Email outreach",
        unit="an email",
        runner="offsetx_apollo_builder.outreach.engine.OutreachEngine",
        implemented=True,
        summary=(
            "A sequence of messages to a list of people, with follow-ups, a send "
            "window, approval before sending and reply rate as the metric."
        ),
        uses_email_columns=True,
    ),
    "image": CampaignKindSpec(
        id="image",
        label="Image and video",
        unit="a picture",
        runner="offsetx_apollo_builder.imagery.engine.ImageCampaignEngine",
        implemented=True,
        summary=(
            "Many generators, mostly free, orchestrated to beat what any single "
            "one produces. Deterministic gates first, then the owner's swipe as "
            "the quality label, then real engagement."
        ),
        missing=(
            # Kept although implemented, because it is the honest answer to "can
            # I do everything I described?". The timeline editor and the video
            # gates now exist (see docs/architecture/VIDEO_EDITOR.md), so what
            # remains is narrower than it was: nothing *generates* video, and
            # none of the AI editing features are wired. Publishing was always
            # the distribution campaign's job.
            "generated video — the editor cuts stills into a video and the gates "
            "read MP4 and WebM, but no generator produces footage or audio yet. "
            "Also missing: every AI editing feature (captions, cutout, reframe), "
            "and publishing, which is the distribution campaign."
        ),
    ),
    "distribution": CampaignKindSpec(
        id="distribution",
        label="Content distribution",
        unit="a post",
        runner="offsetx_apollo_builder.distribution.engine.DistributionEngine",
        implemented=True,
        summary=(
            "Watch competitors, find what is trending, produce content against "
            "it, publish across many accounts and learn from the analytics. "
            "Goal-shaped: 'reach a million views', not 'publish these posts'."
        ),
        missing=(
            # The runner, goals, scheduling and the analytics read-back exist.
            # What is genuinely absent is stated rather than implied, because the
            # gap here is external: each platform allows far less automated
            # posting than it appears to, and off_CRM publishes through official
            # APIs only. See distribution/platforms.py.
            "adapters for the real platforms — every one is declared with its "
            "official API, its preconditions and its quotas, and only the local "
            "outbox can publish today. Also missing: competitor watching and "
            "trend detection, which are limited by what each platform's terms "
            "actually permit."
        ),
    ),
}


def kind_spec(kind: str) -> CampaignKindSpec:
    """Look up a kind, refusing anything unlisted.

    Default-deny, for the same reason the provider registry refuses an unlisted
    provider: a kind nobody declared is a kind nobody wrote a runner for.
    """
    key = str(kind or "").strip().lower()
    if key not in KINDS:
        known = ", ".join(sorted(KINDS))
        raise UnknownCampaignKind(
            f"Unknown campaign kind {kind!r}. Known kinds: {known}."
        )
    return KINDS[key]


def coerce_kind(value: object, *, default: str = DEFAULT_KIND) -> str:
    """Read a kind off a database row.

    Falls back to the default for a missing or empty value, because rows written
    before the column existed are email campaigns. It does **not** fall back for
    a value that is present and unrecognised: that is corruption or a downgrade,
    and quietly calling it email would run the wrong sender over it.
    """
    if value is None:
        return default
    text = str(value).strip().lower()
    if not text:
        return default
    return kind_spec(text).id


def assert_runnable(kind: str) -> CampaignKindSpec:
    """The gate on creating a campaign of this kind."""
    spec = kind_spec(kind)
    if not spec.implemented:
        raise CampaignKindNotImplemented(
            f"{spec.label} campaigns are declared but not implemented yet. "
            f"Still missing: {spec.missing} "
            "Creating one now would put a row in the database that nothing "
            "will ever run."
        )
    return spec


def assert_kind(campaign: Mapping[str, Any], expected: str, *, action: str = "") -> str:
    """Refuse to let a runner act on a campaign belonging to another kind.

    This is the check that makes adding the column safe rather than merely
    tidy. Without it, the first image campaign ever created would be picked up
    by the email sender, which knows nothing about images and would try to post
    one to a mail server.
    """
    actual = coerce_kind(campaign.get("kind"))
    wanted = kind_spec(expected).id
    if actual == wanted:
        return actual
    what = f" {action}" if action else ""
    raise WrongCampaignKind(
        f"Campaign {campaign.get('id', '')!r} is a {kind_spec(actual).label} "
        f"campaign, and{what} is the {kind_spec(wanted).label} runner. "
        "Nothing was done."
    )


def list_kinds() -> list[dict[str, Any]]:
    """Implemented kinds first, then declared ones, each alphabetically."""
    return [
        spec.to_dict()
        for spec in sorted(KINDS.values(), key=lambda item: (not item.implemented, item.id))
    ]


def implemented_kinds() -> tuple[str, ...]:
    return tuple(sorted(spec.id for spec in KINDS.values() if spec.implemented))
