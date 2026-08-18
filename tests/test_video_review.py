"""The review queue: push, ignore, edit.

The gate between a machine that makes videos on its own and an audience. Every
piece the assembler or the director produces lands here, and nothing leaves
except through a person pressing one of two buttons.

Four things are being protected.

**Push means a file, not an opinion.** What a distribution campaign publishes
is bytes. Approving a *document* and then posting whatever render happened to
be lying around is how the wrong video reaches an audience, so push requires an
export of exactly the version on the screen, and that export has to have passed
its gates.

**The baseline outlives the history.** The diff that measures what the owner
changed is taken against the document the machine produced. ``video_history``
is capped, so a project worked on for an afternoon can lose that version — the
review keeps its own copy, and this file proves it survives the trim.

**A verdict is given once.** The point of the queue is to score the thing that
made the piece. A number that can be moved by clicking twice is not a score.

**Ignore is not deletion.** A no is worth as much to the record as a yes, and
an owner who edited for twenty minutes before giving up said something quite
different from one who binned it on sight. Both are measured.
"""
from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from offsetx_apollo_builder.api.app import create_app
from offsetx_apollo_builder.api.config import AppSettings
from offsetx_apollo_builder.campaigns import WrongCampaignKind
from offsetx_apollo_builder.video.engine import VideoEditorEngine
from offsetx_apollo_builder.video.store import HISTORY_LIMIT, VideoStore
from offsetx_apollo_builder.video.timeline import TICKS_PER_SECOND, TimelineError

CAMPAIGN = "campaign-1"
SECOND = TICKS_PER_SECOND

#: A real three-second 1080×1920 file with no audio track. The engine tests use
#: it for the same reason: it is the shape a passing export actually has.
MUXED = Path(__file__).parent / "fixtures" / "muxed_sample.webm"

#: Same shape and same length, different bytes. The duplicate gate refuses a
#: byte-identical re-export, so a test that exports the same project twice needs
#: a second file rather than the same one again.
MUXED_TWO = Path(__file__).parent / "fixtures" / "muxed_sample_audio.webm"


class _Assets:
    def __init__(self, tmp_path: Path):
        self.dir = tmp_path / "assets"
        self.dir.mkdir(parents=True, exist_ok=True)
        self.rows: dict[str, dict] = {}

    def add(self, asset_id: str) -> str:
        path = self.dir / f"{asset_id}.png"
        path.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 64)
        self.rows[asset_id] = {
            "id": asset_id,
            "status": "approved",
            "path": str(path),
            "width": 1024,
            "height": 1024,
            "media_type": "image/png",
            "model_id": "flux",
            "provider_id": "replicate",
        }
        return asset_id

    def get(self, asset_id: str) -> dict:
        if asset_id not in self.rows:
            raise KeyError(f"Asset not found: {asset_id}")
        return self.rows[asset_id]

    def all(self, _campaign_id: str) -> list[dict]:
        return list(self.rows.values())


@pytest.fixture()
def assets(tmp_path: Path) -> _Assets:
    return _Assets(tmp_path)


@pytest.fixture()
def engine(tmp_path: Path, assets: _Assets):
    store = VideoStore(tmp_path / "video.db", renders_dir=tmp_path / "renders")
    runner = VideoEditorEngine(
        store=store,
        campaign_reader=lambda cid: {"id": cid, "kind": "image"},
        asset_reader=assets.get,
        campaign_asset_reader=assets.all,
    )
    try:
        yield runner
    finally:
        store.close()


def _three_second_project(engine: VideoEditorEngine, assets: _Assets) -> str:
    """A project whose length matches the fixture render, so a push can succeed."""
    state = engine.create_project(CAMPAIGN, name="Reel", preset="vertical", fps="30")
    assets.add("asset-1")
    engine.place_asset(state.project.id, asset_id="asset-1", duration=3 * SECOND)
    return state.project.id


def _ready(engine: VideoEditorEngine, project_id: str, *, again: bool = False) -> dict:
    payload = (MUXED_TWO if again else MUXED).read_bytes()
    result = engine.store_render(project_id, payload, renderer="webcodecs/vp09")
    assert result["passed"], result["summary"]
    return result


def _queued(engine: VideoEditorEngine, assets: _Assets) -> str:
    project_id = _three_second_project(engine, assets)
    engine.queue_for_review(project_id)
    return project_id


# ── everything the machine makes goes in the queue ──────────────────────────


def test_an_assembled_project_is_waiting_for_a_verdict_before_anyone_asks(engine, assets):
    """The whole reason the queue exists. A piece produced with nobody watching
    is exactly the piece that must not reach an audience on its own."""
    for index in range(4):
        assets.add(f"asset-{index}")
    state, _ = engine.assemble(CAMPAIGN, recipe="hook_hold_payoff", target_ticks=15 * SECOND)

    queue = engine.review_queue(CAMPAIGN)
    assert [item["project_id"] for item in queue] == [state.project.id]
    assert queue[0]["origin"] == "assemble"
    assert queue[0]["baseline_version"] == 0
    assert queue[0]["edited"] is False


def test_a_directed_project_says_the_model_chose_it(engine, assets):
    """``assemble`` and ``direct`` are not the same claim about what the machine
    did, and the queue is where that difference gets scored."""
    for index in range(3):
        assets.add(f"asset-{index}")
    engine.director = lambda **_: (
        '{"recipe": "three_points", "seconds": 20, '
        '"lines": ["First.", "Second.", "Third."], "rationale": "Listy."}'
    )
    engine.direct_and_assemble(CAMPAIGN, topic="changelogs nobody reads")
    assert engine.review_queue(CAMPAIGN)[0]["origin"] == "direct"


def test_a_hand_built_project_waits_for_nobody_until_it_is_sent(engine, assets):
    """Cutting a timeline is not the same as declaring it finished."""
    project_id = _three_second_project(engine, assets)
    assert engine.review_queue(CAMPAIGN) == []
    engine.queue_for_review(project_id)
    assert engine.review_queue(CAMPAIGN)[0]["origin"] == "manual"


def test_queueing_the_same_project_twice_does_not_queue_it_twice(engine, assets):
    """"Send this for review" is a statement about a project's state, not an
    event to be counted — and a queue with the same reel in it twice is a queue
    somebody answers twice."""
    project_id = _three_second_project(engine, assets)
    first = engine.queue_for_review(project_id)
    second = engine.queue_for_review(project_id)
    assert first["id"] == second["id"]
    assert len(engine.review_queue(CAMPAIGN)) == 1


def test_an_origin_nobody_declared_is_refused(engine, assets):
    project_id = _three_second_project(engine, assets)
    with pytest.raises(ValueError, match="Unknown review origin"):
        engine.queue_for_review(project_id, origin="vibes")


# ── push means a file ───────────────────────────────────────────────────────


def test_push_refuses_a_project_that_was_never_exported(engine, assets):
    """What reaches an audience is bytes. Approving a document that has never
    been rendered approves nothing anyone can post."""
    project_id = _queued(engine, assets)
    with pytest.raises(TimelineError, match="Nothing has been exported yet"):
        engine.push(project_id)


def test_push_refuses_an_export_that_failed_its_checks(engine, assets):
    """The gates exist to catch a browser that gave up mid-encode. Pushing past
    them would make them decoration."""
    state = engine.create_project(CAMPAIGN, name="Reel")
    assets.add("asset-1")
    engine.place_asset(state.project.id, asset_id="asset-1", duration=10 * SECOND)
    engine.queue_for_review(state.project.id)
    assert not engine.store_render(state.project.id, MUXED.read_bytes())["passed"]

    with pytest.raises(TimelineError, match="did not pass the checks"):
        engine.push(state.project.id)


def test_push_refuses_a_render_of_a_version_that_is_no_longer_the_one_on_screen(engine, assets):
    """The bug this rule exists for: export, keep editing, push — and publish a
    video the owner is no longer looking at."""
    project_id = _queued(engine, assets)
    _ready(engine, project_id)
    engine.edit(project_id, "rename", {"name": "Second thoughts"})

    with pytest.raises(TimelineError, match="edited since it was last exported"):
        engine.push(project_id)
    assert engine.review_queue(CAMPAIGN)[0]["ready_to_push"] is False


def test_re_exporting_after_the_edit_makes_push_possible_again(engine, assets):
    project_id = _queued(engine, assets)
    _ready(engine, project_id)
    engine.edit(project_id, "rename", {"name": "Second thoughts"})
    second = _ready(engine, project_id, again=True)

    review = engine.push(project_id)
    assert review["render_id"] == second["render_id"]
    assert review["decided_version"] == 2, "place_asset was 1, the rename 2"


def test_a_push_records_the_file_the_owner_was_looking_at(engine, assets):
    project_id = _queued(engine, assets)
    result = _ready(engine, project_id)

    review = engine.push(project_id, note="goes out Friday")
    assert review["verdict"] == "pushed"
    assert review["render_id"] == result["render_id"]
    assert review["note"] == "goes out Friday"
    assert review["decided_at"]
    assert engine.review_queue(CAMPAIGN) == [], "it left the queue"


def test_the_queue_says_why_push_is_not_available_yet(engine, assets):
    """A dead button with no sentence next to it is a bug report waiting to
    happen."""
    project_id = _queued(engine, assets)
    item = engine.review_queue(CAMPAIGN)[0]
    assert item["ready_to_push"] is False
    assert item["render_id"] == ""
    assert "Export it" in item["blocker"]


# ── the diff is the signal ──────────────────────────────────────────────────


def test_a_push_with_no_edits_says_the_assembler_got_it_right(engine, assets):
    for index in range(4):
        assets.add(f"asset-{index}")
    state, _ = engine.assemble(CAMPAIGN, recipe="hook_hold_payoff", target_ticks=3 * SECOND)
    _ready(engine, state.project.id)

    review = engine.push(state.project.id)
    assert review["diff"]["kept_share"] == 1.0
    assert review["diff"]["added"] == review["diff"]["removed"] == []


def test_the_diff_is_measured_against_what_the_machine_made_not_the_last_edit(engine, assets):
    """Three edits deep, the interesting number is still "how much of the
    original survived" — not "what changed since the previous keystroke"."""
    for index in range(4):
        assets.add(f"asset-{index}")
    state, _ = engine.assemble(CAMPAIGN, recipe="hook_hold_payoff", target_ticks=3 * SECOND)
    project_id = state.project.id
    clips = state.project.tracks[0].clips

    engine.edit(project_id, "remove_clip", {"clip_id": clips[0].id})
    engine.edit(project_id, "rename", {"name": "Take two"})
    engine.edit(project_id, "rename", {"name": "Take three"})
    _ready(engine, project_id)

    diff = engine.push(project_id)["diff"]
    assert diff["removed"] == [clips[0].id]
    assert diff["kept_share"] < 1.0


def test_the_baseline_survives_a_history_deep_enough_to_lose_it(engine, assets):
    """``video_history`` is capped, so the version the machine produced can be
    trimmed away. The diff would then be measured against whatever the oldest
    surviving version happened to be, which is a number that means nothing."""
    for index in range(4):
        assets.add(f"asset-{index}")
    state, _ = engine.assemble(CAMPAIGN, recipe="hook_hold_payoff", target_ticks=3 * SECOND)
    project_id = state.project.id
    original = len(state.project.tracks[0].clips)

    for index in range(HISTORY_LIMIT + 5):
        engine.edit(project_id, "rename", {"name": f"Take {index}"})

    low, _ = engine.store.version_bounds(project_id)
    assert low > 0, "version 0 is gone from the history, which is the point"

    _ready(engine, project_id)
    diff = engine.push(project_id)["diff"]
    # Renaming changes no clip, so everything the assembler laid is still there
    # — measurable only because the baseline was copied, not looked up.
    assert diff["kept_share"] == 1.0
    assert diff["untouched"] == original


def test_an_ignore_after_a_long_edit_is_a_different_verdict_from_one_on_sight(engine, assets):
    """Both are a no. Only the diff can tell them apart, and the difference is
    the whole reason it is measured on an ignore too."""
    for index in range(4):
        assets.add(f"asset-{index}")
    state, _ = engine.assemble(CAMPAIGN, recipe="hook_hold_payoff", target_ticks=3 * SECOND)
    clips = state.project.tracks[0].clips
    for clip in clips[:2]:
        engine.edit(state.project.id, "remove_clip", {"clip_id": clip.id})

    review = engine.ignore(state.project.id, note="never got there")
    assert review["verdict"] == "ignored"
    assert review["diff"]["removed"] == sorted(clip.id for clip in clips[:2])
    assert review["note"] == "never got there"


def test_an_ignore_needs_no_export_at_all(engine, assets):
    """Saying no to something is not a claim that it works."""
    project_id = _queued(engine, assets)
    assert engine.ignore(project_id)["verdict"] == "ignored"
    assert engine.review_queue(CAMPAIGN) == []


def test_the_edited_flag_follows_the_document_and_not_a_stored_boolean(engine, assets):
    """Undo back to the baseline and the piece is untouched again. A flag
    written at edit time would still claim otherwise."""
    project_id = _queued(engine, assets)
    assert engine.review_queue(CAMPAIGN)[0]["edited"] is False
    engine.edit(project_id, "rename", {"name": "Changed"})
    assert engine.review_queue(CAMPAIGN)[0]["edited"] is True


# ── a verdict is given once ─────────────────────────────────────────────────


def test_pushing_twice_is_refused(engine, assets):
    project_id = _queued(engine, assets)
    _ready(engine, project_id)
    engine.push(project_id)
    with pytest.raises(TimelineError, match="not waiting for a verdict"):
        engine.push(project_id)


def test_ignoring_something_already_pushed_is_refused(engine, assets):
    project_id = _queued(engine, assets)
    _ready(engine, project_id)
    engine.push(project_id)
    with pytest.raises(TimelineError, match="not waiting for a verdict"):
        engine.ignore(project_id)


def test_deciding_on_a_project_nobody_queued_says_what_to_do(engine, assets):
    project_id = _three_second_project(engine, assets)
    with pytest.raises(TimelineError, match="Send it to the review queue first"):
        engine.push(project_id)


def test_the_store_refuses_to_move_a_verdict_that_was_already_given(engine, assets):
    """Belt and braces at the layer below: the engine will not offer it, and the
    store will not do it either."""
    project_id = _queued(engine, assets)
    review = engine.ignore(project_id)
    with pytest.raises(ValueError, match="already ignored"):
        engine.store.decide_review(review["id"], verdict="pushed", decided_version=0)


def test_a_verdict_that_is_not_push_or_ignore_is_refused(engine, assets):
    project_id = _queued(engine, assets)
    review = engine.store.open_review_for(project_id)
    with pytest.raises(ValueError, match="A verdict is push or ignore"):
        engine.store.decide_review(review["id"], verdict="maybe", decided_version=0)


def test_a_decided_project_can_be_sent_back_and_collects_a_second_verdict(engine, assets):
    """A piece ignored in January and re-cut in March is a new decision. Both
    are kept: the record of what the owner thought is the point."""
    project_id = _queued(engine, assets)
    engine.ignore(project_id, note="wrong angle")
    engine.edit(project_id, "rename", {"name": "Re-cut"})
    engine.queue_for_review(project_id)
    _ready(engine, project_id)
    engine.push(project_id, note="better")

    verdicts = [review["verdict"] for review in engine.reviews(project_id)]
    assert sorted(verdicts) == ["ignored", "pushed"]


def test_only_one_review_is_ever_open_for_a_project(engine, assets):
    """Enforced by the database rather than by a check the second request can
    also pass."""
    import sqlite3

    project_id = _queued(engine, assets)
    with pytest.raises((sqlite3.IntegrityError, Exception)):
        engine.store.connection.execute(
            "INSERT INTO video_reviews(id, project_id, campaign_id, verdict, created_at)"
            " VALUES('second', ?, ?, 'waiting', '2026-01-01T00:00:00+00:00')",
            (project_id, CAMPAIGN),
        )


def test_a_verdict_never_carries_the_whole_timeline_back_to_the_caller(engine, assets):
    """The baseline is a document per row. A queue of twenty would be megabytes
    to draw three buttons."""
    project_id = _queued(engine, assets)
    engine.ignore(project_id)
    assert all("baseline" not in review for review in engine.reviews(project_id))
    assert all("baseline" not in item for item in engine.review_queue(CAMPAIGN))


# ── the handoff to distribution ─────────────────────────────────────────────


def test_a_pushed_video_appears_where_an_approved_picture_would(engine, assets):
    """Same shape, same question. That is why the publisher needed nothing new."""
    project_id = _queued(engine, assets)
    result = _ready(engine, project_id)
    engine.push(project_id)

    pushed = engine.pushed(CAMPAIGN)
    assert [item["id"] for item in pushed] == [result["render_id"]]
    assert Path(pushed[0]["path"]).exists()
    assert pushed[0]["media_type"].startswith("video/")
    assert pushed[0]["project_name"] == "Reel"


def test_nothing_ignored_reaches_the_handoff(engine, assets):
    project_id = _queued(engine, assets)
    _ready(engine, project_id)
    engine.ignore(project_id)
    assert engine.pushed(CAMPAIGN) == []


def test_deleting_a_project_takes_its_verdicts_with_it(engine, assets):
    project_id = _queued(engine, assets)
    engine.ignore(project_id)
    engine.delete_project(project_id)
    assert engine.store.reviews_for(project_id) == []


# ── the summary ─────────────────────────────────────────────────────────────


def test_the_summary_reports_how_the_owner_has_been_answering(engine, assets):
    for index in range(4):
        assets.add(f"asset-{index}")
    kept, binned = [
        engine.assemble(CAMPAIGN, recipe="hook_hold_payoff", target_ticks=3 * SECOND)[0]
        for _ in range(2)
    ]
    _ready(engine, kept.project.id)
    engine.push(kept.project.id)
    engine.ignore(binned.project.id)
    engine.assemble(CAMPAIGN, recipe="quick_list", target_ticks=3 * SECOND)

    counts = engine.summary(CAMPAIGN)["reviews"]
    assert counts["pushed"] == 1
    assert counts["ignored"] == 1
    assert counts["waiting"] == 1
    assert counts["untouched_pushes"] == 1
    assert counts["kept_share"] == 1.0


def test_the_kept_share_is_averaged_over_pushes_only(engine, assets):
    """Mixing it with ignores would blend "what the assembler gets right" with
    "how often it is wrong altogether" — two questions with two different fixes."""
    for index in range(4):
        assets.add(f"asset-{index}")
    binned, _ = engine.assemble(CAMPAIGN, recipe="hook_hold_payoff", target_ticks=3 * SECOND)
    for clip in binned.project.tracks[0].clips[:2]:
        engine.edit(binned.project.id, "remove_clip", {"clip_id": clip.id})
    engine.ignore(binned.project.id)

    kept, _ = engine.assemble(CAMPAIGN, recipe="hook_hold_payoff", target_ticks=3 * SECOND)
    _ready(engine, kept.project.id)
    engine.push(kept.project.id)

    assert engine.summary(CAMPAIGN)["reviews"]["kept_share"] == 1.0


# ── the kind gate ───────────────────────────────────────────────────────────


def test_every_review_entry_point_checks_the_campaign_kind(tmp_path, assets):
    store = VideoStore(tmp_path / "v.db", renders_dir=tmp_path / "r")
    kinds = {CAMPAIGN: "image"}
    runner = VideoEditorEngine(
        store=store,
        campaign_reader=lambda cid: {"id": cid, "kind": kinds[cid]},
        asset_reader=assets.get,
        campaign_asset_reader=assets.all,
    )
    try:
        project_id = _queued(runner, assets)
        kinds[CAMPAIGN] = "email"
        for call in (
            lambda: runner.review_queue(CAMPAIGN),
            lambda: runner.pushed(CAMPAIGN),
            lambda: runner.queue_for_review(project_id),
            lambda: runner.push(project_id),
            lambda: runner.ignore(project_id),
            lambda: runner.reviews(project_id),
        ):
            with pytest.raises(WrongCampaignKind):
                call()
    finally:
        store.close()


# ── over HTTP ───────────────────────────────────────────────────────────────


@pytest.fixture()
def client(tmp_path: Path):
    settings = AppSettings(
        project_root=Path.cwd(),
        database_path=tmp_path / "outreach.db",
        data_dir=tmp_path / "data",
        export_dir=tmp_path / "exports",
        frontend_dist=tmp_path / "missing-dist",
    )
    with TestClient(create_app(settings)) as test_client:
        yield test_client


def _campaign(client: TestClient) -> str:
    response = client.post(
        "/api/v1/campaigns", json={"name": "Pictures", "kind": "image"}
    )
    assert response.status_code in (200, 201), response.text
    return response.json()["id"]


def _api_project(client: TestClient, campaign_id: str) -> str:
    response = client.post(
        f"/api/v1/campaigns/{campaign_id}/video-projects",
        json={"name": "Reel", "preset": "vertical", "fps": "30"},
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


def test_the_queue_endpoint_starts_empty_and_fills_when_something_is_sent(client):
    campaign_id = _campaign(client)
    project_id = _api_project(client, campaign_id)

    assert client.get(f"/api/v1/campaigns/{campaign_id}/video-queue").json()["items"] == []
    queued = client.post(f"/api/v1/video-projects/{project_id}/queue", json={})
    assert queued.status_code == 201, queued.text
    assert "baseline" not in queued.json()

    items = client.get(f"/api/v1/campaigns/{campaign_id}/video-queue").json()["items"]
    assert [item["project_id"] for item in items] == [project_id]
    assert items[0]["ready_to_push"] is False


def test_a_decision_that_is_neither_push_nor_ignore_is_a_400(client):
    campaign_id = _campaign(client)
    project_id = _api_project(client, campaign_id)
    client.post(f"/api/v1/video-projects/{project_id}/queue", json={})

    response = client.post(
        f"/api/v1/video-projects/{project_id}/decide", json={"decision": "maybe"}
    )
    assert response.status_code == 400
    assert response.json()["detail"]["error"] == "unknown_decision"


def test_pushing_something_never_exported_is_a_422_that_says_what_to_do(client):
    """422 and not 500: the sentence the engine wrote is the whole value of the
    response, and a stack trace would replace it."""
    campaign_id = _campaign(client)
    project_id = _api_project(client, campaign_id)
    client.post(f"/api/v1/video-projects/{project_id}/queue", json={})

    response = client.post(
        f"/api/v1/video-projects/{project_id}/decide", json={"decision": "push"}
    )
    assert response.status_code == 422
    assert "Export it" in response.json()["detail"]


def test_ignoring_over_http_empties_the_queue_and_keeps_the_record(client):
    campaign_id = _campaign(client)
    project_id = _api_project(client, campaign_id)
    client.post(f"/api/v1/video-projects/{project_id}/queue", json={})

    response = client.post(
        f"/api/v1/video-projects/{project_id}/decide",
        json={"decision": "ignore", "note": "wrong angle"},
    )
    assert response.status_code == 200
    assert response.json()["verdict"] == "ignored"
    assert client.get(f"/api/v1/campaigns/{campaign_id}/video-queue").json()["items"] == []

    reviews = client.get(f"/api/v1/video-projects/{project_id}/reviews").json()["items"]
    assert [item["note"] for item in reviews] == ["wrong angle"]


def test_a_pushed_video_is_something_a_post_can_point_at(client):
    """The whole path in one test: export, push, plan a post against the render,
    publish it, and find the file in the outbox."""
    campaign_id = _campaign(client)
    project_id = _api_project(client, campaign_id)

    track = client.get(f"/api/v1/video-projects/{project_id}").json()["document"]["tracks"][0]["id"]
    client.post(
        f"/api/v1/video-projects/{project_id}/edit",
        json={
            "operation": "add_clip",
            "params": {
                "track_id": track,
                "kind": "solid",
                "start": 0,
                "duration": 3 * SECOND,
                "style": {"colour": "#101010"},
            },
        },
    )
    client.post(f"/api/v1/video-projects/{project_id}/queue", json={})

    upload = client.post(
        f"/api/v1/video-projects/{project_id}/renders",
        files={"file": ("out.webm", MUXED.read_bytes(), "video/webm")},
        data={"renderer": "webcodecs/vp09"},
    )
    assert upload.status_code == 201, upload.text
    assert upload.json()["passed"], upload.json()["summary"]
    render_id = upload.json()["render_id"]

    pushed = client.post(
        f"/api/v1/video-projects/{project_id}/decide", json={"decision": "push"}
    )
    assert pushed.status_code == 200, pushed.text
    assert pushed.json()["render_id"] == render_id

    approved = client.get(f"/api/v1/campaigns/{campaign_id}/video-approved").json()["items"]
    assert [item["id"] for item in approved] == [render_id]

    # …and the distribution side can publish it with nothing new learned.
    dist = client.post(
        "/api/v1/campaigns", json={"name": "Posting", "kind": "distribution"}
    ).json()["id"]
    account = client.post(
        "/api/v1/distribution/accounts",
        json={"platform": "local_outbox", "handle": "@studio", "label": "Studio"},
    )
    assert account.status_code in (200, 201), account.text
    post = client.post(
        f"/api/v1/campaigns/{dist}/posts",
        json={"account_id": account.json()["id"], "caption": "new reel", "asset_id": render_id},
    )
    assert post.status_code in (200, 201), post.text
    post_id = post.json()["id"]

    client.post(f"/api/v1/posts/{post_id}/approve")
    client.post(f"/api/v1/posts/{post_id}/schedule", json={"at": "2020-01-01T00:00:00+00:00"})
    published = client.post("/api/v1/distribution/publish-due", json={})
    assert published.status_code == 200, published.text
    assert published.json()["published"] == 1

    # The proof: the video itself is in the outbox, not a record saying it was.
    receipt = published.json()["details"][0]["detail"]
    delivered = Path(str(receipt["asset"]))
    assert delivered.exists()
    assert delivered.read_bytes() == MUXED.read_bytes()


def test_an_export_that_failed_its_checks_cannot_be_posted(client):
    """The gates are what stands between a half-encoded file and an audience.
    A post pointing straight at a failed render would walk around them."""
    campaign_id = _campaign(client)
    project_id = _api_project(client, campaign_id)
    # A ten-second project against a three-second file: the length gate fails.
    track = client.get(f"/api/v1/video-projects/{project_id}").json()["document"]["tracks"][0]["id"]
    client.post(
        f"/api/v1/video-projects/{project_id}/edit",
        json={
            "operation": "add_clip",
            "params": {
                "track_id": track, "kind": "solid", "start": 0,
                "duration": 10 * SECOND, "style": {"colour": "#101010"},
            },
        },
    )
    upload = client.post(
        f"/api/v1/video-projects/{project_id}/renders",
        files={"file": ("out.webm", MUXED.read_bytes(), "video/webm")},
    )
    assert not upload.json()["passed"]
    render_id = upload.json()["render_id"]

    dist = client.post(
        "/api/v1/campaigns", json={"name": "Posting", "kind": "distribution"}
    ).json()["id"]
    account = client.post(
        "/api/v1/distribution/accounts",
        json={"platform": "local_outbox", "handle": "@studio", "label": "Studio"},
    ).json()
    post_id = client.post(
        f"/api/v1/campaigns/{dist}/posts",
        json={"account_id": account["id"], "caption": "oops", "asset_id": render_id},
    ).json()["id"]
    client.post(f"/api/v1/posts/{post_id}/approve")
    client.post(f"/api/v1/posts/{post_id}/schedule", json={"at": "2020-01-01T00:00:00+00:00"})

    published = client.post("/api/v1/distribution/publish-due", json={}).json()
    # The publisher was handed nothing, so it recorded a caption with no file
    # rather than delivering an export the checks rejected.
    assert "asset" not in published["details"][0]["detail"]
