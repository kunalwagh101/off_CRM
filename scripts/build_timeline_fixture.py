"""Regenerate the timeline conformance fixture.

The browser resolves keyframes itself — asking the server what is on screen once
per frame would be a request every 33 milliseconds — so there are two
implementations of one rule. Two implementations drift, and the way that drift
shows up is the worst kind: the preview looks right, the export does not match
it, and nothing failed.

This writes ``tests/fixtures/timeline_conformance.json``: one document, and the
resolved frame at a spread of ticks through it. Both test suites assert against
that file — ``tests/test_video_timeline.py`` and
``frontend/src/video/resolve.test.ts`` — so whichever side moves, a test fails.

Run it **deliberately**, when the resolver's behaviour is meant to change:

    python scripts/build_timeline_fixture.py

Then read the diff. A change to this file is a change to what every existing
project looks like when it is played back, so it should be small and explained.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from offsetx_apollo_builder.video import edits, mixdown  # noqa: E402
from offsetx_apollo_builder.video.timeline import (  # noqa: E402
    TICKS_PER_SECOND,
    Project,
    frame_at,
    new_project,
)

FIXTURE = Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "timeline_conformance.json"

#: Ticks the fixture samples. Chosen rather than evenly spaced: the interesting
#: instants in a timeline are its boundaries, and an even spread walks straight
#: past every one of them.
SAMPLE_TICKS = [
    0,          # the very first frame
    1,          # one tick in, where a fade has barely begun
    22500,      # 0.25s, inside the first fade
    45000,      # 0.5s
    67500,      # a quarter second before the cut: the transition has begun
    89999,      # the tick before a cut
    90000,      # the cut itself, where the half-open interval decides
    90001,      # the tick after
    112499,     # the last tick of the transition window
    112500,     # one past it: only the second clip remains
    135000,     # 1.5s, mid-animation on the second clip
    180000,     # 2s, where the overlay starts
    225000,     # 2.5s, two video tracks and audio all live
    270000,     # 3s
    315000,     # 3.5s, inside the tail fade
    359999,     # the last tick of the timeline
    360000,     # one past the end: everything must be gone
    450000,     # well past the end
]


def build() -> Project:
    """A document that exercises everything the resolver can do.

    Deliberately awkward: overlapping tracks, a hidden one, a muted one, a
    slowed clip whose source time is not its timeline time, every easing, and
    fades that meet in the middle of a clip.
    """
    project = new_project(name="Conformance", preset="vertical", fps="30")
    project.id = "vp_conformance"
    base, audio = project.tracks[0], project.tracks[1]
    base.id, base.name = "track_base", "Base"
    audio.id, audio.name = "track_audio", "Audio"

    project = edits.add_track(project, kind="video", name="Overlay")
    project.tracks[2].id = "track_overlay"
    project = edits.add_track(project, kind="video", name="Hidden")
    project.tracks[3].id = "track_hidden"

    # Base track: a still, then a slowed video, back to back.
    project = edits.add_clip(
        project,
        track_id="track_base",
        kind="image",
        start=0,
        duration=90000,
        asset_id="asset_still",
        label="still",
    )
    project.tracks[0].clips[0].id = "clip_still"

    project = edits.add_clip(
        project,
        track_id="track_base",
        kind="video",
        start=90000,
        duration=270000,
        in_point=45000,
        source_duration=900000,
        asset_id="asset_clip",
        speed=0.5,
        label="slowed",
    )
    project.tracks[0].clips[1].id = "clip_slow"

    # Overlay: a text clip with every easing in one property.
    project = edits.add_clip(
        project,
        track_id="track_overlay",
        kind="text",
        start=180000,
        duration=135000,
        text="Conformance",
        style={"font": "Inter", "size": 72, "colour": "#ffffff", "stroke": 4},
    )
    project.tracks[2].clips[0].id = "clip_text"

    # Hidden track: visible in the document, invisible on screen, and its clip
    # must still appear in the frame with opacity zero rather than vanish.
    project = edits.add_clip(
        project,
        track_id="track_hidden",
        kind="solid",
        start=0,
        duration=360000,
        style={"colour": "#ff0055"},
    )
    project.tracks[3].clips[0].id = "clip_hidden"
    project = edits.set_track(project, track_id="track_hidden", hidden=True)

    # Audio: fades at both ends, and a volume ramp in the middle.
    project = edits.add_clip(
        project,
        track_id="track_audio",
        kind="audio",
        start=0,
        duration=360000,
        source_duration=600000,
        asset_id="asset_music",
    )
    project.tracks[1].clips[0].id = "clip_music"
    project = edits.set_fade(project, clip_id="clip_music", fade_in=45000, fade_out=45000)

    for name, at, value, easing in (
        ("scale", 0, 1.0, "ease_out"),
        ("scale", 90000, 1.25, "linear"),
        ("opacity", 0, 0.0, "ease_in"),
        ("opacity", 45000, 1.0, "hold"),
        ("opacity", 90000, 1.0, "linear"),
    ):
        project = edits.add_keyframe(
            project, clip_id="clip_still", name=name, at=at, value=value, easing=easing
        )
    for name, at, value, easing in (
        ("x", 0, -200.0, "ease_in_out"),
        ("x", 135000, 200.0, "linear"),
        ("rotation", 0, 0.0, "ease_in"),
        ("rotation", 135000, 15.0, "linear"),
    ):
        project = edits.add_keyframe(
            project, clip_id="clip_text", name=name, at=at, value=value, easing=easing
        )
    project = edits.add_keyframe(
        project, clip_id="clip_music", name="volume", at=90000, value=0.4, easing="ease_out"
    )
    project = edits.add_keyframe(
        project, clip_id="clip_music", name="volume", at=270000, value=1.0, easing="linear"
    )
    project = edits.set_property(project, clip_id="clip_slow", name="saturation", value=0.3)
    project = edits.add_marker(project, at=90000, label="cut", colour="#ffcc00")

    # A transition across the cut at 90000. Both clips are drawn for a quarter
    # second either side of it, which is the one case where the resolver returns
    # a clip outside its own bounds — so the browser has to agree about it.
    project = edits.add_transition(
        project, clip_id="clip_still", preset="wipe_left", duration=45000, side="after"
    )
    project.tracks[0].transitions[0] = type(project.tracks[0].transitions[0])(
        id="xt_cut",
        from_clip_id="clip_still",
        to_clip_id="clip_slow",
        preset="wipe_left",
        duration=45000,
    )

    # A blend mode and an applied animation, so the style fields the painter
    # reads are exercised rather than assumed.
    project = edits.set_blend_mode(project, clip_id="clip_text", mode="screen")
    project = edits.apply_animation(project, clip_id="clip_text", preset="pop_in", duration=22500)
    return project


def main() -> int:
    project = build()
    payload = {
        "ticks_per_second": TICKS_PER_SECOND,
        "document": project.to_dict(),
        "frames": [frame_at(project, tick).to_dict() for tick in SAMPLE_TICKS],
        # The export's audio. Pinned here for the same reason the frames are:
        # the mix is planned twice, once in Python and once in the browser, and
        # a silent divergence would mean an exported file whose sound does not
        # match the preview that was approved.
        "mix": mixdown.plan(project).to_dict(),
    }
    FIXTURE.parent.mkdir(parents=True, exist_ok=True)
    FIXTURE.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        f"wrote {FIXTURE} — {len(payload['frames'])} frames, "
        f"{len(payload['mix']['clips'])} mixed clips, duration {project.duration} ticks"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
