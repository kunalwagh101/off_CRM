"""Write the MP4 fixtures the browser's demuxer is tested against.

The WebM side of this already exists in both directions: `frontend/src/video/
webm.ts` writes a file and `video/gates.py` reads it, so neither can drift
alone. MP4 had only one direction — the server parses headers and nothing in
this project ever wrote one.

So this does. It builds a real ISO base media file from the spec, with sample
tables chosen to be awkward in the ways real files are awkward:

* **`stsc` with three entries**, so chunks hold different numbers of samples.
  A parser that assumes a row per chunk, or one sample per chunk, passes a
  simple file and fails this one.
* **`ctts`**, so presentation order is not decode order. This is the table that
  exists because of B-frames, and getting it wrong reorders the video subtly
  enough that nobody notices until a specific clip looks wrong.
* **`stss` listing every fifth sample**, so keyframes are sparse. A decoder fed
  from the wrong place produces green mush.
* **`stts` in runs**, because that is how it is stored.
* **A second file with a version-1 `mdhd`**, which widens two timestamps to 64
  bits and moves the timescale twelve bytes later. Reading the wrong offset
  turns a five-second video into a several-hour one, and the equivalent bug in
  the MP4 *header* parser was a real one this project already made once.

The frame payloads are synthetic — sample *n* is `12 + n % 7` bytes of the value
`n & 0xff`. Nothing decodes them and nothing needs to: what is under test is the
index, which is the only part of MP4 that either side implements.

    python scripts/build_mp4_fixture.py
"""

from __future__ import annotations

import struct
import sys
from pathlib import Path

FIXTURES = Path(__file__).resolve().parents[1] / "tests" / "fixtures"

TIMESCALE = 600
SAMPLES = 24
#: How long each sample lasts, in timescale units. Two runs so `stts` is
#: genuinely run-length encoded rather than a row per sample.
DURATIONS = [20] * 12 + [25] * 12
#: Composition offsets, in the shape B-frames actually produce. Decode order
#: I P B B against display order I B B P: the P is held back two frames and the
#: two B frames are brought forward one each, so decode times 0/20/40/60 present
#: at 0/60/20/40. Negative offsets are why `ctts` has a version 1.
SHIFTS = [0, 40, -20, -20] + [0] * 20
#: Samples that can be decoded from cold, 1-based as `stss` stores them.
SYNCS = [1, 6, 11, 16, 21]
#: How many samples go in each chunk, per `stsc` entry: chunk 1 holds 4,
#: chunks 2-3 hold 6, chunks 4 on hold 8.
STSC = [(1, 4), (2, 6), (4, 8)]

IDENTITY = struct.pack(">9i", 0x10000, 0, 0, 0, 0x10000, 0, 0, 0, 0x40000000)
#: A plausible `avcC`: configuration version 1, then profile / compatibility /
#: level, which is what `avc1.640028` spells out.
AVCC = bytes([0x01, 0x64, 0x00, 0x28, 0xFF, 0xE1, 0x00, 0x04, 0x67, 0x64, 0x00, 0x28, 0x01, 0x00])


def box(tag: bytes, payload: bytes) -> bytes:
    return struct.pack(">I", len(payload) + 8) + tag + payload


def full(tag: bytes, payload: bytes, *, version: int = 0, flags: int = 0) -> bytes:
    return box(tag, bytes([version]) + flags.to_bytes(3, "big") + payload)


def sample_sizes() -> list[int]:
    return [12 + index % 7 for index in range(SAMPLES)]


def sample_payload(index: int) -> bytes:
    return bytes([index & 0xFF]) * (12 + index % 7)


def chunk_layout() -> list[list[int]]:
    """Which sample indices land in which chunk, from the `stsc` runs."""
    chunks: list[list[int]] = []
    sample = 0
    chunk = 0
    while sample < SAMPLES:
        per = STSC[0][1]
        for first, count in STSC:
            if first - 1 <= chunk:
                per = count
            else:
                break
        group = list(range(sample, min(SAMPLES, sample + per)))
        chunks.append(group)
        sample += per
        chunk += 1
    return chunks


def stbl(chunk_offsets: list[int]) -> bytes:
    sizes = sample_sizes()

    # stsd: one avc1 visual sample entry, carrying an avcC.
    avc1 = (
        b"\x00" * 6
        + struct.pack(">H", 1)  # data reference index
        + b"\x00" * 16  # pre-defined / reserved
        + struct.pack(">HH", 640, 360)  # width, height
        + struct.pack(">II", 0x00480000, 0x00480000)  # resolution, 72dpi
        + b"\x00" * 4
        + struct.pack(">H", 1)  # frame count
        + b"\x00" * 32  # compressor name
        + struct.pack(">Hh", 24, -1)  # depth, pre-defined
        + box(b"avcC", AVCC)
    )
    stsd = full(b"stsd", struct.pack(">I", 1) + box(b"avc1", avc1))

    runs: list[tuple[int, int]] = []
    for delta in DURATIONS:
        if runs and runs[-1][1] == delta:
            runs[-1] = (runs[-1][0] + 1, delta)
        else:
            runs.append((1, delta))
    stts = full(
        b"stts",
        struct.pack(">I", len(runs)) + b"".join(struct.pack(">II", count, delta) for count, delta in runs),
    )

    shift_runs: list[tuple[int, int]] = []
    for offset in SHIFTS:
        if shift_runs and shift_runs[-1][1] == offset:
            shift_runs[-1] = (shift_runs[-1][0] + 1, offset)
        else:
            shift_runs.append((1, offset))
    ctts = full(
        b"ctts",
        struct.pack(">I", len(shift_runs))
        + b"".join(struct.pack(">Ii", count, offset) for count, offset in shift_runs),
        # Version 1, because the offsets are signed. A version-0 ctts can only
        # push presentation later, which cannot express a frame that displays
        # before the one decoded ahead of it.
        version=1,
    )

    stss = full(b"stss", struct.pack(">I", len(SYNCS)) + b"".join(struct.pack(">I", n) for n in SYNCS))
    stsc = full(
        b"stsc",
        struct.pack(">I", len(STSC))
        + b"".join(struct.pack(">III", first, per, 1) for first, per in STSC),
    )
    stsz = full(b"stsz", struct.pack(">II", 0, SAMPLES) + b"".join(struct.pack(">I", n) for n in sizes))
    stco = full(
        b"stco",
        struct.pack(">I", len(chunk_offsets)) + b"".join(struct.pack(">I", n) for n in chunk_offsets),
    )
    return box(b"stbl", stsd + stts + ctts + stss + stsc + stsz + stco)


def moov(chunk_offsets: list[int], *, mdhd_version: int) -> bytes:
    total = sum(DURATIONS)
    mvhd = full(b"mvhd", struct.pack(">IIII", 0, 0, TIMESCALE, total) + b"\x00" * 76)

    tkhd = full(
        b"tkhd",
        struct.pack(">IIIII", 0, 0, 1, 0, total)
        + b"\x00" * 8
        + struct.pack(">HHHH", 0, 0, 0, 0)
        + IDENTITY
        + struct.pack(">II", 640 << 16, 360 << 16),
        flags=3,
    )

    if mdhd_version == 1:
        # Creation and modification widen to 64 bits, so the timescale moves.
        body = struct.pack(">QQIQ", 0, 0, TIMESCALE, total) + struct.pack(">HH", 0x55C4, 0)
    else:
        body = struct.pack(">IIII", 0, 0, TIMESCALE, total) + struct.pack(">HH", 0x55C4, 0)
    mdhd = full(b"mdhd", body, version=mdhd_version)

    hdlr = full(b"hdlr", struct.pack(">I", 0) + b"vide" + b"\x00" * 12 + b"Video\x00")
    vmhd = full(b"vmhd", struct.pack(">HHHH", 0, 0, 0, 0), flags=1)
    dref = full(b"dref", struct.pack(">I", 1) + full(b"url ", b"", flags=1))
    dinf = box(b"dinf", dref)
    minf = box(b"minf", vmhd + dinf + stbl(chunk_offsets))
    mdia = box(b"mdia", mdhd + hdlr + minf)
    trak = box(b"trak", tkhd + mdia)

    # A sound track, so the walk has to pick the video one rather than the first.
    sound_hdlr = full(b"hdlr", struct.pack(">I", 0) + b"soun" + b"\x00" * 12 + b"Sound\x00")
    sound_mdhd = full(b"mdhd", struct.pack(">IIII", 0, 0, 48_000, 0) + struct.pack(">HH", 0x55C4, 0))
    sound = box(b"trak", tkhd + box(b"mdia", sound_mdhd + sound_hdlr))

    return box(b"moov", mvhd + sound + trak)


def build(*, mdhd_version: int = 0) -> bytes:
    """`ftyp`, then `mdat`, then `moov` — with the offsets resolved.

    The chunk offsets are absolute positions in the finished file, so `mdat` has
    to be placed before `moov` can be written. Two passes: lay the media out,
    then build the index that points into it.
    """
    ftyp = box(b"ftyp", b"isom" + struct.pack(">I", 512) + b"isomavc1mp42")

    chunks = chunk_layout()
    media = b""
    offsets: list[int] = []
    # `mdat`'s payload starts eight bytes into the box, which itself starts
    # right after `ftyp`.
    base = len(ftyp) + 8
    for group in chunks:
        offsets.append(base + len(media))
        for index in group:
            media += sample_payload(index)
    mdat = box(b"mdat", media)
    return ftyp + mdat + moov(offsets, mdhd_version=mdhd_version)


def main() -> int:
    FIXTURES.mkdir(parents=True, exist_ok=True)
    for name, version in (("sample_tables.mp4", 0), ("sample_tables_v1.mp4", 1)):
        path = FIXTURES / name
        payload = build(mdhd_version=version)
        path.write_bytes(payload)
        print(f"wrote {path} — {len(payload)} bytes, {SAMPLES} samples, mdhd v{version}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
