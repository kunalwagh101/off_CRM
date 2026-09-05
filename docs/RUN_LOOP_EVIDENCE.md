# S-02.02.01 evidence notes

The authoritative DONE evidence belongs in `BOARD.md`; this file records the security properties the focused suite exercises so reviewers can inspect the slice without reverse-engineering test names.

- Hard step budget is enforced by host code and prevents an N+1 model decision or browser action.
- Every decision enters through `EgressBroker.call` and browser page material is classified `INTERNAL`.
- Decision trace rows contain provider, model, duration, estimated token counts and explicitly-labelled `estimated_cost_usd`.
- The model cannot create an eleventh browser verb or pass `confirmed=true` to approve its own consequential click.
- Existing Page confirmation policy stops the run with `needs_confirmation`.
- Real Chromium Gate 2 changes a live tab through a broker-produced structured action and stops at the one-step budget.

Focused command:

```bash
uv run pytest tests/test_agent_run.py -q
```
