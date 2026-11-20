# 2026-11-21 — D-455 image-generation HTTP and failure reporting

Branch: `develop`. Baseline: `1e794b6`. Source fix: `965ddb0`, `9ddc9c4`, `9bf61d6`. Document update pending this commit.

## Test-first coverage

- D-455 no usable image/provider call failed: return HTTP 502 with a next step and no provider raw exception.
- D-455 every image gate rejected: return HTTP 422 with a specific quality instruction.
- Mixed successful and failed images: retain HTTP 200, disclose count, queue usable images, never echo a planted provider secret.
- Failed image attempt: safe operator reference in the engine result and exactly one redacted JSON log entry for that attempt.
- D-463 absent YouTube credential: route must refuse with 422 and explain the missing key rather than a server error.

Tests: `tests/test_e2e_findings_2026_11_13.py::test_D455_image_round_http_status_is_honest`; `::test_D463_missing_youtube_key_is_actionable_4xx_not_server_error`; `tests/test_imagery.py::test_failed_provider_call_records_safe_reference`. Full regression and Python 3.10/3.11/3.12/PostgreSQL/front-end/board replay run automatically in GitHub Actions; inspect exact HEAD conclusion rather than earlier successes.

## Release gates remaining

Actual connected image-provider success/failure and backpressure; real browser manual response/UX; independent adversarial pen testing; CRM D-451 isolation and explicit legacy customer migration; hosted S3 offsite restore and durability; role-team external-provider acceptance. No live Render deployment, main promotion or DONE status is claimed.
