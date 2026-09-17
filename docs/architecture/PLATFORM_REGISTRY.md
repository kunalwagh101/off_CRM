# Browser platform registry

`S-03.02.05` makes a connected browser platform a declaration rather than a Python code change.

## Source of truth

`offsetx_apollo_builder/browser/platforms.yaml` is the only platform-specific source for:

- sign-in and home URLs;
- accessible signed-in / signed-out signals;
- per-account hourly and daily action ceilings;
- host pacing;
- attended vs unattended operation;
- host-specific refused and confirmation-gated actions;
- aliases such as `twitter` -> `x`.

`identity.py`, `budget.py`, and `policy.py` consume the validated registry. A new platform therefore does not require edits in those modules.

## Fail-closed loading

`platform_registry.py` validates the complete file when the process imports it. A malformed declaration prevents startup rather than failing during a browser run. Validation includes required/unknown fields, identifiers, HTTPS URLs, sign-in signal conflicts, action names, non-negative ceilings/pacing, hourly <= daily budgets, alias/domain collisions, and coverage of the declared home host.

An operator may point `OFF_CRM_PLATFORM_REGISTRY` at another trusted registry file. The same validation applies before the browser stack is available.

## Security boundary that configuration cannot weaken

The registry controls platform-specific behavior; it does **not** own generic browser security. `policy.py` still refuses local files, browser-internal schemes, localhost, cloud metadata, and `.internal` hosts before a platform rule is considered. Gmail also remains an explicit CRM boundary rather than becoming a connected-platform row.

That separation is deliberate: adding a platform must be easy, but no data row may turn off host/network protections.

## Adding a platform

Add one row to `platforms.yaml` with the required sign-in signals, account budget and at least one domain policy. Restart the service so the registry is validated and loaded. No Python edit is required.

The acceptance test creates a synthetic `mastodon` declaration in a fresh process and proves that the unchanged product code immediately gains sign-in detection, persisted connection state, action budgeting, pacing and unattended-run enforcement.

## Packaging

`pyproject.toml` includes `platforms.yaml` as `offsetx_apollo_builder.browser` package data. Installed wheels therefore use the same registry as a source checkout.
