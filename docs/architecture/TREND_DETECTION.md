# Trend detection (YouTube)

Watching competitors to find what is rising **now**, early enough to make
something about it. The Amul point from the brief: the value is not knowing what
is popular, it is knowing what is popular in time to act.

```
GET  /trends                    what is rising, with the quota spent
GET  /trends/channels           the watch list
POST /trends/channels           {"handle": "@competitor"}
POST /trends/sweep              {"per_channel": 10}
GET  /trends/topics             what several channels are covering at once
```

Needs `OFFSETX_YOUTUBE_API_KEY` — a Google Cloud key with YouTube Data API v3
enabled. Without one, `/trends` still reports from what has already been
collected; refusing to show data the quota already paid for would be the wrong
kind of strict.

---

## Why YouTube, and only YouTube

Of the four platforms in the brief, YouTube's Data API is the only one that
genuinely allows reading public data at scale — no research application, no
scraping, no approval beyond an API key. Instagram's Business Discovery returns
thin data about other *business* accounts; TikTok's Research API needs a separate
application; Facebook offers competitors almost nothing.

That is not a preference. It is the difference between a feature that works and
one that breaks the terms.

---

## The number that decides the design

Default quota: **10,000 units a day**. The endpoints are not priced anywhere
near each other.

| Call | Units | Returns |
|---|---|---|
| `playlistItems.list` | **1** | up to 50 videos from a channel's uploads |
| `videos.list` | **1** | statistics for up to 50 video ids |
| `channels.list` | **1** | up to 50 channels |
| `search.list` | **100** | one page of results |

A sweep of **1,000 competitor channels through their uploads playlists costs
about 1,100 units** — roughly a ninth of a day, comfortably daily. The same
coverage through `search.list` is not merely expensive, it is impossible: the
entire daily budget buys 100 searches.

So everything is built on uploads playlists, and `search` **exists only to
refuse**, with the arithmetic in the message:

> off_CRM does not use search.list for sweeps. It costs 100 units against a
> 10,000/day quota — the whole budget buys 100 searches — while a channel's
> uploads playlist costs 1 unit for 50 videos. Watch channels instead of
> searching.

A watcher that reached for search would cover nine channels and then stop for
the day, and that presents as a bug in off_CRM rather than as a budget that was
spent. Statistics are fetched **batched fifty at a time** for the same reason:
fifty separate calls buy the identical answer for fifty times the price, and
across a thousand channels that difference is the whole day.

The ledger is counted locally — Google exposes no live balance — from the
documented per-call costs. A sweep that would exceed the budget **stops cleanly
with a note** rather than raising halfway and leaving the day's picture
half-updated.

---

## What "trending" actually means

**Raw view count is the wrong signal.** Sort a competitor set by views and you
get the same answer every week: the biggest channels' oldest videos. Both facts
are already known and neither is actionable.

Two measures are computed instead.

**Velocity** — views per hour since publication. Corrects for age, so a
three-day-old video is not compared against a three-year-old one.

**Outlier multiple** — how many times the channel's *own* median this video is
doing. **This is the one that matters.** A small channel running at 20× its
usual is a signal about the *subject*; a large channel's ordinary upload doing
ten times that in absolute terms is a signal about the channel, which you
already knew.

There is a test for exactly that: a small channel's 20,000-view video outranks a
big channel's 520,000-view one, because the first is 20× its baseline and the
second is 1.04×.

### The median, honestly

It is taken over the videos off_CRM has *seen* for that channel, not over its
whole history. A channel watched for a week has a median of that week.

So a channel needs **5 observations** before its multiples are ranked. Below
that the video is still listed, flagged `ranked: false`, and left out of the
ordering — because it may be exactly the thing worth looking at, and hiding it
would make the list quietly depend on how long each channel had been watched.

Reporting a 20× multiple computed from two videos would be a number that looks
like insight and is arithmetic on noise.

---

## Where it sits

Read-only, and it does **not** go through the egress broker — the same reasoning
as `ai/discovery.py`: the broker guards payloads, and these calls carry a channel
id, a region code and an API key. No owner data.

It **is** written to the egress log, so the log stays a complete record of every
time off_CRM contacted an outside service. A quota-consuming call that left no
trace would be the one nobody could account for later. A test asserts the API key
never appears in what is logged.

One module in `distribution/` touches the network, and it is this one. The
publishing path — `engine.py`, `publishers.py`, `platforms.py`, `store.py` — has
no transport at all, and browser automation is refused across the whole package
with no exception.

---

## Topics: what several channels are covering at once

`GET /trends/topics?window_hours=72&min_channels=3`

One channel running hot is a good week. **Several channels on one subject is an
event**, and it is the stronger signal.

**The measure is distinct channels, not videos.** A channel posting five times
about its own product has a content calendar, not a trend — so a term only one
channel uses scores one however often it repeats.

**A topic is a term that is common now and was not before.** The same shape as
the outlier multiple, one level down: a term's share of channels *inside* the
window against its share *outside* it, and a lift of 2× or more to qualify.

That gives **adaptive stopwords for free.** Watch twenty logistics channels and
"logistics" is in half the titles and always was — high baseline, filtered by
the same arithmetic that finds the spike. Nobody has to write a per-industry
stopword list, and a hand-written one would still miss the words that matter to
one owner and not another. A word *nobody* used before is the strongest case,
not a division by zero.

**Merging is on shared videos, not shared terms.** Term chaining is how
clustering quietly turns everything into one blob: A shares a word with B, B
with C, and three unrelated stories become one topic. Two term-clusters covering
mostly the same videos really are one subject named twice, and those merge.

### The limitation, which matters more than the feature

**This is lexical, not semantic.** "Rotterdam port strike" and "Dutch
dockworkers walk out" are the same story and share no significant word, so they
will not group. Titles are five to twelve words, which leaves little to match
on. The honest description is *shared vocabulary detection*.

It is built this way deliberately: semantic grouping means an embedding or a
model call per sweep — a cost, a provider dependency, and a feature that stops
working when a key expires. Shared vocabulary catches the common case (a place,
a company, an event, a product) deterministically, offline and free.

There is a test named for this, asserting the paraphrase case returns nothing,
so the limitation is found in the repository rather than by someone trusting
the output.

---

## What is not built

- **Turning a trend into a post.** `/trends` and `/trends/topics` report;
  nothing composes a caption from what they found. That is the next piece, and
  it is where the image campaign and this one meet.
- **Scheduled sweeps.** `/trends/sweep` is called; nothing calls it on a timer.
  `AutomationService` is where that belongs.
- **Semantic clustering.** See the limitation above — a deliberate omission,
  not an oversight.
- **Any other platform.** Instagram, TikTok and Facebook are declared in
  `platforms.py` with what their terms actually permit. None of it is a general
  scraper, and none of it is built.
