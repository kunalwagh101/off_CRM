# Hosted companion grants — actual browser acceptance, 2026-11-07

Develop continuation under F-04.01/F-06.03/F-06.02. Component evidence, not whole-feature completion or deployment.

## Failure and fix

Actual Uvicorn/PostgreSQL/Chromium created a companion, granted a registered tool and saved. Removing the tool through the CLI hid its saved ID. Profile save returned400 without a UI control to clear the grant. RED log: `work/three-features/hosted-tools-browser-red.log`. Three added frontend checks failed before the component existed; the browser failure proves the behavioral defect.

AgentTeam displays saved unavailable grants only after a successful catalogue load. Unchecking remains reversible until Save. Errors/loading never prune grants. Existing foreign/invalid-grant authorization remains enforced.

## Reproduction

Build frontend, then run:

```bash
uv run python scripts/qa/hosted_tool_browser.py --backend sqlite
# disposable CREATEDB role only; generated database is dropped afterwards
OFF_CRM_TEST_POSTGRES_URL=<disposable-test-url> uv run python scripts/qa/hosted_tool_browser.py --backend postgres
```

Actual SQL, CLI, Uvicorn and installed Chromium/Google Chrome are used. The helper saves a profile/grant, restarts after deleting disposable local data, verifies SQL persistence, removes the tool, then clears/undoes/clears/saves at1280 and390 widths. Both actual SQLite/PostgreSQL runs passed after final environment isolation, with no horizontal overflow or JavaScript page errors. Artifacts: `work/three-features/browser-isolation-green/`, `browser-postgres-isolated/`. Mobile picker screenshot visually reviewed.

Cold review found operator-path/dotenv contamination in the first utility. A harmless non-database canary reproduced failure. Final children receive allowlisted runtime/proxy/CA trust, generated credentials and explicit disposable paths; dotenv is disabled and cwd private. Browser requests stay on the test origin. Two tests cover poisoned environment and explicit factory settings. Actual poisoned SQLite run passed. No real customer fixture used.

## Verification and limits

- Frontend237 PASS/build PASS; six AgentTeam checks include three added cases.
- Isolation2 PASS; fatal-name/syntax Ruff PASS.
- Independent reviewer reran2 isolation/6 AgentTeam checks, no blocker.
- SQLite browser QA added after CI frontend build. Playwright1.61.0 becomes explicit dev metadata;137 resolved package versions unchanged.
- Previous source34ffb451: full CI42359198333 and container42359198438 SUCCESS; Python3.10/3.11/3.12 each3229 PASS/97 skipped; PostgreSQL3288 PASS/107 skipped; pooler64 PASS/1 intentional skip; Docker3 PASS; board72/72; frontend234/build PASS. New slice needs its own CI.
- No provider spend, sends, live-bucket drill, customer/main/Render deploy. Runtime CRM tenancy and whole three areas remain open. Reverting this editor/QA slice requires no data migration.
