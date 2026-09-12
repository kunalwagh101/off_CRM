# Reliable campaign selection

Story **S-06.02.16 / R-101**, audit **A33 / D-51**. Implemented on the existing
integration branch; live acceptance is pending. This document records the
supported behaviour and its evidence, not a deployment claim.

## Operator behaviour

Creating a campaign immediately selects the saved record. Navigation and reload
retain it. A later manual selection wins over an earlier pending request.
Contacts, edits and video projects use the campaign shown in the header.
Switching campaigns closes the previous campaign's forms and clears its local
page state, including unsaved edits.

On startup, a saved ID is verified before campaign work is enabled. If it falls
outside the latest 200 campaigns, the app reads that record directly. Only a
confirmed detail 404 permits a fallback, with a visible notice naming the new
campaign. An empty workspace clears the saved ID and offers campaign creation.
Permission, rate-limit, network and server errors never mean the record was
deleted. Retry keeps the last verified selection; an initial failure blocks
campaign work until verification succeeds.

A successful creation stays successful when its subsequent list refresh fails.
The error offers a retry. If browser storage is unavailable, selection still
works in the current tab and a warning explains that reload cannot preserve it.

## Data and concurrency contract

`frontend/src/campaignSelection.ts` owns the list and active ID in one immutable
snapshot. React subscribes through `useSyncExternalStore`. Request generations
discard superseded refreshes; choice generations protect newer operator intent;
connection generations discard replies from a signed-out or disconnected app.
Campaign-bound screens remount on ID changes so a form cannot change its target
while retaining another campaign's row identifiers.

The existing authenticated list, detail, create, contact import and video project
endpoints remain the boundary. Creation keeps the existing idempotency header.
No backend schema, credential, provider permission or persistence path changes.
The existing `offsetx-active-campaign` key still contains the plain campaign ID.
No state migration or backup format change is required. Existing WP1 recovery
acceptance remains a required CI gate.

## Acceptance map

| Criterion | Automated evidence |
|---|---|
| Creation, navigation, delayed or older list, reload | Unit snapshot/race tests; live create, overlapping refreshes and CSV import |
| Later manual choice wins | Unit pending-create and refresh races; live held real POST response |
| Saved campaign outside the first page | Unit detail read; live 201-record workspace and real image-campaign video project |
| Confirmed missing ID versus transient failure | Unit 404, 401, 403, 429, 500, 503 and network paths; two live real-404 fallback cases |
| Correct contact and project ownership | Real API writes from Chromium, followed by independent authenticated API readback |
| Old form cannot survive a switch | Live unsaved contact edit, switch, empty destination and unchanged stored contact |
| Save, refresh, disconnect and storage failures | Unit failure/lifecycle tests; live successful save followed by failed refresh and retry |

Local commands: `npm test` and `npm run build` from `frontend/`.
The focused suite is `npm test -- src/campaignSelection.test.ts` (20 tests).
Real-service CI runs `uv run --no-sync pytest
verification/test_campaign_selection_live.py -q -ra` after building the actual
application and production image. It requires sandboxed Chromium and performs
real writes with disposable synthetic records. Only response timing and explicit
transport failures are injected. Evidence includes JUnit, screenshots, browser
errors, server logs and separate import/project ownership readbacks.

The workflow also runs the full Python suite with PostgreSQL and Docker, WP1
browser/container recovery, Windows leases, every board evidence command and
the original production audit. Missing or skipped acceptance evidence fails the
gate. The original audit assertions remain unchanged.

## Operations and rollback

For a refresh error, retry from the displayed error panel. Do not clear browser
storage to work around a permission or server failure. An unavailable campaign
is replaced only after the server confirms its absence. For a storage warning,
restore browser storage access and select the campaign again; the warning clears
after a successful write. No secrets or customer records are stored in this key.

Roll back by restoring the previous frontend build through the existing release
process. Backend records and the plain-ID selection key remain compatible; no
data deletion or reverse migration is needed. The previous build reintroduces
A33, so rollback is containment of a new regression, not a resolution of that
defect. Browser reload coverage verifies the unchanged selection format.

The selector still shows at most the latest 200 rows plus the verified selected
row. Complete campaign browsing/search is audit A23 and remains separate work.
This story performs no external provider calls, publishing or customer sends.
The sandbox output, video export minimum and Gmail audit findings remain release
blockers until their original live checks pass. PR #14 remains draft during that
work; this story does not merge or deploy the application.
