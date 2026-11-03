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
