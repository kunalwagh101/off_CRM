# 2026-11-04 — A20 token-authenticated media (S-06.02.63)

## Source of truth
- Repository: kunalwagh101/off_CRM, branch **develop** only.
- Work order: docs/work-orders/S-06.02.63-token-media-auth.md. Active production audit S-06.02.23 remains IN_PROGRESS.
- RED test source: `b4b2833a8cec1b789db1fd6ca0a16751f9710723`, isolated Render review deployment `dep-dblhbtu417fc738i5b5g`: **8 expected failing / 1 passing** in `src/media-auth.test.ts`. Failure was due to missing shared binary credential handling, not a customer environment.
- First corrective run: `dep-dblhe1lg1s2s73ensrm0` on `fdfee395` failed before exercising tests because a new URL guard regex could not be parsed. Corrected immediately in `af434cfbc8c50bd7ba6a7c937595347b15b1761d`. This regression is a code failure, not a certified GREEN.
- Full review runner: `srv-db86p4u89jmc73cehns0`. Latest GREEN candidate `dep-dblhej942hec73889ntg`, source `af434cfbc8c50bd7ba6a7c937595347b15b1761d`. Frontend Vitest **19 files, 223 tests passed**, including all 9 new media tests. Other QA stages were still running when this entry was prepared.

## Implementation
- `frontend/src/api.ts`: `fetchMedia` applies the bearer header on same-origin API routes, keeps session credentials, refuses token-bearing requests to foreign/non-API paths, and raises readable 401/403 errors. Token-only session is never put in a URL.
- `frontend/src/ProtectedImage.tsx`: fetches protected images, checks type and 32 MiB response size, creates an in-memory object URL, revokes it after unmount/token changes, and shows loading/access errors. Cookie-only mode preserves the native-image path.
- `frontend/src/pages/ImageReview.tsx`, `frontend/src/pages/VideoEditor.tsx`: use protected image rendering for review and thumbnails; the editor reports failed still-asset reads rather than leaving an unhandled promise.
- `frontend/src/video/audio.ts`, `footage.ts`, `export.ts`: audio, footage and still extraction share authenticated transport. Audio 401/403 aborts export instead of being categorised as an undecodable file; missing 404 still has its separate path.
- `frontend/src/media-auth.test.ts`: bearer/cookie, untrusted URL refusal, 401/403, audio/still loading, 404. `tests/test_api_auth.py`: anonymous and bearer-authenticated session/media boundary.

## Security and release restrictions
The isolation test with a foreign URL is an automated negative security case, **not independent penetration testing**. No customer browser session, paid provider or external account was accessed. No `main` change and no customer/demo deployment. Full SQLite/PostgreSQL, Chromium, static/security QA, review runner LIVE status, full-history board verifier and independent live penetration must be assessed independently before DONE or production promotion.
