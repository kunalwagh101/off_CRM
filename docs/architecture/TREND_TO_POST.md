# Trend to post

The piece that joins the three campaign kinds. Everything it needs already
existed — topics report what several competitors are covering, the image runner
turns a brief into candidates and collects a verdict on each, the distribution
runner turns a caption and an asset into a scheduled post. This is the wiring,
and it is what *"run this campaign"* finally means end to end.

```
topic → brief → generate → gates → [ SWIPE ] → caption → draft post → [ APPROVE ] → schedule
                                       ↑                                   ↑
                                 a person decides                   a person decides
```

---

## Where the automation stops is the whole design

The pipeline runs in **two halves**, and the boundary between them is a
judgement that already existed.

**`plan`** goes from a detected topic to candidates waiting in the review queue.
It stops there. Nothing that has not been looked at becomes a post.

**`draft`** picks up the pictures you kept, writes a caption for each and creates
a **draft** post. It stops there too — a draft still needs the approval the
distribution runner has always required before anything can be scheduled.

So the machine does the fetching, the composing, the generating and the
scheduling arithmetic. A person does the two things that are judgement: *is this
picture good* and *does this go out*.

Removing either would let the system publish something nobody ever saw, under
your name. Most of the tests in `test_pipeline.py` exist to make sure neither can
be skipped by accident — including one that asserts a drafted post still cannot
be scheduled without approval.

---

## Using it

```
POST /campaigns/{distribution_id}/pipeline/plan
     {"image_campaign_id": "...", "max_topics": 3, "candidates": 3, "angle": "..."}

  ... you swipe in the Image review screen ...

POST /campaigns/{distribution_id}/pipeline/draft
     {"image_campaign_id": "...", "account_ids": ["..."], "angle": "..."}

  ... you approve, then schedule, then publish-due ...
```

Two campaigns are named in one call, and **both are kind-checked** — the first
must be a distribution campaign and the second an image campaign. Without that
a swapped id would quietly write image briefs against an email campaign.

---

## The same topic is not planned twice

A story that runs for three days is one topic, not three. Every topic that
produces a brief is recorded by a key built from its **sorted terms** — not its
label, because the label is the first three terms and a topic can gain one
between sweeps without becoming a different subject.

Within the cooldown (a week by default) it is skipped with a reason. Without
this, every sweep makes a fresh brief for the same story and the review queue
fills with the same picture.

---

## Writing the words

Composition is **deterministic by default** and takes an optional writer.

With no writer it assembles a brief and a caption from the topic's own terms and
the headlines competitors used. That is genuinely enough for an image brief, and
it is a starting point for a caption that a person reads before approving
anyway.

The brief deliberately **describes the subject, not the composition**.
Over-specifying — lens, lighting, angle — produces the same picture from every
generator, which defeats both running several of them and the swipe that
compares them.

Given a writer, the API supplies one backed by the egress broker, and **the data
class is chosen by what is actually being sent**:

| What goes | Class | Why |
|---|---|---|
| Topic terms + competitor video titles | `public` | Public YouTube data. Any permitted model, cheapest first |
| …plus your angle | `campaign` | Your own positioning is not public, so the tier rules narrow |

This module decides nothing about trust — it picks the class honestly and the
broker applies the rules it already has.

**A failing writer falls back rather than breaking the run.** A model having a
bad day should not cost the sweep, so an exception or an empty answer returns the
deterministic version. There are tests for both.

Working without a writer matters for the same reason trends work without an API
key: a pipeline that cannot run offline is one that stops when a key expires.

---

## What is not built

- **Nothing calls it on a timer.** `plan` and `draft` are invoked; scheduling
  the sweep belongs in `AutomationService`, and is not wired.
- **No UI.** The Image review screen covers the swipe half; the plan and draft
  calls are API-only.
- **No per-account caption variation.** One picture posted to three accounts
  carries the same caption to all three.
- **The angle is a string you supply.** Nothing derives it from your positioning,
  your past posts, or what performed before — though `generator_performance` and
  the context layer both hold material that could.
