from __future__ import annotations

from pathlib import Path

import pytest

from offsetx_apollo_builder.competitor_teardown import (
    CompetitorTeardownError,
    analyse_public_post,
)
from offsetx_apollo_builder.video.engine import VideoEditorEngine
from offsetx_apollo_builder.video.store import VideoStore


def facts(**overrides):
    value = {
        "source_url": "https://www.youtube.com/watch?v=public123",
        "source_id": "public123",
        "platform": "youtube",
        "observed_at": "2026-09-20T00:00:00+00:00",
        "duration_seconds": 18,
        "views": 120000,
        "likes": 8000,
        "comments": 400,
        "channel_median_views": 20000,
        "cuts_per_minute": 42,
        "opening_seconds": 0.8,
        "visual_motion": "high",
    }
    value.update(overrides)
    return value


def test_same_public_facts_always_produce_same_structure():
    first = analyse_public_post(facts())
    second = analyse_public_post(facts())
    assert first == second
    assert first.recipe_id == "fast_montage"
    assert first.performance["outlier_multiple"] == 6.0


@pytest.mark.parametrize("field", ["caption", "transcript", "audio_url", "frame_urls", "media"])
def test_source_copy_or_media_fields_are_refused(field):
    payload = facts()
    payload[field] = "do not copy me"
    with pytest.raises(CompetitorTeardownError, match="structural/performance facts only"):
        analyse_public_post(payload)


def test_session_gated_source_is_refused():
    with pytest.raises(CompetitorTeardownError, match="Automated crawling is disabled"):
        analyse_public_post(
            facts(source_url="https://www.linkedin.com/posts/private-session")
        )


def test_missing_structure_is_insufficient_evidence_not_a_guess():
    with pytest.raises(CompetitorTeardownError, match="insufficient structural evidence"):
        analyse_public_post(
            facts(
                cuts_per_minute=0,
                opening_seconds=0,
                visual_motion="",
            )
        )


class Assets:
    def __init__(self, tmp_path: Path):
        self.dir = tmp_path / "assets"
        self.dir.mkdir()
        path = self.dir / "ours.png"
        path.write_bytes(b"our approved asset")
        self.row = {
            "id": "ours",
            "status": "approved",
            "path": str(path),
            "width": 1080,
            "height": 1920,
        }

    def get(self, asset_id: str):
        assert asset_id == "ours"
        return self.row

    def all(self, _campaign_id: str):
        return [self.row]


def test_teardown_builds_with_our_material_and_enters_existing_review_queue(tmp_path):
    assets = Assets(tmp_path)
    store = VideoStore(tmp_path / "video.db", renders_dir=tmp_path / "renders")
    engine = VideoEditorEngine(
        store=store,
        campaign_reader=lambda cid: {"id": cid, "kind": "image"},
        asset_reader=assets.get,
        campaign_asset_reader=assets.all,
    )
    try:
        teardown = analyse_public_post(
            facts(
                duration_seconds=12,
                cuts_per_minute=0,
                opening_seconds=1.0,
                visual_motion="high",
            )
        )
        state, report = engine.assemble_from_competitor_teardown(
            "campaign-1",
            teardown,
            asset_ids=["ours"],
        )
        queue = engine.review_queue("campaign-1")
        assert queue[0]["project_id"] == state.project.id
        assert queue[0]["origin"] == "competitor_teardown"
        assert report.project.tracks[0].clips
        assert {clip.asset_id for clip in report.project.tracks[0].clips} == {"ours"}
    finally:
        store.close()


def test_boolean_facts_are_not_truthy_strings():
    with pytest.raises(CompetitorTeardownError, match="before_after must be true or false"):
        analyse_public_post(facts(before_after="false"))
