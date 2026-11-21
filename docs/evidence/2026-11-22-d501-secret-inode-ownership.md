# D-501 — existing local credential inode ownership and hardlink guard

**Date:** 2026-11-22. **Scope:** F-06.02 S-06.02.23 security follow-up, local-only bootstrap API token and workspace session signing file.

## Problem

D-500 closed symlink, truncation, broad-permissions and parent-path redirection, but a pre-existing mode-0600 **regular file** was still accepted even if it had another hardlink or belonged to a different Unix account. A privileged service reading an attacker-planted file could accept an attacker-known token or signing key. A hardlinked inode also has a second pathname that is not controlled by the expected credential path. No real attacker compromise or customer data exposure was observed; this is a defensive local file-origin boundary.

## TDD change

- RED test source `5957f6eee5142518dc3dfb5ac3696a9a64b7466d`: four parametrised regression cases in `tests/test_local_secret_file_safety.py`, covering a 0600 hardlinked local API token and signing key, and files whose recorded owner differs from the effective process UID.
- Fix source `48eb240fb5c40997a9e1e07896dd4193d66d5435`: before reading existing file contents from the already-open descriptor, require `st_nlink == 1` and `st_uid == os.geteuid()` on POSIX. Keep existing regular-file, private mode, bounded read, symlink and pinned-directory protections. Reject unsafe files with ValueError, without editing, deleting or generating replacement credentials.
- Non-POSIX hosts do not use Unix UID/link-count checks. The earlier documented parent-swap limitation remains for those platforms.
- File-managed token reload shares the same reader. Explicit environment-supplied credentials are unaffected.

## Acceptance evidence

- **Observed RED:** GitHub Python 3.11 test-only replay [44956948171](https://github.com/kunalwagh101/off_CRM/actions/runs/44956948171): four expected failures for hardlinked token/secret and foreign-owner token/secret, 3,432 unrelated tests passed, 149 skipped; each failure was `DID NOT RAISE ValueError`.
- Fixed-source CI 44956962877 was cancelled by the branch-level concurrency while the RED job ran. The final evidence commit will trigger another five-job CI; do not claim it passed before that terminal result.
- Production-container workflow `44956962856` passed at fixed source.
- Exact-source Render review deployment `dep-dc11mdmc6qcc73ckv3bg` and functional service `dep-dc11me6c6qcc73ckv4h0` were triggered; record actual terminal status, test counts and fresh public-host smoke separately.
- Do not mark the full F-06.02, F-06.03 or F-04.01 DONE from this focused local safeguard. Customer data persistence, offsite S3 recovery, live provider and full authenticated browser testing remain open.

## Operator recovery

If a restored credential is now rejected, stop the service and investigate ownership, link count, permissions and the approved backup. Restore the original credential to an independently owned single-link mode-0600 file via a controlled copy, preserve its value and restart. Never paste the token or signing key into source, logs or tickets. Do not silently overwrite the existing file.

## Verified green checkpoint

Render review targeted security gate `uv run pytest -q tests/test_local_secret_file_safety.py` reported **15 passed in 2.91 seconds** against corrected code `48eb240`. Docker production workflow 44956962856 PASSED. The functional Render deploy `dep-dc11me6c6qcc73ckv4h0` reached LIVE and external 44944989952 rerun passed five HTTPS checks; Render access logs showed three 200s and two expected 401s. The first smoke attempt timed out during Render startup but a later live-host rerun passed; this is not a stress or always-on availability guarantee. Full source-wide CI and complete review deployment remain separate.
