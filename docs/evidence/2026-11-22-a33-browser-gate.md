# F-06.02 / A33 — real campaign selection browser gate

Date 2026-11-22. Branch develop. Story S-06.02.22 (IN_REVIEW), parent audit S-06.02.23 (IN_PROGRESS).

## Acceptance contract

`scripts/qa/a33_campaign_browser.py` starts the actual FastAPI app and production frontend with a disposable SQLite database and generated local-only token, then uses Chromium at 1280px and 390px. For each viewport it must:
1. Read the actual server's existing synthetic campaign.
2. Create a second campaign through the visible modal, prove exactly one row persisted, and check the active campaign ID immediately matches the new row.
3. Navigate to Contacts, reload, and prove the selected campaign remains the same.
4. Select a different campaign and reload; the new manual selection must win.
5. Finish with zero browser JavaScript exceptions. Private data is destroyed with the temporary directory. No real provider or mail actions occur.

Any incorrect selection, missing persistence, UI error, API failure, or browser crash fails the GitHub quality job. Existing unit coverage remains in `frontend/src/campaignSelection.test.ts`.

## Verification boundary

Code and workflow were added to the selected F-06.02 scope as regression QA. This document initially records **no observed final-source browser result**. A completed GitHub quality log must be inspected before calling the new QA verified. The separate Render service `off-crm-qa-major-1997-20261121` (workspace `majors_97`) rejected build `dep-dc1ipb4s728c73ci9jd0` on 2026-11-22 due to exhausted build minutes. This local Chromium proof cannot replace current-source manual Render acceptance or customer-release security and durability checks.

The audit A33 status remains pending live deployment until those checks are completed.

## QA harness correction D-513 (before observed browser result)

A review found an invalid starting-state expectation: desktop creation adds a second campaign, so a fresh mobile browser need not default to the original seeded ID. The test now accepts any actually persisted current selection at startup, while still strictly requiring the newly created campaign and later manual switch to survive reload. This is a test harness correction, not a product repair. Current CI execution is still required.

## Render review dependency

The same A33 script is now required in the `chromium-checks` stage of `Dockerfile.review`, after the 503-contact browser acceptance and before the review QA marker can be published. A green GitHub workflow and this build-stage declaration are not evidence that Render accepted the newest image: the workspace build pipeline is currently blocked by zero remaining minutes. Manual verification against the actual web service remains open.

## Actual first-source RED — D-514

GitHub [45053197067](https://github.com/kunalwagh101/off_CRM/actions/runs/45053197067) ran the new A33 quality step on commit `8d93a6c` but failed before launching Chromium: Python executed `scripts/qa/a33_campaign_browser.py` by path, then raised `ModuleNotFoundError: No module named 'scripts'` while importing the sibling QA environment helper. The earlier 72/72 historical board commands, 242 frontend tests and production frontend build succeeded. This is a real failed CI QA entrypoint, not a failing product UI assertion.

Both CI and Render review launch commands now use module mode (`python -m scripts.qa.a33_campaign_browser`). A static test pins the invocation. New CI GREEN and actual Render build/manual acceptance are still pending. No app runtime change or customer action was performed.
