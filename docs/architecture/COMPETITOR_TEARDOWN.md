# S-05.01.03 — Competitor teardown without copying content

## Product boundary

The purpose is to learn reusable **structure** from a high-performing public
post: pacing, hook shape, visual treatment, duration and recipe choice.

The source media is not an asset library. off_CRM must not copy frames, audio,
captions, transcripts or the original media into a generated project.

This resolves Q-05 using the story contract already present in the backlog:
recipe reference + parameters, never copied media.

## AI decision

Start deterministic, not generative.

The system already has public performance facts in the distribution/trends
layer and known recipes in the video engine. A deterministic analyser gives a
measurable baseline and makes the same facts produce the same recipe.

An LLM can later suggest structural labels only if measured evaluation shows it
beats the deterministic baseline. It still may not receive or return reusable
source media.

## Reused architecture

Do not create a second content engine.

Reuse:

- public-source policy and provenance from discovery;
- performance signals from `distribution/trends.py`;
- existing recipe catalogue in `video/recipes.py`;
- existing project assembly path;
- existing human review queue and distribution approval gates.

The new code should be a narrow analyser between normalized public facts and
existing recipe parameters.

## Contract

A teardown result contains only bounded structured data, for example:

- source URL/id and observation time;
- public performance metrics/evidence class;
- recipe id from the existing catalogue;
- duration band;
- hook class;
- pacing band;
- shot-density/transition/intensity bands where supported;
- visual treatment parameters already understood by the recipe system;
- analyser version and rule provenance.

It must not contain source binary media, copied caption/transcript text, source
audio, downloaded frames or a path to such copies.

## Flow

```text
public post facts + performance evidence
  -> validate sufficient public evidence
  -> deterministic structural analyser
  -> known recipe id + bounded parameters + provenance
  -> existing assembler/project creator
  -> existing review queue
  -> human approval
  -> existing distribution path
```

No new publish path exists in this story.

## Failure controls

Refuse or return `insufficient_evidence` when:

- the source is private/session-gated;
- required public facts are absent;
- a recipe id cannot be resolved;
- a parameter is outside the recipe's supported bounds;
- the input tries to attach media/copy instead of structural facts.

The analyser never fills missing facts by guessing.

## Evaluation

Create a fixed fixture set of normalized public-post facts. Measure:

- deterministic repeatability: 100%;
- valid recipe resolution: 100% on supported fixtures;
- media/copy leakage: 0 bytes / 0 copied text fields;
- review-gate bypass: 0;
- insufficient-evidence refusal: 100% for negative fixtures.

## Rollback

The analyser is additive. Removing it leaves the existing recipe, assembly,
review and distribution systems unchanged.

## Known limits

A deterministic baseline cannot infer subjective creative intent. That is
acceptable for the first production slice: it produces explainable structural
hypotheses, not claims about why a post succeeded.
