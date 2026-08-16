"""The audio mix, as a plan the browser can execute exactly.

The timeline has resolved gain per clip per instant since the day it was
written, and the export has thrown all of it away: every file off_CRM produced
so far is silent. Platforms bury silent video, so this is not a missing extra —
it is the difference between an export that can be posted and one that cannot.

---

**Why a plan rather than samples.**

The obvious approach is to ask the resolver what the gain is and write a sample.
At 48kHz that is forty-eight thousand resolver calls a second, to produce a
number that changes a few times across a whole clip. It would also mean a second
mixing implementation in Python that nothing ever runs, since the audio is
assembled in the browser where the decoder lives.

So this module produces an **envelope**: the points at which each clip's gain
changes, in the clip's own time. WebAudio applies exactly that shape with
``setValueAtTime`` and ``linearRampToValueAtTime``, which is what a ``GainNode``
is for. The arithmetic that decides the shape stays here, testable and offline;
the sample-pushing stays where the samples are.

**Where the envelope is dense and where it is not.**

Between two keyframes the gain is a straight line, and a straight line needs its
two ends and nothing in between. Only two things bend it: an eased keyframe
segment, and a fade — which is itself linear, but *multiplies* the volume curve,
so a fade over a ramp is a product of two lines and therefore a curve. Those
stretches, and only those, are sampled on a 100Hz grid, and whatever turns out
straight anyway is collapsed back to its endpoints.

**What is deliberately not here.** Ducking, compression, EQ, normalisation. Each
is a real feature and each changes what the mix *sounds* like rather than what
it *is*; putting them in before the plain mix works would mean debugging two
things at once. :func:`headroom` reports the number ducking would act on, so the
export can at least be honest about clipping in the meantime.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .timeline import TICKS_PER_SECOND, Clip, Project, Track, clip_gain

#: How finely a curved stretch of an envelope is sampled. A gain change is
#: inaudible as a discontinuity below about 20ms; 10ms is comfortably under
#: that and still produces small envelopes.
ENVELOPE_HZ = 100
ENVELOPE_STEP = TICKS_PER_SECOND // ENVELOPE_HZ  # 900 ticks

#: Two gains this close are the same gain to a listener — about a thousandth of
#: a decibel. Used to drop sampled points that a straight line would have passed
#: through anyway, which is most of a linear fade.
ENVELOPE_TOLERANCE = 1e-4

#: Below this a clip contributes nothing anyone can hear, and including it costs
#: a fetch and a decode. -60dB.
SILENCE = 0.001

#: What the mix is rendered at. 48kHz is what Opus wants and what every browser
#: gives; resampling once at the end is cheaper than resampling every source.
SAMPLE_RATE = 48_000
CHANNELS = 2

#: Clip kinds that can carry sound. A still or a caption cannot.
AUDIBLE_KINDS = ("audio", "video")


@dataclass
class MixClip:
    """One audible clip, and the shape of its gain over its own length."""

    clip_id: str
    asset_id: str
    kind: str
    #: Where it sits on the timeline.
    start: int
    duration: int
    #: Where it reads from inside its own material, and how fast.
    in_point: int
    speed: float
    #: ``(at, gain)`` in the clip's own time, always starting at 0 and ending at
    #: ``duration``. WebAudio ramps linearly between consecutive points.
    envelope: list[tuple[int, float]] = field(default_factory=list)

    @property
    def peak(self) -> float:
        return max((gain for _, gain in self.envelope), default=0.0)

    @property
    def end(self) -> int:
        return self.start + self.duration

    def gain_at(self, offset: int) -> float:
        """The envelope's own reading at ``offset``, interpolated as WebAudio
        will interpolate it."""
        return _interpolate(self.envelope, offset)

    def to_dict(self) -> dict[str, Any]:
        return {
            "clip_id": self.clip_id,
            "asset_id": self.asset_id,
            "kind": self.kind,
            "start": self.start,
            "duration": self.duration,
            "in_point": self.in_point,
            "speed": round(self.speed, 6),
            "envelope": [[at, round(gain, 6)] for at, gain in self.envelope],
        }


@dataclass
class MixPlan:
    """Everything the browser needs to render the audio, and nothing else."""

    duration_ticks: int = 0
    sample_rate: int = SAMPLE_RATE
    channels: int = CHANNELS
    clips: list[MixClip] = field(default_factory=list)
    #: Assets that have to be fetched and decoded before rendering, in the order
    #: they are first heard.
    asset_ids: list[str] = field(default_factory=list)

    @property
    def silent(self) -> bool:
        """Whether there is anything to render at all.

        A silent plan is not a failure — a slideshow with no music is a real
        thing to export. It is the signal that the muxer should be given no
        audio track rather than an empty one.
        """
        return not self.clips

    def to_dict(self) -> dict[str, Any]:
        return {
            "duration_ticks": self.duration_ticks,
            "duration_seconds": round(self.duration_ticks / TICKS_PER_SECOND, 6),
            "sample_rate": self.sample_rate,
            "channels": self.channels,
            "silent": self.silent,
            "headroom": round(headroom(self), 6),
            "clips": [item.to_dict() for item in self.clips],
            "asset_ids": list(self.asset_ids),
        }


def _dense_spans(clip: Clip) -> list[tuple[int, int]]:
    """The stretches of this clip whose gain is not a straight line.

    Two things bend it. A fade, because it multiplies whatever the volume curve
    is doing — flat times a ramp is still a ramp, but a ramp times a ramp is a
    parabola, and this cannot tell which without looking, so it samples both and
    lets the simplifier throw away the one that turned out straight. And an
    eased keyframe, whose whole purpose is to not be a straight line.
    """
    spans: list[tuple[int, int]] = []
    if clip.fade_in > 0:
        spans.append((0, min(clip.fade_in, clip.duration)))
    if clip.fade_out > 0:
        spans.append((max(0, clip.duration - clip.fade_out), clip.duration))
    frames = sorted(clip.keyframes.get("volume", []), key=lambda item: item.at)
    for left, right in zip(frames, frames[1:]):
        if left.easing != "linear" and left.value != right.value:
            spans.append((max(0, left.at), min(clip.duration, right.at)))
    return [(start, end) for start, end in spans if end > start]


def _sample_points(clip: Clip) -> list[int]:
    """Every offset at which this clip's gain is worth asking about."""
    points = {0, clip.duration}
    # The corners: where a fade starts or stops, and where a keyframe sits.
    if clip.fade_in > 0:
        points.add(min(clip.fade_in, clip.duration))
    if clip.fade_out > 0:
        points.add(max(0, clip.duration - clip.fade_out))
    for frame in clip.keyframes.get("volume", []):
        if 0 < frame.at < clip.duration:
            points.add(frame.at)
    for start, end in _dense_spans(clip):
        points.update(range(start, end, ENVELOPE_STEP))
        points.add(end)
    return sorted(point for point in points if 0 <= point <= clip.duration)


def _on_line(left: tuple[int, float], right: tuple[int, float], point: tuple[int, float]) -> bool:
    (left_at, left_gain), (right_at, right_gain) = left, right
    at, gain = point
    span = right_at - left_at
    if span <= 0:
        return abs(gain - left_gain) <= ENVELOPE_TOLERANCE
    expected = left_gain + (right_gain - left_gain) * ((at - left_at) / span)
    return abs(gain - expected) <= ENVELOPE_TOLERANCE


def _simplify(points: list[tuple[int, float]]) -> list[tuple[int, float]]:
    """Drop every point a straight line would have passed through anyway.

    A one-second fade sampled at 100Hz is a hundred points describing a line,
    and WebAudio draws that line from its two ends. Each dropped point is
    checked against the line from the last *kept* point rather than from its
    neighbour, so a shallow curve cannot be walked away from one tolerance at a
    time.
    """
    if len(points) <= 2:
        return list(points)
    kept = [points[0]]
    pending: list[tuple[int, float]] = []
    for point in points[1:]:
        if all(_on_line(kept[-1], point, item) for item in pending):
            pending.append(point)
            continue
        kept.append(pending[-1])
        pending = [point]
    if pending:
        kept.append(pending[-1])
    return kept


def envelope_for(track: Track, clip: Clip) -> list[tuple[int, float]]:
    """The points at which this clip's gain changes.

    Always begins at 0 and ends at ``duration``, so the browser never has to
    guess what happens at the edges. The end is read at ``duration`` itself and
    not one tick earlier, which is how a fade-out arrives at exactly zero on the
    cut rather than at a hundredth of full volume.
    """
    if clip.duration <= 0:
        return []
    sampled = [(at, clip_gain(track, clip, at)) for at in _sample_points(clip)]
    return _simplify(sampled)


def audible_clips(project: Project) -> list[tuple[Track, Clip]]:
    """Every clip that could make a sound.

    A **video** clip counts: it carries its own audio, and although its picture
    cannot be drawn yet, ``decodeAudioData`` reads the sound out of the same
    container quite happily. Silent video is the thing platforms punish, so
    leaving footage out of the mix because its picture is unfinished would be
    the wrong half to keep.
    """
    found: list[tuple[Track, Clip]] = []
    for track in project.tracks:
        if track.muted:
            continue
        for clip in track.clips:
            if clip.kind not in AUDIBLE_KINDS or not clip.asset_id:
                continue
            found.append((track, clip))
    return found


def plan(project: Project) -> MixPlan:
    """The whole mix, ready to hand to the browser.

    Clips whose gain never rises above silence are dropped rather than rendered
    at zero — each one costs a fetch and a decode to contribute nothing.
    """
    result = MixPlan(duration_ticks=project.duration)
    for track, clip in audible_clips(project):
        envelope = envelope_for(track, clip)
        if not envelope:
            continue
        item = MixClip(
            clip_id=clip.id,
            asset_id=clip.asset_id,
            kind=clip.kind,
            start=clip.start,
            duration=clip.duration,
            in_point=clip.in_point,
            speed=clip.speed,
            envelope=envelope,
        )
        if item.peak <= SILENCE:
            continue
        result.clips.append(item)

    result.clips.sort(key=lambda item: (item.start, item.clip_id))
    seen: list[str] = []
    for item in result.clips:
        if item.asset_id not in seen:
            seen.append(item.asset_id)
    result.asset_ids = seen
    return result


def headroom(plan: MixPlan) -> float:
    """The worst-case sum of gains at any instant.

    Two clips at full volume sum to 2.0 and the output clips. Reporting the
    number lets the export say so instead of producing a distorted file and
    calling it done, and it is the number an auto-ducking feature would later
    act on.

    Checked at every envelope point of every overlapping clip rather than at
    clip boundaries only: two crossfading clips are loudest in the middle of the
    crossfade, which is not an edge of anything.
    """
    if not plan.clips:
        return 0.0
    moments: set[int] = set()
    for item in plan.clips:
        moments.add(item.start)
        moments.add(item.end)
        for at, _ in item.envelope:
            moments.add(item.start + at)
    worst = 0.0
    for moment in sorted(moments):
        total = sum(
            item.gain_at(moment - item.start)
            for item in plan.clips
            if item.start <= moment < item.end
        )
        worst = max(worst, total)
    return worst


def _interpolate(envelope: list[tuple[int, float]], offset: int) -> float:
    if not envelope:
        return 0.0
    if offset <= envelope[0][0]:
        return envelope[0][1]
    if offset >= envelope[-1][0]:
        return envelope[-1][1]
    for (left_at, left_gain), (right_at, right_gain) in zip(envelope, envelope[1:]):
        if left_at <= offset <= right_at:
            span = right_at - left_at
            if span <= 0:
                return right_gain
            return left_gain + (right_gain - left_gain) * ((offset - left_at) / span)
    return envelope[-1][1]
