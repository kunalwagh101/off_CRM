# Campaign types — the shape everything must fit

Recorded from the owner, 2026-07-31. **Read this before designing anything new.**
It changes what "campaign" means, and today's schema does not fit it.

---

## The product is not a CRM

It is a CRM **with an AI layer that runs the campaigns itself**.

The owner does not open a screen, select a campaign, and click buttons. The owner
says *"run this campaign"* and provides two things:

- a **template**
- a **list of POIs** with addresses

Everything after that is the AI's job. Manual clicking is the thing being
removed, not the interface being improved.

---

## Email is one campaign type, not the campaign

Planned types, in the owner's words:

### 1. Email campaign — built

What exists today.

### 2. Image / video campaign

An orchestration layer **for image and video models**, the same shape as the text
one: many models, mostly free, combined to beat what any single one produces.

- The output has to clear a **quality benchmark**. The owner has explicitly asked
  for help designing this — see below.
- **Human approval by swipe:** the generated video or image is shown. Swipe right
  to proceed, swipe left to delete, refresh to regenerate against the same brief.
- Reference points named by the owner: Higgsfield and similar platforms.

### 3. Content distribution campaign

The largest one, and it composes the others.

- **Watch competitors** — thousands of them, using the scraping tools already in
  the repo, to see what they are posting.
- **Find what is trending**, and produce topical content against it. The owner's
  example is **Amul**, which is well known for turning current events into
  advertising within a day.
- **Produce** the images and videos using type 2.
- **Operate many accounts** across Instagram, Facebook, TikTok and YouTube.
- **Read the analytics back** and learn from them — which the context layer
  already has the shape for.
- Campaigns are **goal-shaped**, e.g. "reach a million views", not merely
  "publish these posts".
- The learning target is what actually makes content perform: the psychological
  hooks, the openings, the pacing.

### 4. More types after that

Assume the list keeps growing. **Anything built now must not assume email.**

---

## The concrete blocker, today

`outreach/schema.py`, the `campaigns` table:

```sql
daily_send_limit INTEGER NOT NULL CHECK(daily_send_limit > 0),
followup1_working_days INTEGER NOT NULL DEFAULT 4,
send_window_start TEXT NOT NULL DEFAULT '00:00',
send_weekdays_json TEXT NOT NULL DEFAULT '[0,1,2,3,4,5,6]',
experiment_metric TEXT NOT NULL DEFAULT 'reply_rate',
```

Every column is email. **There is no `kind`.** A campaign cannot currently *be*
anything else.

Two bad ways forward and one good one:

| Approach | Result |
|---|---|
| Add image/video columns to this table | A table where most columns are null for most rows |
| A parallel table per type | The scheduling, approval and analytics logic duplicated per type |
| **A `kind` column plus a per-kind settings blob** | One lifecycle, one approval path, one analytics path; the type-specific parts stay in their own module |

The third is the one to take, and it is a small migration **now** versus a large
one later.

---

## What already generalises

Encouragingly, most of the hard parts do not care what a campaign sends:

| Piece | Transfers? |
|---|---|
| Trust tiers, data classes, the egress gate | ✅ unchanged — an image prompt naming a real person is still person data, and this is already handled |
| The verify loop | ✅ the checks differ, the loop does not |
| Eval harness + champion/challenger | ✅ scoring an image is a different scorer, not a different design |
| Thompson traffic shifting | ✅ allocate between *generators* exactly as between template variants |
| The context layer | ✅ counts and a rolling summary, whatever is being counted |
| Response cache | ✅ keyed on the payload, so it already works for image prompts |
| Sandbox + tool registry | ✅ unchanged |
| **The campaign runner** | ❌ email-only, and the schema with it |

So the AI layer is largely type-agnostic already. **The CRM half is not.**

---

## Benchmarking image and video quality

The owner asked for help here and said they do not yet know how. The honest
answer is that it is the same problem the eval harness already solved, in three
layers — and that **no single model judging "is this good" is one of them**.

### Layer 1 — deterministic gates (free, and they never have an off day)

Rules that cannot be wrong, exactly like the copy checks:

- resolution, aspect ratio and duration match the brief
- a face/hand detector flags the classic generation artefacts
- text rendered *in* the image is spelled correctly — still a common failure
- brand colours present, safe-area respected for the target platform
- audio present and within loudness targets, for video

These reject the obviously broken before anything reaches a human or a judge.

### Layer 2 — the swipe **is** the label ⭐

This is the important one, and the owner has already designed it without
naming it as such.

Left-swipe and right-swipe are **human quality labels, collected free as a side
effect of ordinary use.** They are to images exactly what reply rate is to
templates: a real signal, not a model's opinion.

After a few hundred swipes there is a genuine benchmark — the owner's own taste,
recorded — and generators can be scored against it.

### Layer 3 — the real outcome

Views, watch time, engagement. The slow truth, and the only one that finally
matters. Same relationship as reply rate to email: the fast proxy guides, the
real number decides.

### Then reuse what exists

Score each **generator** the way template variants are scored now, and let the
Thompson allocator shift traffic towards whichever is winning. `ai/bandit.py`
does not know or care that the arms are image models rather than email variants.

**What not to do:** ask one model "rate this image out of ten". It is
unrepeatable, it cannot be audited, and it is the same mistake as letting a model
enforce policy.

---

## Two risks worth naming early

Not blockers, but they shape the design and are cheaper to face now.

**Operating many accounts** on Instagram, TikTok, YouTube and Facebook runs into
each platform's automation rules. Some publishing is supported through official
APIs; a lot of what looks similar is not, and account bans are the failure mode.
Worth checking each platform's actual API surface before designing around
per-account automation, because the answer differs sharply between them.

**Competitor scraping** is already in the repo for lead discovery. Applying it to
social platforms hits different terms and different rate limits. The existing
politeness controls are the right foundation; the target list is what changes.

---

## The rule for anything built from here

> **Do not assume email.**

A new feature should ask what *kind* of campaign it belongs to, and put anything
email-specific behind that boundary rather than in the shared path.
