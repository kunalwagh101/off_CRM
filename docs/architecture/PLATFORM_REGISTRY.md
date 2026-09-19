# S-03.02.05 — Browser platform registry

## Contract

Browser platform identity, session signals, domain policy and default account
budget come from one repository-controlled record in
`offsetx_apollo_builder/browser/platforms.json`.

A row declares:

- stable platform id and optional aliases;
- login and home HTTPS URLs;
- signed-in and signed-out accessibility signals;
- owned domains;
- minimum action pace, unattended policy, refused and confirmation actions;
- hourly and daily default action budgets.

`browser/platforms.py` validates the complete registry before any caller uses
it. Unknown keys, duplicate ids/aliases/domains, missing signals, unsafe URLs,
invalid policy actions and invalid budgets fail the whole load. A broken row is
never silently skipped.

## Wiring

The same object is consumed by:

- `browser/identity.py` and `signin.py` for connection state;
- `browser/policy.py` for host pacing/attendance/consequence rules;
- `browser/budget.py` for per-account defaults.

Reddit is the acceptance example: it is declared in JSON and has no
Reddit-specific branch in those modules.

## Security boundary

The registry is data only. It cannot add browser verbs, code, JavaScript,
callbacks, credentials or a network transport. The browser's ten-verb closed
vocabulary remains unchanged.

Built-in declarations are packaged with the application rather than loaded from
a remote URL. A platform-policy change is therefore reviewed and released like
code.

## Migration and rollback

There is no persistent-data migration. Existing connection records keep their
stable platform ids. X keeps `twitter` as an alias and both x.com/twitter.com
domains.

Rollback is a code/config rollback to the prior constants. No account/session
secret is stored in this registry.

## Verification

```bash
uv run pytest tests/test_browser_platform_registry.py tests/test_browser_signin.py tests/test_browser_budget.py -q
```
