# Traffic shifting between variants (§4H)

`ai/context.py` counts sends and replies. This decides what to do with the
numbers: what share of the next batch each variant gets.

---

## Why the obvious approach fails

"Run both to 20 sends, then pick the winner" is how A/B splits are usually
described. On cold outreach it is close to useless, and the arithmetic says why:

| Comparison | Sends needed **per variant** |
|---|---:|
| 2% vs 4% | ~1,140 |
| 2% vs 3% | ~3,800 |
| 3% vs 6% | ~748 |
| 5% vs 10% | ~434 |

And 20 sends with zero replies has a **54% chance of happening even when the
true rate is a healthy 3%.**

A threshold rule fed that data does not make a cautious decision. It makes a
confident wrong one.

---

## Thompson sampling instead

Each variant gets a Beta posterior over its reply rate. To allocate: draw one
sample from each, give the batch to whoever drew highest, repeat. The share each
variant wins **is** its probability of being best.

This behaves correctly at both ends **without anyone choosing a cut-off**:

- **Thin data** → posteriors overlap almost completely → draws come out near
  even → traffic stays near even. The system says *"I don't know"* by **acting**
  like it doesn't know.
- **Real evidence** → posteriors separate → traffic shifts on its own.

That graceful degradation is the entire reason for the choice. **A threshold has
to be right. This does not.**

---

## What it looks like

```
thin: 1/20 vs 3/20          ← looks like a 3× improvement
   rewrite   3/20   obs 15.0%   P(best) 83%   share 80%
   original  1/20   obs  5.0%   P(best) 17%   share 20%
   confident=False
   "Leaning towards rewrite — 83% against 17% — but not conclusive. Separating
    rates this similar takes roughly 223 sends per variant, about 203 more each.
    rewrite already takes 80% of the next batch, and the remaining 20% keeps
    testing the alternative rather than abandoning it."

near-identical: 10/300 vs 11/300
   confident=False
   "...takes roughly 52,382 sends per variant, about 52,082 more each.
    Traffic stays close to even (58% / 42%) while the evidence is this thin."

clear: 20/1000 vs 40/1000
   confident=True
   "rewrite is ahead with 100% probability of being best. Taking 95% of the
    next batch."
```

That 52,382 figure is the useful one — it tells you **to stop trying**, rather
than showing a percentage that looks decisive and isn't.

---

## Guardrails

**The leader never takes everything.** A 5% floor per active variant. Without a
holdout, a winner that later degrades would look fine forever, and a variant
unlucky in its first twenty sends could never recover.

**Retired variants get nothing.** Excluded entirely, not down-weighted.

**Seeded runs are reproducible**, so an owner can re-derive the split they were
shown last week.

**Reply rates are shown as posterior means, not raw fractions.** One reply from
two sends is not a 50% reply rate, and quoting it as one is how people talk
themselves into bad templates.

---

## What it will not do

**It decides *how much*, never *whether*.**

§3 of the brief is explicit that nothing goes live automatically — a rewrite is
offered, saved as a variant, and a human decides if it runs at all. This
allocates only between variants the owner has **already approved**.

The bandit cannot promote an unapproved rewrite, because an unapproved rewrite
is not an active row in the counter table for it to see.

---

## One defect caught while building

The first version's verdict read *"Traffic stays near even while the evidence is
thin"* — while allocating **80/20**. The sentence and the numbers disagreed.

Thompson *does* shift traffic below the confidence bar; that is the point of it.
The text was simply false. It now describes the split that is actually
happening, and there is a parametrised regression test asserting that the
"stays close to even" wording only ever appears when the leader is under 65%.

A dashboard that says one thing and does another is worse than no dashboard.

---

## Using it

```python
context.traffic_split("local", template_id="t1")
# → {"arms": [...], "confident": bool, "verdict": "...", "leader": "rewrite"}
```

The allocation maths is in `ai/bandit.py` and imports no database and no
provider — a structural test enforces that. Keeping it pure is what lets it be
tested exactly.
