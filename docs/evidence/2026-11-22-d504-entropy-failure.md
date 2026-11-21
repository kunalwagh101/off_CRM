# D-504 — local credential generation must not leave invalid files

**Branch:** `develop`, 2026-11-22. **Scope:** local API-token and workspace signing secret bootstrap under S-06.02.23; not customer-hosted storage.

## Finding

`_local_secret_file` originally performed `os.open(O_CREAT|O_EXCL, 0600)` **before** `secrets.token_urlsafe`. A secure random source failure after file creation left a zero-length file; following starts treated the file as invalid instead of generating a new credential. This causes a persistent local-startup availability failure.

## Test first

- Test-only commit `0baa8662d320bbfce92185756bfd189c74db1459` added `tests/test_local_secret_file_safety.py::test_failed_random_secret_generation_does_not_leave_poisoned_file` for **both** token and workspace signing secret.
- Test injects `OSError` from the entropy source, asserts a safe error with **no new credential file**, then restores entropy and proves another attempt creates a reusable matching saved value.
- The original test-only run `44961617228` was cancelled by the implementation push. **Observed RED:** [GitHub Actions 44961617228](https://github.com/kunalwagh101/off_CRM/actions/runs/44961617228), Python 3.11 test-only rerun on original 0baa866: both cases FAILED exactly as expected with `AssertionError: a failed key generation must not poison the next boot`; 3,436 unrelated tests passed and 149 skipped. The failure was captured before the fix.

## Fix

- Implementation commit `4746864dc050ec0339aa7287ee4bd377b1924761` moves secure random generation **before** the exclusive destination-file open.
- Preserves original ancestor directory FD pinning, `O_NOFOLLOW`, `O_EXCL`, private mode 0600, owner/link count, existing-file no-overwrite and bounded reads.
- Generated secret contents are never written to source or logs. No real user key was read or rotated.
- If an actual disk write fails **after** creation, a partial new file could remain: atomic write failure is **not** covered by this fix; investigate as a separate recovery/atomicity issue if necessary.

## Verification

- Exact-source Render `Dockerfile.review` targeted `uv run pytest -q tests/test_local_secret_file_safety.py`: **17 passed** at source `4746864` (logs in review deployment `dep-dc12gabl550s73d6oeeg`).
- Production container workflow `44961630723`: **PASS**.
- Full GitHub CI `44961631957` was cancelled when the test-only RED replay triggered the repository's shared CI concurrency rule. The final evidence commit must receive its own fresh 5-job GREEN run; do not count cancelled CI jobs as passed.
- Render review deployment `dep-dc12gabl550s73d6oeeg`: record final build and PostgreSQL suite status.
- Functional CRM `dep-dc12h3ff3r2c73bd82ug` **LIVE** on exact code `4746864`. A rerun of external GitHub HTTPS workflow [44944989952](https://github.com/kunalwagh101/off_CRM/actions/runs/44944989952) completed PASS at 2026-11-21 23:28 UTC: 5 checks for page, readiness, anonymous session, dashboard refusal and invalid login refusal. This does not test a valid account or durable database.

**Limit:** This is a narrow local secret-file availability fix, not a claim that F-06.02, F-06.03 or F-04.01 is complete. Durable dedicated PostgreSQL, real offsite encrypted S3 recovery, authenticated browser workflows, owner-supplied provider accounts and independent penetration acceptance are still required.

- **Observed targeted GREEN:** exact fixed-source Render review stage `tests/test_local_secret_file_safety.py` logged **17 passed in 2.86 seconds** on commit 4746864. Full GitHub/source-wide review still requires terminal verification.
