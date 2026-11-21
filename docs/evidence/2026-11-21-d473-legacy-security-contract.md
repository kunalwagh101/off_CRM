# D-473 — full regression of D-451 containment, 2026-11-21

Source before correction: `f7021b83`.
RED evidence: GitHub Actions `44900978605` Python 3.11 full suite, **8 failed, 3346 passed, 149 skipped** (2026-11-21, job 136836608442). All failures are from historical tests expecting nonlocal HTTP access to unowned shared CRM data, which the later security boundary D-451 deliberately blocks.

Eight affected checks:
- `tests/test_draft_connectors.py::test_actual_draft_generation_uses_workspace_broker_without_legacy_profiles`
- `tests/test_memory_workspace_api.py::test_memory_reads_writes_stats_approval_and_feedback_are_workspace_owned`
- `tests/test_provider_profile_isolation.py`: malicious provider fields, beta draft routing, unconfirmed legacy profile, provider-call access.
- `tests/test_recall_workspace_mutations.py`: signed forget and unsafe rebuild.

Source change: preserve D-451's HTTP 403 for nonlocal shared CRM while retaining executable owner-token validation of malicious inputs, direct workspace-local profile/memory visibility, and memory generation from actual owner contact/draft/reply actions. Explicit 403 for beta and no secret content in refused responses. The underlying provider-call/recall stores remain tested for scoped records; the owner sees combined historical audit information, customer cannot access it until migration.

No API/egress auth controls changed. The tests require full fresh CI and Render acceptance on the new commit. Do not waive missing independent penetration, browser UX, real backup destination, external provider, CRM migration, or customer release.
