# Bounded Browser Run Loop — S-02.02.01

## What shipped

The browser already had safe hands: perception, ten fixed verbs, policy checks and an append-only trace. This story adds the missing loop that turns an owner goal into a sequence of bounded browser actions:

```text
owner goal
   |
   v
perceive current page
   |
   v
EgressBroker decision
   |
   v
strict structured-action validator
   |
   v
one existing Page verb
   |
   v
append decision + action to Trace
   |
   +----> done / refused / needs confirmation / hard budget stop
   |
   `----> perceive again
```

It does not add an eleventh browser verb, arbitrary JavaScript, selectors, a credential tool, PLAN.md, resume/steering or safety countdowns.

## Security boundary

### Browser content is INTERNAL

A public URL does not imply public page content. Once the owner is signed in, a page can contain CRM records, messages, account information or other private material. Every Run Loop decision therefore creates an `EgressRequest` with `DataClass.INTERNAL`.

The consequence is intentional: only a model/provider trusted for internal material may make the decision. The loop does not downgrade the page to `PUBLIC` simply to widen model availability.

### Every decision uses the egress broker

`agent/run.py` never instantiates or calls a provider. It calls `EgressBroker.call()`, so the existing trust-tier filter, quota checks, allow-list payload construction, scanner, provider selection and egress logging remain the only model door.

The current page snapshot is supplied once as bounded public-context input inside an INTERNAL request. Owner goal/history are supplied separately. Page text is labelled untrusted in the system prompt so content on a website cannot redefine the owner goal or the action contract.

### The model cannot widen the browser vocabulary

A decision must be one JSON object with `status=act` and exactly one of the existing ten verbs:

`goto`, `click`, `type`, `press`, `scroll`, `select`, `wait_for`, `read`, `screenshot`, `back`.

Each verb has an explicit argument allow-list and value bounds. Unknown top-level fields, unknown arguments and unknown verbs fail closed. In particular, `click` does not accept `confirmed`; a model cannot approve its own consequential action. The existing `Page.click()` policy can return `needs_confirmation`, at which point the run stops.

## Hard step budget

`step_budget` is enforced by host code and must be from 1 through 50. It is not a prompt instruction.

One model decision that asks for a browser action consumes one step when that action is attempted, including a refused/confirmation-gated action. When `steps_used == step_budget`, the loop returns `budget_exhausted` immediately after the last permitted action. It does not ask the model for an N+1 decision.

The result reports:

- final status;
- requested goal;
- hard budget;
- steps used;
- reason for stopping;
- last attempted action;
- last known URL;
- trace summary.

## Trace and cost

Every model decision is appended to the existing browser `Trace` with provider id, model id, duration and estimated input/output tokens. `Trace.Step` now also carries `estimated_cost_usd`, and `Trace.summary()` totals it.

This value is deliberately named **estimated**. The current provider adapters do not expose billing usage consistently. The loop estimates tokens as approximately four characters each and applies the selected model's configured input/output price from `config/providers.yaml`. The estimate is for operator visibility only; it is not used for quota enforcement, authorization or billing reconciliation.

Free/self-hosted models can therefore record an explicit `0.0` estimate rather than looking like an unmetered missing value.

## Failure behaviour

The run terminates visibly rather than improvising around a broken boundary:

- browser perception failure → `failed`;
- broker/provider failure → `failed`;
- malformed/forbidden model decision → `refused`;
- browser policy refusal → `refused`;
- consequential action needing owner confirmation → `needs_confirmation`;
- browser action failure → `failed`;
- model says goal is complete → `completed`;
- hard budget reached → `budget_exhausted`.

Every terminal path leaves the append-only trace intact.

## Acceptance evidence

Focused evidence:

```bash
uv run pytest tests/test_agent_run.py -q
```

The suite proves:

1. an endlessly acting model gets exactly N decisions and N action attempts for budget N;
2. decisions use the real `EgressBroker` path with a deterministic test transport and appear in the trace with provider/model/timing/token/cost evidence;
3. browser decisions are classified `INTERNAL`;
4. an `evaluate`/JavaScript-style eleventh verb is refused;
5. a model-supplied `confirmed=true` is refused;
6. the existing confirmation boundary stops the loop;
7. Gate 2 launches real Chromium, obtains a bounded `goto` decision through the broker path, changes the real tab, and stops at the one-step budget before another decision.

Full release gate:

```bash
uv run pytest -q
uv run python scripts/verify_board.py
cd frontend && npm ci && npm test && npm run build
```

## Rollback

No database schema or external data migration is introduced. Rollback is code-only:

- remove `offsetx_apollo_builder/agent/` and its focused tests;
- revert the optional `estimated_cost_usd` field from browser trace handling if the whole increment is reverted.

Trace JSON is forward/backward tolerant because missing `estimated_cost_usd` already reads as `None`; old traces remain readable.

## Scope deliberately left for the next stories

- `S-02.02.02` owns PLAN.md as persistent run memory.
- `S-02.02.03` owns interrupt, steer and resume.
- `S-02.02.04` owns countdowns/owner confirmation before consequential actions.

This story gives the agent bounded will. It does not yet make that will resumable or safe to leave unattended for consequential actions.