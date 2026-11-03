"""Deterministic quality gates for generated images.

Layer one of the three-layer benchmark in ``docs/architecture/CAMPAIGN_TYPES.md``:
rules that cannot be wrong and never have an off day. They run before a human
sees anything, so the owner's attention is spent on pictures that are at least
*valid* — and, more importantly, so the swipe that follows means something. A
reject that only says "this came back broken" is not a judgement about taste,
and mixing the two would poison the signal the whole benchmark rests on.

**Bounded full decoding.** A header is not proof of a usable image.
Pillow verifies the file and decodes its pixels before it enters review.
Encoded size, dimensions and total pixels are bounded before allocation.

What is deliberately *not* a gate: whether the picture is any good. A model
scoring its own output is unrepeatable and unauditable, and it is the same
mistake as letting a model enforce policy. That judgement is the owner's swipe,
and after a few hundred of them it is a real benchmark. These gates only remove
the candidates that were never in the running.
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import io
import re
import struct
from dataclasses import dataclass, field
from typing import Any

from PIL import Image

#: Smaller than this and the "image" is a placeholder, an error page, or the
#: flat grey some models return when they give up. Not a quality judgement —
#: a picture this small has no content at all.
MIN_BYTES = 1024

#: How far a returned aspect ratio may drift from the one asked for. Generators
#: round to their own supported sizes, so 16:9 can come back as 1024x576
#: (1.7778) or 1152x648 — the same ratio — while a square is a different answer
#: to the question.
ASPECT_TOLERANCE = 0.05

# Bound memory before base64 decoding and native pixel decoding.
MAX_IMAGE_BYTES = 16 * 1024 * 1024
MAX_IMAGE_PIXELS = 16_777_216
MAX_IMAGE_SIDE = 8192
_MAX_BASE64_CHARS = ((MAX_IMAGE_BYTES + 2) // 3) * 4
_IMAGE_FORMATS = {
    "PNG": "image/png",
    "JPEG": "image/jpeg",
    "GIF": "image/gif",
    "WEBP": "image/webp",
}

_DATA_URI = re.compile(r"^data:(?P<media>[\w./+-]+);base64,(?P<payload>.*)$", re.DOTALL)


class ImageDecodeError(ValueError):
    """The generator returned something that is not a usable image."""


@dataclass(frozen=True)
class GateResult:
    """One gate, and whether this candidate cleared it."""

    name: str
    passed: bool
    detail: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {"name": self.name, "passed": self.passed, "detail": self.detail}


@dataclass
class GateReport:
    """Every gate run against one candidate."""

    results: list[GateResult] = field(default_factory=list)
    width: int = 0
    height: int = 0
    media_type: str = ""
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
            return f"{self.width}x{self.height} {self.media_type}, all gates passed"
        return "; ".join(f"{item.name}: {item.detail}" for item in self.failures)

    def to_dict(self) -> dict[str, Any]:
        return {
            "passed": self.passed,
            "width": self.width,
            "height": self.height,
            "media_type": self.media_type,
            "sha256": self.sha256,
            "bytes": self.bytes,
            "results": [item.to_dict() for item in self.results],
        }


def decode_data_uri(value: str) -> tuple[str, bytes]:
    """Decode only bounded inline images, never a remote URL."""
    if not isinstance(value, str) or len(value) > _MAX_BASE64_CHARS + 100:
        raise ImageDecodeError("Image payload exceeds the 16 MiB limit.")
    match = _DATA_URI.fullmatch(value.strip())
    if not match:
        raise ImageDecodeError(
            "Expected an inline base64 image. Check that the generator "
            "returned a complete data URI."
        )
    media_type = match.group("media").lower()
    if media_type == "image/jpg":
        media_type = "image/jpeg"
    if media_type not in _IMAGE_FORMATS.values():
        raise ImageDecodeError("Unsupported image type; use PNG, JPEG, GIF or WebP.")
    encoded = match.group("payload")
    if len(encoded) > _MAX_BASE64_CHARS:
        raise ImageDecodeError("Image payload exceeds the 16 MiB limit.")
    try:
        payload = base64.b64decode(encoded, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise ImageDecodeError("The base64 image payload is invalid.") from exc
    if not payload:
        raise ImageDecodeError("The image was empty.")
    if len(payload) > MAX_IMAGE_BYTES:
        raise ImageDecodeError("Image payload exceeds the 16 MiB limit.")
    return media_type, payload


def image_size(data: bytes) -> tuple[int, int, str]:
    """Lightweight media-header probe for video/timeline routing only.

    A plausible header is not proof of a valid image. The image approval gate
    must call _fully_decode_image, never this metadata-only routine.
    """
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        if len(data) < 24 or data[12:16] != b"IHDR":
            raise ImageDecodeError("PNG header is truncated or malformed.")
        width, height = struct.unpack(">II", data[16:24])
        return int(width), int(height), "image/png"

    if data[:2] == b"\xff\xd8":
        return (*_jpeg_size(data), "image/jpeg")

    if data[:6] in (b"GIF87a", b"GIF89a"):
        if len(data) < 10:
            raise ImageDecodeError("GIF dimensions are truncated.")
        width, height = struct.unpack("<HH", data[6:10])
        return int(width), int(height), "image/gif"

    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return (*_webp_size(data), "image/webp")

    raise ImageDecodeError(
        "Unrecognised image format. PNG, JPEG, GIF and WebP are understood; "
        "anything else is refused rather than guessed at."
    )


def _jpeg_size(data: bytes) -> tuple[int, int]:
    """Walk JPEG segments to the frame header.

    JPEG has no fixed offset — the dimensions live in whichever start-of-frame
    marker the encoder used, after any number of metadata segments, so the
    segment chain has to be walked.
    """
    index = 2
    length = len(data)
    while index + 9 < length:
        if data[index] != 0xFF:
            index += 1
            continue
        marker = data[index + 1]
        # Start-of-frame markers, excluding the four that are not frames.
        if 0xC0 <= marker <= 0xCF and marker not in (0xC4, 0xC8, 0xCC):
            height, width = struct.unpack(">HH", data[index + 5 : index + 9])
            return int(width), int(height)
        if marker in (0xD8, 0x01) or 0xD0 <= marker <= 0xD7:
            index += 2
            continue
        segment = struct.unpack(">H", data[index + 2 : index + 4])[0]
        index += 2 + segment
    raise ImageDecodeError("JPEG has no start-of-frame segment.")


def _webp_size(data: bytes) -> tuple[int, int]:
    chunk = data[12:16]
    if chunk == b"VP8X":
        width = int.from_bytes(data[24:27], "little") + 1
        height = int.from_bytes(data[27:30], "little") + 1
        return width, height
    if chunk == b"VP8 ":
        width = struct.unpack("<H", data[26:28])[0] & 0x3FFF
        height = struct.unpack("<H", data[28:30])[0] & 0x3FFF
        return width, height
    if chunk == b"VP8L":
        bits = int.from_bytes(data[21:25], "little")
        return (bits & 0x3FFF) + 1, ((bits >> 14) & 0x3FFF) + 1
    raise ImageDecodeError("WebP variant not recognised.")


def _fully_decode_image(data: bytes) -> tuple[int, int, str]:
    """Full pixel validation for generated images; not a media-header probe.

    Pillow verifies the container and loads the actual raster, with hard limits
    checked before allocating pixel buffers. Invalid pictures cannot reach
    the owner's review queue even if their dimension headers look plausible.
    """
    if len(data) > MAX_IMAGE_BYTES:
        raise ImageDecodeError("Image payload exceeds the 16 MiB limit.")
    try:
        with Image.open(io.BytesIO(data)) as source:
            kind = _IMAGE_FORMATS.get(str(source.format or "").upper())
            if kind is None:
                raise ImageDecodeError("Unsupported image type.")
            width, height = source.size
            if (
                width < 1
                or height < 1
                or width > MAX_IMAGE_SIDE
                or height > MAX_IMAGE_SIDE
                or width * height > MAX_IMAGE_PIXELS
            ):
                raise ImageDecodeError("Image dimensions exceed the safe pixel limit.")
            if getattr(source, "n_frames", 1) != 1:
                raise ImageDecodeError("Animated images are not supported.")
            source.verify()
        with Image.open(io.BytesIO(data)) as decoded:
            decoded.load()
        return int(width), int(height), kind
    except ImageDecodeError:
        raise
    except Exception as exc:  # noqa: BLE001 - untrusted native decoder boundary
        raise ImageDecodeError(
            "The image is corrupt, incomplete or cannot be fully decoded."
        ) from exc


def run_gates(
    image: str,
    *,
    want_width: int = 0,
    want_height: int = 0,
    seen_hashes: set[str] | None = None,
    min_bytes: int = MIN_BYTES,
) -> GateReport:
    """Check one candidate. Never raises — a broken image is a failed gate.

    Raising here would make one bad candidate abort a whole batch, when the
    right answer is to drop that candidate and keep the others.
    """
    report = GateReport()
    try:
        claimed_type, payload = decode_data_uri(image)
    except ImageDecodeError as exc:
        report.results.append(GateResult("decodes", False, str(exc)))
        return report

    report.bytes = len(payload)
    report.sha256 = hashlib.sha256(payload).hexdigest()
    if len(payload) < min_bytes:
        report.results.append(
            GateResult(
                "not_blank",
                False,
                f"{len(payload)} bytes is below {min_bytes}; this is a placeholder, "
                "not a picture",
            )
        )
    else:
        report.results.append(GateResult("not_blank", True))

    try:
        width, height, detected = _fully_decode_image(payload)
        if claimed_type != detected:
            raise ImageDecodeError(
                "The declared image type does not match the decoded image."
            )
    except ImageDecodeError as exc:
        report.results.append(GateResult("decodes", False, str(exc)))
        return report

    report.width, report.height = width, height
    report.media_type = detected
    report.results.append(GateResult("decodes", True, f"{len(payload)} decoded bytes"))
    report.results.append(GateResult("readable_header", True, f"{width}x{height}"))

    if want_width and want_height:
        wanted = want_width / want_height
        actual = width / height if height else 0.0
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
                    f"got {width}x{height} ({actual:.3f}), asked for "
                    f"{want_width}x{want_height} ({wanted:.3f})",
                )
            )

    if seen_hashes is not None:
        if report.sha256 in seen_hashes:
            report.results.append(
                GateResult(
                    "not_duplicate",
                    False,
                    "byte-identical to a candidate already produced for this brief",
                )
            )
        else:
            report.results.append(GateResult("not_duplicate", True))

    return report
