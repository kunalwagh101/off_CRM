# Two defects found during the audit

Both reproduced against the real code, not inferred.

---

## Finding 1 — Simple mode never picks the cheap model (cost, not security)

**Severity:** high cost impact, no security impact.
**Where:** `ai/broker.py:281-283`.

### What the UI promises

`ai/modes.py:63-66`:

> "Picks the cheapest model that is allowed and good at this. **Fastest and
> cheapest.** Use this for everyday work."

### What actually happens

`registry.candidates_for` correctly returns every permitted provider+model pair
**cheapest first** (`registry.py:707-713`, sorting on
`(tag_match, free_first, cost, name)`).

Then `broker.plan()` discards all but the highest tier:

```python
best_rank = max(candidate.tier.rank for candidate in with_budget)
same_tier = [c for c in with_budget if c.tier.rank == best_rank]
```

### Reproduction

Setup: Mistral (FR, tier A, cost 20.0) and DeepSeek (CN, tier C, cost 3.57)
both connected. Task: `data_class=public` — a coding question, nobody
identifiable.

```
data_class = public
  registry says permitted (cheapest first): [('deepseek','C',3.57), ('mistral','A',20.0)]
  broker.plan() will actually use        : [('mistral','A',20.0)]
  DROPPED -> deepseek: DeepSeek is tier C; this task is running at tier A.
             off_CRM never fails over to a lower trust tier.
```

**5.6× the cost, on work where the cheap model is fully permitted.**

Remove the tier A provider and DeepSeek runs fine — proving it was always
allowed to hold this data class.

### Why the current rule is wrong *here*

The rule exists to stop **failover** silently demoting restricted data. That is
correct and must stay. But it is being applied to **initial selection**, and
those are different situations:

- **Demotion (real risk):** a task needs tier A, tier A fails, so we quietly
  hand the same material to tier C. Must never happen.
- **Selection (not a risk):** `candidates_for` has *already* filtered every
  candidate through `resolved.permits(data_class)` (`registry.py:689`). Every
  model in that list is permitted for this data class. Picking the cheap one is
  not a demotion — the permission check already passed.

The rejection message is also misleading: it says "never fails over" when
nothing failed. This is the first choice, not a fallback.

Note too that each candidate gets its **own** payload built under its **own**
policy (`broker.py:352`: `payload = build_payload(request, candidate.policy)`).
So a tier C candidate would receive the tier C payload, not the tier A one.
This is exactly what compare mode already does safely across tiers.

### The fix applied

Narrowed the rule to where it earns its keep:

- `DataClass.PUBLIC` — by definition contains no identity — uses the full
  cost-sorted list across tiers.
- Every other data class keeps today's behaviour: highest tier only.

This captures the cost win where it is largest (all software and code work is
`public`) with **zero** new privacy exposure, because public data carries no
identity to expose.

A `cross_tier_public_routing` setting on `WorkspaceEgressSettings` allows
switching back to the old behaviour per workspace. It defaults to on.

---

## Finding 2 — `best_text` does not mean best

**Severity:** latent. Not currently wrong on screen; wrong the day anything
reads it.
**Where:** `ai/modes.py:166-173`.

```python
@property
def best_text(self) -> str:
    """The single answer a caller should use when it wants just one."""
    if self.steps:
        done = [step for step in self.steps if step.text]
        return done[-1].text if done else ""
    ok = [branch for branch in self.branches if branch.ok]
    return ok[0].text if ok else ""
```

With the sort immediately above (`modes.py:229`) on
`(tier, ok, duration_ms)`, `ok[0]` is **the fastest successful answer from the
highest trust tier**. Not the best answer. Nothing compares quality — nothing
in the module can, because there is no scorer.

In orchestrated mode it returns `steps[-1]` — whatever the last step happened to
emit.

### Fairness to the existing code

The docstrings are honest. Compare mode's own docstring says the **owner** reads
the answers and picks (`modes.py:8-10`). That is true and correct behaviour.

The problem is only the **name**, which promises a judgement the code does not
make — and `best_text` is exported through `to_dict()` (`modes.py:187`) into the
API and typed at `frontend/src/types.ts:728`. No component reads it today, which
is why this is latent rather than live. The day an automated caller picks it up,
it silently gets "fastest trusted" while the name says "best".

### The fix applied

Renamed to `first_permitted_text`, with a docstring that states the ordering
rule outright and says explicitly that no quality comparison is performed.
`best_text` is kept as a deprecated alias so the API contract does not break,
and both are emitted in `to_dict()`.

When the eval harness lands, a real `best_text` can be added that actually
scores branches — and the name will then be true.
