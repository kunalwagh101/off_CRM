"""Effects and filters: 48 pixel operations in code, a catalogue of looks as data.

The registry that makes the largest part of an editor searchable. CapCut's eight
hundred filters written as eight hundred implementations would be eight hundred
units of work and eight hundred things an orchestrator cannot rank; written over
a small set of operations they are one code change per operation and one row per
look.

Four properties are protected here.

**Amount zero is a guaranteed no-op.** Every scaling parameter declares the
value at which its primitive does nothing, and a strength slider interpolates
from there. If that ever stops holding, every "apply at 30%" in the product is
quietly wrong and nothing else would catch it.

**Structural parameters do not interpolate.** Half a kaleidoscope fold is not a
weaker fold, it is a different picture — so segment counts, mirror axes and
colours pass through untouched whatever the strength.

**Default-deny.** An unlisted primitive or look is refused by name. A registry
that fell back to "no effect" would export something nobody chose and look like
it had worked.

**The names match the shaders.** Every primitive here has a program in
`frontend/src/video/shaders/glsl.ts` and every parameter arrives as a uniform of
the same name. That correspondence is checked by reading the TypeScript, because
nothing else would notice a rename on one side.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

from offsetx_apollo_builder.video import effects as fx

GLSL = Path(__file__).resolve().parents[1] / "frontend" / "src" / "video" / "shaders" / "glsl.ts"


# ── the registry ────────────────────────────────────────────────────────────


def test_every_primitive_declares_a_group_a_note_and_a_cost():
    for item in fx.PRIMITIVES.values():
        assert item.group in fx.PRIMITIVE_GROUPS, f"{item.id} is in no group"
        assert len(item.note) > 20, f"{item.id} has no explanation"
        assert item.passes >= 1


def test_every_look_belongs_to_a_pack_and_names_only_real_primitives():
    for look in fx.EFFECTS.values():
        assert look.pack in fx.EFFECT_PACKS, f"{look.id} is in no pack"
        assert look.steps, f"{look.id} does nothing"
        for step in look.steps:
            assert step.primitive in fx.PRIMITIVES, f"{look.id} names {step.primitive}"


def test_every_look_resolves_and_names_only_real_parameters():
    """The one that catches a typo in a hundred rows of data. A parameter a
    primitive does not have is refused rather than ignored."""
    for effect_id in fx.EFFECTS:
        fx.resolve(effect_id)


def test_the_catalogue_is_large_enough_to_be_worth_searching():
    """Not an arbitrary bar — the point of the registry is that an orchestrator
    has something to choose between."""
    assert len(fx.PRIMITIVES) >= 40
    assert len(fx.EFFECTS) >= 100
    assert len({look.pack for look in fx.EFFECTS.values()}) == len(fx.EFFECT_PACKS)


def test_ids_and_labels_are_unique():
    labels = [look.label for look in fx.EFFECTS.values()]
    assert len(set(labels)) == len(labels), "two looks share a name"


# ── strength ────────────────────────────────────────────────────────────────


def test_strength_zero_is_a_no_op_for_every_look_in_the_catalogue():
    """The property the whole strength slider rests on. Checked over all 124
    rather than over a sample: one look whose parameter forgot its neutral is
    one "apply at 30%" that does something at 0%."""
    for effect_id in fx.EFFECTS:
        for step in fx.resolve(effect_id, amount=0.0):
            spec = fx.PRIMITIVES[step["primitive"]]
            for name, value in step["numbers"].items():
                neutral = spec.numbers[name][3]
                if neutral is None:
                    continue
                assert value == pytest.approx(neutral), (
                    f"{effect_id} → {step['primitive']}.{name} is {value} at strength 0, "
                    f"but does nothing only at {neutral}"
                )


def test_strength_interpolates_linearly_between_nothing_and_the_look():
    full = fx.resolve("mono_contrast", amount=1.0)[1]["numbers"]["amount"]
    half = fx.resolve("mono_contrast", amount=0.5)[1]["numbers"]["amount"]
    assert half == pytest.approx(full / 2)


def test_a_structural_parameter_is_not_weakened_by_a_low_strength():
    """Three segments is not half of six; it is a different picture."""
    weak = fx.resolve_stack([
        {"primitive": "kaleidoscope", "amount": 0.2, "params": {"segments": 8}}
    ])[0]
    assert weak["numbers"]["segments"] == 8
    assert weak["numbers"]["amount"] == pytest.approx(0.2)


def test_a_colour_is_not_interpolated_by_strength_either():
    faint = fx.resolve("duotone" if "duotone" in fx.EFFECTS else "risograph", amount=0.1)
    tinted = [step for step in faint if step["colours"]][0]
    assert all(value.startswith("#") for value in tinted["colours"].values())


def test_strength_is_clamped_rather_than_trusted():
    assert fx.resolve("mono", amount=9.0)[0]["numbers"]["amount"] == 1.0
    assert fx.resolve("mono", amount=-4.0)[0]["numbers"]["amount"] == 0.0


# ── default-deny ────────────────────────────────────────────────────────────


def test_a_look_nobody_declared_is_refused_by_name():
    with pytest.raises(fx.UnknownEffect, match="make_it_cinematic"):
        fx.resolve("make_it_cinematic")


def test_a_primitive_nobody_implemented_is_refused_with_the_real_list():
    with pytest.raises(fx.UnknownPrimitive) as caught:
        fx.resolve_primitive("deepfry")
    assert "grayscale" in str(caught.value), "the refusal names what does exist"


def test_a_parameter_a_primitive_does_not_have_is_refused_rather_than_ignored():
    """Silently ignoring it is how a knob does nothing and nobody finds out."""
    with pytest.raises(ValueError, match="no parameter 'radius'"):
        fx.resolve_primitive("saturation", {"radius": 4})


def test_an_override_no_step_in_the_look_accepts_is_refused():
    with pytest.raises(ValueError, match="no step with a 'segments' parameter"):
        fx.resolve("mono", params={"segments": 6})


def test_an_override_reaches_the_step_that_has_that_parameter():
    widened = fx.resolve("glow", params={"radius": 60})
    assert widened[0]["primitive"] == "bloom"
    assert widened[0]["numbers"]["radius"] == 60


def test_a_reference_must_name_exactly_one_of_preset_or_primitive():
    for ref in ({}, {"preset": "mono", "primitive": "blur"}):
        with pytest.raises(ValueError, match="exactly one"):
            fx.resolve_stack([ref])


def test_numbers_are_clamped_to_the_range_the_primitive_declares():
    huge = fx.resolve_stack([{"primitive": "blur", "params": {"radius": 9999}}])[0]
    assert huge["numbers"]["radius"] == fx.PRIMITIVES["blur"].numbers["radius"][2]


def test_a_colour_that_is_not_a_colour_is_refused():
    with pytest.raises(ValueError, match="hex colour"):
        fx.resolve_stack([{"primitive": "vignette", "params": {"colour": "dark"}}])


def test_a_short_hex_colour_is_expanded_so_the_renderer_never_sees_one():
    step = fx.resolve_stack([{"primitive": "vignette", "params": {"colour": "#0Af"}}])[0]
    assert step["colours"]["colour"] == "#00aaff"


def test_a_stack_deeper_than_the_ceiling_is_refused_with_the_number():
    stack = [{"primitive": "invert"} for _ in range(fx.MAX_STEPS_PER_CLIP + 1)]
    with pytest.raises(ValueError, match=str(fx.MAX_STEPS_PER_CLIP)):
        fx.resolve_stack(stack)


def test_a_stack_may_mix_looks_and_bare_primitives():
    """What lets an orchestrator compose something the catalogue does not name,
    without being able to invent an operation the renderer cannot run."""
    chain = fx.resolve_stack([
        {"preset": "noir", "amount": 0.8},
        {"primitive": "pixelate", "params": {"size": 24}},
    ])
    assert [step["primitive"] for step in chain][-1] == "pixelate"
    assert len(chain) == len(fx.effect("noir").steps) + 1


# ── the shaders on the other side ───────────────────────────────────────────


def _glsl_programs() -> dict[str, tuple[set[str], set[str]]]:
    """Parse `PROGRAMS` out of the TypeScript: id → (numbers, colours).

    Reading the other language rather than trusting a list written twice. A
    primitive renamed on one side and not the other is exactly the kind of drift
    that only shows up as a clip quietly losing its filter.
    """
    text = GLSL.read_text(encoding="utf-8")
    # Cut at the object's own closing brace: what follows it is the two Sets,
    # and their contents would otherwise be read as one more program's colours.
    body = text.split("export const PROGRAMS", 1)[1].split("\n};", 1)[0]
    found: dict[str, tuple[set[str], set[str]]] = {}
    # `  name: shader(` … then the two array literals that close the call.
    for match in re.finditer(r"^  ([a-z_]+): shader\(", body, re.M):
        name = match.group(1)
        tail = body[match.end():]
        end = tail.find("\n  )")
        chunk = tail[: end if end >= 0 else len(tail)]
        arrays = re.findall(r"\[([^\]]*)\]", chunk.split("`", 2)[-1])
        parsed = [
            {piece.strip().strip('"') for piece in group.split(",") if piece.strip()}
            for group in arrays
        ]
        numbers = parsed[0] if parsed else set()
        colours = parsed[1] if len(parsed) > 1 else set()
        found[name] = (numbers, colours)
    return found


def test_every_primitive_has_a_shader_on_the_other_side():
    programs = _glsl_programs()
    missing = sorted(set(fx.PRIMITIVES) - set(programs))
    assert not missing, f"declared with no shader: {missing}"


def test_no_shader_exists_for_something_the_registry_never_declared():
    """The other direction. A program nobody can reach is dead code that looks
    like a feature."""
    programs = _glsl_programs()
    extra = sorted(set(programs) - set(fx.PRIMITIVES))
    assert not extra, f"shaders for undeclared primitives: {extra}"


def test_every_parameter_arrives_as_a_uniform_of_the_same_name():
    """Nothing translates between the two files, so nothing can translate them
    differently — but only if the names actually match."""
    programs = _glsl_programs()
    for item in fx.PRIMITIVES.values():
        numbers, colours = programs[item.id]
        assert set(item.numbers) == numbers, f"{item.id} numbers differ from its shader"
        assert set(item.colours) == colours, f"{item.id} colours differ from its shader"


def test_no_shader_shadows_a_glsl_builtin_it_also_calls():
    """A uniform called `mix` compiles until something below it calls `mix()`,
    and then the whole program fails at run time on somebody else's machine.
    This is the check that found exactly that during the build."""
    text = GLSL.read_text(encoding="utf-8")
    builtins = ("mix", "step", "dot", "length", "clamp", "smoothstep", "texture", "abs")
    for name in builtins:
        assert f"uniform float {name};" not in text, f"a uniform named {name} shadows {name}()"
        assert f"uniform vec3 {name};" not in text, f"a uniform named {name} shadows {name}()"


def test_no_shader_body_contains_a_backtick_or_a_template_hole():
    """Both terminate the template literal the shader lives in, and the failure
    is a TypeScript parse error hundreds of lines from the cause."""
    text = GLSL.read_text(encoding="utf-8")
    for block in re.findall(r"`(#version 300 es.*?)`", text, re.S):
        assert "${" not in block, "a shader contains a template hole"


# ── what a document stores ──────────────────────────────────────────────────


def test_a_stored_reference_is_the_name_and_never_the_resolution():
    """A document holds the name of a look, so improving the look improves every
    project that used it — and a timeline stays a few hundred bytes."""
    entry = fx.normalise({"preset": "noir", "amount": 0.7, "params": {}})
    assert entry == {"preset": "noir", "amount": 0.7, "params": {}}
    assert "primitive" not in entry


def test_normalising_clamps_the_strength_and_refuses_an_unknown_name():
    assert fx.normalise({"preset": "mono", "amount": 5})["amount"] == 1.0
    with pytest.raises(fx.UnknownEffect):
        fx.normalise({"preset": "nope", "amount": 1})


def test_the_catalogue_endpoint_carries_what_a_screen_needs_to_draw_a_slider():
    catalogue = fx.catalogue()
    blur = next(item for item in catalogue["primitives"] if item["id"] == "blur")
    assert blur["numbers"]["radius"] == {
        "default": 8.0, "min": 0.0, "max": 200.0, "neutral": 0.0, "scales": True
    }
    assert blur["passes"] == 2, "a separable gaussian is two draws"
    noir = next(item for item in catalogue["effects"] if item["id"] == "noir")
    assert noir["pack"] == "cine"
    assert noir["passes"] == 4
    assert catalogue["max_steps_per_clip"] == fx.MAX_STEPS_PER_CLIP


def test_a_looks_cost_is_the_sum_of_what_its_steps_cost():
    """`glow` is one bloom, and a bloom is three draws — the blur it needs is
    two of them. An editor that reported one would be wrong by a factor of three
    on the thing people ask about."""
    assert fx.effect("glow").passes == 3
    assert fx.effect("mono").passes == 1


# ── on a timeline ───────────────────────────────────────────────────────────


from offsetx_apollo_builder.video import edits  # noqa: E402
from offsetx_apollo_builder.video.assembly import difference  # noqa: E402
from offsetx_apollo_builder.video.timeline import (  # noqa: E402
    TICKS_PER_SECOND,
    Project,
    TimelineError,
    new_project,
)

SECOND = TICKS_PER_SECOND


def _project() -> tuple[Project, str, str]:
    project = new_project(name="Reel", preset="vertical", fps="30")
    track = project.tracks[0].id
    project = edits.add_clip(
        project, track_id=track, kind="solid", start=0, duration=3 * SECOND,
        style={"colour": "#202020"},
    )
    return project, track, project.tracks[0].clips[0].id


def test_a_look_lands_on_the_clip_as_a_name_and_survives_a_round_trip():
    project, _, clip_id = _project()
    project = edits.add_effect(project, clip_id=clip_id, preset="noir", amount=0.8)
    reloaded = Project.from_dict(project.to_dict())
    assert reloaded.tracks[0].clips[0].effects == [
        {"preset": "noir", "amount": 0.8, "params": {}}
    ]


def test_the_stack_keeps_the_order_it_was_given_and_is_never_sorted():
    """A grade after a grain is a different picture from a grain after a grade."""
    project, _, clip_id = _project()
    for preset in ("vhs", "noir", "glow"):
        project = edits.add_effect(project, clip_id=clip_id, preset=preset)
    assert [item["preset"] for item in project.tracks[0].clips[0].effects] == [
        "vhs", "noir", "glow"
    ]


def test_an_effect_can_be_inserted_rather_than_only_appended():
    project, _, clip_id = _project()
    project = edits.add_effect(project, clip_id=clip_id, preset="noir")
    project = edits.add_effect(project, clip_id=clip_id, preset="glow", index=0)
    assert [item["preset"] for item in project.tracks[0].clips[0].effects] == ["glow", "noir"]


def test_reordering_the_stack_is_its_own_edit():
    project, _, clip_id = _project()
    for preset in ("noir", "glow", "vhs"):
        project = edits.add_effect(project, clip_id=clip_id, preset=preset)
    project = edits.move_effect(project, clip_id=clip_id, index=2, to=0)
    assert [item["preset"] for item in project.tracks[0].clips[0].effects] == [
        "vhs", "noir", "glow"
    ]


def test_dialling_one_entry_merges_parameters_rather_than_replacing_them():
    """Turning one knob must not silently reset the others."""
    project, _, clip_id = _project()
    project = edits.add_effect(project, clip_id=clip_id, primitive="vignette",
                               params={"radius": 0.5, "softness": 0.2})
    project = edits.set_effect(project, clip_id=clip_id, index=0,
                               amount=0.4, params={"radius": 0.9})
    entry = project.tracks[0].clips[0].effects[0]
    assert entry["params"] == {"radius": 0.9, "softness": 0.2}
    assert entry["amount"] == 0.4


def test_a_look_nobody_declared_never_reaches_a_document():
    project, _, clip_id = _project()
    with pytest.raises(TimelineError, match="Unknown effect"):
        edits.add_effect(project, clip_id=clip_id, preset="make_it_cinematic")
    assert project.tracks[0].clips[0].effects == []


def test_a_refused_effect_leaves_the_document_exactly_as_it_was():
    project, _, clip_id = _project()
    project = edits.add_effect(project, clip_id=clip_id, preset="noir")
    before = project.to_dict()
    with pytest.raises(TimelineError):
        edits.add_effect(project, clip_id=clip_id, primitive="saturation",
                         params={"radius": 3})
    assert project.to_dict() == before


def test_an_audio_clip_is_told_that_effects_are_pixels():
    project = new_project(name="Reel", preset="vertical", fps="30")
    audio = project.tracks[1].id
    project = edits.add_clip(project, track_id=audio, kind="audio", start=0,
                             duration=2 * SECOND, asset_id="bed", source_duration=9 * SECOND)
    clip_id = project.tracks[1].clips[0].id
    with pytest.raises(TimelineError, match="no picture to filter"):
        edits.add_effect(project, clip_id=clip_id, preset="noir")


def test_removing_and_clearing_both_work_and_say_so_when_there_is_nothing_there():
    project, _, clip_id = _project()
    with pytest.raises(TimelineError, match="nothing to remove"):
        edits.remove_effect(project, clip_id=clip_id, index=0)
    project = edits.add_effect(project, clip_id=clip_id, preset="noir")
    project = edits.add_effect(project, clip_id=clip_id, preset="glow")
    with pytest.raises(TimelineError, match="numbered 0 to 1"):
        edits.remove_effect(project, clip_id=clip_id, index=7)
    project = edits.remove_effect(project, clip_id=clip_id, index=0)
    assert [item["preset"] for item in project.tracks[0].clips[0].effects] == ["glow"]
    project = edits.clear_effects(project, clip_id=clip_id)
    assert project.tracks[0].clips[0].effects == []


def test_apply_to_all_grades_every_picture_clip_and_leaves_the_sound_alone():
    """Grading one clip of twelve is worse than grading none, which is why every
    editor has this button."""
    project = new_project(name="Reel", preset="vertical", fps="30")
    track = project.tracks[0].id
    for index in range(3):
        project = edits.add_clip(project, track_id=track, kind="solid",
                                 start=index * 2 * SECOND, duration=2 * SECOND,
                                 style={"colour": "#202020"})
    project = edits.add_clip(project, track_id=project.tracks[1].id, kind="audio",
                             start=0, duration=6 * SECOND, asset_id="bed",
                             source_duration=9 * SECOND)
    project = edits.apply_effect_to_all(project, preset="teal_orange", amount=0.6)
    assert all(clip.effects for clip in project.tracks[0].clips)
    assert project.tracks[1].clips[0].effects == []


def test_apply_to_all_twice_stacks_unless_it_is_told_to_replace():
    project = new_project(name="Reel", preset="vertical", fps="30")
    project = edits.add_clip(project, track_id=project.tracks[0].id, kind="solid",
                             start=0, duration=2 * SECOND, style={"colour": "#111111"})
    project = edits.apply_effect_to_all(project, preset="noir")
    project = edits.apply_effect_to_all(project, preset="glow")
    assert len(project.tracks[0].clips[0].effects) == 2
    project = edits.apply_effect_to_all(project, preset="vhs", replace=True)
    assert [item["preset"] for item in project.tracks[0].clips[0].effects] == ["vhs"]


def test_a_stack_past_the_ceiling_is_refused_at_the_edit_and_not_at_the_render():
    project, _, clip_id = _project()
    with pytest.raises(TimelineError, match=str(fx.MAX_STEPS_PER_CLIP)):
        for _ in range(fx.MAX_STEPS_PER_CLIP + 2):
            project = edits.add_effect(project, clip_id=clip_id, primitive="invert")


def test_pasting_a_clips_look_carries_its_effects_and_replaces_rather_than_merges():
    """A stack is an ordered thing. Merging two produces an order neither clip
    had, which is the one result nobody asked for."""
    project = new_project(name="Reel", preset="vertical", fps="30")
    track = project.tracks[0].id
    for index in range(2):
        project = edits.add_clip(project, track_id=track, kind="solid",
                                 start=index * 2 * SECOND, duration=2 * SECOND,
                                 style={"colour": "#202020"})
    source, target = (clip.id for clip in project.tracks[0].clips)
    project = edits.add_effect(project, clip_id=source, preset="noir")
    project = edits.add_effect(project, clip_id=target, preset="glow")
    project = edits.copy_attributes(project, from_clip_id=source, to_clip_ids=[target])
    assert [item["preset"] for item in project.tracks[0].clips[1].effects] == ["noir"]


def test_the_edit_diff_notices_a_filter_and_notices_a_reorder():
    """The review queue's learning signal. An owner who reordered two filters
    changed the picture, and a comparison that shrugged at that would miss it."""
    project, _, clip_id = _project()
    before = edits.add_effect(project, clip_id=clip_id, preset="noir")
    before = edits.add_effect(before, clip_id=clip_id, preset="glow")

    filtered = edits.add_effect(project, clip_id=clip_id, preset="noir")
    assert difference(project, filtered)["refiltered"] == [clip_id]

    reordered = edits.move_effect(before, clip_id=clip_id, index=1, to=0)
    assert difference(before, reordered)["refiltered"] == [clip_id]
    assert difference(before, before)["refiltered"] == []


# ── the manifest, and the seam between the two languages ────────────────────


from fastapi.testclient import TestClient  # noqa: E402

from offsetx_apollo_builder.api.app import create_app  # noqa: E402
from offsetx_apollo_builder.api.config import AppSettings  # noqa: E402


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


def _reel(client: TestClient) -> tuple[str, str, str]:
    campaign = client.post("/api/v1/campaigns", json={"name": "Pictures", "kind": "image"})
    campaign_id = campaign.json()["id"]
    created = client.post(
        f"/api/v1/campaigns/{campaign_id}/video-projects",
        json={"name": "Reel", "preset": "vertical", "fps": "30"},
    ).json()
    project_id = created["id"]
    track = created["document"]["tracks"][0]["id"]
    client.post(
        f"/api/v1/video-projects/{project_id}/edit",
        json={"operation": "add_clip", "params": {
            "track_id": track, "kind": "solid", "start": 0,
            "duration": 3 * SECOND, "style": {"colour": "#202020"}}},
    )
    document = client.get(f"/api/v1/video-projects/{project_id}").json()["document"]
    return campaign_id, project_id, document["tracks"][0]["clips"][0]["id"]


def test_the_catalogue_is_served_whole(client):
    body = client.get("/api/v1/video/effects").json()
    assert len(body["primitives"]) == len(fx.PRIMITIVES)
    assert len(body["effects"]) == len(fx.EFFECTS)
    assert set(body["packs"]) == set(fx.EFFECT_PACKS)


def test_the_manifest_hands_over_passes_and_never_a_preset_name(client):
    """The browser must not have to look anything up: the catalogue is far too
    large to ship in order to draw one clip, and a look nobody declared must
    never reach a renderer that would have to decide what to do about it."""
    _, project_id, clip_id = _reel(client)
    client.post(
        f"/api/v1/video-projects/{project_id}/edit",
        json={"operation": "add_effect", "params": {"clip_id": clip_id,
                                                    "preset": "noir", "amount": 0.5}},
    )
    manifest = client.get(f"/api/v1/video-projects/{project_id}/manifest").json()
    chain = manifest["effects"]["clips"][clip_id]
    assert [step["primitive"] for step in chain] == [
        "grayscale", "contrast", "vignette", "grain"
    ]
    assert all("preset" not in step for step in chain)
    # Half strength, all the way down the stack.
    assert chain[0]["numbers"]["amount"] == pytest.approx(0.5)
    assert manifest["effects"]["passes_per_frame"] == 4
    assert manifest["renderable"] is True


def test_a_project_with_no_effects_carries_an_empty_table_rather_than_nothing(client):
    _, project_id, _ = _reel(client)
    manifest = client.get(f"/api/v1/video-projects/{project_id}/manifest").json()
    assert manifest["effects"] == {"clips": {}, "passes_per_frame": 0}


def test_a_look_retired_out_from_under_a_document_is_a_warning_and_not_a_crash(client):
    """A document can only reach this state by being written by something other
    than the edit operations, or by an id being retired. The clip draws
    unfiltered rather than not at all, and the manifest says which clip."""
    _, project_id, clip_id = _reel(client)
    engine = client.app.state.video_store
    record = engine.get_project(project_id)
    document = record["document"]
    document["tracks"][0]["clips"][0]["effects"] = [
        {"preset": "a_look_from_2029", "amount": 1.0, "params": {}}
    ]
    engine.save_version(project_id=project_id, document=document,
                        operation="hand_edit", params={})

    manifest = client.get(f"/api/v1/video-projects/{project_id}/manifest").json()
    assert manifest["renderable"] is False
    assert any(clip_id in warning and "no longer exists" in warning
               for warning in manifest["warnings"])


def test_the_edit_endpoint_refuses_an_invented_look_with_a_422_and_a_sentence(client):
    _, project_id, clip_id = _reel(client)
    response = client.post(
        f"/api/v1/video-projects/{project_id}/edit",
        json={"operation": "add_effect", "params": {"clip_id": clip_id,
                                                    "preset": "make_it_pop"}},
    )
    assert response.status_code == 422
    assert "make_it_pop" in response.json()["detail"]
