"""Research-notebook export (§4G).

You point a research notebook — NotebookLM, or anything like it — at what a
campaign has learned, and ask it questions. This module builds the sources.

---

**The honest shape of it.**

NotebookLM has no public write API. There is no endpoint to push a source to,
no token to store, no integration to authorise. Anything claiming otherwise is
scraping a logged-in session, which breaks the moment Google changes a button.

So what this produces is a **bundle**: a folder of Markdown files that you
upload once, by hand. That is a smaller feature than "connect your notebook",
and it is the one that actually works. The same bundle uploads to a Claude
Project, a ChatGPT Project, Gemini, or a notebook you host yourself — nothing
in it is NotebookLM-shaped.

---

**Why this is an egress path, not a file writer.**

The governing rule of this system is *models never pull, off_CRM pushes*. An
export that you drag into NotebookLM is a push. The only difference is that the
transport is a person instead of an HTTP request, and the rules do not care
about transport.

So the bundle is built the way a payload is built:

- **From an allowlist.** Sections are declared, each naming the data class it
  carries. Nothing is copied out of the database and then trimmed.
- **Against a destination tier.** NotebookLM's free tier is Google, and Google
  sits at tier C in this system because its free-tier terms permit training on
  submitted content (BUILD_STATE §5.3). Tier C reaches ``pseudonymous``, so the
  people in the bundle arrive as ``PERSON_3`` and ``COMPANY_3``, and the
  campaign's own material does not go at all.
- **Scanned before anything is written.** A finding blocks the whole export and
  raises. Nothing is redacted, for the reason the scanner already documents: a
  hit means the builder has a bug, and cleaning it up silently hides the bug.
- **With the withholding shown, not silent.** Every section that did not make it
  is listed in the README and the manifest, with the reason and the fix.

**Mailbox content is never exported at any tier, under any policy, with any
override.** Replies are counted; reply text is not written. There is no flag for
it here — the way to send mailbox content somewhere is the mailbox unlock in
``ai/tiers.py``, and a folder on disk is not a provider you can unlock.

---

**Why it does not assume email.**

Email is one campaign kind and there are more coming (see
``docs/architecture/CAMPAIGN_TYPES.md``). Sections declare which kinds they
apply to; the email-specific ones — reply rates, follow-up stages, template
copy — sit behind that declaration rather than in the shared path. An image or
distribution campaign gets the universal sections and a stated reason for the
rest, with no code change here.

``campaigns`` has no ``kind`` column yet, so :func:`campaign_kind` reads one and
falls back to ``email``. When the column lands, this file does not change.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping, Sequence

from .campaigns import DEFAULT_KIND as DEFAULT_CAMPAIGN_KIND
from .campaigns import coerce_kind
from .ai.payload import (
    COMPANY_TOKEN,
    PERSON_TOKEN,
    PersonPublic,
    scrub_identity,
    tokenise_addresses,
)
from .ai.scanner import ScanReport, scan_payload
from .ai.tiers import (
    DataClass,
    DataPolicy,
    TrustTier,
    coerce_tier,
    policy_ceiling_for_tier,
    tier_permits_class,
)

#: The folder inside the output directory that gets uploaded. Everything the
#: destination must never see lives beside it, not in it.
BUNDLE_DIRNAME = "bundle"

#: Maps ``PERSON_3`` back to a real person. Written **outside** the bundle
#: directory on purpose: a file inside it will eventually get uploaded with the
#: rest, whatever the filename warns.
KEY_FILENAME = "identity-key.json"


class NotebookExportError(RuntimeError):
    """Configuration or input problem. Nothing was written."""


class NotebookExportBlocked(NotebookExportError):
    """The pre-flight scan found something. Nothing was written.

    Carries the report so the caller can show what was found and where, the same
    way the broker does when a payload is refused.
    """

    def __init__(self, report: ScanReport) -> None:
        super().__init__(
            "The export was blocked before anything reached disk: "
            + report.summary()
        )
        self.report = report


# ─────────────────────────────────────────────────────────────────────────────
# Never exported
# ─────────────────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class NeverExported:
    """Something the bundle will not contain, at any tier.

    Present as data rather than as an absence so the README can list it. A
    limitation you can read is a design decision; one you have to infer is a
    bug waiting to be reported.
    """

    what: str
    why: str

    def to_dict(self) -> dict[str, str]:
        return {"what": self.what, "why": self.why}


NEVER_EXPORTED: tuple[NeverExported, ...] = (
    NeverExported(
        what="Reply text, and any received mail",
        why=(
            "Mailbox content is the one class no destination carries. Replies "
            "are counted so the numbers are right; the words are not written."
        ),
    ),
    NeverExported(
        what="Email addresses",
        why=(
            "A research notebook does not need them, and a folder of addresses "
            "is the single worst thing to hand to anyone. Addresses are "
            "tokenised out at every policy level including full."
        ),
    ),
    NeverExported(
        what="Credentials, provider keys and mail headers",
        why="Blocked at every level by the same scanner the broker uses.",
    ),
    NeverExported(
        what="Deal values, commission and pipeline stages",
        why=(
            "Revenue fields are internal to off_CRM. They are not part of what "
            "a notebook is being asked, and the scanner refuses them by name."
        ),
    ),
)


# ─────────────────────────────────────────────────────────────────────────────
# Destinations
# ─────────────────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class ExportTarget:
    """Where the bundle is going, and how far that place is trusted.

    A destination is a tier, exactly like a provider. The difference is only
    that you carry the payload there yourself.
    """

    id: str
    label: str
    tier: TrustTier
    why: str
    override_reason: str = ""

    @property
    def policy(self) -> DataPolicy:
        """The most this destination may receive.

        There is no requested-policy argument on an export. A provider call has
        a task that might genuinely need less than the ceiling; a notebook wants
        everything it is allowed, so the ceiling *is* the policy.
        """
        return policy_ceiling_for_tier(self.tier)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "label": self.label,
            "tier": self.tier.value,
            "tier_label": self.tier.label,
            "policy": self.policy.value,
            "policy_label": self.policy.label,
            "why": self.why,
            "override_reason": self.override_reason,
        }


BUILT_IN_TARGETS: dict[str, ExportTarget] = {
    "notebooklm": ExportTarget(
        id="notebooklm",
        label="Google NotebookLM (free)",
        tier=TrustTier.C,
        why=(
            "Google, at the free tier whose terms permit training on submitted "
            "content. Acceptable jurisdiction, unacceptable data terms, so it "
            "lands at C — the same demotion the provider registry applies."
        ),
    ),
    "hosted_notebook": ExportTarget(
        id="hosted_notebook",
        label="A hosted notebook on a paid, no-training agreement",
        tier=TrustTier.B,
        why=(
            "For a paid tier whose terms you have read and which excludes "
            "training on your content. off_CRM cannot verify your agreement, so "
            "this is your assertion, recorded as one."
        ),
    ),
    "self_hosted": ExportTarget(
        id="self_hosted",
        label="A notebook you host yourself",
        tier=TrustTier.A,
        why="The files stay on hardware you control. Nothing leaves.",
    ),
}


def list_targets() -> list[dict[str, Any]]:
    """The built-in destinations, ordered most restrictive first."""
    return [
        target.to_dict()
        for target in sorted(BUILT_IN_TARGETS.values(), key=lambda item: item.tier.rank)
    ]


def resolve_target(
    target_id: str,
    *,
    tier_override: object = None,
    override_reason: str = "",
) -> ExportTarget:
    """Look up a destination, optionally raising its tier with a written reason.

    The override exists for the same reason the ``full`` policy override does:
    the owner is allowed to decide, and the decision is recorded rather than
    silent. Raising a tier without a reason is refused — an unexplained
    override is indistinguishable from a mistake six months later.
    """
    key = str(target_id or "").strip().lower()
    if key not in BUILT_IN_TARGETS:
        known = ", ".join(sorted(BUILT_IN_TARGETS))
        raise NotebookExportError(
            f"Unknown export destination {target_id!r}. Known destinations: {known}."
        )
    target = BUILT_IN_TARGETS[key]
    if tier_override is None:
        return target

    # ``coerce_tier`` fails closed to D on nonsense, which is right for config
    # read at startup and wrong for an argument someone just typed: silently
    # exporting nothing because of a typo is not a helpful failure.
    if not isinstance(tier_override, TrustTier):
        text = str(tier_override or "").strip().upper()
        if text not in {item.value for item in TrustTier}:
            raise NotebookExportError(
                f"Unknown trust tier {tier_override!r}. Use one of A, B, C, D."
            )
    tier = coerce_tier(tier_override)
    if tier is target.tier:
        return target
    reason = str(override_reason or "").strip()
    if tier.rank > target.tier.rank and not reason:
        raise NotebookExportError(
            f"Raising {target.label} from tier {target.tier.value} to "
            f"{tier.value} needs a written reason. Say why this destination is "
            "more trustworthy than its default."
        )
    return ExportTarget(
        id=target.id,
        label=target.label,
        tier=tier,
        why=target.why,
        override_reason=reason,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Campaign kind
# ─────────────────────────────────────────────────────────────────────────────


def campaign_kind(campaign: Mapping[str, Any]) -> str:
    """What sort of campaign this is.

    Delegates to the registry so there is one definition of what a kind is. It
    was written before the ``kind`` column existed and needed no change when the
    column landed, which was the point of routing every reader through here.
    """
    return coerce_kind(campaign.get("kind"), default=DEFAULT_CAMPAIGN_KIND)


# ─────────────────────────────────────────────────────────────────────────────
# Sections
# ─────────────────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class SectionSpec:
    """One file in the bundle, and the conditions under which it exists.

    The conditions are declared here rather than checked inside the builders, so
    the gate can be evaluated — and shown to the owner — without building
    anything. That is what makes :meth:`NotebookExport.plan` possible.
    """

    id: str
    filename: str
    title: str
    data_class: DataClass
    minimum_policy: DataPolicy
    build: Callable[["_BundleContext"], str]
    #: Empty means every campaign kind. Non-empty restricts it.
    campaign_kinds: tuple[str, ...] = ()
    description: str = ""

    def applies_to_kind(self, kind: str) -> bool:
        return not self.campaign_kinds or kind in self.campaign_kinds


@dataclass(frozen=True)
class Withheld:
    """A section that did not make it, and what would let it through."""

    section: str
    title: str
    data_class: str
    reason: str
    fix: str = ""

    def to_dict(self) -> dict[str, str]:
        return {
            "section": self.section,
            "title": self.title,
            "data_class": self.data_class,
            "reason": self.reason,
            "fix": self.fix,
        }


# ─────────────────────────────────────────────────────────────────────────────
# People
# ─────────────────────────────────────────────────────────────────────────────

_PERSON_TOKEN_RE = re.compile(rf"\b{re.escape(PERSON_TOKEN)}\b")
_COMPANY_TOKEN_RE = re.compile(rf"\b{re.escape(COMPANY_TOKEN)}\b")


@dataclass(frozen=True)
class PersonView:
    """One person as the bundle will show them.

    Built by the same construction rule as a payload: named fields are copied
    across, so a new contacts column cannot appear in an export without someone
    editing this file.
    """

    token: str
    company_token: str
    name: str
    company: str
    title: str
    category: str
    route: str
    hook: str
    status: str
    variant: str
    sent_count: int
    replied: bool
    identified: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "token": self.token,
            "company_token": self.company_token,
            "name": self.name,
            "company": self.company,
            "title": self.title,
            "category": self.category,
            "route": self.route,
            "hook": self.hook,
            "status": self.status,
            "variant": self.variant,
            "sent_count": self.sent_count,
            "replied": self.replied,
        }


def _person_views(
    rows: Sequence[Mapping[str, Any]], policy: DataPolicy
) -> tuple[list[PersonView], dict[str, dict[str, str]]]:
    """Turn campaign-contact rows into export rows, plus the key to reverse it.

    Tokens are numbered per bundle, which is the only way a pseudonymous export
    stays useful: one shared ``PERSON_1`` for two hundred people is not an
    anonymised list, it is a list with the answers removed. Numbering is by
    position in this export and means nothing outside it — ``PERSON_3`` in
    Tuesday's bundle and ``PERSON_3`` in Friday's are not the same person unless
    the underlying order happens to match.
    """
    views: list[PersonView] = []
    key: dict[str, dict[str, str]] = {}
    identified = policy.rank >= DataPolicy.MINIMAL.rank

    for index, row in enumerate(rows, start=1):
        person = PersonPublic.from_contact(row)
        token = f"PERSON_{index}"
        company_token = f"COMPANY_{index}"

        def _free_text(value: object) -> str:
            text = tokenise_addresses(str(value or "").strip())
            if identified:
                return text
            text = scrub_identity(text, person)
            text = _PERSON_TOKEN_RE.sub(token, text)
            return _COMPANY_TOKEN_RE.sub(company_token, text)

        views.append(
            PersonView(
                token=token,
                company_token=company_token,
                name=person.full_name if identified else token,
                company=person.company if identified else company_token,
                title=person.title,
                category=person.category,
                route=person.route,
                hook=_free_text(person.public_hook),
                status=str(row.get("status") or "").strip(),
                variant=str(row.get("variant_id") or "").strip(),
                sent_count=int(row.get("sent_count") or 0),
                replied=str(row.get("status") or "").strip() == "replied",
                identified=identified,
            )
        )
        if not identified:
            key[token] = {
                "contact_id": str(row.get("contact_id") or ""),
                "full_name": person.full_name,
                "company": person.company,
                "company_token": company_token,
            }
    return views, key


# ─────────────────────────────────────────────────────────────────────────────
# Build context
# ─────────────────────────────────────────────────────────────────────────────


@dataclass
class _BundleContext:
    """Everything the section builders are allowed to read.

    Deliberately not the store. A builder that could reach the database could
    reach the mailbox tables; one that can only read this object cannot, and the
    fields here are the allowlist.
    """

    campaign_name: str
    campaign_kind: str
    campaign_status: str
    created_at: str
    target: ExportTarget
    policy: DataPolicy
    generated_at: str
    people: list[PersonView] = field(default_factory=list)
    contact_status: dict[str, int] = field(default_factory=dict)
    messages_by_stage: dict[str, int] = field(default_factory=dict)
    ab_rows: list[dict[str, Any]] = field(default_factory=list)
    templates: list[dict[str, Any]] = field(default_factory=list)
    scoreboard: list[dict[str, Any]] = field(default_factory=list)
    traffic: dict[str, Any] = field(default_factory=dict)
    memory: list[dict[str, Any]] = field(default_factory=list)
    withheld: list[Withheld] = field(default_factory=list)

    @property
    def named(self) -> bool:
        """Whether the campaign may be called by its name.

        A campaign name is usually the ICP written out — "Q3 Nordic fintech
        founders" says more about the business than the contact list does.
        """
        return self.policy.rank >= DataPolicy.MINIMAL.rank

    @property
    def campaign_label(self) -> str:
        return self.campaign_name if self.named else "CAMPAIGN_1"


def _table(headers: Sequence[str], rows: Iterable[Sequence[object]]) -> str:
    lines = [
        "| " + " | ".join(headers) + " |",
        "|" + "|".join("---" for _ in headers) + "|",
    ]
    empty = True
    for row in rows:
        empty = False
        lines.append("| " + " | ".join(_cell(value) for value in row) + " |")
    if empty:
        return "_Nothing recorded yet._"
    return "\n".join(lines)


def _cell(value: object) -> str:
    text = str(value if value is not None else "").replace("|", "\\|")
    return re.sub(r"\s+", " ", text).strip() or "—"


# ─────────────────────────────────────────────────────────────────────────────
# Section builders
# ─────────────────────────────────────────────────────────────────────────────


def _build_overview(ctx: _BundleContext) -> str:
    lines = [
        f"# {ctx.campaign_label} — overview",
        "",
        "This is an off_CRM export. It is a set of sources for a research "
        "notebook, not a database dump: it holds what this destination is "
        "permitted to receive and nothing else.",
        "",
        _table(
            ["Field", "Value"],
            [
                ("Campaign", ctx.campaign_label),
                ("Kind", ctx.campaign_kind),
                ("Status", ctx.campaign_status),
                ("Created", ctx.created_at),
                ("People", len(ctx.people)),
                ("Exported", ctx.generated_at),
                ("Destination", ctx.target.label),
                ("Trust tier", f"{ctx.target.tier.value} — {ctx.target.tier.label}"),
                ("Data policy", ctx.policy.value),
            ],
        ),
        "",
        "## What this destination may receive",
        "",
        ctx.policy.description,
        "",
    ]
    if not ctx.named:
        lines += [
            "The campaign's own name is withheld at this tier, because a "
            "campaign name is usually the ideal customer profile written out. "
            "It appears here as `CAMPAIGN_1`.",
            "",
        ]
    if ctx.target.override_reason:
        lines += [
            "## Recorded override",
            "",
            f"This destination was raised to tier {ctx.target.tier.value}. "
            f"Reason given: {ctx.target.override_reason}",
            "",
        ]
    return "\n".join(lines)


def _build_audience(ctx: _BundleContext) -> str:
    categories: dict[str, int] = {}
    routes: dict[str, int] = {}
    for person in ctx.people:
        categories[person.category or "uncategorised"] = (
            categories.get(person.category or "uncategorised", 0) + 1
        )
        routes[person.route or "unspecified"] = routes.get(person.route or "unspecified", 0) + 1

    return "\n".join(
        [
            "# Audience shape",
            "",
            "Counts only. Nobody is named in this file at any tier, which makes "
            "it the one section that survives every destination.",
            "",
            "## By category",
            "",
            _table(
                ["Category", "People"],
                sorted(categories.items(), key=lambda item: (-item[1], item[0])),
            ),
            "",
            "## By route",
            "",
            _table(
                ["Route", "People"],
                sorted(routes.items(), key=lambda item: (-item[1], item[0])),
            ),
            "",
            "## By status",
            "",
            _table(
                ["Status", "People"],
                sorted(ctx.contact_status.items(), key=lambda item: (-item[1], item[0])),
            ),
            "",
            "## Messages sent, by stage",
            "",
            _table(
                ["Stage", "Sent"],
                sorted(ctx.messages_by_stage.items(), key=lambda item: item[0]),
            ),
            "",
        ]
    )


def _build_people(ctx: _BundleContext) -> str:
    identified = ctx.policy.rank >= DataPolicy.MINIMAL.rank
    preface = (
        "Real names, because this destination is trusted with them."
        if identified
        else (
            "Names and companies are replaced by tokens. The tokens are numbered "
            "for this export only and mean nothing outside it. The file mapping "
            "them back to real people was written outside this folder and is not "
            "part of what you upload."
        )
    )
    return "\n".join(
        [
            "# People",
            "",
            preface,
            "",
            _table(
                ["Ref", "Name", "Company", "Title", "Category", "Status", "Variant", "Sent"],
                [
                    (
                        person.token,
                        person.name,
                        person.company,
                        person.title,
                        person.category,
                        person.status,
                        person.variant,
                        person.sent_count,
                    )
                    for person in ctx.people
                ],
            ),
            "",
            "## Public hooks",
            "",
            "The public, verifiable reason each person was approached.",
            "",
            _table(
                ["Ref", "Hook"],
                [(person.token, person.hook) for person in ctx.people if person.hook],
            ),
            "",
        ]
    )


def _build_outcomes(ctx: _BundleContext) -> str:
    rows = []
    for row in ctx.ab_rows:
        rows.append(
            (
                row.get("variant_id", ""),
                row.get("contacts", 0),
                row.get("initial_sent", 0),
                row.get("replies", 0),
                f"{row.get('reply_rate', 0.0)}%",
                f"{row.get('ci_low', 0.0)}–{row.get('ci_high', 0.0)}%",
                row.get("sample_status", ""),
            )
        )
    hypothesis = ""
    metric = "reply_rate"
    minimum = 0
    if ctx.ab_rows:
        hypothesis = str(ctx.ab_rows[0].get("hypothesis") or "")
        metric = str(ctx.ab_rows[0].get("primary_metric") or metric)
        minimum = int(ctx.ab_rows[0].get("minimum_sample") or 0)

    lines = [
        "# Outcomes by variant",
        "",
        f"Primary metric: **{metric}**.",
        "",
    ]
    if hypothesis:
        lines += [f"Hypothesis under test: {hypothesis}", ""]
    how_to_read = (
        "The interval matters more than the rate. Two variants at 3% and 5% "
        "over forty sends each are the same variant as far as the data is "
        "concerned — their intervals overlap almost completely."
    )
    if minimum:
        how_to_read += (
            f" A `collecting` sample has fewer than {minimum} initial sends and "
            "has not earned a conclusion yet."
        )

    lines += [
        _table(
            ["Variant", "People", "Initial sent", "Replies", "Rate", "95% interval", "Sample"],
            rows,
        ),
        "",
        "## How to read this",
        "",
        how_to_read,
        "",
        "Reply *text* is not in this bundle and never will be. These are counts.",
        "",
    ]
    return "\n".join(lines)


def _build_templates(ctx: _BundleContext) -> str:
    lines = [
        "# Templates",
        "",
        "The approved copy this campaign sent. This is the part a notebook can "
        "actually reason about — the numbers say which variant won, the text "
        "says what winning looked like.",
        "",
    ]
    if not ctx.templates:
        lines += ["_No templates recorded._", ""]
    for item in ctx.templates:
        lines += [
            f"## {item.get('name') or item.get('id') or 'Template'}",
            "",
            _table(
                ["Field", "Value"],
                [
                    ("Stage", item.get("stage", "")),
                    ("Route", item.get("route", "")),
                    ("Variant", item.get("variant_id", "")),
                    ("Tags", ", ".join(item.get("tags") or [])),
                ],
            ),
            "",
            f"**Subject:** {_cell(item.get('subject_template', ''))}",
            "",
            "```",
            str(item.get("body_template") or "").strip(),
            "```",
            "",
        ]
    return "\n".join(lines)


def _build_what_worked(ctx: _BundleContext) -> str:
    lines = [
        "# What worked",
        "",
        "off_CRM's own running record of template performance, and how it is "
        "currently dividing traffic between the variants you approved.",
        "",
        "## Scoreboard",
        "",
        _table(
            ["Template", "Variant", "Sends", "Replies", "Rate", "Enough data?", "Winner"],
            [
                (
                    row.get("label", ""),
                    row.get("variant_id", ""),
                    row.get("sends", 0),
                    row.get("replies", 0),
                    f"{row.get('reply_rate', 0.0)}%",
                    "yes" if row.get("judged") else "not yet",
                    "yes" if row.get("is_winner") else "",
                )
                for row in ctx.scoreboard
            ],
        ),
        "",
    ]
    arms = list(ctx.traffic.get("arms") or [])
    if arms:
        lines += [
            "## Traffic split for the next batch",
            "",
            _table(
                ["Variant", "Share", "P(best)", "Sends", "Replies"],
                [
                    (
                        arm.get("label") or arm.get("arm_id", ""),
                        f"{round(float(arm.get('share', 0.0)) * 100, 1)}%",
                        f"{round(float(arm.get('probability_best', 0.0)) * 100, 1)}%",
                        arm.get("sends", 0),
                        arm.get("replies", 0),
                    )
                    for arm in arms
                ],
            ),
            "",
            str(ctx.traffic.get("verdict") or ""),
            "",
            "Shares are allocated by Thompson sampling, so a variant that is "
            "probably better gets more traffic while it is still being proven, "
            "rather than after. Deciding *how much* is automatic; deciding "
            "*whether* a new variant goes live stays with you.",
            "",
        ]
    return "\n".join(lines)


def _build_notes(ctx: _BundleContext) -> str:
    return "\n".join(
        [
            "# Notes you approved",
            "",
            "Facts off_CRM has been told or has learned and you have approved. "
            "Unapproved items are not exported — an unreviewed guess becomes a "
            "fact the moment a notebook cites it.",
            "",
            _table(
                ["Kind", "Note", "Confidence", "Tags"],
                [
                    (
                        item.get("kind", ""),
                        item.get("content", ""),
                        item.get("confidence", ""),
                        ", ".join(item.get("tags") or []),
                    )
                    for item in ctx.memory
                ],
            ),
            "",
        ]
    )


SECTIONS: tuple[SectionSpec, ...] = (
    SectionSpec(
        id="overview",
        filename="00-overview.md",
        title="Overview",
        data_class=DataClass.PUBLIC,
        minimum_policy=DataPolicy.STRICT,
        build=_build_overview,
        description="What this bundle is, and the rules it was built under.",
    ),
    SectionSpec(
        id="audience",
        filename="10-audience.md",
        title="Audience shape",
        data_class=DataClass.PUBLIC,
        minimum_policy=DataPolicy.STRICT,
        build=_build_audience,
        description="Counts by category, route and status. Nobody named.",
    ),
    SectionSpec(
        id="people",
        filename="20-people.md",
        title="People",
        data_class=DataClass.PERSON_PUBLIC,
        minimum_policy=DataPolicy.PSEUDONYMOUS,
        build=_build_people,
        description="One row per person, tokenised below minimal policy.",
    ),
    SectionSpec(
        id="outcomes",
        filename="30-outcomes.md",
        title="Outcomes by variant",
        data_class=DataClass.CAMPAIGN,
        minimum_policy=DataPolicy.PSEUDONYMOUS,
        build=_build_outcomes,
        campaign_kinds=("email",),
        description="Reply rates and intervals per variant.",
    ),
    SectionSpec(
        id="what_worked",
        filename="40-what-worked.md",
        title="What worked",
        data_class=DataClass.CAMPAIGN,
        minimum_policy=DataPolicy.PSEUDONYMOUS,
        build=_build_what_worked,
        description="The context layer's scoreboard and current traffic split.",
    ),
    SectionSpec(
        id="templates",
        filename="50-templates.md",
        title="Templates",
        data_class=DataClass.CAMPAIGN,
        minimum_policy=DataPolicy.STANDARD,
        build=_build_templates,
        campaign_kinds=("email",),
        description="The approved copy itself.",
    ),
    SectionSpec(
        id="notes",
        filename="60-notes.md",
        title="Notes you approved",
        data_class=DataClass.INTERNAL,
        minimum_policy=DataPolicy.STANDARD,
        build=_build_notes,
        description="Approved memory items.",
    ),
)


# ─────────────────────────────────────────────────────────────────────────────
# Plan and result
# ─────────────────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class ExportPlan:
    """What an export would contain, computed without building it."""

    campaign_id: str
    campaign_kind: str
    target: ExportTarget
    policy: DataPolicy
    included: tuple[str, ...]
    withheld: tuple[Withheld, ...]
    tokenised: bool

    def to_dict(self) -> dict[str, Any]:
        by_id = {spec.id: spec for spec in SECTIONS}
        return {
            "campaign_id": self.campaign_id,
            "campaign_kind": self.campaign_kind,
            "target": self.target.to_dict(),
            "policy": self.policy.value,
            "tokenised": self.tokenised,
            "included": [
                {
                    "section": section_id,
                    "title": by_id[section_id].title,
                    "filename": by_id[section_id].filename,
                    "data_class": by_id[section_id].data_class.value,
                    "description": by_id[section_id].description,
                }
                for section_id in self.included
            ],
            "withheld": [item.to_dict() for item in self.withheld],
            "never_exported": [item.to_dict() for item in NEVER_EXPORTED],
        }


@dataclass(frozen=True)
class BundleFile:
    """One written file, with a digest so the manifest can be checked."""

    name: str
    bytes: int
    sha256: str

    def to_dict(self) -> dict[str, Any]:
        return {"name": self.name, "bytes": self.bytes, "sha256": self.sha256}


@dataclass(frozen=True)
class RenderedBundle:
    """A complete bundle held in memory, already scanned and not yet written."""

    plan: ExportPlan
    files: dict[str, str]
    identity_key: dict[str, dict[str, str]]
    scan: ScanReport


@dataclass(frozen=True)
class ExportResult:
    """Where the bundle landed and what is in it."""

    bundle_dir: Path
    key_path: Path | None
    files: tuple[BundleFile, ...]
    plan: ExportPlan
    scan: ScanReport

    def to_dict(self) -> dict[str, Any]:
        return {
            "bundle_dir": str(self.bundle_dir),
            "key_path": str(self.key_path) if self.key_path else "",
            "files": [item.to_dict() for item in self.files],
            "plan": self.plan.to_dict(),
            "scan": self.scan.to_dict(),
        }


# ─────────────────────────────────────────────────────────────────────────────
# The exporter
# ─────────────────────────────────────────────────────────────────────────────


class NotebookExport:
    """Builds a research-notebook bundle from a campaign.

    Takes the store rather than a path so the caller owns the connection, and
    an optional context layer — a workspace that has never run the AI layer
    still exports, it just has no scoreboard to show.
    """

    def __init__(
        self,
        store: Any,
        *,
        context: Any = None,
        workspace_id: str = "local",
        owner_domains: Iterable[str] = (),
        owner_addresses: Iterable[str] = (),
        max_people: int = 5000,
    ) -> None:
        self.store = store
        self.context = context
        self.workspace_id = workspace_id
        self.owner_domains = tuple(owner_domains)
        self.owner_addresses = tuple(owner_addresses)
        self.max_people = max(1, int(max_people))

    # ── planning ────────────────────────────────────────────────────────────

    def plan(self, campaign_id: str, target: ExportTarget) -> ExportPlan:
        """Decide which sections survive this destination. Reads nothing heavy."""
        campaign = self.store.get_campaign(campaign_id)
        kind = campaign_kind(campaign)
        policy = target.policy
        included: list[str] = []
        withheld: list[Withheld] = []

        for spec in SECTIONS:
            reason, fix = self._gate(spec, kind, target, policy)
            if reason:
                withheld.append(
                    Withheld(
                        section=spec.id,
                        title=spec.title,
                        data_class=spec.data_class.value,
                        reason=reason,
                        fix=fix,
                    )
                )
            else:
                included.append(spec.id)

        return ExportPlan(
            campaign_id=str(campaign_id),
            campaign_kind=kind,
            target=target,
            policy=policy,
            included=tuple(included),
            withheld=tuple(withheld),
            tokenised=policy.rank < DataPolicy.MINIMAL.rank,
        )

    @staticmethod
    def _gate(
        spec: SectionSpec, kind: str, target: ExportTarget, policy: DataPolicy
    ) -> tuple[str, str]:
        """Why this section is refused, and what would let it through.

        Order matters: the campaign-kind check runs first because "this section
        is about email and your campaign is not" is a clearer answer than a tier
        rule the owner could act on but should not.
        """
        if not spec.applies_to_kind(kind):
            kinds = ", ".join(spec.campaign_kinds)
            return (
                f"This section only applies to {kinds} campaigns, and this "
                f"campaign is {kind}.",
                "",
            )
        # Mailbox has no section, so this is a guard against a future one being
        # added without noticing that a folder cannot be unlocked.
        if spec.data_class is DataClass.MAILBOX:
            return (
                "Mailbox content is never exported, at any tier.",
                "There is no fix. Mailbox content does not leave off_CRM this way.",
            )
        if not tier_permits_class(target.tier, spec.data_class):
            return (
                f"A tier {target.tier.value} destination does not receive: "
                f"{spec.data_class.label}.",
                f"Export to a destination trusted at the tier that carries "
                f"{spec.data_class.value}, or record an override with a reason.",
            )
        if policy.rank < spec.minimum_policy.rank:
            return (
                f"This section needs the {spec.minimum_policy.value} policy and "
                f"this destination reaches {policy.value}.",
                "A more trusted destination reaches a higher policy.",
            )
        return ("", "")

    # ── building ────────────────────────────────────────────────────────────

    def render(self, campaign_id: str, target: ExportTarget) -> RenderedBundle:
        """Build every file in memory and scan it. Writes nothing.

        Separated from :meth:`export` so the scan runs before the first byte
        reaches disk — a blocked export must leave no partial folder behind for
        someone to upload by mistake.
        """
        plan = self.plan(campaign_id, target)
        ctx, key = self._context_for(campaign_id, plan)

        files: dict[str, str] = {}
        for spec in SECTIONS:
            if spec.id in plan.included:
                files[spec.filename] = spec.build(ctx).rstrip() + "\n"

        files["README.md"] = _build_readme(ctx, plan)

        report = scan_payload(
            {"bundle": dict(files)},
            policy=plan.policy,
            owner_domains=self.owner_domains,
            owner_addresses=self.owner_addresses,
            allow_addresses=False,
        )
        if not report.clean:
            raise NotebookExportBlocked(report)

        # The manifest is built last and is not scanned, because it contains
        # only digests of files that already passed.
        files["MANIFEST.json"] = _build_manifest(ctx, plan, files)

        return RenderedBundle(
            plan=plan,
            files=files,
            identity_key=key if plan.tokenised else {},
            scan=report,
        )

    def export(
        self, campaign_id: str, target: ExportTarget, out_dir: Path | str
    ) -> ExportResult:
        """Write the bundle. Refuses to write into a directory that has content.

        Overwriting an export is how you end up uploading yesterday's people
        list believing it is today's, so the caller picks a new directory or
        clears the old one deliberately.
        """
        rendered = self.render(campaign_id, target)
        plan, files, key = rendered.plan, rendered.files, rendered.identity_key

        root = Path(out_dir)
        if root.exists() and any(root.iterdir()):
            raise NotebookExportError(
                f"{root} is not empty. Choose an empty directory so an old "
                "bundle is never half-replaced by a new one."
            )
        bundle = root / BUNDLE_DIRNAME
        bundle.mkdir(parents=True, exist_ok=True)

        written: list[BundleFile] = []
        for name in sorted(files):
            text = files[name]
            path = bundle / name
            data = text.encode("utf-8")
            path.write_bytes(data)
            written.append(
                BundleFile(
                    name=name,
                    bytes=len(data),
                    sha256=hashlib.sha256(data).hexdigest(),
                )
            )

        key_path: Path | None = None
        if key:
            key_path = root / KEY_FILENAME
            key_path.write_text(
                json.dumps(
                    {
                        "campaign_id": plan.campaign_id,
                        "generated_at": _now(),
                        "note": (
                            "Maps the tokens in the bundle back to real people. "
                            "This file is outside the bundle folder on purpose. "
                            "Do not upload it."
                        ),
                        "people": key,
                    },
                    indent=2,
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            try:
                os.chmod(key_path, 0o600)
            except OSError:
                pass

        return ExportResult(
            bundle_dir=bundle,
            key_path=key_path,
            files=tuple(written),
            plan=plan,
            scan=rendered.scan,
        )

    # ── reading ─────────────────────────────────────────────────────────────

    def _context_for(
        self, campaign_id: str, plan: ExportPlan
    ) -> tuple[_BundleContext, dict[str, dict[str, str]]]:
        """Read only what the surviving sections need.

        A withheld section costs nothing to withhold: its data is never fetched,
        so a tier C export does not load the template bodies into memory before
        deciding not to send them.
        """
        summary = self.store.campaign_summary(campaign_id)
        campaign = summary.get("campaign") or {}

        ctx = _BundleContext(
            campaign_name=str(campaign.get("name") or ""),
            campaign_kind=plan.campaign_kind,
            campaign_status=str(campaign.get("status") or ""),
            created_at=str(campaign.get("created_at") or ""),
            target=plan.target,
            policy=plan.policy,
            generated_at=_now(),
            contact_status=dict(summary.get("contact_status") or {}),
            messages_by_stage=dict(summary.get("messages_by_stage") or {}),
            withheld=list(plan.withheld),
        )

        rows, _ = self.store.list_campaign_contacts(campaign_id, limit=self.max_people)
        views, key = _person_views(rows, plan.policy)
        ctx.people = views

        if "outcomes" in plan.included:
            ctx.ab_rows = list(self.store.ab_report(campaign_id))
        if "templates" in plan.included:
            templates, _ = self.store.list_templates(limit=200, active_only=True)
            ctx.templates = list(templates)
        if "what_worked" in plan.included and self.context is not None:
            ctx.scoreboard = [
                score.to_dict() for score in self.context.scoreboard(self.workspace_id)
            ]
            ctx.traffic = self.context.traffic_split(self.workspace_id, seed=0)
        if "notes" in plan.included:
            memory, _ = self.store.search_memory_items(
                approved_only=True, workspace_id=self.workspace_id, limit=200
            )
            ctx.memory = list(memory)
        return ctx, key


# ─────────────────────────────────────────────────────────────────────────────
# README and manifest
# ─────────────────────────────────────────────────────────────────────────────


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _build_readme(ctx: _BundleContext, plan: ExportPlan) -> str:
    lines = [
        f"# {ctx.campaign_label} — notebook sources",
        "",
        f"Exported {ctx.generated_at} for **{ctx.target.label}** "
        f"(trust tier {ctx.target.tier.value}, policy `{plan.policy.value}`).",
        "",
        "## How to use it",
        "",
        "Upload every `.md` file in this folder as sources. `MANIFEST.json` is "
        "for checking the bundle, not for uploading — it holds a digest of each "
        "file so you can confirm nothing changed on the way.",
        "",
        "Then ask the notebook questions. It will answer from these files and "
        "nothing else, which is the point: the answers stay inside what you "
        "chose to send.",
        "",
        "## What is in it",
        "",
        _table(
            ["File", "Section", "Carries"],
            [
                (
                    spec.filename,
                    spec.title,
                    spec.data_class.label,
                )
                for spec in SECTIONS
                if spec.id in plan.included
            ],
        ),
        "",
        "## What was held back",
        "",
    ]
    if plan.withheld:
        lines += [
            _table(
                ["Section", "Why", "What would change it"],
                [
                    (item.title, item.reason, item.fix or "—")
                    for item in plan.withheld
                ],
            ),
            "",
        ]
    else:
        lines += [
            "Nothing was held back by the destination's tier — this "
            "destination is trusted with every section.",
            "",
        ]
    lines += [
        "## Never exported, to anywhere",
        "",
        _table(
            ["What", "Why"],
            [(item.what, item.why) for item in NEVER_EXPORTED],
        ),
        "",
    ]
    if plan.tokenised:
        lines += [
            "## About the tokens",
            "",
            "People and companies appear as `PERSON_1`, `COMPANY_1` and so on. "
            "The numbering is per export and carries no meaning between "
            "exports. The file that maps them back to real people was written "
            "**outside this folder** so it cannot be uploaded by selecting "
            "everything.",
            "",
        ]
    lines += [
        "## Provenance",
        "",
        "Generated by off_CRM. No AI model was involved in producing this "
        "bundle — it is read from your own database and formatted. Whatever "
        "the notebook says about it afterwards is the notebook's, not off_CRM's.",
        "",
    ]
    return "\n".join(lines)


def _build_manifest(ctx: _BundleContext, plan: ExportPlan, files: Mapping[str, str]) -> str:
    entries = []
    for name in sorted(files):
        data = files[name].encode("utf-8")
        entries.append(
            {
                "name": name,
                "bytes": len(data),
                "sha256": hashlib.sha256(data).hexdigest(),
            }
        )
    payload = {
        "generated_at": ctx.generated_at,
        "generator": "off_CRM notebook export",
        "campaign": {
            "id": plan.campaign_id,
            "kind": plan.campaign_kind,
            "label": ctx.campaign_label,
            "named": ctx.named,
            "people": len(ctx.people),
        },
        "destination": plan.target.to_dict(),
        "policy": plan.policy.value,
        "tokenised": plan.tokenised,
        "sections": plan.to_dict()["included"],
        "withheld": [item.to_dict() for item in plan.withheld],
        "never_exported": [item.to_dict() for item in NEVER_EXPORTED],
        "files": entries,
    }
    return json.dumps(payload, indent=2, ensure_ascii=False) + "\n"
