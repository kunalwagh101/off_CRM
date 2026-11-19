# S-06.01.01 · Workspace keys and platform sessions

Mode TASK; leading role full-stack/security engineer; implementer Codex /root.
User authorised the next ready capability. WIP owner must be recorded before code.

## Scope and acceptance

AC1: two workspaces cannot reach each other's provider keys or platform sessions.
This remains the local-first product: one configured, authenticated app instance
per workspace. It is not a shared multi-tenant SaaS or the pending permissions
story S-06.01.02. Identity comes from trusted startup configuration, not request
headers/body/query parameters. Local/default installs keep their existing paths.

- T-06.01.01.a: validate a stable workspace identity; scope app data/database,
  generated API token, settings and API responses. Reject client identity spoofing.
- T-06.01.01.b: isolate encrypted provider key/settings files; prevent global env
  fallback in nonlocal workspaces; bind the app broker once, rather than mutating
  a shared credential resolver on requests. Fail closed on corrupt key storage.
- T-06.01.01.c: cryptographically bind vault envelopes to workspace/account;
  isolate browser contexts and scope cookie capture/restore/revoke to that context.
- T-06.01.01.d: test concurrent workspaces, envelope swaps, context mismatches,
  secrets, auth/session boundaries and local compatibility; document explicit
  migration/rollback and verify through the existing GitHub CI path.

## Files and contracts

Create shared workspace identity/path helpers in offsetx_apollo_builder/workspaces.py.
Edit api/config.py, api/app.py and api/auth.py for configured workspace binding.
Edit ai/workspace.py for per-workspace secrets/settings and bound store access.
Keep local paths/env compatibility. Nonlocal environment names use a collision-free
workspace-derived namespace, never lossy uppercase/dash-to-underscore aliases.
Edit ai/broker.py only for optional immutable workspace binding and validation.
Edit browser/vault.py, browser/page.py and browser/session.py for context-safe
session handling; wire signin/revoke through the same checks. Reuse existing
BrowserBox per-workspace volumes. Browser context management is trusted host code,
never a new model action. Preserve all ten-verb and egress/review invariants.

API defaults remain local. OFFSETX_WORKSPACE_ID selects a canonical workspace
before startup; each nonlocal app uses private paths and authentication material.
Requests cannot choose another identity. Add a metadata-only workspace endpoint.
No new frontend is needed for this server/runtime boundary.

## Compatibility and evidence

Existing local settings, encrypted keys and v1 browser envelopes need a deliberate
migration path. Do not silently reinterpret or copy another workspace's credentials.
Cover migration/backup/restore with tests; record any required operator action.
Baseline: relevant AI API, vault/wiring and API auth suites: 54 passed.
Previous source revision passed CI with 2060 Python and 116 frontend tests, plus
all 59 board evidence commands (work/CI_FINAL_VERIFICATION.json).

Use test-first reproductions for actual isolation failures. Then run focused
unit/integration/attack probes, full Python and frontend checks, static checks,
and project verifier. Local managed Chromium is restricted; the existing connected
GitHub app and draft PR #29 supply standard-browser CI without weakening policy.
Keep IN_REVIEW until the necessary gate passes. Self-review is not independent
penetration assessment. No live provider keys/calls, deployment or merge required.

## Reopened during final restart review

A new test reproduces shared OS-keychain master creation racing across distinct
workspace vault directories. Serialize first initialization with a common private
OS-user lock, recheck the backend after locking, preserve existing master values
and fail closed to the explicit passphrase path if the lock cannot be used.
Verify reopen/decryption for both workspaces. Never overwrite an existing master.
