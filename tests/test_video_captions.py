"""Auto-captions: the transcription call, and turning words into readable lines.

The transcription part is short. Everything hard is what happens to the words
afterwards, and two properties matter more than the rest.

**The timeline's invariant is the specification.** Clips on a track cannot
overlap by a single tick, and speech does not respect that — words run
together, a stretched short caption reaches into the next one, and two adjacent
cues rounded to the same frame collide. So the caption builder has to produce a
legal track or the editor refuses the whole batch. Most of these tests are
about that.

**The scanner cannot read a waveform.** Every other egress path is protected by
a pre-flight scan. Audio defeats it completely: a recording of somebody reading
a customer list scans clean, because there is nothing to read. The classes whose
protection *is* that scan are refused by class instead, and that refusal is
tested from both sides.
"""
from __future__ import annotations

import struct
from pathlib import Path
from typing import Any

import pytest

from offsetx_apollo_builder.ai.broker import (
    TRANSCRIBE_FORBIDDEN_CLASSES,
    TranscriptWord,
    read_transcript_words,
)
from offsetx_apollo_builder.ai.tiers import DataClass
from offsetx_apollo_builder.video import captions as captioning
from offsetx_apollo_builder.video.captions import (
    MAX_CHARS,
    READABLE_CPS,
    Cue,
    Word,
    build_cues,
    lay_out,
    report,
    to_timeline,
    words_from_transcript,
)
from offsetx_apollo_builder.video.engine import VideoEditorEngine
from offsetx_apollo_builder.video.gates import VideoDecodeError, probe
from offsetx_apollo_builder.video.store import VideoStore
from offsetx_apollo_builder.video.timeline import TICKS_PER_SECOND, Clip, TimelineError

CAMPAIGN = "campaign-1"
SECOND = TICKS_PER_SECOND
FRAME_30 = SECOND // 30


def wav(seconds: float = 2.0, *, rate: int = 16000, channels: int = 1, bits: int = 16) -> bytes:
    """A real RIFF/WAVE file, which is what an uncompressed voiceover is."""
    byte_rate = rate * channels * bits // 8
    body = b"\x00" * int(byte_rate * seconds)
    fmt = struct.pack("<HHIIHH", 1, channels, rate, byte_rate, channels * bits // 8, bits)
    chunks = (
        b"fmt " + struct.pack("<I", len(fmt)) + fmt
        + b"data" + struct.pack("<I", len(body)) + body
    )
    return b"RIFF" + struct.pack("<I", 4 + len(chunks)) + b"WAVE" + chunks


def spoken(pairs: list[tuple[str, float, float]]) -> list[Word]:
    return words_from_transcript(
        [{"word": text, "start": start, "end": end} for text, start, end in pairs]
    )


SENTENCE = [
    ("The", 0.00, 0.20),
    ("port", 0.20, 0.55),
    ("of", 0.55, 0.65),
    ("Rotterdam", 0.65, 1.30),
    ("closed", 1.30, 1.80),
    ("today.", 1.80, 2.30),
    ("Nobody", 3.20, 3.70),
    ("expected", 3.70, 4.20),
    ("it,", 4.20, 4.50),
    ("and", 4.50, 4.70),
    ("the", 4.70, 4.85),
    ("backlog", 4.85, 5.40),
    ("is", 5.40, 5.55),
    ("already", 5.55, 6.10),
    ("enormous", 6.10, 6.90),
]


# ── reading what the model returned ─────────────────────────────────────────


def test_word_timings_are_read_from_whichever_shape_the_host_used():
    """Some hosts return a flat word list, some only nest words in segments."""
    flat = read_transcript_words({"words": [{"word": "hi", "start": 0.0, "end": 0.4}]})
    nested = read_transcript_words(
        {"segments": [{"words": [{"word": "hi", "start": 0.0, "end": 0.4}]}]}
    )
    assert flat == nested == [TranscriptWord(word="hi", start=0.0, end=0.4)]


def test_a_segment_only_answer_is_kept_rather_than_refused():
    """Sentence timings make worse captions than word timings and much better
    ones than no captions."""
    words = read_transcript_words({"segments": [{"text": "one two", "start": 0, "end": 3}]})
    assert [word.word for word in words] == ["one two"]


def test_a_word_with_no_timing_is_dropped_not_guessed_at():
    words = read_transcript_words(
        {"words": [{"word": "a", "start": 0, "end": 1}, {"word": "b"}, {"word": "c", "start": "x"}]}
    )
    assert [word.word for word in words] == ["a"]


def test_words_arrive_in_the_order_they_were_said():
    words = read_transcript_words(
        {"words": [{"word": "b", "start": 2, "end": 3}, {"word": "a", "start": 0, "end": 1}]}
    )
    assert [word.word for word in words] == ["a", "b"]


# ── where to break ──────────────────────────────────────────────────────────


def test_a_sentence_ending_always_breaks():
    cues = build_cues(spoken(SENTENCE))
    assert cues[0].text == "The port of Rotterdam closed today."


def test_a_pause_breaks_so_a_caption_never_spans_silence():
    words = spoken([("one", 0.0, 0.3), ("two", 2.0, 2.3)])
    assert len(build_cues(words)) == 2


def test_a_line_is_broken_before_it_gets_too_long_to_read():
    words = spoken([(f"word{index}", index * 0.3, index * 0.3 + 0.25) for index in range(20)])
    for cue in build_cues(words):
        assert len(cue.text) <= MAX_CHARS, cue.text


def test_a_comma_does_not_break_a_line_that_has_barely_started():
    """Breaking at every comma gives a stutter of two-word captions, which is
    harder to read than the long line it was avoiding."""
    cues = build_cues(spoken(SENTENCE))
    assert any("it, and" in cue.text for cue in cues), [cue.text for cue in cues]


def test_no_word_is_lost_between_the_transcript_and_the_captions():
    words = spoken(SENTENCE)
    said = " ".join(word.text for word in words)
    captioned = " ".join(cue.text for cue in build_cues(words))
    assert captioned == said


def test_a_long_sentence_with_no_punctuation_still_breaks_on_time():
    words = spoken([("word", index * 1.0, index * 1.0 + 0.9) for index in range(12)])
    for cue in build_cues(words):
        assert cue.end - cue.start <= captioning.MAX_TICKS


# ── landing them on a track the timeline will accept ────────────────────────


def test_captions_never_overlap_which_is_what_the_timeline_demands():
    cues = lay_out(build_cues(spoken(SENTENCE)), fps="30")
    for left, right in zip(cues, cues[1:]):
        assert left.end <= right.start, (left.text, right.text)


def test_every_caption_lands_on_a_frame_boundary():
    for cue in lay_out(build_cues(spoken(SENTENCE)), fps="30"):
        assert cue.start % FRAME_30 == 0
        assert cue.end % FRAME_30 == 0


def test_a_very_short_caption_is_stretched_into_the_silence_after_it():
    words = spoken([("go", 0.0, 0.12), ("again", 3.0, 3.4)])
    cues = lay_out(build_cues(words), fps="30")
    assert cues[0].duration >= captioning.MIN_TICKS


def test_stretching_never_reaches_into_the_next_caption():
    words = spoken([("go", 0.0, 0.10), ("now.", 0.30, 0.45), ("again", 4.0, 4.5)])
    cues = lay_out(build_cues(words), fps="30")
    for left, right in zip(cues, cues[1:]):
        assert left.end <= right.start


def test_a_caption_that_cannot_have_one_frame_joins_the_one_before_it():
    """Losing a word is worse than a short caption."""
    words = spoken([("hello.", 0.0, 0.50), ("hi.", 0.50, 0.505)])
    cues = lay_out(build_cues(words), fps="30")
    assert " ".join(cue.text for cue in cues) == "hello. hi."


def test_captions_stop_at_the_end_of_the_material():
    cues = lay_out(build_cues(spoken(SENTENCE)), fps="30", limit=4 * SECOND)
    assert cues
    assert max(cue.end for cue in cues) <= 4 * SECOND


# ── mapping media time onto the timeline ────────────────────────────────────


def _clip(**kwargs) -> Clip:
    base = {
        "id": "clip_1",
        "kind": "audio",
        "start": 0,
        "duration": 7 * SECOND,
        "in_point": 0,
        "source_duration": 30 * SECOND,
        "asset_id": "media-1",
        "speed": 1.0,
    }
    return Clip(**{**base, **kwargs})


def test_captions_move_with_the_clip_they_belong_to():
    cues = to_timeline(build_cues(spoken(SENTENCE)), _clip(start=10 * SECOND), fps="30")
    assert cues[0].start >= 10 * SECOND


def test_a_trimmed_clip_is_captioned_with_what_is_left_of_it():
    """Words spoken in the part that was cut away are not captioned."""
    cues = to_timeline(
        build_cues(spoken(SENTENCE)),
        _clip(in_point=3 * SECOND, duration=4 * SECOND),
        fps="30",
    )
    assert cues
    assert all("Rotterdam" not in cue.text for cue in cues)
    assert any("backlog" in cue.text for cue in cues)


def test_a_slowed_clip_stretches_its_captions_with_the_speech():
    normal = to_timeline(build_cues(spoken(SENTENCE)), _clip(), fps="30")
    slowed = to_timeline(
        build_cues(spoken(SENTENCE)),
        _clip(speed=0.5, duration=14 * SECOND),
        fps="30",
    )
    assert slowed[-1].end > normal[-1].end
    assert slowed[0].end - slowed[0].start > normal[0].end - normal[0].start


def test_captions_never_run_past_the_end_of_their_clip():
    clip = _clip(duration=3 * SECOND)
    for cue in to_timeline(build_cues(spoken(SENTENCE)), clip, fps="30"):
        assert cue.end <= clip.start + clip.duration


# ── telling the truth about the result ──────────────────────────────────────


def test_a_caption_nobody_could_read_in_time_is_reported():
    fast = [Cue(text="x" * 90, start=0, end=SECOND)]
    summary = report(fast)
    assert summary["too_fast"] == 1
    assert str(READABLE_CPS) in summary["warnings"][0]


def test_captions_at_a_readable_speed_produce_no_warning():
    assert report(lay_out(build_cues(spoken(SENTENCE)), fps="30"))["warnings"] == []


# ── the media that makes any of this possible ───────────────────────────────


class _Transcriber:
    """A scripted speech model. The broker is tested separately."""

    def __init__(self, words=None, *, fail: bool = False):
        self.words = words if words is not None else spoken(SENTENCE)
        self.calls = 0
        self.fail = fail

    def __call__(self, **kwargs):
        self.calls += 1
        if self.fail:
            raise RuntimeError("provider down")
        self.audio_bytes = len(kwargs.get("audio") or b"")

        class _Result:
            words = [
                TranscriptWord(word=item.text, start=item.start / SECOND, end=item.end / SECOND)
                for item in self.words
            ]
            text = " ".join(item.text for item in self.words)
            provider_id = "groq"
            model_id = "whisper-large-v3"
            log_id = "log-1"

        return _Result()


@pytest.fixture()
def engine(tmp_path: Path):
    store = VideoStore(tmp_path / "video.db", renders_dir=tmp_path / "renders")
    runner = VideoEditorEngine(
        store=store,
        campaign_reader=lambda cid: {"id": cid, "kind": "image"},
        transcriber=_Transcriber(),
    )
    try:
        yield runner
    finally:
        store.close()


def test_an_uploaded_voiceover_is_described_from_its_header(engine):
    media = engine.import_media(CAMPAIGN, wav(seconds=3.0), name="voiceover.wav")
    assert media["kind"] == "audio"
    assert media["media_type"] == "audio/wav"
    assert media["duration_ticks"] == 3 * SECOND
    assert media["has_audio"] is True
    assert Path(media["path"]).exists()


def test_the_same_upload_twice_is_one_file(engine):
    first = engine.import_media(CAMPAIGN, wav(), name="a.wav")
    second = engine.import_media(CAMPAIGN, wav(), name="b.wav")
    assert first["id"] == second["id"]


def test_a_picture_cannot_be_imported_through_the_media_path(engine):
    """Pictures come from the image campaign and its swipe, which is where
    their quality is judged."""
    png = (
        b"\x89PNG\r\n\x1a\n"
        + struct.pack(">I", 13)
        + b"IHDR"
        + struct.pack(">IIBBBBB", 8, 8, 8, 2, 0, 0, 0)
        + b"\x00" * 4
    )
    with pytest.raises(TimelineError, match="picture"):
        engine.import_media(CAMPAIGN, png)


def test_an_mp3_is_refused_with_the_reason(engine):
    """Its length cannot be read from a header, only by counting every frame."""
    with pytest.raises(TimelineError, match="MP3"):
        engine.import_media(CAMPAIGN, b"\xff\xfb\x90\x00" + b"\x00" * 9000)


def test_imported_audio_lands_on_an_audio_track(engine):
    project = engine.create_project(CAMPAIGN, name="Reel")
    media = engine.import_media(CAMPAIGN, wav(seconds=4.0))
    after = engine.place_media(project.project.id, media_id=media["id"])
    audio_track = next(track for track in after.project.tracks if track.kind == "audio")
    assert len(audio_track.clips) == 1
    assert audio_track.clips[0].source_duration == 4 * SECOND


# ── the whole caption flow ──────────────────────────────────────────────────


def _captioned(engine, *, seconds: float = 8.0):
    project = engine.create_project(CAMPAIGN, name="Reel")
    media = engine.import_media(CAMPAIGN, wav(seconds=seconds))
    state = engine.place_media(project.project.id, media_id=media["id"])
    clip = next(track for track in state.project.tracks if track.kind == "audio").clips[0]
    return project.project.id, media, clip


def test_captions_become_ordinary_text_clips_on_their_own_track(engine):
    project_id, _, clip = _captioned(engine)
    result = engine.add_captions(project_id, clip_id=clip.id)
    document = engine.open_project(project_id).project
    track = next(item for item in document.tracks if item.name == "Captions")
    assert result["captions"] == len(track.clips)
    assert {item.kind for item in track.clips} == {"text"}
    assert track.clips[0].text.startswith("The port")


def test_the_whole_set_of_captions_is_one_step_of_undo(engine):
    """Fifteen steps of undo to remove something asked for once is a chore, not
    a history."""
    project_id, _, clip = _captioned(engine)
    before = engine.open_project(project_id).record["version"]
    engine.add_captions(project_id, clip_id=clip.id)
    engine.undo(project_id)
    document = engine.open_project(project_id).project
    track = next((item for item in document.tracks if item.name == "Captions"), None)
    assert track is None or track.clips == []
    assert engine.open_project(project_id).record["version"] == before + 1


def test_captioning_twice_replaces_rather_than_stacks(engine):
    project_id, _, clip = _captioned(engine)
    first = engine.add_captions(project_id, clip_id=clip.id)
    second = engine.add_captions(project_id, clip_id=clip.id)
    document = engine.open_project(project_id).project
    track = next(item for item in document.tracks if item.name == "Captions")
    assert len(track.clips) == second["captions"] == first["captions"]


def test_the_transcript_is_paid_for_once(engine):
    project_id, media, clip = _captioned(engine)
    engine.add_captions(project_id, clip_id=clip.id)
    engine.add_captions(project_id, clip_id=clip.id)
    assert engine.transcriber.calls == 1
    assert engine.transcribe(media["id"])["reused"] is True


def test_asking_for_a_refresh_calls_the_model_again(engine):
    project_id, media, clip = _captioned(engine)
    engine.add_captions(project_id, clip_id=clip.id)
    engine.add_captions(project_id, clip_id=clip.id, refresh=True)
    assert engine.transcriber.calls == 2


def test_a_clip_with_no_sound_cannot_be_captioned(engine):
    project = engine.create_project(CAMPAIGN, name="Reel")
    state = engine.edit(
        project.project.id,
        "add_clip",
        {
            "track_id": project.project.tracks[0].id,
            "kind": "solid",
            "start": 0,
            "duration": 3 * SECOND,
        },
    )
    clip = state.project.tracks[0].clips[0]
    with pytest.raises(TimelineError, match="no sound"):
        engine.add_captions(project.project.id, clip_id=clip.id)


def test_a_silent_recording_says_so_rather_than_making_an_empty_track(tmp_path):
    store = VideoStore(tmp_path / "v.db", renders_dir=tmp_path / "r")
    runner = VideoEditorEngine(
        store=store,
        campaign_reader=lambda cid: {"id": cid, "kind": "image"},
        transcriber=_Transcriber(words=[]),
    )
    try:
        project = runner.create_project(CAMPAIGN)
        media = runner.import_media(CAMPAIGN, wav(seconds=3.0))
        state = runner.place_media(project.project.id, media_id=media["id"])
        clip = next(t for t in state.project.tracks if t.kind == "audio").clips[0]
        with pytest.raises(TimelineError, match="no timed words"):
            runner.add_captions(project.project.id, clip_id=clip.id)
    finally:
        store.close()


def test_without_a_transcriber_the_editor_says_what_to_connect(tmp_path):
    store = VideoStore(tmp_path / "v.db", renders_dir=tmp_path / "r")
    runner = VideoEditorEngine(
        store=store, campaign_reader=lambda cid: {"id": cid, "kind": "image"}
    )
    try:
        media = runner.import_media(CAMPAIGN, wav())
        with pytest.raises(TimelineError, match="Groq hosts Whisper"):
            runner.transcribe(media["id"])
    finally:
        store.close()


def test_captions_land_where_a_platform_will_not_cover_them(engine):
    """Centred vertically covers the subject; at the very bottom the platform
    draws its own caption over it."""
    project_id, _, clip = _captioned(engine)
    engine.add_captions(project_id, clip_id=clip.id)
    document = engine.open_project(project_id).project
    track = next(item for item in document.tracks if item.name == "Captions")
    offset = track.clips[0].properties["y"]
    assert 0 < offset < document.height / 2


def test_the_caption_track_is_not_where_new_pictures_land(engine):
    """Otherwise a placed picture would appear in the middle of the subtitles."""
    project_id, _, clip = _captioned(engine)
    engine.add_captions(project_id, clip_id=clip.id)
    state = engine.edit(
        project_id,
        "add_clip",
        {
            "track_id": engine.open_project(project_id).project.tracks[0].id,
            "kind": "solid",
            "start": 0,
            "duration": SECOND,
        },
    )
    captions = next(item for item in state.project.tracks if item.name == "Captions")
    assert all(item.kind == "text" for item in captions.clips)


# ── the rule that cannot be checked, and so is refused ──────────────────────


def test_audio_is_refused_for_the_classes_whose_safety_is_the_scanner():
    assert set(TRANSCRIBE_FORBIDDEN_CLASSES) == {DataClass.MAILBOX, DataClass.INTERNAL}


def test_the_broker_blocks_unscannable_classes_before_anything_is_sent():
    from offsetx_apollo_builder.ai.broker import EgressBroker, EgressRequest
    from offsetx_apollo_builder.ai.errors import EgressBlocked

    sent: list[Any] = []

    class _Registry:
        def get(self, provider_id):  # pragma: no cover - never reached
            sent.append(provider_id)
            return None

    broker = EgressBroker(registry=_Registry(), credential_resolver=lambda pid: "k")
    for data_class in TRANSCRIBE_FORBIDDEN_CLASSES:
        with pytest.raises(EgressBlocked, match="never sent as audio"):
            broker.call_transcript(
                EgressRequest(task_type="video_transcription", data_class=data_class),
                object(),
                audio=b"\x00" * 100,
            )
    # The refusal happens before a provider is even looked up.
    assert sent == []


# ── through the API ─────────────────────────────────────────────────────────


def test_media_upload_and_the_caption_refusal_work_over_http(tmp_path):
    from fastapi.testclient import TestClient

    from offsetx_apollo_builder.api.app import create_app
    from offsetx_apollo_builder.api.config import AppSettings

    settings = AppSettings(
        project_root=Path.cwd(),
        database_path=tmp_path / "outreach.db",
        data_dir=tmp_path / "data",
        export_dir=tmp_path / "exports",
        frontend_dist=tmp_path / "missing-dist",
    )
    with TestClient(create_app(settings)) as client:
        campaign = client.post("/api/v1/campaigns", json={"name": "Reels", "kind": "image"}).json()

        uploaded = client.post(
            f"/api/v1/campaigns/{campaign['id']}/video-media",
            files={"file": ("voiceover.wav", wav(seconds=5.0), "audio/wav")},
        )
        assert uploaded.status_code == 201, uploaded.text
        media = uploaded.json()
        assert media["kind"] == "audio"
        assert media["duration_ticks"] == 5 * SECOND

        listed = client.get(f"/api/v1/campaigns/{campaign['id']}/video-media").json()
        assert [item["id"] for item in listed["items"]] == [media["id"]]

        served = client.get(f"/api/v1/video-media/{media['id']}/file")
        assert served.status_code == 200
        assert served.headers["content-type"].startswith("audio/wav")

        project = client.post(
            f"/api/v1/campaigns/{campaign['id']}/video-projects", json={"name": "Cut"}
        ).json()
        placed = client.post(
            f"/api/v1/video-projects/{project['id']}/place-media",
            json={"media_id": media["id"]},
        )
        assert placed.status_code == 200, placed.text
        document = placed.json()["document"]
        audio_track = next(track for track in document["tracks"] if track["kind"] == "audio")
        clip = audio_track["clips"][0]

        # No provider is connected in a fresh workspace, so the honest answer is
        # a refusal naming what to connect — not an empty caption track.
        refused = client.post(
            f"/api/v1/video-projects/{project['id']}/captions",
            json={"clip_id": clip["id"]},
        )
        assert refused.status_code == 409, refused.text
        assert "provider" in refused.text.lower()


def test_the_api_refuses_media_it_cannot_measure(tmp_path):
    from fastapi.testclient import TestClient

    from offsetx_apollo_builder.api.app import create_app
    from offsetx_apollo_builder.api.config import AppSettings

    settings = AppSettings(
        project_root=Path.cwd(),
        database_path=tmp_path / "outreach.db",
        data_dir=tmp_path / "data",
        export_dir=tmp_path / "exports",
        frontend_dist=tmp_path / "missing-dist",
    )
    with TestClient(create_app(settings)) as client:
        campaign = client.post("/api/v1/campaigns", json={"name": "R", "kind": "image"}).json()
        refused = client.post(
            f"/api/v1/campaigns/{campaign['id']}/video-media",
            files={"file": ("song.mp3", b"\xff\xfb\x90\x00" + b"\x00" * 9000, "audio/mpeg")},
        )
        assert refused.status_code == 422
        assert "MP3" in refused.json()["detail"]


def test_footage_on_a_timeline_is_renderable_now_that_its_picture_is_drawn(engine):
    """This used to be blocked. The manifest refused to call a project with
    footage on it renderable, because the painter handled stills and nothing
    else. The browser demuxes and decodes footage now, so the block is gone —
    and it has to stay gone, which is what this asserts."""
    project = engine.create_project(CAMPAIGN, name="Reel")
    # A real container, borrowed from the muxer's own fixture.
    fixture = Path(__file__).parent / "fixtures" / "muxed_sample.webm"
    media = engine.import_media(CAMPAIGN, fixture.read_bytes(), name="clip.webm")
    assert media["kind"] == "video"
    engine.place_media(project.project.id, media_id=media["id"])
    manifest = engine.manifest(project.project.id)
    assert manifest["renderable"], manifest["warnings"]
    assert not any("not drawn" in warning for warning in manifest["warnings"])
