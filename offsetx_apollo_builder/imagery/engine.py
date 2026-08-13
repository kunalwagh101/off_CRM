"""The image campaign runner.

The second campaign kind. Email sends messages to people; this one produces
pictures against a brief and asks the owner to keep or discard each one.

```
brief  →  generate  →  deterministic gates  →  review queue  →  swipe
                              ↓ fail                              ↓
                         never shown                    generator score
                                                              ↓
                                                    who draws the next batch
```

**The swipe is the label.** This is the whole design, and the owner described it
without naming it: right to keep, left to discard, refresh to try again. Those
are quality judgements on a generator's work, collected free as a side effect of
ordinary use. They are to images exactly what reply rate is to email templates —
a real signal rather than a model's opinion of itself.

So a decision does two things: it settles the picture, and it scores the
generator that made it. After a few hundred swipes the scores are a benchmark of
the owner's own taste, and ``ai/bandit.py`` allocates the next batch towards
whoever is winning. The allocator does not know or care that its arms are image
models rather than email variants.

**What this does not do: publish.** An approved picture is an asset. Posting it
across accounts is the content-distribution campaign, which is not built. The
boundary is deliberate — publishing has its own credentials, its own per-platform
rules and its own failure modes, and folding it in here would make one module
responsible for two jobs that fail differently.

**Everything protective is inherited, not reimplemented.** Generation goes
through ``EgressBroker.call_image``, so an image prompt gets the same tier
filter, the same allowlist payload construction, the same blocking scanner and
the same egress log as any other call. A prompt naming a real person is person
data, and that was already true before this module existed.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from typing import Any, Sequence

from ..ai.bandit import Arm, allocate
from ..ai.payload import EgressRequest
from ..ai.tiers import DataClass
from ..campaigns import assert_kind
from .gates import GateReport, decode_data_uri, run_gates
from .store import ImageStore

#: How many candidates one round asks for per brief, unless told otherwise.
#: Small on purpose: every candidate costs a call, and the owner reviews them
#: one at a time.
DEFAULT_BATCH = 3

#: Candidates below this many decisions are not yet worth allocating on. Matches
#: the reasoning in ``ai/bandit.py``: a lopsided result from four swipes is
#: noise, and acting on it would starve a generator that has not had a chance.
MIN_DECISIONS_TO_JUDGE = 12


@dataclass
class GenerationRound:
    """What one call to :meth:`ImageCampaignEngine.generate` produced."""

    brief_id: str
    requested: int
    stored: int = 0
    gate_failed: int = 0
    call_failed: int = 0
    assets: list[str] = field(default_factory=list)
    failures: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "brief_id": self.brief_id,
            "requested": self.requested,
            "stored": self.stored,
            "gate_failed": self.gate_failed,
            "call_failed": self.call_failed,
            "assets": list(self.assets),
            "failures": list(self.failures),
        }


class ImageCampaignEngine:
    """Runs image campaigns: generate, gate, review, score.

    Takes the broker and the store rather than constructing them, so a test can
    drive it with a scripted generator and so the same protective path is used
    as everywhere else.
    """

    CAMPAIGN_KIND = "image"

    def __init__(
        self,
        *,
        store: ImageStore,
        broker: Any,
        settings_resolver: Any,
        campaign_reader: Any = None,
        workspace_id: str = "local",
    ) -> None:
        self.store = store
        self.broker = broker
        #: Called with a workspace id, returns ``WorkspaceEgressSettings``.
        self.settings_resolver = settings_resolver
        #: Optional callable returning a campaign row, so the kind can be
        #: checked. Without it the engine trusts its caller — which is why the
        #: API always passes one.
        self.campaign_reader = campaign_reader
        self.workspace_id = workspace_id
        self._lock = threading.RLock()

    # ── the kind gate ───────────────────────────────────────────────────────

    def _require_own_kind(self, campaign_id: str, action: str) -> None:
        """Refuse a campaign belonging to another runner.

        The mirror of ``OutreachEngine._require_own_kind``. Both runners now
        check, so neither can pick up the other's work — the email sender will
        not try to post a picture, and this will not try to draw an email.
        """
        if self.campaign_reader is None:
            return
        assert_kind(self.campaign_reader(campaign_id), self.CAMPAIGN_KIND, action=action)

    # ── briefs ──────────────────────────────────────────────────────────────

    def add_brief(
        self,
        campaign_id: str,
        *,
        brief: str,
        width: int = 0,
        height: int = 0,
        wanted: int = 1,
    ) -> str:
        self._require_own_kind(campaign_id, "adding a brief")
        return self.store.create_brief(
            campaign_id=campaign_id,
            brief=brief,
            width=width,
            height=height,
            wanted=wanted,
            workspace_id=self.workspace_id,
        )

    # ── generation ──────────────────────────────────────────────────────────

    def generate(
        self,
        brief_id: str,
        *,
        count: int = DEFAULT_BATCH,
        provider_id: str = "",
    ) -> GenerationRound:
        """Produce candidates for a brief, gate them, queue the survivors.

        One call per candidate rather than asking for ``n`` images at once: the
        allocator picks a generator per candidate, so a round can be split
        across models and the comparison stays honest.
        """
        brief = self.store.get_brief(brief_id)
        self._require_own_kind(str(brief["campaign_id"]), "generating images")

        settings = self.settings_resolver(self.workspace_id)
        wanted = max(1, int(count))
        result = GenerationRound(brief_id=brief_id, requested=wanted)
        seen = self.store.hashes_for_brief(brief_id)

        for _ in range(wanted):
            chosen = provider_id or self._next_generator()
            # Same shape the AI screen's image call uses, so both go through
            # one path. The brief is the instruction; it is text, so if it names
            # a real person the trust rules apply to it unchanged.
            request = EgressRequest(
                task_type="image_generation",
                data_class=DataClass.PUBLIC,
                instructions=str(brief["brief"]),
                task_tags=("image",),
            )
            try:
                with self._lock:
                    generated = self.broker.call_image(
                        request, settings, provider_id=chosen
                    )
            except Exception as exc:  # noqa: BLE001 - recorded, round continues
                result.call_failed += 1
                result.failures.append({"stage": "call", "detail": str(exc)[:300]})
                continue

            for image in generated.images:
                report = run_gates(
                    image,
                    want_width=int(brief["width"] or 0),
                    want_height=int(brief["height"] or 0),
                    seen_hashes=seen,
                )
                stored = self._store_candidate(brief, generated, image, report, seen)
                if stored is None:
                    result.gate_failed += 1
                    result.failures.append(
                        {"stage": "gate", "detail": report.summary()}
                    )
                else:
                    result.stored += 1
                    result.assets.append(stored)
        return result

    def _store_candidate(
        self,
        brief: dict[str, Any],
        generated: Any,
        image: str,
        report: GateReport,
        seen: set[str],
    ) -> str | None:
        """Write one candidate, whichever side of the gates it fell.

        A gate failure is stored rather than dropped. It never enters the review
        queue, but "this generator returns the wrong aspect ratio four times out
        of five" is exactly the kind of thing the owner should be able to see,
        and a discarded candidate cannot tell them.
        """
        try:
            _, payload = decode_data_uri(image)
        except Exception:  # noqa: BLE001 - a broken candidate is a failed gate
            self.store.record_gate_failure(
                provider_id=generated.provider_id,
                model_id=generated.model_id,
                workspace_id=self.workspace_id,
            )
            return None

        seen.add(report.sha256)
        status = "pending" if report.passed else "gate_failed"
        asset_id = self.store.store_asset(
            brief_id=str(brief["id"]),
            campaign_id=str(brief["campaign_id"]),
            payload=payload,
            provider_id=generated.provider_id,
            model_id=generated.model_id,
            gate_report=report,
            status=status,
            log_id=getattr(generated, "log_id", ""),
            workspace_id=self.workspace_id,
        )
        if report.passed:
            self.store.record_shown(
                provider_id=generated.provider_id,
                model_id=generated.model_id,
                workspace_id=self.workspace_id,
            )
            return asset_id
        self.store.record_gate_failure(
            provider_id=generated.provider_id,
            model_id=generated.model_id,
            workspace_id=self.workspace_id,
        )
        return None

    # ── review: the swipe ───────────────────────────────────────────────────

    def review_queue(self, campaign_id: str, *, limit: int = 50) -> list[dict[str, Any]]:
        """Candidates waiting for a decision, oldest first."""
        self._require_own_kind(campaign_id, "reviewing images")
        return self.store.list_assets(campaign_id, status="pending", limit=limit)

    def approve(self, asset_id: str) -> dict[str, Any]:
        """Swipe right. Keep the picture, and credit the generator."""
        return self._decide(asset_id, approved=True)

    def reject(self, asset_id: str, *, delete_file: bool = True) -> dict[str, Any]:
        """Swipe left. Discard the picture, and record it against the generator.

        The bytes go; the row stays. The record of having rejected it is what
        the benchmark is made of.
        """
        asset = self._decide(asset_id, approved=False)
        if delete_file:
            self.store.delete_asset_file(asset_id)
        return asset

    def _decide(self, asset_id: str, *, approved: bool) -> dict[str, Any]:
        asset = self.store.get_asset(asset_id)
        if asset["status"] != "pending":
            raise ValueError(
                f"This picture was already {asset['status']}. A decision is made "
                "once, so the generator's score cannot be moved by clicking twice."
            )
        self._require_own_kind(str(asset["campaign_id"]), "deciding on an image")
        updated = self.store.set_asset_status(
            asset_id, "approved" if approved else "rejected"
        )
        self.store.record_decision(
            provider_id=str(asset["provider_id"]),
            model_id=str(asset["model_id"]),
            approved=approved,
            workspace_id=self.workspace_id,
        )
        self._close_brief_if_fulfilled(str(asset["brief_id"]))
        return updated

    def regenerate(self, asset_id: str, *, provider_id: str = "") -> GenerationRound:
        """The refresh button: discard this one and try the same brief again.

        Deliberately a rejection plus a generation rather than a silent swap.
        The owner said no to this picture, and that no is worth as much to the
        benchmark as any other — dropping it would quietly bias the scores
        towards whichever generator happened to be refreshed most.
        """
        asset = self.store.get_asset(asset_id)
        self.reject(asset_id)
        return self.generate(
            str(asset["brief_id"]), count=1, provider_id=provider_id
        )

    def _close_brief_if_fulfilled(self, brief_id: str) -> None:
        brief = self.store.get_brief(brief_id)
        if brief["status"] != "open":
            return
        approved = len(
            self.store.list_assets(
                str(brief["campaign_id"]),
                status="approved",
                brief_id=brief_id,
                limit=10000,
            )
        )
        if approved >= int(brief["wanted"]):
            self.store.set_brief_status(brief_id, "fulfilled")

    # ── the benchmark ───────────────────────────────────────────────────────

    def generator_arms(self) -> list[Arm]:
        """Generator scores as bandit arms.

        ``Arm`` calls them ``sends`` and ``replies`` because it was written for
        email variants. The names do not fit here — they are *shown* and
        *approved* — but the arithmetic is identical, and duplicating a
        Thompson sampler to rename two fields would be the worse trade.
        """
        arms = []
        for row in self.store.generator_stats(workspace_id=self.workspace_id):
            decided = int(row["approved"]) + int(row["rejected"])
            arms.append(
                Arm(
                    id=f"{row['provider_id']}:{row['model_id']}",
                    label=str(row["model_id"]) or str(row["provider_id"]),
                    sends=decided,
                    replies=int(row["approved"]),
                )
            )
        return arms

    def allocation(self, *, seed: int | None = None) -> dict[str, Any]:
        """How the next batch should be split between generators."""
        return allocate(self.generator_arms(), seed=seed).to_dict()

    def _next_generator(self) -> str:
        """Which generator draws the next candidate.

        Returns a provider id, or an empty string meaning "let the broker choose
        the cheapest permitted one". Until there are enough decisions to judge,
        that is the honest answer: allocating on four swipes would starve a
        generator that has not had a fair run.
        """
        arms = [arm for arm in self.generator_arms() if arm.sends >= MIN_DECISIONS_TO_JUDGE]
        if len(arms) < 2:
            return ""
        allocation = allocate(self.generator_arms())
        leader = allocation.leader
        return leader.arm_id.split(":", 1)[0] if leader else ""

    def summary(self, campaign_id: str) -> dict[str, Any]:
        """Where this campaign stands."""
        self._require_own_kind(campaign_id, "reading the summary")
        counts: dict[str, int] = {}
        for status in ("pending", "approved", "rejected", "gate_failed"):
            counts[status] = len(
                self.store.list_assets(campaign_id, status=status, limit=100000)
            )
        briefs = self.store.list_briefs(campaign_id)
        return {
            "campaign_id": campaign_id,
            "briefs": len(briefs),
            "briefs_open": len([item for item in briefs if item["status"] == "open"]),
            "assets": counts,
            "generators": self.store.generator_stats(workspace_id=self.workspace_id),
            "allocation": self.allocation(seed=0),
            "min_decisions_to_judge": MIN_DECISIONS_TO_JUDGE,
        }
