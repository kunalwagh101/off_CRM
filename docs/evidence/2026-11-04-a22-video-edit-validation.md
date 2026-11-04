# S-06.02.65 / A22 — Nested video-edit request validation

## Observed defect and repair
On `POST /api/v1/video-projects/{project_id}/edit`, old batch input `list[dict[str, Any]]` let nested params be non-object values, causing HTTP 500 in `edits.apply(...).items()`. Extra operation fields, conflicting aliases and mixed batch/single commands could be accepted without warning. The repair adds nested strict Pydantic schema validation and bounds before the engine loads or saves any project. The existing operation registry and history/undo engine remain unchanged.

## Test-first evidence
- RED source `86da047da8aa5a2adad58a8db6f03b96c214ba28`, isolated Render `dep-dbln67d6e07s739droo0`: focused A22 **6 FAILED, 2 passed**. These failures are the original defect; expected during test-driven development.
- Corrected executable source `384070d0c9e36bdb3f6c2462fe32c47819a558d5`, isolated Render `dep-dbln72ff3r2c73e4r2q0`: `uv run pytest -q tests/test_video_edit_validation_a22.py` **8 passed**, 1 warning in 6.15 seconds. HTTP TestClient calls exercise real app and disposable local project DB; invalid requests leave saved version and document unchanged; single/batch editing and undo remain functional.
- Full SQLite, PostgreSQL, frontend/Chromium, security, and review LIVE status: **pending at initial checkpoint**. Do not cite older source's full runs as proof for this code.

## Rollback and incomplete acceptance
No schema or credentials changes. If a rollback is required, revert the request schema and handler together; do not delete projects or edit history. Reverting reopens malformed batch input acceptance. Browser editor E2E, independent penetration, complete A22 write-API matrix, full-history verifier, and customer release remain separate gates; S-06.02.23 production audit is still IN_PROGRESS. `main` and customer services untouched.

Requirement R-192; defect D-367; design DD-144. Work order: `docs/work-orders/S-06.02.65-video-edit-input.md`.

## Escaped Unicode attack surface (D-368)

A minimal real FastAPI/Pydantic HTTP handler returned HTTP 500 when `json.dumps(ensure_ascii=False)` of a decoded lone Unicode surrogate was UTF-8 encoded. The full application was not exercised at that exact minimal reproduction. Regression source 1201495 adds two actual off_CRM HTTP tests with raw JSON escapes for parameter values/keys, expects 422 without mutation, and rejects those characters before any project access. It also escapes JSON for bounded size measurement. The latest isolated Render dep-dblnc3tg1s2s73cvcvn0 must pass 10 A22 tests plus the full gates before this is certified; earlier green 8 belongs only to 384070d. No main/customer rollout.
