"""Deterministic gates for a rendered video, and the header parsing they need.

The image runner's gates answer "is this a picture at all, and is it the shape I
asked for". These answer the same question one dimension further along, because
a video has a length and a picture does not — and length is where a browser
export goes wrong. An encoder that stops early, a canvas that was never painted,
a stream that muxed no video track: all three produce a file that opens without
complaint and is not the video anybody made.

**No ffmpeg, no decoder.** Width, height, duration and track list are header
fields, and both containers that matter put them somewhere findable. MP4 is a
tree of length-prefixed boxes; WebM is EBML, which is the same idea with
variable-length integers. Walking those two trees is this file. Decoding a
frame would need a codec; reading the shape of the file does not, and the shape
is what a gate is for.

This is the same call ``imagery/gates.py`` made about Pillow, for the same
reason: two hundred lines of exact parsing against a large dependency that would
be pulled in to read four integers.

**What is deliberately not a gate: whether the edit is any good.** That is the
owner's judgement, and the swipe already collects it.
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import re
import struct
from dataclasses import dataclass, field
from typing import Any

from ..imagery.gates import GateResult, ImageDecodeError, image_size
from .timeline import TICKS_PER_SECOND

#: A video below this is not a video. An empty WebM — a container with a header
#: and no frames — lands around a kilobyte, and that is exactly the failure this
#: catches: an export where the encoder ran and nothing was ever painted.
MIN_BYTES = 4096

#: How far the exported length may drift from the timeline's. Encoders round to
#: whole frames and a muxer may hold the last one back, so an exact match is not
#: a fair test. Two frames at 30fps is 6000 ticks; the proportional term takes
#: over on anything longer than about ten seconds.
DURATION_TOLERANCE_TICKS = 6000
DURATION_TOLERANCE_RATIO = 0.02

#: Same tolerance the image gates use, and for the same reason: encoders round
#: to macroblock multiples, so 1080x1920 can come back as 1080x1920 and 608x1080
#: is still 9:16.
ASPECT_TOLERANCE = 0.05

_DATA_URI = re.compile(r"^data:(?P<media>[\w./+-]+);base64,(?P<payload>.*)$", re.DOTALL)

#: EBML element ids, kept with their marker bits so they compare directly
#: against what the parser reads.
_EBML_HEADER = 0x1A45DFA3
_SEGMENT = 0x18538067
_INFO = 0x1549A966
_TIMECODE_SCALE = 0x2AD7B1
_DURATION = 0x4489
_TRACKS = 0x1654AE6B
_TRACK_ENTRY = 0xAE
_TRACK_TYPE = 0x83
_VIDEO = 0xE0
_AUDIO = 0xE1
_PIXEL_WIDTH = 0xB0
_PIXEL_HEIGHT = 0xBA
_DISPLAY_WIDTH = 0x54B0
_DISPLAY_HEIGHT = 0x54BA

#: EBML containers this parser descends into. Anything else is skipped whole,
#: which is what keeps a 200MB file's Clusters from being walked to read a
#: header that lives in the first few kilobytes.
_EBML_CONTAINERS = (_SEGMENT, _INFO, _TRACKS, _TRACK_ENTRY, _VIDEO, _AUDIO)


class VideoDecodeError(ValueError):
    """The file is not a video this build can read the shape of."""


@dataclass
class MediaProbe:
    """What a file turned out to be, read from its header alone."""

    #: "video", "audio" or "image". A container with sound and no picture is
    #: audio whatever its extension claims, because putting it on a video track
    #: would draw nothing.
    kind: str = ""
    media_type: str = ""
    width: int = 0
    height: int = 0
    duration_ticks: int = 0
    has_video: bool = False
    has_audio: bool = False
    rotated: bool = False
    sample_rate: int = 0
    channels: int = 0

    @property
    def duration_seconds(self) -> float:
        return self.duration_ticks / TICKS_PER_SECOND

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "media_type": self.media_type,
            "width": self.width,
            "height": self.height,
            "duration_ticks": self.duration_ticks,
            "duration_seconds": round(self.duration_seconds, 3),
            "has_video": self.has_video,
            "has_audio": self.has_audio,
            "rotated": self.rotated,
            "sample_rate": self.sample_rate,
            "channels": self.channels,
        }


@dataclass
class VideoGateReport:
    """Every gate run against one rendered file."""

    results: list[GateResult] = field(default_factory=list)
    probe: MediaProbe = field(default_factory=MediaProbe)
    sha256: str = ""
    bytes: int = 0

    @property
    def passed(self) -> bool:
        return all(item.passed for item in self.results)

    @property
    def failures(self) -> list[GateResult]:
        return [item for item in self.results if not item.passed]

    def summary(self) -> str:
        if self.passed:
            return (
                f"{self.probe.width}x{self.probe.height} "
                f"{self.probe.media_type}, {self.probe.duration_seconds:.2f}s, "
                "all gates passed"
            )
        return "; ".join(f"{item.name}: {item.detail}" for item in self.failures)

    def to_dict(self) -> dict[str, Any]:
        return {
            "passed": self.passed,
            "sha256": self.sha256,
            "bytes": self.bytes,
            "probe": self.probe.to_dict(),
            "results": [item.to_dict() for item in self.results],
        }


def decode_media(value: str | bytes) -> tuple[str, bytes]:
    """Accept a data: URI or raw bytes, and return a declared type and payload.

    The browser posts the export as raw bytes because base64 costs a third more
    on a file that can be tens of megabytes. The data: URI form is kept because
    a generated video from a model arrives the same way a generated picture
    does, and one function should read both.
    """
    if isinstance(value, (bytes, bytearray, memoryview)):
        payload = bytes(value)
        if not payload:
            raise VideoDecodeError("The upload was empty.")
        return "", payload
    match = _DATA_URI.match(str(value or "").strip())
    if not match:
        raise VideoDecodeError(
            "Expected raw bytes or a data: URI. A provider URL is not accepted — "
            "off_CRM stores the file, so it cannot expire or track."
        )
    try:
        payload = base64.b64decode(match.group("payload"), validate=True)
    except (binascii.Error, ValueError) as exc:
        raise VideoDecodeError(f"The base64 payload did not decode: {exc}") from exc
    if not payload:
        raise VideoDecodeError("The video was empty.")
    return match.group("media"), payload


def probe(data: bytes) -> MediaProbe:
    """Read the shape of a file from its header. Fails closed.

    Handles video containers here and delegates stills to the image gates, which
    already parse PNG, JPEG, GIF and WebP by hand. One entry point matters
    because the timeline holds both: a still on a video track is an ordinary
    clip, and the editor should not need to know which parser to reach for.
    """
    if len(data) >= 12 and data[4:8] == b"ftyp":
        return _probe_mp4(data)
    if data[:4] == struct.pack(">I", _EBML_HEADER):
        return _probe_webm(data)
    if data[:4] == b"RIFF" and data[8:12] == b"WAVE":
        return _probe_wav(data)
    try:
        width, height, media_type = image_size(data)
    except (ImageDecodeError, IndexError, struct.error) as exc:
        raise VideoDecodeError(
            "Unrecognised file. MP4/MOV, WebM and WAV are understood for video "
            "and audio, and PNG, JPEG, GIF and WebP for stills. MP3 is not: its "
            "length cannot be read from a header, only by counting every frame "
            f"in the file. ({exc})"
        ) from exc
    return MediaProbe(kind="image", media_type=media_type, width=width, height=height)


def _probe_wav(data: bytes) -> MediaProbe:
    """RIFF/WAVE, which is what an uncompressed voiceover arrives as.

    Duration comes from the data chunk's size over the byte rate — exact, and
    the reason WAV is worth supporting when MP3 is not: an MP3's length can only
    be had by walking every frame in the file.
    """
    result = MediaProbe(kind="audio", media_type="audio/wav", has_audio=True)
    index = 12
    byte_rate = 0
    while index + 8 <= len(data):
        tag = data[index : index + 4]
        (size,) = struct.unpack("<I", data[index + 4 : index + 8])
        body = index + 8
        if tag == b"fmt " and body + 16 <= len(data):
            channels, sample_rate, rate = struct.unpack("<HII", data[body + 2 : body + 12])
            byte_rate = rate
            result.sample_rate = int(sample_rate)
            result.channels = int(channels)
        elif tag == b"data":
            usable = min(size, max(0, len(data) - body))
            if byte_rate:
                result.duration_ticks = int(round(usable * TICKS_PER_SECOND / byte_rate))
            break
        index = body + size + (size % 2)  # chunks are word-aligned
    if not result.sample_rate:
        raise VideoDecodeError("This WAV has no format chunk, so it describes nothing.")
    return result


# ── MP4: a tree of length-prefixed boxes ────────────────────────────────────


def _boxes(data: bytes, start: int, end: int):
    """Walk one level of the box tree, yielding (type, payload_start, payload_end).

    A box is a 32-bit size, a four-character type and a payload. Size 1 means the
    real size is a 64-bit field after the type — that is how files over 4GB are
    written — and size 0 means the box runs to the end of the file.
    """
    index = start
    while index + 8 <= end:
        size = struct.unpack(">I", data[index : index + 4])[0]
        kind = data[index + 4 : index + 8]
        body = index + 8
        if size == 1:
            if body + 8 > end:
                return
            size = struct.unpack(">Q", data[body : body + 8])[0]
            body += 8
        elif size == 0:
            size = end - index
        if size < 8 or index + size > end:
            return
        yield kind, body, index + size
        index += size


def _find_box(data: bytes, start: int, end: int, path: tuple[bytes, ...]):
    """Follow a path like (b"moov", b"mvhd") down the tree."""
    if not path:
        return None
    for kind, body, stop in _boxes(data, start, end):
        if kind != path[0]:
            continue
        if len(path) == 1:
            return body, stop
        found = _find_box(data, body, stop, path[1:])
        if found:
            return found
    return None


def _probe_mp4(data: bytes) -> MediaProbe:
    result = MediaProbe(kind="video", media_type="video/mp4")
    moov = _find_box(data, 0, len(data), (b"moov",))
    if not moov:
        raise VideoDecodeError(
            "This MP4 has no moov box, so it carries no description of itself. "
            "That is what a file looks like when the encoder was interrupted "
            "before it finished writing."
        )
    moov_start, moov_end = moov

    mvhd = _find_box(data, moov_start, moov_end, (b"mvhd",))
    if mvhd:
        body, _ = mvhd
        version = data[body]
        if version == 1:
            timescale = struct.unpack(">I", data[body + 20 : body + 24])[0]
            duration = struct.unpack(">Q", data[body + 24 : body + 32])[0]
        else:
            timescale = struct.unpack(">I", data[body + 12 : body + 16])[0]
            duration = struct.unpack(">I", data[body + 16 : body + 20])[0]
        if timescale:
            result.duration_ticks = int(round(duration * TICKS_PER_SECOND / timescale))

    for kind, body, stop in _boxes(data, moov_start, moov_end):
        if kind != b"trak":
            continue
        handler = _find_box(data, body, stop, (b"mdia", b"hdlr"))
        handler_type = data[handler[0] + 8 : handler[0] + 12] if handler else b""
        if handler_type == b"soun":
            result.has_audio = True
            continue
        if handler_type and handler_type != b"vide":
            continue
        if result.has_video:
            continue
        tkhd = _find_box(data, body, stop, (b"tkhd",))
        if not tkhd:
            continue
        head = tkhd[0]
        version = data[head]
        # The version-1 header widens creation, modification and duration to
        # 64 bits — twelve bytes more before the display matrix. Getting this
        # wrong reads the matrix as part of the volume field and reports a
        # rotation that is not there.
        matrix = head + (52 if version == 1 else 40)
        width = struct.unpack(">I", data[matrix + 36 : matrix + 40])[0] >> 16
        height = struct.unpack(">I", data[matrix + 40 : matrix + 44])[0] >> 16
        # The display matrix is how a phone records sideways and plays upright.
        # A rotation of 90 or 270 degrees puts a zero in the top-left, and the
        # dimensions in the header are pre-rotation — reporting those would call
        # a portrait video landscape and fail the aspect gate for no reason.
        term_a = struct.unpack(">i", data[matrix : matrix + 4])[0]
        term_b = struct.unpack(">i", data[matrix + 4 : matrix + 8])[0]
        if term_a == 0 and term_b != 0:
            width, height = height, width
            result.rotated = True
        if width and height:
            result.has_video = True
            result.width, result.height = int(width), int(height)

    if not result.has_video and not result.has_audio:
        raise VideoDecodeError("This MP4 declares no tracks at all.")
    if not result.has_video:
        # An .m4a is an MP4 with only a sound track. Calling it video would put
        # it on a video track, where it would draw nothing.
        result.kind = "audio"
        result.media_type = "audio/mp4"
    return result


# ── WebM: EBML, which is the same idea with variable-length integers ────────


def _vint(data: bytes, index: int, *, keep_marker: bool) -> tuple[int, int]:
    """Read one variable-length integer, returning its value and the next index.

    The first byte's leading zero count gives the width. Element ids keep the
    marker bit (the id *is* those bytes); sizes strip it, because there the
    marker only says how long the field is.
    """
    if index >= len(data):
        raise VideoDecodeError("WebM ended in the middle of a number.")
    first = data[index]
    if first == 0:
        raise VideoDecodeError("WebM has a number wider than eight bytes.")
    length = 1
    mask = 0x80
    while not first & mask:
        mask >>= 1
        length += 1
    if index + length > len(data):
        raise VideoDecodeError("WebM ended in the middle of a number.")
    value = int.from_bytes(data[index : index + length], "big")
    if not keep_marker:
        value &= (1 << (7 * length)) - 1
        # All ones is EBML's "unknown length", used by live muxers that cannot
        # know the size in advance. It means "to the end of the parent".
        if value == (1 << (7 * length)) - 1:
            return -1, index + length
    return value, index + length


def _ebml_uint(data: bytes, start: int, end: int) -> int:
    return int.from_bytes(data[start:end], "big") if end > start else 0


def _ebml_float(data: bytes, start: int, end: int) -> float:
    width = end - start
    if width == 4:
        return float(struct.unpack(">f", data[start:end])[0])
    if width == 8:
        return float(struct.unpack(">d", data[start:end])[0])
    return 0.0


def _probe_webm(data: bytes) -> MediaProbe:
    result = MediaProbe(kind="video", media_type="video/webm")
    #: Nanoseconds per timecode unit. One millisecond is the WebM default and
    #: the value every browser's MediaRecorder writes.
    scale = 1_000_000
    raw_duration = 0.0
    display: tuple[int, int] = (0, 0)
    pixels: tuple[int, int] = (0, 0)
    track_kind = 0

    def walk(start: int, end: int) -> None:
        nonlocal scale, raw_duration, display, pixels, track_kind
        index = start
        while index < end:
            try:
                element, index = _vint(data, index, keep_marker=True)
                size, index = _vint(data, index, keep_marker=False)
            except VideoDecodeError:
                return
            stop = end if size < 0 else min(end, index + size)
            if element in _EBML_CONTAINERS:
                walk(index, stop)
            elif element == _TIMECODE_SCALE:
                scale = _ebml_uint(data, index, stop) or scale
            elif element == _DURATION:
                raw_duration = _ebml_float(data, index, stop)
            elif element == _TRACK_TYPE:
                track_kind = _ebml_uint(data, index, stop)
                if track_kind == 1:
                    result.has_video = True
                elif track_kind == 2:
                    result.has_audio = True
            elif element == _PIXEL_WIDTH:
                pixels = (_ebml_uint(data, index, stop), pixels[1])
            elif element == _PIXEL_HEIGHT:
                pixels = (pixels[0], _ebml_uint(data, index, stop))
            elif element == _DISPLAY_WIDTH:
                display = (_ebml_uint(data, index, stop), display[1])
            elif element == _DISPLAY_HEIGHT:
                display = (display[0], _ebml_uint(data, index, stop))
            index = stop

    # Skip the EBML header and walk the Segment, which is where everything is.
    index = 0
    while index < len(data):
        element, next_index = _vint(data, index, keep_marker=True)
        size, next_index = _vint(data, next_index, keep_marker=False)
        stop = len(data) if size < 0 else min(len(data), next_index + size)
        if element == _SEGMENT:
            walk(next_index, stop)
            break
        if element != _EBML_HEADER:
            raise VideoDecodeError("This WebM does not begin with an EBML header.")
        index = stop

    # DisplayWidth wins when present: it is what the file asks to be shown at,
    # and PixelWidth can differ on anisotropic content.
    result.width, result.height = display if all(display) else pixels
    if raw_duration > 0:
        result.duration_ticks = int(round(raw_duration * scale * TICKS_PER_SECOND / 1_000_000_000))
    if not result.has_video and not result.has_audio:
        raise VideoDecodeError("This WebM declares no tracks at all.")
    if not result.has_video:
        # What the browser's own recorder produces for a voiceover.
        result.kind = "audio"
        result.media_type = "audio/webm"
    return result


# ── the gates ───────────────────────────────────────────────────────────────


def run_gates(
    media: str | bytes,
    *,
    want_width: int = 0,
    want_height: int = 0,
    want_duration_ticks: int = 0,
    require_video: bool = True,
    seen_hashes: set[str] | None = None,
    min_bytes: int = MIN_BYTES,
) -> VideoGateReport:
    """Check one rendered file. Never raises — a broken file is a failed gate.

    Same contract as the image gates: raising would make one bad export abort a
    batch when the right answer is to record why it failed and keep going.
    """
    report = VideoGateReport()
    try:
        declared, payload = decode_media(media)
    except VideoDecodeError as exc:
        report.results.append(GateResult("decodes", False, str(exc)))
        return report

    report.bytes = len(payload)
    report.sha256 = hashlib.sha256(payload).hexdigest()
    report.results.append(GateResult("decodes", True, f"{len(payload)} bytes"))

    if len(payload) < min_bytes:
        report.results.append(
            GateResult(
                "not_empty",
                False,
                f"{len(payload)} bytes is below {min_bytes}. A container this "
                "small holds a header and no frames — the encoder ran and "
                "nothing was ever painted.",
            )
        )
    else:
        report.results.append(GateResult("not_empty", True))

    try:
        found = probe(payload)
        report.probe = found
        report.results.append(
            GateResult(
                "readable_header",
                True,
                f"{found.media_type} {found.width}x{found.height} "
                f"{found.duration_seconds:.2f}s",
            )
        )
    except VideoDecodeError as exc:
        report.results.append(GateResult("readable_header", False, str(exc)))
        return report

    if declared and found.media_type and declared != found.media_type:
        report.results.append(
            GateResult(
                "type_matches",
                False,
                f"declared {declared} but the header says {found.media_type}",
            )
        )

    if require_video:
        if found.has_video:
            report.results.append(GateResult("has_video_track", True))
        else:
            report.results.append(
                GateResult(
                    "has_video_track",
                    False,
                    "the file muxed no video track. This is an audio file with a "
                    "video extension, not an export.",
                )
            )

    if want_width and want_height:
        wanted = want_width / want_height
        actual = found.width / found.height if found.height else 0.0
        drift = abs(actual - wanted) / wanted if wanted else 1.0
        if drift <= ASPECT_TOLERANCE:
            report.results.append(
                GateResult("aspect_ratio", True, f"{actual:.3f} vs {wanted:.3f}")
            )
        else:
            report.results.append(
                GateResult(
                    "aspect_ratio",
                    False,
                    f"exported {found.width}x{found.height} ({actual:.3f}), the "
                    f"project is {want_width}x{want_height} ({wanted:.3f})",
                )
            )

    if want_duration_ticks > 0:
        if found.duration_ticks <= 0:
            report.results.append(
                GateResult(
                    "duration_matches",
                    False,
                    "the container declares no duration. A fragmented or "
                    "unfinalised file does this, and it will not seek properly "
                    "wherever it is posted.",
                )
            )
        else:
            allowed = max(
                DURATION_TOLERANCE_TICKS,
                int(want_duration_ticks * DURATION_TOLERANCE_RATIO),
            )
            drift = abs(found.duration_ticks - want_duration_ticks)
            detail = (
                f"{found.duration_seconds:.2f}s against a timeline of "
                f"{want_duration_ticks / TICKS_PER_SECOND:.2f}s"
            )
            if drift <= allowed:
                report.results.append(GateResult("duration_matches", True, detail))
            else:
                report.results.append(
                    GateResult(
                        "duration_matches",
                        False,
                        f"{detail} — off by {drift / TICKS_PER_SECOND:.2f}s. The "
                        "export stopped somewhere other than the end of the edit.",
                    )
                )

    if seen_hashes is not None:
        if report.sha256 in seen_hashes:
            report.results.append(
                GateResult(
                    "not_duplicate",
                    False,
                    "byte-identical to a render already stored for this project",
                )
            )
        else:
            report.results.append(GateResult("not_duplicate", True))

    return report
