# D-500 — local credential file safety review, 2026-11-22

## Finding

The old `AppSettings.ensure_api_token` and `ensure_session_secret` loaded a linked file as a legitimate token if it held 32 or more characters. If a token file was present but shorter, they opened the same path with `O_TRUNC`, following a final symlink and potentially overwriting unrelated content. They also accepted an already world-readable token file. During an operator-controlled directory swap, unpinned path creation could redirect a new credential to a different parent. This is a local filesystem security boundary, not an observed remote CRM exploit.

## Scope and TDD

- Tests introduced before implementation: `tests/test_local_secret_file_safety.py` at `1b33fec62e967c03b32b09a920be3a995a6f0576` (linked file, invalid existing file, 0644 permissions, injected parent-directory swap, private file and reuse for both bootstrap API token and session signing key).
- Fix on `develop`: `c93b2e34aa814ac7ce530e6a36edb383482aca37` modifies only `offsetx_apollo_builder/api/config.py`. Uses directory-descriptor pinning and `O_NOFOLLOW` on POSIX, `O_EXCL` to create new mode-0600 files, never `O_TRUNC` or silently regenerate a damaged existing credential. Reads at most 4097 bytes, requires regular private ASCII text of at least 32 characters. The existing API-token reload path also uses this guarded reader.
- An additional reload-symlink regression is staged for the final evidence commit; do not claim it executed before the final-source run completes.
- Production Docker build: GitHub Actions `44952349680` completed successfully on source `c93b2e34`, including a container restart and readiness probe.
- Fixed-source CI `44952349677`: Python 3.10/3.11/3.12 each 3,431 passed, 149 skipped; real PostgreSQL 3,542 passed, 107 skipped; quality/board PASS. All five CI jobs are successful. The exact-source review deploy is not yet complete.
- All five fixed-source CI jobs on `44952349677` passed; exact-source Render QA is a separate pending release gate.
- Test-first RED was captured by re-running the Python 3.11 job of old commit `1b33fec` ([44952285835](https://github.com/kunalwagh101/off_CRM/actions/runs/44952285835)): **8 failed, 3,423 passed, 149 skipped**. All eight failures were the newly added D-500 cases, with no other test failure. Fixed source GREEN: [44952349677](https://github.com/kunalwagh101/off_CRM/actions/runs/44952349677) all five jobs PASS.

## Operational impact and limits

Pre-existing file symlinks, broad file permissions or incomplete credentials now cause a startup error instead of reading an unsafe file or silently overwriting it. An operator must examine the real file and restore a protected original (or correct verified permissions to 0600) before restarting. Never paste a live credential into a ticket or console log. This preserves data rather than guessing a new identity.

The pinned parent-descriptor guarantee applies to POSIX platforms with `dir_fd` and `O_NOFOLLOW`. Non-POSIX hosts use a preflight linked-parent check and retain a concurrent parent-swap limitation. File creation is exclusive but an independent process reading a credential during its initial creation may receive an invalid/partial file and fail closed; it does not receive unapproved access.

**Not a parent-feature release:** No operator credential, customer database, customer browser flow, live model/provider, S3 backup or restore was used. F-06.02, F-06.03 and F-04.01 remain open on the board.

## Exact test record

**Observed D-500 RED:** test-only GitHub commit 1b33fec replayed Python 3.11 job 44952285835: 8 expected D-500 tests failed (2 symlink, 2 invalid-existing-file, 2 broad-permissions, 2 parent-directory swap); 3423 other tests passed and 149 skipped. **Observed GREEN:** fixed c93b2e3 GitHub CI 44952349677 all 5 jobs passed (Python 3.10/3.11/3.12 each 3431 passed/149 skipped; real PostgreSQL 3542 passed/107 skipped), production container 44952349680 passed. Render exact-source QA/manual acceptance remain pending.

Targeted early Dockerfile.review gate and guarded-reload regression are included in the final evidence commit; they require exact-source GitHub and Render verification.


## 2026-11-22 — exact-source review status

Source `9321f614` included the D-500 fix, targeted early Review Dockerfile gate and token-reload regression. GitHub CI [44954100077](https://github.com/kunalwagh101/off_CRM/actions/runs/44954100077) succeeded all five jobs; Render review deploy `dep-dc117356e07s73bva02g` reached LIVE with 3,494 PostgreSQL-suite tests passing and 156 skipped. The functional Render app `dep-dc1173mtlv9c73anm800` was also live. These constitute current-code CI and disposable Render QA, not authorised owner login/provider/backup or independent penetration. D-501 is the distinct subsequent inode ownership hardening.
