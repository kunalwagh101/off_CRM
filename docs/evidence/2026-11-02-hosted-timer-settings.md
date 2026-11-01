# S-06.03.06 — Hosted timer-settings slice: TDD evidence

Date: 2026-11-02 IST. Repository: kunalwagh101/off_CRM, branch develop.

## Requirement and solution

One identified risk in F-06.03: owner-defined automation settings lived in `automation.json` and `content_automation.json`, which disappear on a free Render restart. The implementation uses two named documents through the same hosted storage used for provider settings and AI quota. Owner-configured local installations retain their existing files. No storage migration is attempted without explicit approval and no new send is triggered.

## Observed test-first sequence

- RED source `9a30a43f32bcbe34410d289def374818094826ee`, isolated Render `dep-dbjqsn3bc2fs73dkcag0`: **6 failed**, no false PASS, review build stopped at the early test gate.
- Implementation source `ff40ea84843ea119be48b7d1eedbebac23f9e838`, Render `dep-dbjqtnjbc2fs73dkedjg`: **5 passed, 1 failed**. The one failure was the new test fixture omitting `AppSettings.secrets_key`. Validation correctly refused a half-configured hosted install. No app validation was changed to hide this.
- Corrected test source `6166be72a618736e6bb0a60afcd6235bb45cee22`, isolated Render `dep-dbjqubh42hec73dr2bu0`: **6 passed, 1 warning** for the new test file; **7 passed, 1 warning** for `tests/test_hosted_storage_readiness.py`. Remaining broad review stages are recorded only when observed.

## Security and limits

The test cases cover application restart, lost disposable folder, failed hosted write, local-file ambiguity and backward compatibility. The hosted store uses the existing transaction and secret-protected configuration. Real external cloud database backup and restore, cross-instance actual task execution, external SMTP/SES success, complete old-configuration migration, unsupervised sending and full project penetration remain unverified. No customer data was modified and no customer-facing service deployed.
