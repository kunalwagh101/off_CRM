# F-06.02 / S-06.02.23 — exact scope of audit-source verification

Date: 2026-11-22. Branch: `develop`. Scope: A01-A04, A26, A30, A31, A35.

**Previously passing commit** `28470a8`, GitHub [45019165204](https://github.com/kunalwagh101/off_CRM/actions/runs/45019165204): 5/5 jobs passed. Python 3.11 3459 passed/149 skipped; real PostgreSQL 3570 passed/107 skipped; quality npm production and development audits found 0 vulnerabilities. This was before the A26 and A35 new tests, so it is **not** their final-source full CI evidence.

| Audit item | Actual test/proof on develop | What is NOT proven |
|---|---|---|
| A01 | test_audit_wp1.py::test_production_configuration_refuses_ephemeral_customer_state | Hosted customer database/object durability |
| A02 | test_audit_wp1.py::test_failed_concurrent_transaction_cannot_rollback_another_writer, nested savepoints, WP1 concurrent write/restart | Live multi-instance customer transaction proof |
| A03 | test_audit_wp1.py::test_rejected_backup_does_not_break_existing_workspace and restore service rebinding | Independent offsite restore |
| A04 | test_audit_wp1.py::test_backup_contains_durable_stores_assets_and_unsubscribe_secret, oversize restorable backup, every-store restore | Full current hosted workspace backup and empty-target recovery |
| A26 | [Production Docker 45024963091](https://github.com/kunalwagh101/off_CRM/actions/runs/45024963091) on `0c42801`: build, app, readiness, actual five lock-matched runtime imports, binary libpq, no dev tools, restart PASS | Live hosted provider/SQL/recovery/customer rollout |
| A30 | tests/test_a30_active_runbook.py and source docs, 45019165204 PASS | Entire production and feature-tree/release acceptance |
| A31 | quality job two npm audits with 0 reported vulnerabilities at 45019165204 | Future advisory updates, independent runtime exploit assessment |
| A35 | Existing test_frontend_routes_exist.py source boundary PASS at 45019165204; improved matcher recognizes nested TypeScript generics | Dynamic/indirect URL calls, authenticated Render UI |

## A35 D-510 independent TDD

A separate local Python regex fixture reproducing the live scanner first returned only simple `api.get("/meta")`; the unit expectation for `api.get<Paginated<Contact>>("/contacts")` and multiline `api.post<Promise<Result<Item>>>("/campaigns")` failed (1 failed, exit code 1). After changing `(?:<[^>(]*>)?` to `(?:<[^()]*>)?` and allowing whitespace before `(`, the same pytest case passed (1 passed). An equivalent named regression is now committed to `tests/test_frontend_routes_exist.py`; its final GitHub execution must be observed separately.

## Live/customer constraints

F-06.02 remains IN_PROGRESS. The actual Render QA service has not deployed the newest source because the selected workspace ran out of build pipeline minutes. Current source QA, isolated Docker, a disposable Render demo and a signed-in production customer workflow are **different evidence categories**. No customer records/provider emails or paid infrastructure were touched. Outstanding: independent offsite encrypted backup and actual restore, dedicated hosted PostgreSQL, durable media/object storage, supervised worker, cross-workspace CRM tenant isolation, live browser/provider/sandbox and independent penetration.
