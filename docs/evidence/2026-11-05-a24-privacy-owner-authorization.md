# A24 / S-06.02.67 — Owner-only subject-access and deletion API

## Source and scope
Branch: `develop`; initial head `c8f9bf7790c1731a0a985e34253443a830238f8f`. Existing `PrivacyService` already implements 12-store personal-data inventory, preview, confirmed multi-adapter deletion, failure receipt and synthetic tests. The missing boundary was **authorisation of API callers**, not an absent deletion service.

The CRM is not yet fully workspace-owned (Q-27). Ordinary workspace cookies previously had permission to issue privacy subject-access, deletion-preview, execute/retry known deletion request IDs and retrieve the deletion phrase. A subject could be matched through globally shared contact rows. This is an unauthorised personal-data access/erasure risk (D-371).

## TDD RED, actual isolated Render
- Test-only source `f80815665335982fde7226309755554c9c973565`; review gate executable source `4c97f564641c73048b30f37721da877d3e91b231`.
- Deploy `dep-dbm3nv9srm7s73f07bs0` on isolated review service `off-crm-review-runner-20261015`.
- `uv run pytest -q tests/test_audit_a24_privacy_owner_authorization.py`: **4 failed, 1 passed, 1 warning**. The 4 failures exposed missing 403s for ordinary workspace logins, known preview ID and fresh session. The owner-path test already passed. No customer data.

## GREEN source and gate
- Fixed only `offsetx_apollo_builder/api/app.py` at `411770421133ea292153e68d9d0642cd1e198fc5`.
- Reused existing `require_install_owner(request)` on `/api/v1/privacy/subject-access`, `/api/v1/privacy/deletion-preview`, `/api/v1/privacy/deletions/{request_id}`, `/api/v1/privacy/deletion-confirmation`. Guard executes before accessing subject inventory/erasure service.
- Render review `dep-dbm3oj8ae00c7389h7d0` step #27: same command **5 passed, 1 deprecation warning in 6.29s**. Synthetic owner login in workspace `local` and install API token still access and complete confirmed deletion while unrelated contact survives.
- No schema migrations, new package, data erasure in real user storage, provider API call, main promotion or customer deployment. Security test uses disposable CRM and isolated login sessions.

## Release and rollback boundaries
The correction prevents ordinary workspace sessions performing privacy reads/deletions. It does **not** prove that complete person data is deleted from every store, restored backups, legal-hold or retention decisions; A24's whole lifecycle remains OPEN. Q-27 CRM tenancy and Q-07 automatic retention are owner decisions. Full source-bound Render SQLite/PostgreSQL, Ruff, Chromium, full Git-history verifier, independent penetration and customer-host acceptance remain separate evidence gates.

Rollback: revert only the four route guards (do not delete privacy requests or CRM data). Doing so re-opens D-371; not a safe customer rollback unless privacy API is disabled or client access blocked by an equivalent control.

## Cross references
- D-371: `DEFECT_LOG.md`
- DD-147: `DECISIONS.md`
- Requirement: R-194, story S-06.02.67, active audit S-06.02.23
- Audit finding: A24 in `docs/audits/2026-09-07-production-audit.md`
