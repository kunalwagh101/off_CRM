# Live end-to-end sweep

Drives a **real local off_CRM server** over HTTP with a **real AI key**, the way
a customer would, and writes one JSON line per check. Written for the
2026-11-13 sweep (`docs/evidence/2026-11-13-live-e2e-sweep.md`), which found
D-440 to D-458 after 3,292 green unit tests.

Nothing here is product code. It never imports `create_provider`; the only AI
calls go through the running app's own broker.

## Run it

Start a throwaway server first, with the AI key **not** in its environment
(keys come only from the app, DD-64):

```bash
export OFFSETX_DATA_DIR=$(mktemp -d) OFFSETX_WEB_PORT=8777
export OFFSETX_LOCAL_API_TOKEN=e2e-$(openssl rand -hex 20)
export OFFSETX_DEMO_USERNAME=major OFFSETX_DEMO_PASSWORD=Correct-Horse-Battery-9
export OFFSETX_SESSION_SECRET=$(openssl rand -hex 32)
env -u NVIDIA_API_KEY uv run offsetx-web > server.log 2>&1 &
```

Then, from another shell with the same variables plus the key:

```bash
export OFFCRM_E2E_TOKEN=$OFFSETX_LOCAL_API_TOKEN OFFCRM_E2E_SERVER_LOG=$PWD/server.log
cd scripts/qa/live_e2e_sweep
uv run python sweep.py http://127.0.0.1:8777 "$OFFCRM_E2E_TOKEN" openapi.json sweep.json
for part in a_ai b_crm b2_send c_rest d_sec e_dur; do uv run python $part.py; done
```

`sweep.py` needs the OpenAPI document first:
`curl -H "X-OffsetX-Token: $OFFCRM_E2E_TOKEN" localhost:8777/api/openapi.json -o openapi.json`.

## Order matters

`a_ai` connects NVIDIA through the app; `b_crm` creates the campaign the
later parts reuse (saved in `state.json`); `d_sec` creates a second workspace
and probes isolation; `e_dur` exports and restores a backup, which rewinds
anything created after it.

## Reading a FAIL

A FAIL is a lead, not a verdict. In the first run, 11 of 33 FAILs were the
script's own wrong inputs, and the app's error message said so precisely.
Each real defect went to `DEFECT_LOG.md` with a test in
`tests/test_e2e_findings_2026_11_13.py`.
