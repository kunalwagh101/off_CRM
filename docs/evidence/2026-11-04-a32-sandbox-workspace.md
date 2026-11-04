# 2026-11-04 — S-06.02.64 / A32 sandbox workspace evidence

## Verified outcome
Fixed the audited `/work` EACCES for a **real non-root POSIX subprocess** using UID/GID 65534 and a directly opened mount directory. The host job root is private (0700), the work mount sticky-writable (01777), inbox remains read-only to the container, store absent; sandbox Docker flags unchanged. Legacy directories are repaired on prepare. Symlinked root/inbox/work paths are refused before chmod.

## Test-first source/Render evidence
- RED test-only source `64af3c58116040087c435433c2a217f17c8954af`; isolated Render `dep-dblipuff3r2c73a96th0` build FAILED at early A32 gate: 5 expected FAIL, 43 deselected. This was the original defect, not a release build failure in fixed code.
- GREEN executable source `c63fe5c2a048562d0cabb3cc99b3b40585ec3add`; isolated review `dep-dbliqluc6qcc73bht1hg`: `uv run pytest -q tests/test_ai_sandbox.py -k A32` 5 PASS, 43 deselected, including an actual POSIX UID 65534 subprocess write, private-root check, legacy permissions repair and 3 symlink cases.
- Broad pinned review: `uv run pytest -q` on SQLite: 3,002 PASS/56 skipped/44 warnings. Native PostgreSQL-focused: 215 PASS. 12/12 separate repeated concurrency tests. Browser A09 Enter 4, A18 numeric Chrome 2, desktop/mobile Contacts and Public Demo all PASS. Ruff, Vitest/build, npm security gates and structural board verifier PASS. Full real disposable PostgreSQL overall: 3,026 PASS/101 skipped/44 warnings, in addition to focused PostgreSQL 215 PASS. Exact tested source c63fe5c isolated Render review dep-dbliqluc6qcc73bht1hg confirmed LIVE at 2026-11-04 13:24:37 UTC. The HTTP marker shows all configured build gates completed; it is not native Docker container runtime acceptance.
- Structural board verification in Docker uses `--skip-tests` because Git history is absent; it does not verify historical DONE evidence commands or complete `uv run python scripts/verify_board.py` with Git.

## Security and rollback
Before: unprivileged container user could not create a result file under the host-owned mount. After: only the dedicated job's `/work` child is sticky-writable, and host users without job-root access cannot traverse it. `store` is not mounted; `/inbox` is read-only. Existing `--network=none`, `--read-only`, `--cap-drop=ALL`, `--security-opt=no-new-privileges` and `--user=65534:65534` must be preserved. No schema, migrations, credentials or external calls were added.

Rollback must pause untrusted sandbox execution first; revert the `prepare()` change only when a different safe writable mount strategy is available. Reverting directly would reopen A32.

## Not proven (required for DONE)
- A real **nested/native Docker** `/work/result.txt` write under a pre-pulled, pinned image. This Render review runner builds containers but cannot run privileged Docker-in-Docker. The POSIX UID subprocess is a meaningful write test, not a native Docker acceptance.
- Independently conducted penetration, container/host symlink race pressure, log-reference failures, full-history board verifier with Git history, actual hosted product acceptance.
- Release remains IN_REVIEW. S-06.02.23 audit IN_PROGRESS. `main` and customer services untouched.

## References
- Code: `offsetx_apollo_builder/ai/sandbox.py`
- Tests: `tests/test_ai_sandbox.py`
- Work order: `docs/work-orders/S-06.02.64-sandbox-writable-workspace.md`
- Audit defect: `D-121`; decision: `DD-143`; requirement `R-191`.
