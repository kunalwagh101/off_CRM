# Image campaigns

The second campaign kind. Email sends messages to people; this one produces
pictures against a brief and asks you to keep or discard each one.

```
brief  →  generate  →  deterministic gates  →  review queue  →  swipe
                             ↓ fail                              ↓
                        never shown                     generator score
                                                              ↓
                                                   who draws the next batch
```

---

## The swipe is the label

This is the whole design, and it is the answer to the benchmark question:
*how do you measure whether an image is good?*

Not with a model rating its own output — that is unrepeatable, unauditable, and
the same mistake as letting a model enforce policy. With **your own decisions**,
collected free as a side effect of using the thing.

Right keeps it. Left discards it. Refresh asks for another. Each of those is a
quality judgement on a generator's work, and each one scores that generator.
After a few hundred, the scores are a benchmark of your taste — and
`ai/bandit.py` allocates the next batch towards whoever is winning, using the
same Thompson sampler that shifts traffic between email templates. The allocator
does not know its arms are image models.

Three consequences, each with a test:

- **A decision is made once.** Otherwise a generator's score moves by clicking
  twice.
- **Refresh counts as a rejection.** You said no to that picture. Dropping the
  no would bias the scores towards whichever generator got refreshed most.
- **Rejection deletes the bytes and keeps the verdict.** The record of having
  rejected it *is* the benchmark.

**It waits before steering.** Under 12 decisions per generator the allocator
stays out of the way and the broker picks. A lopsided result from four swipes is
noise, and acting on it would starve a generator that never had a fair run.

---

## The gates come first, and they are not about taste

Layer one of the three-layer benchmark in `CAMPAIGN_TYPES.md`: rules that cannot
be wrong.

| Gate | Catches |
|---|---|
| `decodes` | The generator returned something that is not an image |
| `not_blank` | Under 1 KB — a placeholder, an error page, or the flat grey a model returns when it gives up |
| `readable_header` | A format nothing here can read. Fails **closed**: a zero would silently pass a dimension check |
| `aspect_ratio` | A square when the brief said 16:9, with 5% tolerance so a generator rounding to 1152×648 still passes |
| `not_duplicate` | Byte-identical to something already produced for this brief |

A failed gate is **never shown to you**, so your attention goes on pictures that
are at least valid. More importantly: a reject that only means "this came back
broken" is not a judgement about taste, and mixing the two would poison the
signal the benchmark rests on. They are separate statuses and separate counters.

Failed candidates are still **stored**. *"This generator returns the wrong
aspect ratio four times in five"* is worth knowing, and a discarded candidate
cannot tell you.

### No image library

Reading a width and a height is a header parse, and every format that matters
puts them in a fixed place — PNG in the IHDR at a fixed offset, JPEG in whichever
start-of-frame marker the encoder used, GIF at byte 6, WebP in three variants.
Adding Pillow to decode two integers would pull a large dependency into a
project that has been careful about them. Forty lines instead.

---

## What it inherits rather than reimplements

Generation goes through `EgressBroker.call_image`, so an image prompt gets the
**same** tier filter, the same allowlist payload construction, the same blocking
scanner and the same egress log as any other call.

A prompt naming a real person is person data. That was already true before this
module existed, and a structural test asserts `imagery/` imports no transport —
a module that could reach a provider directly would inherit none of it.

The kind gate runs from both sides now: `OutreachEngine` refuses an image
campaign and `ImageCampaignEngine` refuses an email one, so neither runner can
pick up the other's work.

---

## Storage

Its own database (`imagery.db`), three tables, and **pictures are files**.

| Table | Holds |
|---|---|
| `image_briefs` | The ask: text, target size, how many you want |
| `image_assets` | One candidate: generator, path, hash, dimensions, status, gate results |
| `image_generator_stats` | shown / approved / rejected / gate_failed per generator — the benchmark |

The bytes go to `image_assets/<campaign>/<id>.png` at `0600`; the row keeps a
path and a hash. A base64 blob in a database column bloats every backup that did
not want it — the same decision the egress log already made when it chose to
record the prompt and never the picture.

---

## Using it

```
POST /campaigns                        {"name": "...", "kind": "image"}
POST /campaigns/{id}/image-briefs      {"brief": "...", "width": 16, "height": 9, "wanted": 2}
POST /image-briefs/{id}/generate       {"count": 3}
GET  /campaigns/{id}/image-queue
POST /image-assets/{id}/decide         {"decision": "approve" | "reject" | "regenerate"}
GET  /campaigns/{id}/image-summary
```

The **Image review** screen shows one candidate at a time with three buttons and
arrow-key shortcuts (← discard, → keep, R for another).

One at a time, not a grid. A grid invites picking a favourite and ignoring the
rest, and "ignored" is not a label. One at a time forces a verdict on each, and
a verdict on each is what the benchmark is made of.

---

## What is not built

- **Video.** The gates read image headers. Duration, frame rate and audio
  loudness are a different piece of work, and claiming video without them would
  be claiming a benchmark that does not exist.
- **Publishing.** An approved picture is an asset. Posting it across accounts is
  the content-distribution campaign. The boundary is deliberate: publishing has
  its own credentials, its own per-platform rules and its own failure modes, and
  folding it in here would make one module responsible for two jobs that fail
  differently.
- **Layer three of the benchmark** — views, watch time, engagement. That needs
  the distribution campaign to exist, because it is what would report them.
- **Brief authoring in the UI.** Briefs are created through the API; the screen
  reviews what exists.
- **Prompt improvement between rounds.** Refresh regenerates against the *same*
  brief. Rewriting the brief from what you rejected is a real feature and it is
  not here.
