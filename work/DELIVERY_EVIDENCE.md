# Delivery evidence · 2026-11-17

Mode TASK; implementer Codex /root. Stories S-03.02.05, S-02.02.02,
S-04.01.01. Implementation revision: 551c27e (with earlier story commits 450f595 and 0a170ea).
Code implemented; release gate remains open. All three IN_REVIEW.
The next-five breakdown and leaf-task results are in NEXT_FIVE.md.

## Reproduction

Working directory: /workspace/off_CRM. This managed container needs writable
cache/tool locations. Set these for every command below:

```bash
export UV_CACHE_DIR=/workspace/.uv-cache
export UV_TOOL_DIR=/workspace/.uv-tools
uv sync --extra dev --extra email --locked
npm ci --prefix frontend --cache /workspace/.npm-cache
```

| Exact command | Actual outcome | Raw evidence |
|---|---|---|
| `uv run pytest tests/test_browser_platform_registry.py tests/test_agent_plan.py tests/test_agent_companions.py -q` | 75 passed in 0.76s | story-acceptance.log |
| `uv run pytest tests/test_agent_companions.py tests/test_agent_plan.py tests/test_browser_platform_registry.py tests/test_agent_report.py tests/test_agent_resume.py tests/test_agent_run.py tests/test_ai_egress_wall.py tests/test_security_audit.py -q` | 175 passed, 2 warnings in 3.92s | acceptance-security.log |
| `uv run pytest -q` | 1994 passed, 21 failed, 4 skipped, 3 warnings in 78.48s | python-final.log |
| `npm test --prefix frontend` | 8 files, 116 tests passed | frontend-tests.log |
| `npm run build --prefix frontend` | TypeScript and Vite production build passed | frontend-build.log |
| `uv run ruff check --select E9,F63,F7,F82 .` | All checks passed | Repeated at delivery |
| `git diff --check` | exit 0 | Repeated at delivery |
| `uv build --wheel --out-dir work/dist` | wheel built; new modules and YAML found inside it | wheel-build.log |
| `uv run python scripts/verify_board.py --skip-tests` | structural board checks pass | board-structure-final.log |
| `uv run python -u scripts/verify_board.py` | 55 historical evidence commands replayed; 27 passed, 28 failed on browser tests | board-final.log |

The full verifier snapshot was taken while companions were still IN_PROGRESS;
its final structural snapshot records 0 IN_PROGRESS and 3 IN_REVIEW. None of the
three was promoted to DONE. The 28 failed historical commands overlap the same
21 Chromium tests; they are not 28 new defects.

Original baseline: 1918 passed, 22 failed, 4 skipped. Failures are named in
python-original-baseline.log. Comparison of FAILED node IDs confirms zero new
failures; Graphify succeeds after UV_TOOL_DIR is writable. The other 21 fail
because Chromium cannot start its sandbox in this container. A disposable test
wrapper also demonstrated that managed browser policy blocks data: fixtures; it
was removed. No system policy, application security control or test was disabled.

## Test-first evidence

- platform-red.log: all 25 initial declaration criteria failed before the code.
- plan-red.log: 8 failed, 2 passed before plan support; unchanged-file and XSS
  checks already passed on the old behaviour and are not represented as RED.
- companions-red.log: an ungranted click executed before the host grant check.
- platform-duplicate-red.log and platform-dns-red.log: self-review findings
  reproduced before fixes. Further security/edge tests were added during review.

## Review

Separate implementer self-review; no independent reviewer was used. Found and
fixed duplicate-key ambiguity (D-52) and overly narrow valid-DNS validation
(D-53). Checked registry consumers, packaged files, plan/broker truncation,
report escaping, grant enforcement before dispatch/memo reuse, workspace and
INTERNAL boundaries, corrupt storage, atomic profile writes and resume bindings.

Local attack probes cover unsafe config/URLs, hostname lookalikes, path traversal,
symlinks, XSS, secrets in plans/profiles/memory, ungranted verbs and resumed grant
escalation. These are local application security tests, not an independent or
remote penetration test. No live provider requests or deployment were performed.

Architecture guides document compatibility and rollback. Acceptance tests execute
registry removal/restoration, profile update/delete and interrupted-run recovery.
Before a code downgrade, stop active runs and preserve plans/profile snapshots;
older code cannot enforce the new controls on an existing bound trace.

## Remaining gate

D-51: rerun the full Python suite and board verifier in an environment with a
working browser that permits the embedded test pages. Do not mark these stories
DONE until that gate and review pass. No owner decision or provider credential
is needed for the remaining local browser proof.


Certification update · 2026-11-19: GitHub Actions run 2291 passed full Python
(2060 passed, 4 skipped), all 55 historical evidence commands, frontend 116 and
the production build. S-03.02.05, S-02.02.02, S-04.01.01 and S-05.01.01 are now
DONE. Earlier IN_REVIEW statements describe the prior local-only evidence stage.
See work/REMOTE_VERIFICATION.md and work/ci-run-2291.log. PR #29 is unmerged;
no deployment or independent penetration assessment is claimed.
