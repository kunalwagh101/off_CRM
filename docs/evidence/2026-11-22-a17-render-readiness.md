# A17 — Render readiness and safe cold-start smoke (2026-11-22)

**Scope:** Audit S-06.02.23, public endpoint verification only. Source `develop` `4e5de7d4ceca52439c7287a6aba6d4760b19ef6c`. Defects D-505 and D-506; decision DD-182.

## Tests and release evidence

- RED first (isolated local Python): 6 failed, 19 passed. Five synthetic `/health/ready` HTTP 200 bodies falsely passed without JSON `status=ready`; one transient initial GET caused a false-negative smoke. Existing safety cases passed.
- GREEN (same 25 tests): `python -m pytest -q tests/test_render_functional_smoke.py` -> 25 passed. Scope of retry: first public GET /, once, transport failures only. No retry on HTTP status failures, authenticated features, or POST.
- Full GitHub CI [45005353735](https://github.com/kunalwagh101/off_CRM/actions/runs/45005353735): 5/5 jobs green. Real PostgreSQL 3,563 passed/107 skipped; board verifier 72/72 historical commands; frontend 242 passed. The existing runtime-health failure test `tests/test_audit_wp1.py::test_readiness_fails_when_required_database_is_unavailable` remains in the full suite.
- Actual functional Render deploy `dep-dc1au02jnfac7388nh1g` on `srv-dc0vbd8m7kps73di4pm0`, `majors_97`: LIVE on same commit. GitHub hosted HTTPS smoke [45005353383](https://github.com/kunalwagh101/off_CRM/actions/runs/45005353383), rerun attempt 2, PASS 8/8. Render access logs independently match eight read/negative-auth requests. No 5xx request logs matched the short smoke time window query.
- Separate full Render review `dep-dc1aub7f3r2c73c6lmeg`: running when evidence was written, not claimed complete. Preliminary hosted-backup suite: 26 passed/1 skip; companion/skills/roles: 57 passed/2 skipped.

## Hard limits

This is NOT a proof of offsite backup, customer data surviving a deploy, real-provider traffic, an authenticated CRM customer browser path, independent penetration review, or a full live database-outage drill. Do not promote F-06.02, F-06.03, F-04.01 or S-06.02.23 to DONE on this evidence alone.
