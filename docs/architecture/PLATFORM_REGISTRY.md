# Browser platform registry

`S-03.02.05` makes an account platform a declaration rather than three Python edits.

The owner-editable registry is `config/platforms.yaml`. A byte-identical copy is packaged as `offsetx_apollo_builder/browser/platforms.yaml` so installed deployments do not depend on a source checkout. `OFFSETX_PLATFORM_REGISTRY=/path/to/platforms.yaml` is the explicit deployment/test override.

## What one row owns

One platform row declares:

- `id` and optional `aliases`;
- display `label`;
- `login_url` and signed-in `home_url`;
- accessibility-tree `signed_in` and `signed_out` signals;
- one or more domain rules: suffix, minimum action interval, attended/unattended permission, refused actions and countdown-confirmed actions;
- the default `actions_per_hour` and `actions_per_day` account budget;
- optional operator notes.

`identity.py`, `policy.py`, and `budget.py` consume the same validated row. They do not maintain parallel platform lists.

## Adding a platform

Add one row to `config/platforms.yaml`, then copy that file unchanged to the packaged `browser/platforms.yaml`. No Python code should change. The registry test deliberately injects a brand-new synthetic platform into a fresh process and proves sign-in recognition, policy and budget all follow the declaration.

The declaration is loaded at process start. Restart after changing it. Runtime hot reload is intentionally not supported: pace, attendance and account limits are safety controls and must not change halfway through a run.

## Validation and failure behaviour

Loading fails before a run if a declaration is incomplete or ambiguous. Errors name the platform whenever an `id` is available. The loader rejects, among other things:

- missing identity, URL, sign-in signal, domain or budget fields;
- malformed IDs, aliases, URLs or domain suffixes;
- overlapping signed-in and signed-out signals;
- negative pace values or a non-boolean unattended flag;
- zero/negative declared budgets or hourly limits above daily limits;
- duplicate IDs, aliases or domain suffixes across platforms.

An undeclared platform is still refused by the sign-in API. Unknown non-platform browser hosts continue to receive the conservative open-web policy and a non-zero fallback action budget.

## Host-only rules

Not every host is an account platform. Gmail remains an explicit host safety rule in `browser/policy.py`: it needs send/delete confirmation and attended use, but inventing social-platform sign-in signals and an account-action budget merely to fit the registry schema would make the data dishonest.

## Evidence

Primary acceptance evidence is `tests/test_browser_platform_registry.py`, with regression coverage in `tests/test_browser_signin.py`, `tests/test_browser_budget.py`, and `tests/test_browser_agent.py`.
