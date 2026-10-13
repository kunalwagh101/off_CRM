# off_CRM develop — next three Send Queue slices, 2026-10-13

**Stories:** S-06.02.47, S-06.02.48, S-06.02.49. **Status:** IN_REVIEW / code prepared only. **Authorised target:** develop; main untouched. **External CI runner:** blocked.

## Source facts before change
- `GET /api/v1/campaigns/{campaign_id}/queue` returned the entire `send_queue` list and `total=len(items)` regardless of campaign size.
- `frontend/src/pages/Queue.tsx` rendered the whole list, computed Ready/Needs approval/Replies by filtering the returned list, and offered no role-specific view or pagination.
- `OutreachEngine.run_due` independently iterates `send_queue(campaign_id, now=...)` and enforces confirmation, limits, approvals, preflight, suppression and atomic claims; its behaviour must remain unchanged.

## S-06.02.47 — bounded detailed view
- Store: added `send_queue_view`; keeps existing sender `send_queue` full-campaign by default, adds an optional explicit `only_ids` for the UI page.
- Queue API: validated `limit` 1–200, `offset>=0`, `view` in known choices; default 100 items.
- UI: 100-item page, accessible controls with page range and total; page is reset/corrected when view shrinks.
- Internal tradeoff: the view scans all lightweight campaign control rows per request to compute exact counters/order. It does **not** load every person's full name, email, generated metadata into the page response. Large-campaign profiling remains required.

## S-06.02.48 — campaign-wide counters
- Store computes counts once over all campaign records, before filtering/paging, and applies timezone-aware `parse_datetime` to both next-action and manually scheduled draft times as the existing send_queue method does.
- `ready` = nonterminal + due + approved + sendable. `approval` = nonterminal + due + not approved, including no draft. `replied` = status replied. A terminal row does not qualify as ready/approval.
- Screen cards now read server `counts`, not the page's list.
- **Limit:** Ready is a *candidate*, not exact sent count; actual delivery still depends on suppression, recipient validity, provider preflight, send window, recipient consent and campaign cap.

## S-06.02.49 — actionable views
- `view=all|ready|approval|replied` is applied by the store before slicing records into pages, with an accurate view-specific total.
- A labelled dropdown shows campaign-wide counts, resets the page on change, and gives an appropriate empty-view sentence; switching a view cannot approve or send messages.
- Explicit Gmail confirmation remains required for any live send.

## Tests authored (not run in this environment)
- `tests/test_queue_views.py`: 211 contacts, ready and replied records beyond the first page, all-campaign count truthfulness, 100-item page boundaries, due-time gating, view totals, unknown view and invalid pagination, and authenticated API responses.
- `frontend/src/pages/Queue.test.tsx`: server path, accessible controls, cohort options and full-campaign stat rendering on a small page.
- Existing `tests/test_outreach_engine.py` and `tests/test_outreach_api.py` are regression gates protecting the send path.

## Needed execution
```bash
uv run ruff check --select E9,F63,F7,F82 .
uv run pytest tests/test_queue_views.py tests/test_outreach_api.py tests/test_outreach_engine.py -q
uv run pytest -q
uv run python scripts/verify_board.py
cd frontend && npm ci && npm test && npm run build
```
Follow with real browser pagination and changes during reload, PostgreSQL time-zone/scheduled drafts, and one safe local-outbox dry run demonstrating unchanged sender semantics. CI on develop has failed before runner allocation with zero steps, so these test commands are *not claimed as passed*. Required independent review and rollback execution remain outstanding. No production release is certified.

## Defect/decision register
Source gaps: D-277, unbounded queue response/UI; D-278, dashboard counters dependent on unbounded visible list (liable to become page-inaccurate); D-279, no role-specific queue view. The full DEFECT_LOG.md remains pending connector-safe update. Design decisions: DD-99, DD-100, DD-101. No schema migration. Rollback: revert Queue frontend/queue API and new store view, leaving original sender untouched.
