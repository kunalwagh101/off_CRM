# Failure classification

What happens when a model call goes wrong.

```
GET /api/v1/ai/failure-kinds        # the taxonomy, the action, the owner action
GET /api/v1/ai/egress-log/stats     # by_failure: what has been failing, and how
```

---

## What it was doing before

Every provider failure was treated identically: record it, move to the next
candidate, and cool the model off after two. That is the right answer for
exactly one kind of failure — a provider having a bad day — and the wrong answer
for most of the others.

Three of them cost real money:

**A broken API key looked like a busy provider.** A 401 failed over silently to
the next model, which worked. So nobody found out. The key stays broken, every
call quietly runs on a model the owner did not choose and costs whatever that
one costs, and the first sign of trouble is a bill.

**A payload we built wrong took out healthy providers.** A 400 is our bug, not
theirs, and every other model rejects it identically — but failing over tried
each one and opened the circuit breaker on the way past. One malformed request
could leave the workspace with no usable model for a minute.

**A rate limit fell through to another provider's quota.** A 429 usually means
*wait a moment*, often with the server saying exactly how long. Spending a
second provider's budget is the expensive answer to a free problem.

---

## Four actions, and classes that exist to choose between them

Classification is only worth having if each class leads to a different action.
So the actions came first.

| Action | What the broker does |
|---|---|
| `RETRY_SAME` | Wait, then ask the same model again |
| `FAILOVER` | This model is unhealthy; try the next one **in the same tier** |
| `STOP_REQUEST` | The request is wrong; every model fails the same way |
| `STOP_CONFIG` | A human has to fix something; nothing works until they do |

Both `STOP` actions refuse to fail over. **That refusal is the point** — failing
over is what hid the problem.

| Kind | Action | Counts against the provider? |
|---|---|---|
| `timeout`, `connection`, `server_error`, `overloaded` | failover | ✅ |
| `empty_response`, `malformed_response` | failover | ✅ |
| `content_filter` | failover | ❌ — this model refused, another may not |
| `rate_limited` | retry same | ❌ |
| `auth`, `payment`, `model_not_found`, `truncated` | **stop_config** | ❌ |
| `bad_request`, `context_length` | **stop_request** | ❌ |
| `unknown` | failover, no retry | ❌ |

### Only provider health opens the circuit

A 400 we caused says nothing about their service. Letting it trip the breaker is
how one malformed payload takes a whole tier offline, so only the ✅ rows above
count towards it.

### `unknown` fails over once and never retries

Default-deny, applied to spending. An error nobody has classified, retried three
times, costs three times as much and has no particular reason to succeed. It is
recorded under `unknown` so the gap shows up in the log rather than in a bill.

---

## On retries and time

The owner's question was whether retrying costs a lot of time.

**No second retry loop was added.** `outreach/providers.py` already retries
three times inside the HTTP call for connection errors, 429 and 5xx. Adding
another loop on top would make nine attempts against one model, which is not
resilience — it is a stuck request. `RETRY_SAME` is reserved for what the
transport layer does not handle, and it is bounded:

| Bound | Default |
|---|---|
| Same-provider retries, across the whole chain | 2 |
| Wall clock over everything — attempts, retries, failover | 120s |

The deadline is one clock for the entire call. A slow failure across several
providers, each with its own transport retries, cannot become an unbounded wait
for whoever is holding the request. When it runs out the attempt list says
`deadline_exceeded` rather than pretending nothing happened.

`Retry-After` is honoured when the server sends it, capped at 300s. Waiting the
time the server named beats guessing at it.

---

## The message the owner gets

A `STOP` names what to do, and says explicitly that nothing was routed around:

> The provider rejected the API key. Reconnect it in Connectors, or set
> `OFFSETX_AI_<PROVIDER>_KEY`. Nothing was sent to another model, because
> failing over would have hidden this.
> *(provider nvidia, model meta/llama-3.1-70b-instruct, auth)*

Over HTTP that is a **502** with the kind, the action and the owner action in
the body. 502 rather than 503: the upstream gave a definite answer and off_CRM
chose not to route around it, so "try again later" would be the wrong advice.

---

## Seeing the pattern

The kind is written to the egress log in a `failure_kind` column, and
`GET /ai/egress-log/stats` groups by it.

That column is the reason classification is worth having at all. *"NVIDIA has
been returning auth errors for a week"* is a question a kind column answers and
a pile of 500-character error strings does not.

This is the log's **first migration**, applied additively on both backends
through `Database.add_column_if_missing` — an existing log gains the column and
keeps its rows rather than being thrown away. Verified against a log built
without it.

---

## A bug this found in its own first draft

The content-filter pattern started as `refus`, which matches **"Connection
refused"**. A dead network was being filed as a content filter — so off_CRM
would have failed over politely instead of reporting that nothing could be
reached.

Patterns on an error path are exercised by text nobody chose. Each alternative
now has to be wrong about only what it is for, and there is a test pinning
exactly that pair:

```python
classify("ConnectionError(Connection refused)").kind  # connection
classify("the model refused to answer").kind          # content_filter
```

---

## What is not built

- **No adaptive backoff or jitter across providers.** The transport layer's
  fixed `2**attempt` is unchanged; only the classification above it is new.
- **No persistence of circuit-breaker state.** It lives in memory, so a restart
  forgets which models were cooling down.
- **No alerting.** The kinds are in the log and the stats endpoint; nothing
  emails the owner when `auth` starts appearing.
- **Quality failures are not here.** An answer that arrives and fails its checks
  is the verify loop's job, not this module's — a repair round, not a retry.
