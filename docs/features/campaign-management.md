# Product feature — Campaign Management

**Module:** Campaigns; `off_CRM/develop`; state **IN_REVIEW**.

This is a *product capability*, not a one-line story: the user can configure and maintain an existing campaign without editing code.

## Supported lifecycle

Create and select still works. Campaign cards now offer a real editable settings form for email campaigns (name, sending cap, timezone, send window, weekdays, follow-up intervals, approval policy, experiment hypothesis, sample size and control variant). Other campaign kinds only offer their universal name here; they manage type-specific generation settings in their own screens.

The backend reuses the existing protected `PATCH /campaigns/{id}` endpoint with Pydantic bounds and persistent `campaign_updated` event. Added valid IANA timezone enforcement on creation and editing to fail at the change boundary instead of later during mail sending. Existing campaign kind and A/B assignment remain immutable, and old sent content is not rewritten.

Pause/resume is visible; archiving requires typing ARCHIVE and preserves evidence, drafts and recipients. Archived campaigns are restored as **paused**, never automatically resumed live.

## Acceptance and tests

Given saved settings, when the process restarts, the same values should still be returned. Given invalid timezone or invalid control variant, the API must reject it with no write. Given archiving, the operator must explicitly confirm. See `tests/test_campaign_product_features.py` and `frontend/src/pages/CampaignOperations.test.tsx`.

No new database tables. Rollback means reverting the UI editor, IANA guard and lifecycle form only. **Unverified:** real browser form, SQLite/PostgreSQL, deployment and CI runners.
