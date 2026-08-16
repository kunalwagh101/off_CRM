"""The video editor runner: projects, edits, and what gets exported.

```
approved picture ─┐
AI video          ├─→ timeline ──→ edits ──→ manifest ──→ browser renders ──→ gates ──→ render
generated audio  ─┘        ▲                                                              │
                           └──────────────── undo / redo ────────────────┘                ▼
                                                                             an asset the distribution
                                                                             campaign can publish
```

**Where the work happens is the design.** The browser draws and encodes,
because a canvas is already a compositor and every machine running off_CRM has
one; the server holds the document, validates every edit and checks the file
that comes back. That split is not a compromise — it is the same shape as the
rest of this project. The part with rules lives where rules can be tested, and
the part that needs a GPU lives where there is one.

**A rendered video is an asset, not an ending.** It goes into the same place an
approved picture goes, so the distribution campaign can post it without learning
anything new. The editor is a producer of assets, and the thing that already
knows how to publish assets keeps doing that.

**Which campaign owns a timeline.** The ``image`` kind, whose registry entry has
said from the day it was written that video was the thing it was missing. A
video project consumes that campaign's approved pictures and produces another
asset for it, so putting it anywhere else would mean two campaigns owning
halves of one workflow.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Mapping

from ..campaigns import assert_kind
from . import captions as captioning
from . import edits
from . import mixdown
from .gates import VideoDecodeError, VideoGateReport, probe, run_gates
from .store import VideoStore
from .timeline import (
    TICKS_PER_SECOND,
    Project,
    TimelineError,
    frame_at,
    new_project,
    ticks_per_frame,
)

#: How long a still is when it is dropped on the timeline with no length given.
#: Five seconds is long enough to read a picture and short enough that nobody
#: leaves it there by accident.
DEFAULT_STILL_TICKS = 5 * TICKS_PER_SECOND

#: Asset statuses a clip may point at. ``rejected`` is refused because the swipe
#: deletes the file — placing one would put a clip on the timeline whose picture
#: no longer exists, and the failure would not show up until export.
PLACEABLE_STATUSES = ("pending", "approved")


@dataclass
class ProjectState:
    """A project as the API returns it: the row, the document, and what can be
    done to it next."""

    record: dict[str, Any]
    project: Project
    can_undo: bool
    can_redo: bool

    def to_dict(self) -> dict[str, Any]:
        item = dict(self.record)
        item["document"] = self.project.to_dict()
        item["can_undo"] = self.can_undo
        item["can_redo"] = self.can_redo
        return item


class VideoEditorEngine:
    """Every entry point the API has into a timeline.

    ``campaign_reader`` is injected rather than imported so this module never
    reaches into the CRM's database. Same shape as the image and distribution
    runners, and the reason is the same: the moment a runner opens the CRM store
    directly, the two can no longer move separately.
    """

    def __init__(
        self,
        *,
        store: VideoStore,
        campaign_reader: Callable[[str], Mapping[str, Any]],
        asset_reader: Callable[[str], Mapping[str, Any]] | None = None,
        transcriber: Callable[..., Any] | None = None,
        workspace_id: str = "local",
    ) -> None:
        self.store = store
        self.campaign_reader = campaign_reader
        self.asset_reader = asset_reader
        #: Called with ``(audio=, media_type=, filename=, language=)`` and
        #: returning the broker's ``TranscriptResult``. Injected rather than
        #: imported so this module owns no transport and no provider knowledge —
        #: the same rule the image runner follows.
        self.transcriber = transcriber
        self.workspace_id = workspace_id

    # ── the kind gate ───────────────────────────────────────────────────────

    def _require_own_kind(self, campaign_id: str, action: str) -> None:
        assert_kind(self.campaign_reader(campaign_id), "image", action=action)

    def _campaign_of(self, project_id: str) -> str:
        return str(self.store.get_project(project_id).get("campaign_id") or "")

    # ── projects ────────────────────────────────────────────────────────────

    def create_project(
        self,
        campaign_id: str,
        *,
        name: str = "Untitled",
        preset: str = "vertical",
        fps: str = "30",
        width: int = 0,
        height: int = 0,
    ) -> ProjectState:
        self._require_own_kind(campaign_id, "creating a video project")
        project = new_project(name=name, preset=preset, fps=fps, width=width, height=height)
        record = self.store.create_project(
            project_id=project.id,
            campaign_id=campaign_id,
            document=project.to_dict(),
            workspace_id=self.workspace_id,
        )
        return ProjectState(record=record, project=project, can_undo=False, can_redo=False)

    def list_projects(self, campaign_id: str, *, limit: int = 100) -> list[dict[str, Any]]:
        self._require_own_kind(campaign_id, "listing video projects")
        return self.store.list_projects(campaign_id, limit=limit)

    def open_project(self, project_id: str) -> ProjectState:
        record = self.store.get_project(project_id)
        self._require_own_kind(str(record.get("campaign_id") or ""), "opening a video project")
        project = Project.from_dict(record["document"])
        low, high = self.store.version_bounds(project_id)
        version = int(record["version"])
        return ProjectState(
            record=record,
            project=project,
            can_undo=version > low,
            can_redo=version < high,
        )

    def delete_project(self, project_id: str) -> None:
        record = self.store.get_project(project_id)
        self._require_own_kind(str(record.get("campaign_id") or ""), "deleting a video project")
        self.store.delete_project(project_id)

    # ── editing ─────────────────────────────────────────────────────────────

    def edit(self, project_id: str, operation: str, params: Mapping[str, Any] | None = None) -> ProjectState:
        """Apply one named edit and store the result as a new version.

        The document is only written when the operation succeeded, so a refused
        edit leaves the project exactly as it was — including its version number,
        which means a rejected edit does not consume a step of undo.
        """
        state = self.open_project(project_id)
        changed = edits.apply(state.project, operation, params or {})
        changed.id = state.project.id
        record = self.store.save_version(
            project_id=project_id,
            document=changed.to_dict(),
            operation=operation,
            params=dict(params or {}),
        )
        low, high = self.store.version_bounds(project_id)
        return ProjectState(
            record=record,
            project=changed,
            can_undo=int(record["version"]) > low,
            can_redo=int(record["version"]) < high,
        )

    def batch(self, project_id: str, operations: list[Mapping[str, Any]]) -> ProjectState:
        """Apply several edits as one version.

        Dragging a clip produces a stream of moves and undo should return to
        where the drag started, not to the middle of it. The whole batch is
        validated against the document in memory before anything is stored, so a
        batch that fails halfway stores nothing.
        """
        state = self.open_project(project_id)
        working = state.project
        names: list[str] = []
        for item in operations:
            name = str(item.get("op") or item.get("operation") or "")
            working = edits.apply(working, name, item.get("params") or {})
            names.append(name)
        working.id = state.project.id
        record = self.store.save_version(
            project_id=project_id,
            document=working.to_dict(),
            operation=" + ".join(names)[:60] or "batch",
            params={"count": len(operations)},
        )
        low, high = self.store.version_bounds(project_id)
        return ProjectState(
            record=record,
            project=working,
            can_undo=int(record["version"]) > low,
            can_redo=int(record["version"]) < high,
        )

    def undo(self, project_id: str) -> ProjectState:
        self.store.get_project(project_id)
        self.store.move_version(project_id=project_id, delta=-1)
        return self.open_project(project_id)

    def redo(self, project_id: str) -> ProjectState:
        self.store.get_project(project_id)
        self.store.move_version(project_id=project_id, delta=+1)
        return self.open_project(project_id)

    def history(self, project_id: str, *, limit: int = 50) -> list[dict[str, Any]]:
        return self.store.history(project_id, limit=limit)

    # ── putting generated material on the timeline ──────────────────────────

    def place_asset(
        self,
        project_id: str,
        *,
        asset_id: str,
        track_id: str = "",
        start: int = -1,
        duration: int = 0,
    ) -> ProjectState:
        """Drop a generated picture onto the timeline.

        Reads the asset's real dimensions from the image store rather than
        trusting the caller, so a clip's crop and scale are computed against what
        the file actually is. A rejected asset is refused by name: the swipe
        deletes its bytes, and a clip pointing at a deleted file is a hole that
        would not be noticed until export.
        """
        if self.asset_reader is None:
            raise TimelineError("This engine was built without access to generated assets.")
        asset = dict(self.asset_reader(asset_id))
        status = str(asset.get("status") or "")
        if status not in PLACEABLE_STATUSES:
            raise TimelineError(
                f"Asset {asset_id!r} is {status}. A rejected picture has had its "
                "file deleted, so there is nothing to put on the timeline."
            )
        if not str(asset.get("path") or ""):
            raise TimelineError(
                f"Asset {asset_id!r} has no file on disk any more. It was "
                "discarded after it was generated."
            )

        state = self.open_project(project_id)
        track = state.project.track(track_id) if track_id else _first_track(state.project)
        at = track.duration if int(start) < 0 else max(0, int(start))
        span = int(duration) if int(duration) > 0 else DEFAULT_STILL_TICKS
        return self.edit(
            project_id,
            "add_clip",
            {
                "track_id": track.id,
                "kind": "image",
                "start": at,
                "duration": span,
                "asset_id": asset_id,
                "label": str(asset.get("model_id") or asset.get("provider_id") or "")[:120],
                "style": {
                    "source_width": int(asset.get("width") or 0),
                    "source_height": int(asset.get("height") or 0),
                    "fit": "cover",
                },
            },
        )

    # ── material that was not generated here ────────────────────────────────

    def import_media(
        self,
        campaign_id: str,
        payload: bytes,
        *,
        name: str = "",
    ) -> dict[str, Any]:
        """Take in a recording or a clip, and describe it from its header.

        This is what makes captions possible at all: nothing in off_CRM
        generates speech, so the audio has to come from somewhere, and a
        voiceover recorded in the browser is the honest answer.

        The header is read before anything is stored. A file whose length cannot
        be determined is refused rather than kept, because a clip whose
        ``source_duration`` is a guess is a clip the timeline cannot stop from
        reading past its own end.
        """
        self._require_own_kind(campaign_id, "importing media")
        try:
            found = probe(payload)
        except VideoDecodeError as exc:
            raise TimelineError(str(exc)) from exc
        if found.kind == "image":
            raise TimelineError(
                "That is a picture. Pictures come from the image campaign and its "
                "swipe, which is where their quality is judged — placing one "
                "through here would skip that."
            )
        if found.duration_ticks <= 0:
            raise TimelineError(
                "This file does not declare how long it is, so nothing can stop "
                "a clip reading past its end. Re-export it with a duration."
            )
        media_id = self.store.store_media(
            campaign_id=campaign_id,
            name=name or f"{found.kind} {found.duration_seconds:.1f}s",
            payload=payload,
            probe=found,
            workspace_id=self.workspace_id,
        )
        return self.store.get_media(media_id)

    def place_media(
        self,
        project_id: str,
        *,
        media_id: str,
        track_id: str = "",
        start: int = -1,
        duration: int = 0,
    ) -> ProjectState:
        """Put imported material on the timeline, on a track that suits it."""
        media = self.store.get_media(media_id)
        state = self.open_project(project_id)
        kind = "audio" if str(media.get("kind")) == "audio" else "video"
        if track_id:
            track = state.project.track(track_id)
        else:
            track = _first_track(state.project, "audio" if kind == "audio" else "video")
        at = track.duration if int(start) < 0 else max(0, int(start))
        span = int(duration) if int(duration) > 0 else int(media["duration_ticks"])
        return self.edit(
            project_id,
            "add_clip",
            {
                "track_id": track.id,
                "kind": kind,
                "start": at,
                "duration": span,
                "source_duration": int(media["duration_ticks"]),
                "asset_id": media_id,
                "label": str(media.get("name") or "")[:120],
                "style": {
                    "source_width": int(media.get("width") or 0),
                    "source_height": int(media.get("height") or 0),
                    "fit": "cover",
                },
            },
        )

    def media(self, campaign_id: str, *, limit: int = 100) -> list[dict[str, Any]]:
        self._require_own_kind(campaign_id, "listing media")
        return self.store.list_media(campaign_id, limit=limit)

    # ── captions ────────────────────────────────────────────────────────────

    def transcribe(
        self,
        media_id: str,
        *,
        language: str = "",
        refresh: bool = False,
    ) -> dict[str, Any]:
        """Words and their timings for one piece of media.

        A stored transcript is reused unless ``refresh`` is asked for. That is
        not the response cache — that one is keyed on a payload and refuses
        anything whose output is a message. This is a fact about a specific file
        that cannot change unless the file does, and paying twice for it would
        be paying twice for the same answer.
        """
        media = self.store.get_media(media_id)
        if not media.get("has_audio"):
            raise TimelineError(
                f"{media.get('name') or media_id} has no sound track, so there is "
                "nothing to transcribe."
            )
        if not refresh:
            stored = self.store.get_transcript(media_id, language=language)
            if stored:
                return {**stored, "reused": True}

        if self.transcriber is None:
            raise TimelineError(
                "This engine was built without a way to transcribe. Connect a "
                "provider that hosts a speech model — Groq hosts Whisper on the "
                "same key as its chat models."
            )
        path = Path(str(media.get("path") or ""))
        if not path.exists():
            raise TimelineError("That media is no longer on disk.")

        result = self.transcriber(
            audio=path.read_bytes(),
            media_type=str(media.get("media_type") or "audio/webm"),
            filename=path.name,
            language=language,
        )
        words = [word.to_dict() for word in getattr(result, "words", [])]
        self.store.store_transcript(
            media_id=media_id,
            language=language,
            provider_id=getattr(result, "provider_id", ""),
            model_id=getattr(result, "model_id", ""),
            text=getattr(result, "text", ""),
            words=words,
            log_id=getattr(result, "log_id", ""),
            workspace_id=self.workspace_id,
        )
        stored = self.store.get_transcript(media_id, language=language) or {}
        return {**stored, "reused": False}

    def add_captions(
        self,
        project_id: str,
        *,
        clip_id: str,
        language: str = "",
        style: Mapping[str, Any] | None = None,
        max_chars: int = captioning.MAX_CHARS,
        refresh: bool = False,
    ) -> dict[str, Any]:
        """Caption one clip, as ordinary text clips on a captions track.

        The result is not a special object. It is the same text clips anyone can
        add by hand, so every edit already in the editor works on them — retime
        one, restyle it, fix a misheard word, delete a line. A transcript is a
        guess about what was said, and it goes out under the owner's name, so a
        person reads it before anything is published.

        Running it twice **replaces** rather than stacks: the existing captions
        over the same span are removed in the same batch. Two layers of slightly
        different captions is not a state anyone asks for, and the overlap rule
        would refuse it anyway — with a message about tick collisions rather
        than about captions.
        """
        state = self.open_project(project_id)
        track, clip = state.project.find_clip(clip_id)
        if clip.kind not in ("video", "audio"):
            raise TimelineError(
                f"A {clip.kind} clip has no sound. Captions come from speech — "
                "select the voiceover or the footage."
            )
        if not clip.asset_id:
            raise TimelineError("That clip has no media behind it to listen to.")

        transcript = self.transcribe(clip.asset_id, language=language, refresh=refresh)
        words = captioning.words_from_transcript(transcript.get("words") or [])
        if not words:
            raise TimelineError(
                "The transcript came back with no timed words, so there is "
                "nothing to place. The recording may be silent."
            )

        cues = captioning.to_timeline(
            captioning.build_cues(words, max_chars=max_chars),
            clip,
            fps=state.project.fps,
        )
        if not cues:
            raise TimelineError(
                "Every caption fell outside what this clip actually shows. The "
                "speech is in a part of the media the clip was trimmed away from."
            )

        caption_style, y = captioning.caption_style(style, height=state.project.height)
        existing = next(
            (
                item
                for item in state.project.tracks
                if item.kind == "video" and item.name == captioning.CAPTION_TRACK_NAME
            ),
            None,
        )
        operations: list[dict[str, Any]] = []
        if existing is None:
            after = self.edit(
                project_id,
                "add_track",
                {"kind": "video", "name": captioning.CAPTION_TRACK_NAME},
            )
            caption_track = next(
                item
                for item in after.project.tracks
                if item.name == captioning.CAPTION_TRACK_NAME
            )
        else:
            caption_track = existing
            first, last = cues[0].start, cues[-1].end
            operations.extend(
                {"op": "remove_clip", "params": {"clip_id": item.id}}
                for item in existing.clips
                if item.start < last and item.start + item.duration > first
            )

        operations.extend(
            captioning.as_operations(cues, track_id=caption_track.id, style=caption_style, y=y)
        )
        final = self.batch(project_id, operations)
        return {
            **captioning.report(cues),
            "track_id": caption_track.id,
            "language": str(transcript.get("language") or language or ""),
            "provider_id": str(transcript.get("provider_id") or ""),
            "model_id": str(transcript.get("model_id") or ""),
            "reused_transcript": bool(transcript.get("reused")),
            "project": final.to_dict(),
        }

    # ── what the renderer needs ─────────────────────────────────────────────

    def resolve_asset(self, asset_id: str) -> dict[str, Any]:
        """One asset id, whichever store it came from.

        A timeline holds two kinds of material — pictures the image campaign
        generated, and recordings imported here — and a clip refers to both the
        same way. Resolving in one place means nothing else in the editor has to
        know which store an id belongs to, and adding a third source later
        touches this function alone.
        """
        try:
            media = self.store.get_media(asset_id)
        except KeyError:
            pass
        else:
            return {
                "id": asset_id,
                "source": "media",
                "path": str(media.get("path") or ""),
                "media_type": str(media.get("media_type") or ""),
                "width": int(media.get("width") or 0),
                "height": int(media.get("height") or 0),
                "duration_ticks": int(media.get("duration_ticks") or 0),
                "has_audio": bool(media.get("has_audio")),
                "status": "imported",
            }
        if self.asset_reader is None:
            raise KeyError(f"Asset not found: {asset_id}")
        asset = dict(self.asset_reader(asset_id))
        return {
            "id": asset_id,
            "source": "image",
            "path": str(asset.get("path") or ""),
            "media_type": str(asset.get("media_type") or ""),
            "width": int(asset.get("width") or 0),
            "height": int(asset.get("height") or 0),
            "duration_ticks": 0,
            "has_audio": False,
            "status": str(asset.get("status") or ""),
        }

    def manifest(self, project_id: str) -> dict[str, Any]:
        """Everything the browser needs to draw this project, and what is wrong
        with it.

        The warnings are the point. A timeline can reference a picture that was
        swiped away after it was placed, and the honest thing is to say so before
        an export runs — not to render a black rectangle and hand back a file
        that looks finished.
        """
        state = self.open_project(project_id)
        project = state.project
        assets: list[dict[str, Any]] = []
        warnings: list[str] = []
        for asset_id in project.asset_ids():
            entry: dict[str, Any] = {"id": asset_id, "available": False}
            try:
                asset = self.resolve_asset(asset_id)
            except KeyError:
                warnings.append(f"Asset {asset_id} is referenced by a clip and no longer exists.")
                assets.append(entry)
                continue
            path = str(asset.get("path") or "")
            entry.update({**asset, "available": bool(path) and Path(path).exists()})
            entry.pop("path", None)
            if not entry["available"]:
                warnings.append(
                    f"Asset {asset_id} was discarded after it was placed, so its "
                    "clip has nothing to draw."
                )
            assets.append(entry)

        if project.duration <= 0:
            warnings.append("This timeline is empty. There is nothing to export.")

        # What the export's audio track should be. Stated by the server so the
        # browser's mixer has an answer to be checked against, and so the editor
        # can say "this will clip" before a render rather than after one.
        mix = mixdown.plan(project).to_dict()
        # Deliberately not folded into ``warnings``: nothing about the sound
        # stops a file being produced, and ``renderable`` is the flag that
        # decides whether the export button works. A silent video is a bad idea,
        # not an impossible one.
        notes: list[str] = []
        if mix["silent"] and project.duration > 0:
            notes.append(
                "Nothing on this timeline makes a sound, so the export will be "
                "silent. Most platforms bury silent video."
            )
        if mix["headroom"] > 1.0:
            notes.append(
                f"Clips overlap loudly enough to sum to {mix['headroom']:.2f}, past "
                "the point where the output would distort. The export turns the "
                "whole mix down by that much to compensate — setting a clip's "
                "volume yourself keeps more of the level."
            )
        mix["notes"] = notes

        return {
            "project_id": project.id,
            "version": int(state.record["version"]),
            "name": project.name,
            "width": project.width,
            "height": project.height,
            "fps": project.fps,
            "ticks_per_frame": round(ticks_per_frame(project.fps), 6),
            "ticks_per_second": TICKS_PER_SECOND,
            "duration_ticks": project.duration,
            "duration_seconds": round(project.duration / TICKS_PER_SECOND, 3),
            "frames": project.frame_count(),
            "background": project.background,
            "assets": assets,
            "mix": mix,
            "warnings": warnings,
            "renderable": not warnings,
        }

    def frame(self, project_id: str, tick: int) -> dict[str, Any]:
        """What is on screen at one instant. The same answer the browser draws."""
        return frame_at(self.open_project(project_id).project, tick).to_dict()

    def conformance(self, project_id: str, *, samples: int = 24) -> dict[str, Any]:
        """Resolved frames at evenly spaced ticks, for checking a second
        implementation against this one.

        The browser has to resolve keyframes itself — asking the server per frame
        would be one request per 33 milliseconds — so there are two
        implementations of one rule, and two implementations drift. This is the
        fixture that catches it: the same document, the same ticks, and a
        byte-comparable answer. See ``docs/architecture/VIDEO_EDITOR.md``.
        """
        state = self.open_project(project_id)
        project = state.project
        total = max(1, project.duration)
        step = max(1, total // max(1, int(samples)))
        ticks = list(range(0, total, step))[: max(1, int(samples))]
        return {
            "document": project.to_dict(),
            "frames": [frame_at(project, tick).to_dict() for tick in ticks],
        }

    # ── the file that comes back ────────────────────────────────────────────

    def store_render(
        self,
        project_id: str,
        payload: bytes,
        *,
        renderer: str = "",
        require_video: bool = True,
    ) -> dict[str, Any]:
        """Gate an exported file and keep it.

        Checked against the project it claims to be a render of — its shape and
        its length — because those are exactly the two things a browser export
        gets wrong when something goes sideways mid-encode. A file that fails is
        stored with its report rather than thrown away: a gate result nobody can
        check the file against is an assertion, not evidence.
        """
        state = self.open_project(project_id)
        project = state.project
        # Whether the file is *required* to have sound is the project's own
        # answer, not the exporter's: the browser saying "I could not encode
        # Opus" and the server checking "does this timeline make a sound" are
        # the two halves that catch a silent export.
        report: VideoGateReport = run_gates(
            payload,
            want_width=project.width,
            want_height=project.height,
            want_duration_ticks=project.duration,
            require_video=require_video,
            require_audio=not mixdown.plan(project).silent,
            seen_hashes=self.store.render_hashes(project_id),
        )
        render_id = self.store.store_render(
            project_id=project_id,
            campaign_id=str(state.record.get("campaign_id") or ""),
            payload=payload,
            gate_report=report,
            status="ready" if report.passed else "gate_failed",
            renderer=renderer,
            project_version=int(state.record["version"]),
            workspace_id=self.workspace_id,
        )
        return {
            "render_id": render_id,
            "passed": report.passed,
            "summary": report.summary(),
            "gates": report.to_dict(),
        }

    def renders(self, project_id: str, *, limit: int = 50) -> list[dict[str, Any]]:
        return self.store.list_renders(project_id, limit=limit)

    def summary(self, campaign_id: str) -> dict[str, Any]:
        """The campaign's editing work at a glance."""
        self._require_own_kind(campaign_id, "reading the video summary")
        projects = self.store.list_projects(campaign_id, limit=200)
        renders = [render for project in projects for render in self.store.list_renders(project["id"])]
        ready = [render for render in renders if render["status"] == "ready"]
        return {
            "campaign_id": campaign_id,
            "projects": len(projects),
            "total_duration_seconds": round(
                sum(int(item["duration_ticks"]) for item in projects) / TICKS_PER_SECOND, 2
            ),
            "renders": len(renders),
            "renders_passed": len(ready),
            "renders_failed": len(renders) - len(ready),
        }


def _first_track(project: Project, kind: str = "video"):
    for track in project.tracks:
        if track.kind == kind and not track.locked:
            # Captions get their own track, and dropping new material onto it
            # would put a picture in the middle of the subtitles.
            if kind == "video" and track.name == captioning.CAPTION_TRACK_NAME:
                continue
            return track
    raise TimelineError(f"This project has no unlocked {kind} track to place a clip on.")
