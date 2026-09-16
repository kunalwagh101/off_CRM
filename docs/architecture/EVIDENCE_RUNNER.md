# Evidence runner

`S-06.02.08` makes a green or red Board mean one thing on every machine.

## Clean-checkout verification

From a clean checkout, after installing `uv`, Python 3.10+ and Node.js 24/npm,
run exactly this setup and verifier:

```bash
uv sync --extra dev --extra email --locked
npm ci --prefix frontend
uv run --no-sync python scripts/verify_board.py
```

There is no second environment-preparation step. The first command creates the
locked Python environment including test and email extras. The second installs
the locked frontend dependencies. `--no-sync` on the verifier is deliberate: if
the setup is incomplete, verification fails instead of silently repairing its
environment.

## One command shape on the Board

Every `DONE` item records only:

```text
command: python scripts/run_evidence.py S-nn.nn.nn
```

The Board does not carry shell pipelines, `cd`, a choice between `python` and
`uv`, or a private install command. `verify_board.py` checks the command text,
then launches `run_evidence.py` itself with the verifier's `sys.executable`.
Therefore every Python evidence test uses the exact interpreter selected by the
single `uv run --no-sync ... verify_board.py` invocation above.

`run_evidence.py` reads the story's existing `tests:` field:

- `tests/...` is replayed with `sys.executable -m pytest ... -q`;
- `frontend/...` is replayed with `npm test -- ...` from `frontend/`;
- `verification/...` remains environment-gated live evidence and is reported,
  not silently treated as clean-checkout evidence.

A DONE story with no replayable Python or frontend test is refused. Unknown test
locations are refused. The runner never executes Board text through a shell.

## Why this boundary exists

Before this story, DONE evidence mixed `python -m pytest`, `uv run pytest`,
`uv run --no-sync pytest`, npm commands and compound shell expressions. A stale
or unsynchronised environment could therefore turn the Board red while the code
was correct. That is a dangerous failure mode for a verifier: once a lie
detector cries wolf, people learn to ignore it.

The invariant now is simple: **one locked setup, one verifier interpreter, one
evidence runner.**
