"""Reading the shape of a video without a decoder, and gating an export.

Two containers, parsed by hand for the reason `imagery/gates.py` gives about
Pillow: width, height and duration are header fields, and pulling in ffmpeg to
read four integers would be a large dependency doing a small job.

**Where the fixtures come from matters.**

The WebM happy path is a file written by the real muxer in
`frontend/src/video/webm.ts`, committed at `tests/fixtures/muxed_sample.webm`
and regenerated with `npm run fixtures`. That is a genuine cross-language check:
one language writes the container, the other reads it, and neither can drift
alone. It was also confirmed against ffmpeg, which reads it as
`matroska,webm 1080x1920, 3.00s, vp9, 30fps`.

The MP4 fixtures and the awkward WebM cases are built here from the spec,
because they are the shapes no ordinary encoder produces on request — a
rotation matrix, a 64-bit header, a segment of unknown length, a file whose moov
never got written.
"""
from __future__ import annotations

import struct
from pathlib import Path

import pytest

from offsetx_apollo_builder.video.gates import (
    MIN_BYTES,
    VideoDecodeError,
    decode_media,
    probe,
    run_gates,
)
from offsetx_apollo_builder.video.timeline import TICKS_PER_SECOND

MUXED = Path(__file__).parent / "fixtures" / "muxed_sample.webm"
#: The same muxer's output with an Opus track in it, for the audio gate.
MUXED_AUDIO = Path(__file__).parent / "fixtures" / "muxed_sample_audio.webm"
SECOND = TICKS_PER_SECOND

#: The identity display matrix, in the 16.16 / 2.30 fixed point MP4 uses.
IDENTITY = struct.pack(">9i", 0x10000, 0, 0, 0, 0x10000, 0, 0, 0, 0x40000000)
#: Ninety degrees, which is how a phone records sideways and plays upright.
ROTATED = struct.pack(">9i", 0, 0x10000, 0, -0x10000, 0, 0, 0, 0, 0x40000000)


def box(tag: bytes, payload: bytes) -> bytes:
    return struct.pack(">I", 8 + len(payload)) + tag + payload


def mvhd(*, timescale: int, duration: int, version: int = 0) -> bytes:
    if version == 1:
        head = bytes([1, 0, 0, 0]) + struct.pack(">QQI Q", 0, 0, timescale, duration)
    else:
        head = bytes([0, 0, 0, 0]) + struct.pack(">IIII", 0, 0, timescale, duration)
    return box(b"mvhd", head + b"\x00" * 80)


def tkhd(*, width: int, height: int, matrix: bytes = IDENTITY, version: int = 0) -> bytes:
    if version == 1:
        head = bytes([1, 0, 0, 0]) + struct.pack(">QQIIQ", 0, 0, 1, 0, 0)
    else:
        head = bytes([0, 0, 0, 0]) + struct.pack(">IIIII", 0, 0, 1, 0, 0)
    head += b"\x00" * 8          # reserved
    head += struct.pack(">hhhh", 0, 0, 0, 0)  # layer, group, volume, reserved
    head += matrix
    head += struct.pack(">II", width << 16, height << 16)
    return box(b"tkhd", head)


def trak(*, handler: bytes, width: int = 0, height: int = 0, matrix: bytes = IDENTITY,
         version: int = 0) -> bytes:
    hdlr = box(b"hdlr", b"\x00" * 8 + handler + b"\x00" * 12)
    return box(
        b"trak",
        tkhd(width=width, height=height, matrix=matrix, version=version)
        + box(b"mdia", hdlr),
    )


def mp4(
    *,
    width: int = 1080,
    height: int = 1920,
    seconds: float = 3.0,
    timescale: int = 600,
    matrix: bytes = IDENTITY,
    version: int = 0,
    audio: bool = False,
    padding: int = 8192,
) -> bytes:
    tracks = trak(handler=b"vide", width=width, height=height, matrix=matrix, version=version)
    if audio:
        tracks += trak(handler=b"soun")
    moov = box(
        b"moov",
        mvhd(timescale=timescale, duration=int(seconds * timescale), version=version) + tracks,
    )
    # An mdat of real length, so the file is not rejected for being tiny before
    # the header is ever looked at.
    mdat = box(b"mdat", b"\x00" * padding)
    return box(b"ftyp", b"isom" + struct.pack(">I", 512) + b"isomiso2mp41") + mdat + moov


# ── EBML, for the cases no encoder writes on request ────────────────────────


def vint(value: int) -> bytes:
    width = 1
    while width < 8 and value >= 2 ** (7 * width) - 1:
        width += 1
    raw = bytearray(value.to_bytes(width, "big"))
    raw[0] |= 0x80 >> (width - 1)
    return bytes(raw)


def ebml(element_id: bytes, payload: bytes) -> bytes:
    return element_id + vint(len(payload)) + payload


def ebml_uint(element_id: bytes, value: int) -> bytes:
    raw = value.to_bytes(max(1, (value.bit_length() + 7) // 8), "big")
    return ebml(element_id, raw)


def webm(*, width: int = 1080, height: int = 1920, duration_ms: float | None = 3000,
         unknown_size: bool = False, audio_only: bool = False, silent: bool = False,
         padding: int = 8192) -> bytes:
    header = ebml(b"\x1aE\xdf\xa3", ebml(b"\x42\x82", b"webm"))
    info = ebml_uint(b"\x2a\xd7\xb1", 1_000_000)
    if duration_ms is not None:
        info += ebml(b"\x44\x89", struct.pack(">d", duration_ms))
    entries = b""
    if not audio_only:
        entries += ebml(
            b"\xae",
            ebml_uint(b"\x83", 1)
            + ebml(b"\xe0", ebml_uint(b"\xb0", width) + ebml_uint(b"\xba", height)),
        )
    if not silent:
        entries += ebml(b"\xae", ebml_uint(b"\x83", 2) + ebml(b"\xe1", ebml_uint(b"\x9f", 2)))
    body = ebml(b"\x15\x49\xa9\x66", info) + ebml(b"\x16\x54\xae\x6b", entries)
    body += ebml(b"\x1f\x43\xb6\x75", ebml_uint(b"\xe7", 0) + b"\xa3" + vint(padding) + b"\x00" * padding)
    if unknown_size:
        # A live muxer cannot know the length in advance and writes all-ones.
        return header + b"\x18\x53\x80\x67" + b"\xff" + body
    return header + ebml(b"\x18\x53\x80\x67", body)


# ── MP4 ─────────────────────────────────────────────────────────────────────


def test_dimensions_and_duration_are_read_from_the_boxes():
    found = probe(mp4(width=1080, height=1920, seconds=3.0))
    assert (found.width, found.height) == (1080, 1920)
    assert found.duration_ticks == 3 * SECOND
    assert found.media_type == "video/mp4"
    assert found.has_video and not found.has_audio


def test_a_sixty_four_bit_header_is_read_the_same_way():
    """Files over four gigabytes use version 1 boxes, and the fields move."""
    found = probe(mp4(width=1920, height=1080, seconds=2.0, version=1))
    assert (found.width, found.height) == (1920, 1080)
    assert found.duration_ticks == 2 * SECOND


def test_a_rotated_recording_reports_the_shape_it_plays_at():
    """A phone records landscape and rotates on playback. Reporting the header
    dimensions would call a portrait video landscape and fail the aspect gate
    for no reason."""
    found = probe(mp4(width=1920, height=1080, matrix=ROTATED))
    assert (found.width, found.height) == (1080, 1920)
    assert found.rotated


def test_an_audio_track_is_noticed_without_being_mistaken_for_the_video_one():
    found = probe(mp4(audio=True))
    assert found.has_video and found.has_audio
    assert (found.width, found.height) == (1080, 1920)


def test_a_file_whose_moov_was_never_written_is_refused():
    """What an interrupted encode leaves behind."""
    truncated = mp4()
    without = truncated[: truncated.find(b"moov") - 4]
    with pytest.raises(VideoDecodeError, match="no moov box"):
        probe(without)


def test_a_box_claiming_more_than_the_file_holds_stops_the_walk():
    broken = bytearray(mp4())
    index = broken.find(b"moov") - 4
    broken[index : index + 4] = struct.pack(">I", 10_000_000)
    with pytest.raises(VideoDecodeError):
        probe(bytes(broken))


# ── WebM ────────────────────────────────────────────────────────────────────


def test_the_file_the_browser_muxer_wrote_is_read_back_correctly():
    """The cross-language check. `frontend/src/video/webm.ts` wrote this."""
    found = probe(MUXED.read_bytes())
    assert found.media_type == "video/webm"
    assert (found.width, found.height) == (1080, 1920)
    assert found.duration_ticks == 3 * SECOND
    assert found.has_video and not found.has_audio


def test_a_muxed_export_clears_every_gate_against_the_project_it_came_from():
    report = run_gates(
        MUXED.read_bytes(), want_width=1080, want_height=1920, want_duration_ticks=3 * SECOND
    )
    assert report.passed, report.summary()
    assert {result.name for result in report.results} >= {
        "decodes",
        "not_empty",
        "readable_header",
        "has_video_track",
        "aspect_ratio",
        "duration_matches",
    }


def test_a_segment_of_unknown_length_still_parses():
    """What a streaming muxer writes when it cannot know the size in advance."""
    found = probe(webm(unknown_size=True))
    assert (found.width, found.height) == (1080, 1920)
    assert found.has_video


def test_display_dimensions_win_over_pixel_dimensions():
    body = webm(width=1080, height=1920)
    # Insert DisplayWidth/DisplayHeight, which is what the file asks to be
    # shown at when the two disagree.
    patched = body.replace(
        ebml_uint(b"\xb0", 1080) + ebml_uint(b"\xba", 1920),
        ebml_uint(b"\xb0", 1080)
        + ebml_uint(b"\xba", 1920)
        + ebml_uint(b"\x54\xb0", 540)
        + ebml_uint(b"\x54\xba", 960),
    )
    found = probe(patched)
    assert (found.width, found.height) == (540, 960)


def test_a_file_that_is_not_a_container_at_all_is_refused():
    with pytest.raises(VideoDecodeError, match="Unrecognised file"):
        probe(b"\x00" * 5000)


def test_a_still_goes_through_the_same_entry_point():
    """The timeline holds pictures and video, and the editor should not have to
    know which parser to reach for."""
    png = (
        b"\x89PNG\r\n\x1a\n"
        + struct.pack(">I", 13)
        + b"IHDR"
        + struct.pack(">IIBBBBB", 800, 600, 8, 2, 0, 0, 0)
        + b"\x00" * 4
    )
    found = probe(png)
    assert found.kind == "image"
    assert (found.width, found.height) == (800, 600)


# ── the gates ───────────────────────────────────────────────────────────────


def test_an_empty_container_is_caught_before_anything_else_looks_at_it():
    """A header with no frames: the encoder ran and nothing was ever painted."""
    report = run_gates(webm(padding=16), want_width=1080, want_height=1920)
    assert not report.passed
    failure = next(item for item in report.failures if item.name == "not_empty")
    assert str(MIN_BYTES) in failure.detail


def test_an_export_of_the_wrong_shape_fails_and_says_both_shapes():
    report = run_gates(mp4(width=1920, height=1080), want_width=1080, want_height=1920)
    failure = next(item for item in report.failures if item.name == "aspect_ratio")
    assert "1920x1080" in failure.detail and "1080x1920" in failure.detail


def test_an_encoder_rounding_to_its_own_size_still_passes():
    """Encoders round to macroblock multiples; 608x1080 is still 9:16."""
    report = run_gates(mp4(width=608, height=1080), want_width=1080, want_height=1920)
    assert all(item.name != "aspect_ratio" or item.passed for item in report.results)


def test_an_export_that_stopped_early_is_caught():
    report = run_gates(
        mp4(seconds=1.0), want_width=1080, want_height=1920, want_duration_ticks=10 * SECOND
    )
    failure = next(item for item in report.failures if item.name == "duration_matches")
    assert "off by" in failure.detail


def test_a_frame_or_two_of_drift_is_not_a_failure():
    """Encoders round to whole frames and a muxer may hold the last one back."""
    report = run_gates(
        mp4(seconds=3.03), want_width=1080, want_height=1920, want_duration_ticks=3 * SECOND
    )
    assert report.passed, report.summary()


def test_a_container_that_declares_no_duration_is_a_failure_not_a_pass():
    """MediaRecorder writes exactly this, which is why the exporter does not use
    it — a length that cannot be checked is not a length that was verified."""
    report = run_gates(
        webm(duration_ms=None), want_width=1080, want_height=1920, want_duration_ticks=3 * SECOND
    )
    failure = next(item for item in report.failures if item.name == "duration_matches")
    assert "no duration" in failure.detail


def test_a_file_with_no_video_track_is_not_an_export():
    report = run_gates(webm(audio_only=True), want_width=1080, want_height=1920)
    failure = next(item for item in report.failures if item.name == "has_video_track")
    assert "no video track" in failure.detail


def test_the_mp4_fixtures_are_still_what_the_builder_produces():
    """`scripts/build_mp4_fixture.py` writes the files the browser's demuxer is
    tested against, and a fixture nobody can regenerate is a fixture nobody can
    trust. This also means the server's own MP4 parser reads a file written from
    the spec by something other than itself."""
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "build_mp4_fixture", Path(__file__).parents[1] / "scripts" / "build_mp4_fixture.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    for name, version in (("sample_tables.mp4", 0), ("sample_tables_v1.mp4", 1)):
        path = Path(__file__).parent / "fixtures" / name
        assert path.read_bytes() == module.build(mdhd_version=version), (
            f"{name} is out of date — run python scripts/build_mp4_fixture.py"
        )
        found = probe(path.read_bytes())
        assert (found.width, found.height) == (640, 360)
        assert found.has_video and found.has_audio
        # 540 units of a 600Hz timescale.
        assert found.duration_ticks == int(0.9 * SECOND)


def test_the_audio_track_the_browser_muxer_wrote_is_read_back_correctly():
    """The cross-language check for Stage 4.

    `frontend/src/video/webm.ts` wrote this file with a real `opusHead()` from
    `audio.ts` as its CodecPrivate, and this parser reads the track out of it.
    Two halves of one format, written on two sides of the wire."""
    found = probe(MUXED_AUDIO.read_bytes())
    assert found.media_type == "video/webm"
    assert (found.width, found.height) == (1080, 1920)
    assert found.duration_ticks == 3 * SECOND
    assert found.has_video and found.has_audio
    assert (found.sample_rate, found.channels) == (48_000, 2)


def test_an_export_with_both_tracks_clears_every_gate():
    report = run_gates(
        MUXED_AUDIO.read_bytes(),
        want_width=1080,
        want_height=1920,
        want_duration_ticks=3 * SECOND,
        require_audio=True,
    )
    assert report.passed, report.summary()
    assert {result.name for result in report.results} >= {
        "has_video_track",
        "has_audio_track",
        "aspect_ratio",
        "duration_matches",
    }


def test_a_timeline_that_makes_a_sound_must_export_one():
    """The failure this gate exists for: a perfect picture and no sound.

    The browser can lose its audio track a dozen ways — no Opus encoder, an
    asset that would not decode, a mixer that threw — and every one of them
    still hands back a file that looks completely finished."""
    report = run_gates(
        MUXED.read_bytes(),
        want_width=1080,
        want_height=1920,
        want_duration_ticks=3 * SECOND,
        require_audio=True,
    )
    failure = next(item for item in report.failures if item.name == "has_audio_track")
    assert "no audio track" in failure.detail
    assert not report.passed


def test_an_export_with_the_sound_in_it_clears_the_gate():
    report = run_gates(webm(), want_width=1080, want_height=1920, require_audio=True)
    result = next(item for item in report.results if item.name == "has_audio_track")
    assert result.passed, result.detail


def test_a_silent_timeline_is_not_asked_for_an_audio_track():
    """A slideshow with no music is a real export, not a broken one."""
    report = run_gates(
        webm(silent=True), want_width=1080, want_height=1920, want_duration_ticks=3 * SECOND
    )
    assert report.passed, report.summary()
    assert not any(item.name == "has_audio_track" for item in report.results)


def test_the_same_bytes_twice_is_caught():
    data = MUXED.read_bytes()
    first = run_gates(data)
    report = run_gates(data, seen_hashes={first.sha256})
    failure = next(item for item in report.failures if item.name == "not_duplicate")
    assert "byte-identical" in failure.detail


def test_a_broken_upload_is_a_failed_gate_and_never_an_exception():
    """One bad export must not abort a batch."""
    report = run_gates(b"not a video at all")
    assert not report.passed
    assert report.failures


def test_raw_bytes_and_a_data_uri_are_both_accepted():
    import base64

    data = MUXED.read_bytes()
    declared, payload = decode_media(data)
    assert declared == "" and payload == data
    uri = "data:video/webm;base64," + base64.b64encode(data).decode()
    declared, payload = decode_media(uri)
    assert declared == "video/webm" and payload == data


def test_a_provider_url_is_refused_rather_than_fetched():
    with pytest.raises(VideoDecodeError, match="raw bytes or a data: URI"):
        decode_media("https://example.com/video.mp4")


def test_a_lie_about_the_media_type_is_reported():
    import base64

    uri = "data:video/mp4;base64," + base64.b64encode(MUXED.read_bytes()).decode()
    report = run_gates(uri)
    failure = next(item for item in report.failures if item.name == "type_matches")
    assert "video/webm" in failure.detail


def test_wav_files_written_by_the_standard_library_are_read_exactly():
    """An independent implementation of the format, checked both ways.

    ``wave`` is stdlib and knows nothing about this parser. Sample rate,
    channel count and duration all have to come back exactly, because a
    duration that is nearly right puts every caption slightly out of place.
    """
    import io
    import wave as wave_module

    for rate, channels, seconds in ((44100, 2, 1.5), (16000, 1, 3.0), (48000, 2, 0.25)):
        buffer = io.BytesIO()
        with wave_module.open(buffer, "wb") as handle:
            handle.setnchannels(channels)
            handle.setsampwidth(2)
            handle.setframerate(rate)
            handle.writeframes(b"\x00" * (rate * channels * 2 * 4))
            handle.writeframes(b"\x11" * int(rate * channels * 2 * (seconds - 4 / rate * rate)))
        buffer.seek(0)
        with wave_module.open(io.BytesIO(buffer.getvalue()), "rb") as check:
            expected = check.getnframes() / check.getframerate()
        found = probe(buffer.getvalue())
        assert found.kind == "audio"
        assert found.sample_rate == rate
        assert found.channels == channels
        assert found.duration_seconds == pytest.approx(expected, abs=0.001)


def test_a_wav_with_no_format_chunk_describes_nothing_and_is_refused():
    body = b"data" + struct.pack("<I", 8) + b"\x00" * 8
    broken = b"RIFF" + struct.pack("<I", 4 + len(body)) + b"WAVE" + body
    with pytest.raises(VideoDecodeError, match="no format chunk"):
        probe(broken)


def test_a_container_with_sound_and_no_picture_is_audio_whatever_it_claims():
    """An .m4a is an MP4. Calling it video would put it on a video track, where
    it would draw nothing."""
    audio_only = mp4(audio=True)
    stripped = audio_only.replace(b"vide", b"soun", 1)
    found = probe(stripped)
    assert found.kind == "audio"
    assert found.media_type == "audio/mp4"
    assert found.has_audio and not found.has_video
