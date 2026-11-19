# S-06.01.01 verification

Mode TASK; full-stack/security implementer Codex /root. Self-review only.
Scope and subtasks: work/WORKSPACE_WORK_ORDER.md. Configuration, migration,
rollback and trust boundary: docs/architecture/WORKSPACES.md.

## Acceptance coverage

- Fixed startup identity, private storage/database/authentication and metadata:
  tests/test_workspace_api.py. Spoofed header/query/body IDs cannot change it.
- Independent encrypted keys/settings and fixed broker resolver:
  tests/test_workspace_isolation.py. No global fallback, cross-process writes,
  corrupt state, symlink probes and explicit legacy migration/rollback.
- Separate browser contexts and authenticated workspace/platform vault binding:
  tests/test_workspace_browser.py. Cookie capture/restore/revoke is page scoped;
  migrations require owner verification; disconnect removes owned backups.
- Local compatibility: existing AI API/auth/provider/vault suites.
- Egress invariants and credential scanning: existing egress-wall/security suites.

## Test-first evidence and review

work/workspace-red.log records the initial ten failing cases. Additional red
logs reproduce legacy-provider boundaries, startup identity rebinding, missing
cookie signing secret and token symlink attacks. Failure injection also verifies
provider/vault migration rollback. No live credentials or external provider calls.
Security probes cover tenant confusion, key inheritance, traversal/ambiguous IDs,
relabelled encrypted sessions, cookie replay, wrong browser context, lost concurrent
writes and corrupt encrypted state. These are automated adversarial tests and
implementer review, not an independent penetration assessment.

## Local checks

- `uv run pytest tests/test_workspace_browser.py tests/test_workspace_isolation.py tests/test_workspace_api.py tests/test_outreach_providers.py tests/test_api_auth.py tests/test_browser_vault.py tests/test_browser_vault_wiring.py tests/test_ai_api.py tests/test_ai_egress_wall.py tests/test_security_audit.py -q -k 'not real_chrome'`:
  154 passed, 1 deselected, 2 warnings; work/workspace-focused-final.log.
- Full regression: `UV_CACHE_DIR=/workspace/.uv-cache UV_TOOL_DIR=/workspace/.uv-tools uv run pytest -q`:
  2067 passed, 22 failed, 4 skipped. All 21 prior managed-Chromium failures recur;
  the added real context-isolation test hits the same environment restriction.
  work/workspace-full-python-final.log. This run preceded the final token/signer
  hardening tests; the focused rerun and CI cover those changes.
- Critical Ruff: `uv run ruff check --select E9,F63,F7,F82 .` passed.
- `npm test -- --run`: 116 passed; `npm run build` passed.
- `uv build --wheel --out-dir /tmp/off-crm-workspace-wheel` passed.
- `uv run offsetx-web --help` passed. Raw logs are under work/workspace-*.log.
- `uv run python scripts/verify_board.py --skip-tests` passed. This is a
  structural check only; CI must rerun historical evidence before DONE.

## CI

GitHub Actions run 2295 passed on source commit
`487f85dcfa6799e411d4ed6a1c511d9c8c20631c`:
https://github.com/kunalwagh101/off_CRM/actions/runs/44573830141

- 2091 Python passed, 4 skipped, 6 warnings; all 31 workspace cases included.
- Real Chromium context isolation and explicit restart/restore passed.
- 59/59 historical board evidence commands passed.
- 116 frontend passed; production build, static checks and CLI smoke checks passed.
- Raw log: work/workspace-ci-2295.log; manifest: work/WORKSPACE_CI_VERIFICATION.json.

That earlier revision was promoted to DONE, then reopened for the D-68 restart race. The metadata update adds the workspace command to
the verifier, bringing the board to 60 DONE stories; final CI will certify this
updated evidence record. No merge, deployment, live provider call or independent
penetration assessment is claimed.

## D-68 amended source

`work/workspace-keychain-red.log` proves that concurrent initialization in two
vault directories replaced a shared OS root and failed to reopen one session.
The fix serializes first creation under `~/.off_crm/browser_vault_keychain`,
rechecks the backend under that lock and preserves an already installed master.
If the shared lock is unavailable, no OS master is created: the explicit
passphrase path remains available. No provider or browser policy changed.

`uv run pytest tests/test_workspace_api.py tests/test_workspace_isolation.py tests/test_workspace_browser.py tests/test_api_auth.py tests/test_browser_vault.py tests/test_browser_vault_wiring.py tests/test_ai_egress_wall.py tests/test_security_audit.py -q -k 'not real_chrome'`:
117 passed, 1 deselected, 2 warnings; work/workspace-keychain-green.log.
The workspace suite now has 34 cases. Critical Ruff and source whitespace checks
pass. Story is IN_REVIEW pending amended-source CI and its board evidence gate.
