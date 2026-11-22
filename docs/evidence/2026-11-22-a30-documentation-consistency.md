# A30 — truthful branch, hosting and production-state instructions

**Scope:** F-06.02, active audit story S-06.02.23, A30, D-508. **Branch:** `develop` only. This is a documentation correctness fix and automated regression, **not a production capability, migration or customer deployment**.

## What was wrong

The active `docs/BRANCHING.md` and `render.yaml` claimed GitHub Actions runners were unavailable, even though [45014613268](https://github.com/kunalwagh101/off_CRM/actions/runs/45014613268) passed all 5 jobs. The branch guide's 2026-09 single-disk configuration looked like a production readiness recipe but omitted dedicated hosted PostgreSQL, independent encrypted backup, object storage, durable email worker and recovery proof. It also tied data loss to a Git push rather than service restart/redeploy. `FEATURE_TREE.md` still listed `S-02.02.01` as next even though it is DONE on the live `BOARD.md`.

## Test and implementation

- **First:** `tests/test_a30_active_runbook.py` committed `2041004`, with active CI/disk/ephemeral requirements. Direct current-source checks at the old docs content failed the no-CI-runner, historical disk and missing-dependencies expectations. A focused pytest RED output should be linked separately; do not assume source checks equal executed pytest.
- **Fix:** Updated only guidance and tests, not Render services or deployment configuration behaviour. Added guards for historic feature priority and blueprint notes. Do not claim the historical SQLite proposal is a production rollout.
- **GREEN:** Final GitHub five-job CI result must be attached after it finishes. Until then current source is not final verified.

## Remaining A30 / feature gates

Operator review of the live Render service, customer-visible login/storage behaviour, current-source feature map alignment, S-06.01.06 tenancy, S-06.03.04/.06 durable/offsite storage and backup, S-06.02.40 worker and independent security/pentest remain **OPEN**. No production DONE label, customer records, paid resource or real provider execution was involved.

## Current-source CI (2026-11-22)

[GitHub run 45019165204](https://github.com/kunalwagh101/off_CRM/actions/runs/45019165204) on `28470a8` completed **all five jobs successfully**, including the A30 documentation checks. This is the current source-level verification of A30; no customer-host rollout or completion of all related feature dependencies is implied.
