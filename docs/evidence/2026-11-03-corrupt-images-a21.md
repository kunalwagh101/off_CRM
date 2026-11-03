# A21 S-06.02.56 — generated image corruption

Date 2026-11-03. Branch develop only; code is not released to main/customer.

## Scope and acceptance

`imagery/gates.py`: reject corrupt/truncated PNG/JPEG/GIF/WebP after complete Pillow `verify()` and `load()`, reject MIME mismatch, animation and oversized media. Limits: 16 MiB encoded, 16,777,216 pixels, 8192 side. Reuse GateReport/engine path; decoded valid image from same batch can enter approval queue. `pyproject.toml` adds existing-locked pillow 12.3.0 as explicit runtime dependency; no new external egress, schema, data migration or changed providers.

## TDD evidence

- RED `84add30`, Render `dep-dbkolbnb9u1s73819ns0`: 2 failed, 2 passed, 22 deselected. Real defects: truncated GIF struct.error; PNG spoofed as JPEG passed. Two original fixture cases gave misleading passes because of escaped bytes (D-356).
- GREEN code `7748855`, Render `dep-dbkonpnb9u1s7381fptg`: A21 7 passed, 22 deselected; broader suite still pending. Binary test correction `9ba6cea`, new deterministic 32 corrupt bodies and animated GIF `db02e52`.
- Final exact-code/test isolated Render `dep-dbkopnp5efls73f7u9j0`: pending. Record observed full Python/frontend/PostgreSQL/Chromium results before promoting review status.

## Security and rollback

Payload length and image bounds are checked before full pixel allocation; unexpected decoder exceptions fail as safe reports. Real user path is image-campaign generation and review. Tests include forged headers, MIME spoof, base64 limit, corrupted bytes, valid fixtures and mixed valid/invalid batch. Synthetic hostile bytes are not an independent penetration test. Peak native decoder memory/CPU, live provider data and production rollout remain unverified. No schema change or data migration. A simple rollback reopens D-355 and therefore needs approved replacement protection. The production audit S-06.02.23 and the full F-06.02 are not completed.

## 2026-11-03 full-suite regression and correction

- First full SQLite review `dep-dbkopnp5efls73f7u9j0` on `db02e52` **failed**: 3 failed, 2946 passed, 50 skipped. Cases: `tests/test_imagery.py::test_a_placeholder_sized_response_is_caught`, `tests/test_video_captions.py::test_a_picture_cannot_be_imported_through_the_media_path`, `tests/test_video_gates.py::test_a_still_goes_through_the_same_entry_point`. Do not erase this failure.
- Root cause: `image_size` is a shared *header probe* for video/timeline classification; replacing it with full-image verification broke that existing contract. The old mock header-only fixture in the placeholder test gave way to a real valid compressed PNG larger than 1024 bytes.
- Corrected implementation `e45469a7c8aaba03ffb1d892422ec43af50524a9`: keep lightweight `image_size` for video and add private `_fully_decode_image` called exclusively by `run_gates`; make the placeholder a genuine sub-1024-byte small PNG. Add `test_A21_header_only_probe_must_not_bypass_strict_image_approval`. Do not loosen the full image-approval check.
- New isolated Render review `dep-dbkp0b7b9u1s738244k0`: **10 A21 passed**, **113 image/video integration passed** at focused early gates; full SQLite/PostgreSQL/Chromium QA is pending at this writing.
- Early static Ruff, AI numerical checks, and CRM duplicate regression passed on this exact source.

## 2026-11-03 — corrected full Render QA evidence

Exact source e45469a7c8aaba03ffb1d892422ec43af50524a9, isolated Render dep-dbkp0b7b9u1s738244k0. Full SQLite 2950 passed/50 skipped/44 warnings. Full real disposable PostgreSQL 2973 passed/96 skipped/44 warnings; separate focused PostgreSQL 215 passed. A21 10 passed, image/video integration 113 passed, verifier unit 67 passed; repeated concurrency 12/12 passed; critical Ruff and frontend test/build/audit gates passed; contacts and visitor demo Chromium desktop/mobile PASS and two A18 Chromium PASS. Structural `uv run python scripts/verify_board.py --skip-tests` passed, but did not rerun historical evidence commands. Complete Docker review image built with both PostgreSQL and Chromium stages, while Render service activation was still in progress at checkpoint. No independent penetration, extreme-memory benchmark, real image-provider call or customer acceptance. No main/customer release. A21 remains IN_REVIEW, not DONE; production audit S-06.02.23 remains open.

**Render status verification, 2026-11-03 08:04:59 UTC:** QA-only service `srv-db86p4u89jmc73cehns0` completed deploy `dep-dbkp0b7b9u1s738244k0` as **LIVE** on exact tested code `e45469a7c8aaba03ffb1d892422ec43af50524a9`. This is a test-runner readiness marker, not deployment of a new image feature to the customer-facing application or main branch. Independent penetration and customer acceptance remain open.
