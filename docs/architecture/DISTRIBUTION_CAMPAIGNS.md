# Content distribution campaigns

The third campaign kind, and the one that composes the others: an approved
picture becomes a post, the post goes out, and what the audience did comes back
as the measurement everything else has been missing.

```
asset (image campaign)  →  post  →  approve  →  schedule  →  publish
                                                                 ↓
   generator score  ←────────────  views, likes  ←────────  read back
```

---

## Read this first: what the platforms actually allow

The brief was to operate many accounts across Instagram, Facebook, TikTok and
YouTube. Most of the difficulty is not code. **Each platform allows far less
automated posting than it looks like from outside, and the tools that appear to
offer more are the ones that get accounts banned.**

**off_CRM publishes through official APIs only.** Browser automation, mobile-app
endpoints and session-cookie replay breach the terms every one of these
platforms publishes, and the failure mode is your account — not an error
message. That is a worse outcome than a feature honest about needing setup.

Today that means **one working adapter: the local outbox.** Every real platform
is declared with its official API, its preconditions and its quotas, and
connecting an account off_CRM cannot post to is refused *at connection*:

```
off_CRM has no Instagram adapter yet. The official route is Instagram Content
Publishing API. Nothing was scheduled, because a post that cannot be delivered
is worse than one that was never planned.
```

| Platform | Publish | Official route | The catch |
|---|---|---|---|
| **local outbox** | ✅ supported | writes to disk | Not a stub — the device `LocalOutboxProvider` is for email |
| **YouTube** | adapter missing | Data API v3 `videos.insert` | Quota is **per API project, not per channel**: an upload costs ~1,600 of 10,000/day, so ~6 uploads a day across *every* channel you own |
| **Instagram** | adapter missing | Content Publishing API | Business/Creator account only — **no API can post to a personal account**. 25 posts per account per 24h. Meta app review required |
| **Facebook** | adapter missing | Pages API | A Page, not a profile. App review for `pages_manage_posts` |
| **TikTok** | restricted | Content Posting API | Until your app is audited it may only post **privately to the connecting account**. A campaign counting those as reach would be lying to you |
| **LinkedIn** | restricted | Posts API | Partner-programme approval for most scopes |
| **X** | adapter missing | API v2 | Paid tier; the free write allowance is minimal |

The YouTube quota line is the one people get wrong. "More channels" does not
mean more uploads, and a planner assuming it did would over-promise by however
many channels you have.

### Watching competitors

Scraping Instagram, TikTok or Facebook is against their terms, whatever the
tooling. What is permitted is narrower and worth knowing precisely: YouTube's
Data API serves public video and channel data under the same quota; Instagram's
Business Discovery returns limited public data about other *business* accounts;
TikTok's Research API needs a separate approval. Competitors' own websites and
feeds are ordinary web pages, and the discovery module's politeness controls
already cover them.

Each platform records which of those applies. **YouTube trend detection is
built** on exactly that basis — see `TREND_DETECTION.md`. The others remain
groundwork, because what they permit is narrow enough that a general scraper
would be the wrong thing to write.

---

## Goal-shaped, not post-shaped

A campaign has a target — *"a million views"* — and progress is measured against
it, exactly as described.

```
views: 250,000 / 1,000,000  (25.0%)  met=False
```

### Snapshots are not increments

Engagement readings accumulate: views on Tuesday are not *new* views on Friday.
A total built by summing every reading would count the same view once per
measurement and report a goal as met when it is not.

So each reading is a snapshot, and totals use the **newest reading per post**.
Ordering is by time and then by id, because an earlier version compared only the
timestamp — and since timestamps were second-precision, two readings a moment
apart both matched the maximum and were summed. It reported 100 views where
there were 60. Caught by
`test_later_readings_replace_earlier_ones_rather_than_adding`.

Recording engagement for a post that never went out is refused. Otherwise
fiction enters the benchmark.

---

## Two ceilings, and the owner's is the one that matters

The platform says what is **allowed**. The owner says what they are **willing to
do with their name on it**, and for almost everybody that is a much smaller
number — Instagram permits 25 API posts a day and nobody sane posts 25 a day.

So an account carries a `daily_cap`: the most that handle may commit to in one
day, set by the owner. It sits under the platform's published limit, under the
pacing arithmetic, and under any goal.

**Zero means no cap, not zero posts.** Nothing here invents a default. A number
this code made up would be a limit the owner never chose being enforced as
though they had, and the honest state before anyone sets one is the platform's
own limit and nothing else.

**Checked when a post is scheduled**, alongside the platform's, and counted
**across every campaign** — it is the handle that gets restricted, and it does
not care which campaign filled its day. Reconnecting an account does not reset
its cap: the limit is a decision about the handle, not about that connection.

A campaign's own ceiling is the **sum** of the caps on the accounts it posts to,
because the rate is one campaign-wide number and three handles capped at two
really can carry six posts between them. If any enabled account has no cap, the
campaign has none — summing over a partly-capped set would invent a limit out of
handles the owner deliberately left open.

## Recommending and doing are two different things

`pacing.py` is good at the arithmetic. It can see the goal, the deadline, how
many views a post is actually worth and what the platform allows. What it cannot
see is whether you want to speak that loudly this week.

So the rate has three modes, and the middle one is the default:

| Mode | What happens |
|---|---|
| `off` | The rate is whatever you set. The step does not even run. |
| **`suggest`** | The ideal rate is worked out every cycle and **waits for you**. |
| `auto` | It moves on its own — still never past your cap. |

In `suggest` the cycle computes the number, stores it as `pending_pace` with its
reasoning, and **returns the config untouched**. `POST /content-automation/pace`
with `accept` or `dismiss` is the owner answering. That endpoint takes a word
rather than a rate on purpose: setting the rate is a `PATCH` on the automation,
and this is a different act — a person answering something the machine asked.

It is the same shape the video review queue has, for the same reason. **A
machine that makes things unattended must not also be the thing that decides
they go out.**

A suggestion is only stored when it differs from what is already running. A
screen that shows the same suggestion every hour is a screen people stop
reading.

**The old `auto_pace` boolean still works.** `True` reads as `auto` and `False`
as `off`, so a workspace configured before there were three modes does not
change behaviour because the default did.

---

## This closes the benchmark

`CAMPAIGN_TYPES.md` described three layers: deterministic gates, the owner's
swipe, then real engagement. The gates and the swipe came with the image runner.
**This is layer three**, and it is joined back to layer two:
`generator_performance` groups views by the generator that drew the picture.

So the two signals can be compared — and can disagree. A picture you loved that
nobody watched is information, and it is the kind that only arrives here.

Without an `asset_reader` the join cannot be made, and the answer is an empty
list rather than a guess.

---

## Using it

```
GET  /distribution/platforms              what each allows, what is refused
POST /distribution/accounts               {"platform": "local_outbox", "handle": "@you",
                                           "daily_cap": 3}          0 or absent = no cap
PATCH /distribution/accounts/{id}         {"daily_cap": 3}          change it later
GET  /campaigns/{id}/pacing               what the ideal rate would be, and why
POST /content-automation/pace             {"decision": "accept" | "dismiss"}
POST /campaigns                           {"name": "...", "kind": "distribution"}
POST /campaigns/{id}/goals                {"metric": "views", "target": 1000000}
POST /campaigns/{id}/posts                {"account_id": "...", "caption": "...", "asset_id": "..."}
POST /posts/{id}/approve
POST /posts/{id}/schedule                 {"at": "2026-08-12T09:00:00+00:00"}
POST /distribution/publish-due
POST /posts/{id}/metrics                  {"views": 250000, "likes": 900}
GET  /campaigns/{id}/progress
```

Approval is required before scheduling: it is the point at which a person agreed
to it going out. Both daily ceilings — your cap and the platform's — are checked
**when a post is scheduled**, not when it is sent: a schedule that cannot be
delivered looks like a plan, and you would act as though it were one.

The **Posting** screen is where this lives: a cap box per handle, the three
modes, and the waiting suggestion with its reasoning and an Accept button.

---

## What is not built

- **Adapters for the real platforms.** Each is declared with the route that
  would serve it. Each needs OAuth per account and, for Meta and TikTok, app
  review — setup work, not code this module is missing.
- **Competitor watching on platforms other than YouTube.** YouTube trend
  detection is built — see `TREND_DETECTION.md`. The others are limited by what
  their terms permit, and none of it is a general scraper.
- **Automatic caption generation.** A post carries a caption you wrote and
  optionally an asset from an image campaign. Composing it from a trend is the
  next piece.
- **Scheduled publishing.** `publish-due` is called; nothing calls it on a timer
  yet. `AutomationService` is where that belongs.
- **A UI for most of it.** The **Posting** screen covers the caps and the rate;
  accounts, goals, posts and metrics are still API only.
- **A cap per platform rather than per handle.** The limit is on the account,
  which is the thing that gets restricted. Somebody with six Instagram handles
  who wants one number across all of them has to set six.
- **Nothing recommends the cap itself.** The pacer recommends a *rate* and
  respects the cap; it does not look at how an account has fared at different
  rates and suggest what the cap should be. That needs a history of caps and
  outcomes, and there is not one yet.
