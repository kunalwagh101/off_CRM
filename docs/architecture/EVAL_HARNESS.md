# The eval harness

Answers the question the run modes could not: **does orchestration actually beat
one good model?**

Before this, `modes.py` offered simple, compare and orchestrated, the UI called
compare "pick the best", and nothing measured either claim. A grep of the AI
module for `eval`, `champion`, `win_rate` or `benchmark` returned zero hits.

---

## Run it

```bash
offsetx-evals list                                    # suites and case counts
offsetx-evals run --suite email_first_contact --dry-run   # plan + call count, spends nothing
offsetx-evals run --suite email_first_contact --modes     # score models AND modes, decide routing
offsetx-evals champion --suite email_first_contact        # what it routes to now
```

Global flags come before the subcommand: `offsetx-evals --workspace local run …`.

---

## What it found immediately

On the shipped suite with two scripted models, compare mode scored **exactly the
same as the champion**:

```
  mistral      1.0000
  deepseek     0.3333
  compare      1.0000
```

Not similar. Identical — because `RunResult.first_permitted_text` returns the
branch from the **highest trust tier**, and that branch *is* the champion's
answer. Compare mode fanned out to two models, paid for two calls, and returned
the text one of them would have produced alone.

That is not a bug in compare mode. Compare mode is designed for the owner to
read every branch and choose. But it means **using compare mode programmatically
buys nothing**, and nobody could have known that without measuring.

This is the whole argument for the harness in one result.

---

## How a score is produced

A check is a **pure function of the output text**. Same output, same score,
forever. No model judges anything — for the same reason no model enforces
policy: a grader that varies is not a measurement.

```
score(case) = checks passed / checks total
score(suite) = mean over cases
```

Twelve check kinds ship, in `ai/evals.py`:

| Kind | Catches |
|---|---|
| `no_preamble` | "Certainly! Here is the email:" — answering the instruction, not doing the task |
| `no_placeholder` | `{{first_name}}`, `[NAME]`, `XXX` left unfilled |
| `no_email_address` | An **invented** address. Worse than a missing one — it looks deliverable. |
| `forbids_any` | AI tells: "I hope this email finds you well", "delve into", "game-changer" |
| `word_count` / `char_count` | Length bounds |
| `requires_pattern` / `forbids_pattern` | Regex must / must not match |
| `mentions_all` | Required terms present |
| `valid_json` / `json_has_keys` | Structured output, tolerating a code fence |
| `valid_python` | Parses. Does **not** execute — that needs the sandbox (§4J). |

An unknown check kind **fails** rather than passing, so a typo in a check name
cannot silently inflate every score that uses it.

---

## The gate

```
champion   = best measured single model
challenger = a run mode

promote the challenger ONLY IF all three hold:
   1. higher mean score
   2. case-level win margin unlikely under chance  (p < 0.05)
   3. cost within the ceiling                      (default 4x)
```

Every other path keeps the champion. The default is always "do not change" — the
same fail-closed instinct as the egress gate.

### Why a significance test and not `>`

A suite has tens of cases, not thousands. Comparing two means and shipping
whichever is higher flips the winner on noise roughly **half the time when the
two are genuinely equal** — and each flip costs real money, because the
challenger runs several models per task.

Both subjects run the *same* cases, so the comparison is paired. The honest test
for paired data is a **sign test**: count the cases each side wins, and ask how
likely that split is from a coin. Exact, no dependencies, no assumption about
how scores are distributed.

```
 wins  losses     p
   10       0   0.001   promote
   15       5   0.021   promote
    8       2   0.055   keep champion — just misses
    6       4   0.377   keep champion — this is the one `>` gets wrong
    5       5   0.623   keep champion
```

Ties are excluded, which is standard: a case both sides score identically
carries no information about which is better. Zero decided cases returns
`p = 1.0`, so "no evidence" can never look like "significant".

---

## Rules it inherits

- **Nothing bypasses the broker.** An eval is an ordinary caller with ordinary
  tier rules. A case carrying person data cannot reach a provider not allowed to
  hold it — asserted by running the suite against a tier D aggregator and
  confirming every case is refused.
- **No model can read or write the scoreboard.** No query interface, no tool, no
  provider import. Asserted by an AST walk, the same technique
  `test_ai_egress_wall.py:412` uses for the egress gate. A scoreboard a model
  could edit tells you what the model wants you to hear.
- **The suite is config.** `config/evals.yaml`, beside `providers.yaml`. Adding
  a case is a data edit.

---

## Storage

`ai_evals.db`, SQLite, beside the other stores.

| Table | Holds |
|---|---|
| `ai_eval_runs` | One row per subject per run: score, per-case scores, errors, duration |
| `ai_champions` | Current champion per suite, with the reason it won |

`route_for()` returns `simple` when nothing has been measured. **An unmeasured
system routes to one model, never to an ensemble nobody has checked.**

---

## The honest limitation

**Seven cases is not enough.** The shipped suite is a starting skeleton, and the
CLI says so on every `list`:

```
NOTE: 3 cases is too few to detect a small difference.
      Aim for 30+ before trusting a close verdict.
```

With three cases, a challenger needs a clean sweep to reach p < 0.05 — and even
then the estimate of *how much* better is worthless. The most valuable thing you
can do with `config/evals.yaml` is **add cases from real work you were unhappy
with**. A suite made of your own failures measures your own quality; a suite of
invented examples measures nothing.

Second limitation: these checks measure whether a draft is **well-formed**, not
whether it **gets replies**. Reply rate is the only ground truth that matters,
and `ai/context.py` already counts it per template with a 20-send threshold
before judging. This harness is the fast proxy you run before shipping; the
context layer is the slow truth you get afterwards. Use both.
