"""The image campaign runner.

The second campaign kind, and the first that produces something other than a
message. Its shape:

    brief → generate → deterministic gates → review queue → swipe
                            ↓ fail                            ↓
                       never shown                    generator score

Two properties matter more than the rest.

**The swipe is the label.** A decision settles the picture *and* scores the
generator that made it. That is the quality benchmark, collected free as a side
effect of ordinary use, and it is what `ai/bandit.py` then allocates on. A
decision that failed to score, or that could be applied twice, would corrupt the
only real signal this campaign kind has.

**A gate failure is not a rejection.** The owner rejecting a picture is a
statement about taste; a file that will not decode is a statement about the
file. Mixing them poisons the benchmark, so they are separate statuses and
separate counters.
"""
from __future__ import annotations

import base64
import os
import struct
import zlib
from pathlib import Path

import pytest

from offsetx_apollo_builder.campaigns import WrongCampaignKind
from offsetx_apollo_builder.imagery.engine import (
    MIN_DECISIONS_TO_JUDGE,
    ImageCampaignEngine,
)
from offsetx_apollo_builder.imagery.gates import (
    ImageDecodeError,
    decode_data_uri,
    image_size,
    run_gates,
)
from offsetx_apollo_builder.imagery.store import ImageStore

CAMPAIGN = "campaign-1"


def png(width: int, height: int, *, noise: int = 4096) -> str:
    """A real PNG with a real IHDR, padded with incompressible bytes.

    Random padding rather than zeros: zeros compress to nothing and the result
    falls under the blank-image gate, which is correct behaviour and useless as
    a fixture.
    """

    def chunk(tag: bytes, data: bytes) -> bytes:
        return (
            struct.pack(">I", len(data))
            + tag
            + data
            + struct.pack(">I", zlib.crc32(tag + data))
        )

    header = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    body = (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", header)
        + chunk(b"IDAT", os.urandom(noise))
        + chunk(b"IEND", b"")
    )
    return "data:image/png;base64," + base64.b64encode(body).decode()


class _Generated:
    """What `broker.call_image` returns."""

    def __init__(self, images, provider_id="nvidia", model_id="flux"):
        self.images = images
        self.provider_id = provider_id
        self.provider_name = provider_id
        self.model_id = model_id
        self.tier = "B"
        self.policy = "standard"
        self.duration_ms = 10
        self.log_id = "log-1"
        self.rejected = []


class _Broker:
    """A broker whose image calls are scripted."""

    def __init__(self):
        self.script: list = []
        self.calls: list[str] = []

    def call_image(self, request, settings, *, provider_id=""):
        self.calls.append(provider_id)
        if not self.script:
            return _Generated([png(1024, 576)])
        item = self.script.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


@pytest.fixture()
def engine(tmp_path: Path):
    store = ImageStore(tmp_path / "imagery.db", assets_dir=tmp_path / "assets")
    broker = _Broker()
    made = ImageCampaignEngine(
        store=store,
        broker=broker,
        settings_resolver=lambda workspace: object(),
        campaign_reader=lambda cid: {"id": cid, "kind": "image"},
    )
    made.broker = broker
    yield made
    store.close()


# ─────────────────────────────────────────────────────────────────────────────
# Gates
# ─────────────────────────────────────────────────────────────────────────────


def test_dimensions_are_read_from_the_header_without_an_image_library():
    """Reading two integers should not cost a large dependency."""
    assert image_size(decode_data_uri(png(1024, 576))[1]) == (1024, 576, "image/png")

    gif = b"GIF89a" + struct.pack("<HH", 800, 600) + os.urandom(2000)
    assert image_size(gif) == (800, 600, "image/gif")


def test_an_unrecognised_format_raises_rather_than_returning_zero():
    """Fails closed. A zero would silently pass a dimension check."""
    with pytest.raises(ImageDecodeError):
        image_size(b"\x00\x01\x02\x03 not an image at all")


def test_a_square_does_not_pass_a_sixteen_by_nine_brief():
    report = run_gates(png(1024, 1024), want_width=16, want_height=9)
    assert not report.passed
    assert any(item.name == "aspect_ratio" for item in report.failures)


def test_a_generator_rounding_to_its_own_size_still_passes():
    """1024x576 and 1152x648 are both 16:9; a tolerance is not sloppiness."""
    for width, height in ((1024, 576), (1152, 648), (1920, 1080)):
        report = run_gates(png(width, height), want_width=16, want_height=9)
        assert report.passed, f"{width}x{height} should satisfy 16:9"


def test_a_placeholder_sized_response_is_caught():
    report = run_gates(png(1024, 576, noise=0))
    assert not report.passed
    assert any(item.name == "not_blank" for item in report.failures)


def test_a_broken_candidate_is_a_failed_gate_not_an_exception():
    """One bad candidate must not abort a whole batch."""
    report = run_gates("this is not a data uri")
    assert not report.passed
    assert report.failures[0].name == "decodes"


def test_a_byte_identical_repeat_is_caught():
    image = png(1024, 576)
    first = run_gates(image)
    second = run_gates(image, seen_hashes={first.sha256})
    assert not second.passed
    assert any(item.name == "not_duplicate" for item in second.failures)


# ─────────────────────────────────────────────────────────────────────────────
# Generating
# ─────────────────────────────────────────────────────────────────────────────


def test_a_round_stores_candidates_and_queues_them(engine):
    brief = engine.add_brief(CAMPAIGN, brief="a warehouse at dawn", width=16, height=9)
    engine.broker.script = [_Generated([png(1024, 576)]) for _ in range(3)]

    result = engine.generate(brief, count=3)
    assert result.stored == 3
    assert result.gate_failed == 0
    assert len(engine.review_queue(CAMPAIGN)) == 3


def test_a_candidate_that_fails_a_gate_never_reaches_the_queue(engine):
    """The owner's attention is spent on pictures that are at least valid."""
    brief = engine.add_brief(CAMPAIGN, brief="a warehouse", width=16, height=9)
    engine.broker.script = [_Generated([png(512, 512)]), _Generated([png(1024, 576)])]

    result = engine.generate(brief, count=2)
    assert result.stored == 1
    assert result.gate_failed == 1
    assert len(engine.review_queue(CAMPAIGN)) == 1


def test_a_failed_gate_is_kept_so_the_pattern_is_visible(engine):
    """"This generator returns the wrong ratio four times in five" is worth knowing.

    A discarded candidate cannot tell the owner that, so the row is stored with
    a `gate_failed` status even though it is never shown.
    """
    brief = engine.add_brief(CAMPAIGN, brief="a warehouse", width=16, height=9)
    engine.broker.script = [_Generated([png(512, 512)])]
    engine.generate(brief, count=1)

    failed = engine.store.list_assets(CAMPAIGN, status="gate_failed")
    assert len(failed) == 1
    assert any(
        item["name"] == "aspect_ratio" and not item["passed"]
        for item in failed[0]["gates"]["results"]
    )
    stats = engine.store.generator_stats()[0]
    assert stats["gate_failed"] == 1
    assert stats["shown"] == 0, "a gate failure was never shown to anyone"


def test_a_failing_call_does_not_abort_the_round(engine):
    brief = engine.add_brief(CAMPAIGN, brief="a warehouse")
    engine.broker.script = [
        RuntimeError("AI provider returned 503: overloaded"),
        _Generated([png(1024, 576)]),
    ]
    result = engine.generate(brief, count=2)
    assert result.call_failed == 1
    assert result.stored == 1


def test_the_picture_is_a_file_and_the_row_points_at_it(engine):
    """Base64 blobs in a database bloat every backup that did not want them."""
    brief = engine.add_brief(CAMPAIGN, brief="a warehouse")
    engine.generate(brief, count=1)
    asset = engine.review_queue(CAMPAIGN)[0]
    path = Path(asset["path"])
    assert path.exists() and path.stat().st_size == asset["bytes"]
    assert oct(path.stat().st_mode)[-3:] == "600"


# ─────────────────────────────────────────────────────────────────────────────
# The swipe
# ─────────────────────────────────────────────────────────────────────────────


def test_approving_keeps_the_picture_and_credits_the_generator(engine):
    brief = engine.add_brief(CAMPAIGN, brief="a warehouse")
    engine.generate(brief, count=1)
    asset = engine.review_queue(CAMPAIGN)[0]

    updated = engine.approve(asset["id"])
    assert updated["status"] == "approved"
    assert Path(updated["path"]).exists()

    stats = engine.store.generator_stats()[0]
    assert stats["approved"] == 1 and stats["rejected"] == 0
    assert stats["approval_rate"] == 100.0


def test_rejecting_deletes_the_bytes_and_keeps_the_verdict(engine):
    """The record of having rejected it is what the benchmark is made of."""
    brief = engine.add_brief(CAMPAIGN, brief="a warehouse")
    engine.generate(brief, count=1)
    asset = engine.review_queue(CAMPAIGN)[0]
    path = Path(asset["path"])

    updated = engine.reject(asset["id"])
    assert updated["status"] == "rejected"
    assert not path.exists(), "the picture is gone"
    assert engine.store.get_asset(asset["id"])["status"] == "rejected", "the verdict is not"
    assert engine.store.generator_stats()[0]["rejected"] == 1


def test_a_decision_is_made_once(engine):
    """Otherwise a generator's score moves by clicking twice."""
    brief = engine.add_brief(CAMPAIGN, brief="a warehouse")
    engine.generate(brief, count=1)
    asset_id = engine.review_queue(CAMPAIGN)[0]["id"]

    engine.approve(asset_id)
    with pytest.raises(ValueError) as exc:
        engine.approve(asset_id)
    assert "already" in str(exc.value)
    assert engine.store.generator_stats()[0]["approved"] == 1


def test_refresh_counts_as_a_rejection(engine):
    """The owner said no to that picture, and the no is worth keeping.

    Dropping it would bias the scores towards whichever generator happened to
    be refreshed most.
    """
    brief = engine.add_brief(CAMPAIGN, brief="a warehouse")
    engine.generate(brief, count=1)
    asset_id = engine.review_queue(CAMPAIGN)[0]["id"]

    engine.regenerate(asset_id)
    assert engine.store.get_asset(asset_id)["status"] == "rejected"
    assert engine.store.generator_stats()[0]["rejected"] == 1
    assert len(engine.review_queue(CAMPAIGN)) == 1, "a fresh candidate took its place"


def test_a_brief_closes_once_it_has_what_it_asked_for(engine):
    brief = engine.add_brief(CAMPAIGN, brief="a warehouse", wanted=2)
    engine.generate(brief, count=3)
    queue = engine.review_queue(CAMPAIGN)

    engine.approve(queue[0]["id"])
    assert engine.store.get_brief(brief)["status"] == "open"
    engine.approve(queue[1]["id"])
    assert engine.store.get_brief(brief)["status"] == "fulfilled"


# ─────────────────────────────────────────────────────────────────────────────
# The benchmark
# ─────────────────────────────────────────────────────────────────────────────


def test_the_swipes_become_bandit_arms(engine):
    """Shown and approved, mapped onto sends and replies.

    The names do not fit — `Arm` was written for email variants — but the
    arithmetic is identical, and duplicating a Thompson sampler to rename two
    fields would be the worse trade.
    """
    brief = engine.add_brief(CAMPAIGN, brief="a warehouse")
    engine.broker.script = [
        _Generated([png(1024, 576)], provider_id="nvidia", model_id="flux"),
        _Generated([png(1024, 576)], provider_id="nvidia", model_id="sdxl"),
    ]
    engine.generate(brief, count=2)
    queue = engine.review_queue(CAMPAIGN)
    engine.approve(queue[0]["id"])
    engine.reject(queue[1]["id"])

    arms = {arm.id: arm for arm in engine.generator_arms()}
    assert arms["nvidia:flux"].replies == 1
    assert arms["nvidia:sdxl"].replies == 0
    assert all(arm.sends == 1 for arm in arms.values())

    allocation = engine.allocation(seed=0)
    assert {item["arm_id"] for item in allocation["arms"]} == set(arms)


def test_allocation_waits_for_enough_decisions_before_steering(engine):
    """A lopsided result from four swipes is noise.

    Acting on it would starve a generator that has not had a fair run, so until
    there is enough evidence the broker picks and this stays out of the way.
    """
    assert engine._next_generator() == "", "no data, no opinion"

    for index in range(MIN_DECISIONS_TO_JUDGE + 2):
        engine.store.record_decision(
            provider_id="nvidia", model_id="flux", approved=index % 2 == 0
        )
        engine.store.record_decision(
            provider_id="openai", model_id="dalle", approved=False
        )
    assert engine._next_generator() in {"nvidia", "openai"}


def test_the_summary_reports_where_the_campaign_stands(engine):
    # The brief has to state a ratio, or the square candidate legitimately
    # passes and there is no gate failure to count.
    brief = engine.add_brief(
        CAMPAIGN, brief="a warehouse", width=16, height=9, wanted=1
    )
    engine.broker.script = [_Generated([png(1024, 576)]), _Generated([png(512, 512)])]
    engine.generate(brief, count=2)
    engine.approve(engine.review_queue(CAMPAIGN)[0]["id"])

    summary = engine.summary(CAMPAIGN)
    assert summary["assets"]["approved"] == 1
    assert summary["assets"]["gate_failed"] == 1
    assert summary["briefs"] == 1 and summary["briefs_open"] == 0
    assert summary["min_decisions_to_judge"] == MIN_DECISIONS_TO_JUDGE


# ─────────────────────────────────────────────────────────────────────────────
# The kind gate, from the other side
# ─────────────────────────────────────────────────────────────────────────────


def test_the_image_runner_refuses_an_email_campaign(tmp_path):
    """The mirror of the check in OutreachEngine.

    Both runners check now, so neither can pick up the other's work: the mail
    sender will not try to post a picture, and this will not try to draw an
    email.
    """
    store = ImageStore(tmp_path / "i.db", assets_dir=tmp_path / "a")
    engine = ImageCampaignEngine(
        store=store,
        broker=_Broker(),
        settings_resolver=lambda workspace: object(),
        campaign_reader=lambda cid: {"id": cid, "kind": "email"},
    )
    try:
        for call in (
            lambda: engine.add_brief(CAMPAIGN, brief="x"),
            lambda: engine.review_queue(CAMPAIGN),
            lambda: engine.summary(CAMPAIGN),
        ):
            with pytest.raises(WrongCampaignKind):
                call()
    finally:
        store.close()


def test_generation_goes_through_the_broker_and_nothing_else():
    """Structural: this module owns no transport.

    Everything protective — the tier filter, the allowlist payload, the blocking
    scanner, the egress log — is inherited by calling the broker. A module that
    could reach a provider directly would inherit none of it.
    """
    import ast

    root = Path(__file__).resolve().parents[1] / "offsetx_apollo_builder" / "imagery"
    imported: set[str] = set()
    for path in root.glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                imported.add(node.module or "")
                imported.update(alias.name for alias in node.names)

    assert not (imported & {"requests", "httpx", "urllib.request", "openai"}), imported
    assert not any("providers" in name for name in imported), imported
