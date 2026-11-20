# D-451 provisional shared-CRM HTTP containment (2026-11-21)

Repository: `kunalwagh101/off_CRM`, working branch `develop`.

## Root cause (verified in code)
`offsetx_apollo_builder/api/app.py::_engine(request)` resolves a single shared `request.app.state.engine` regardless of the authenticated workspace, while `_sales`, `_privacy` and other services are also shared. `docs/architecture/CRM_TENANCY.md` explicitly says the native workspace registry has NOT been connected to the production request path. No row-ownership migration was attempted.

## Temporary control

- New pure predicate `is_unscoped_crm_api_path` matches exact root or root followed by slash, so guessed IDs and nested endpoints remain covered; near-match paths do not inherit unrelated restrictions.
- The authentication middleware, after resolving the signed-in workspace and before executing the endpoint, returns 403 with an operator-readable message for secondary workspace access to known shared CRM route families. This refuses read, modification, search, CSV/export, send and other operations; `local` owner keeps the legacy path.
- Media and video paths covered by existing A05 cross-workspace HTTP tests remain usable; shared campaign, posting and other unscoped operations stay blocked. The public demo's dedicated sample-only CRM list/contacts GET and redacted settings status also remain usable. These safe exceptions were added in b6a70e2, test-first 01630da, source d1d7fe6.
- Test-first commit `617496d123d0537d80e0a93a250e14df90666f05` adds an alpha/beta/local HTTP matrix; code `a348f734aab59d5e30e8757857b44296176ca9bc`; follow-up `11c95b56331f8a17a3cd28adaa9a9eb4cbf510ca` pins route-prefix boundaries.

## Acceptance still missing

Existing media tests validate asset ownership but do not prove global campaign ownership. No full per-root legacy ownership manifest, archive or verified rollback; native registry not activated; no per-workspace CRM data made accessible to ordinary users; no full worker/raw-consumer audit; no independent tenant penetration run, live manual browser checks or staged customer migration. D-451 and S-06.01.06 remain OPEN and block production promotion. The new guard has a deliberate visible downside: nonlocal CRM screens refuse access instead of showing data. Contact the install owner rather than retrying or switching workspaces.

## Rollback

Revert the middleware guard only if replaced by a fully verified workspace-owned CRM cutover, never to restore previously unsafe multi-customer browsing. Do not toggle this off on a production deployment simply to make a demo work.
