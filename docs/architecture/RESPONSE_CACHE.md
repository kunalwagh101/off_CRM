# The response cache

## On the name

The literature calls this a "semantic cache" and quotes **60–90% hit rates**.
Those figures come from chat and support systems where many users ask the same
handful of questions.

**They do not transfer to off_CRM.** Personalised outreach means every payload
carries a different token and a different hook, so the near-duplicate rate is
close to zero.

Where it genuinely pays:

- **re-running an eval suite** — the same cases against the same models, over and
  over, which is exactly what tuning looks like
- **retries** after a transient provider failure
- **repair rounds** in the verify loop that regenerate an identical payload
- **public and code questions** asked more than once

It is also **not embedding-based**. There is no embedding model here, and adding
one would mean either a network call from a module whose point is avoiding
calls, or a heavy local dependency. It does **exact match plus lexical
near-match**, which covers the cases above completely. Calling that "semantic"
would be overclaiming.

So the cache reports its own hit rate. Whether it earns its place is a question
to answer with your numbers, not mine.

---

## The safety property

The key includes the **constructed payload**, not the question.

That matters because payloads are built per policy. Verified before writing a
line:

```
pseudonymous  fields=[instructions, recipient, recipient_token, schema_version, sender_token, task]
standard      fields=[..., template]          ← the template only travels at standard
```

Keying on the payload makes it **structurally impossible** for a response
produced from a richer payload to be served for a thinner one.

This matters more than it first appears. **A response is not only shown to you —
it can travel back out as `prior_drafts` on a later call.** A cache that blurred
policy boundaries would be a slow path for material derived from a tier A
payload to reach a tier C provider.

The key also includes the workspace (one user's answers never surface in
another's) and the provider (so *"what did DeepSeek say"* stays answerable).

Tested in both directions, including that near-matching cannot cross the
boundary however similar two texts look.

---

## Where it sits in the broker

```
1. tier filter
2. quota filter
3. build payload          ← the payload IS the cache key, so it must exist first
4. pre-flight scan
4b. CACHE LOOKUP          ← after the checks, never before
5. call provider
```

**A lookup must never become a way around the checks that precede it.** If the
scanner blocks the payload, nothing is served and nothing is stored — tested.

---

## A cache hit is logged as a hit, not a send

Nothing left the machine. The egress log records `cache_exact` or `cache_near`
rather than `succeeded`.

The egress log is the one thing in off_CRM that must never lie. Showing a cache
hit as a send would make the audit trail wrong in the direction that matters.

---

## Near matching, and its limits

Threshold **0.92 Jaccard on word triples**, and both of those choices are
deliberate:

- **Word triples, not single words.** Single-word overlap would call two
  different questions about the same subject "similar". Triples require the
  phrasing to line up.
- **A high threshold.** At 0.92 a "near" match is the same text with different
  whitespace, punctuation or casing — not a different question sharing
  vocabulary. **Serving a stale answer to a genuinely different request is a
  worse failure than missing a hit**, so the threshold errs towards missing.

Switchable off entirely with `near_match=False` if you want exact-only.

---

## What is never stored

| | Why |
|---|---|
| Empty responses | Caching "the provider returned nothing" turns one transient failure into a week of them |
| Failed calls | Same reason — tested |
| `DataClass.MAILBOX` | Unreachable today, but if that ever changes the cache must not be the thing that quietly starts persisting received mail |

---

## Housekeeping

- **7-day TTL.** Model behaviour drifts, providers change what sits behind a
  name, and a draft written six weeks ago against a since-rewritten template is
  worse than no draft.
- **5,000-row cap**, oldest evicted. This is a cache, not an archive — the
  egress log holds the permanent record.
- `purge_expired()` and `clear(workspace_id=...)` for manual control.

---

## Measuring it

```python
cache.stats()
# {"entries": 412, "exact_hits": 88, "near_hits": 12,
#  "misses": 340, "lookups": 440, "hit_rate": 0.227,
#  "calls_avoided": 100}
```

Exact and near hits are counted **separately**, because they carry different
risk and are worth telling apart.
