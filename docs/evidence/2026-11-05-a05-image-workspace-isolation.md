# A05 / S-06.02.69 — Generated images belong to their authenticated workspace

## 2026-11-06 local and GitHub verification checkpoint

The historical “not run” statements below describe 5 November. On source `79fce1d`, the complete 9 image cases now PASS locally, alongside 43 model-egress cases (52 PASS combined). GitHub run [42120555626](https://github.com/kunalwagh101/off_CRM/actions/runs/42120555626) completed the SQLite suite: 3,114 PASS / 33 skipped, including these image tests. It did not complete the quality job: historical board evidence hit the 15-minute timeout. Its PostgreSQL suite had a separate backup-client restore failure; no complete green pipeline is claimed.

Command: `UV_CACHE_DIR=/workspace/.uv-cache uv run pytest -q tests/test_audit_a05_image_workspace_isolation.py tests/test_ai_egress_wall.py`. Local output: `52 passed, 1 warning in 10.28s`. Synthetic sessions and data; no provider/customer actions. This establishes current regression GREEN but does not retroactively invent an observed pre-fix RED.

Full audit, Q-27 CRM ownership, independent live penetration and customer release remain OPEN. S-06.02.69 stays BACKLOG. Latest CI corrections and run outcomes are recorded in [the backlog/Render/CI audit](../audits/2026-11-06-backlog-render-ci-local.md).

## 2026-11-05 state: implemented on develop, Render QA BLOCKED

**Status is unverified.** Source changes and tests are committed, but no TDD RED, GREEN, complete SQLite, PostgreSQL, Chromium, independent penetration or customer deployment acceptance has been executed for this new A05 image slice. Do not mark S-06.02.69 DONE or imply this security finding is closed.

## Existing vulnerability and ownership boundary

- `ImageStore` already has `workspace_id` on `image_briefs`, `image_assets` and generator statistics.
- The real image API read image bytes by global `asset_id`, and used campaign-only lists. Both unrelated authenticated workspace sessions can share one CRM campaign until Q-27 is decided. The image runner previously obtained a brief/asset by its ID without checking the row's owner before generation or approve/reject/regenerate. These source facts indicate a cross-workspace confidentiality and integrity flaw; an executable exploit reproduction is **not yet available**.
- `_video(request)` also connected an unscoped `image_store.get_asset` reader and unscoped approved-picture list to the video editor. The prior video ownership fix S-06.02.68 did not protect external generated-image attachments.

## Test-first source and attempted RED runner

- `tests/test_audit_a05_image_workspace_isolation.py` was committed **before** production code at `b023f25273846b463bcebaf8ff60b0592e920d85`; it was extended at `ce160cf0bce0a8531bcedfbfaa1cea1718d0e58d`.
- The early QA gate was committed at `80173d6273df7836efddd32a4ac27dc9da63ea56` in `Dockerfile.review`.
- The isolated Render review deploy `dep-dbm5af95efls73chr69g` used that test-first source. **Render returned `build_failed` before any Docker test step**:
  > Build canceled: your workspace has run out of build pipeline minutes for the current billing period.
- This is a **pipeline-minute entitlement/billing blocker**, not a failed pytest result. There is no observed RED baseline, so never say the tests reproduced the vulnerability on Render.
- The alert pointed to the workspace build settings: `https://dashboard.render.com/w/tea-cspt7hggph6c739lq5j0/settings#build-pipeline`. Do not increase paid spend or plans without explicit owner approval.

## Changes committed to develop

- `offsetx_apollo_builder/imagery/store.py` at `8024b4f27059f654839bdf8b83911e19159a68be`: `list_briefs` and `list_assets` accept an optional `workspace_id` and apply the SQL owner predicate **before** order and LIMIT. Existing standalone store/internal default calls are unchanged.
- `offsetx_apollo_builder/imagery/engine.py` at `cc1eb565fece02d21f344238cb0f9259d2b20d0c`: `_owned_brief` and `_owned_asset` check actual stored owner against the authenticated engine workspace before generation, swipes, file removal or regeneration. Review queue, fulfilled-brief count and summaries use scoped rows.
- `offsetx_apollo_builder/api/app.py` at `7ee0031d552dd3be55272f88713c51bd97d347fa`: image brief and asset list handlers pass the real `_workspace_id(request)`; image file downloads return 404 before serving a foreign file. Video `asset_reader` refuses foreign picture IDs, and video auto-assembly's approved-picture list filters by owner before LIMIT.
- No schema migration, dependency change, main/customer deploy, live model call or real customer data was part of this implementation.

## Regression cases added — written, NOT RUN

Nine focused pytest cases (including a 3-way decision parameter): two authenticated cookie sessions with a **shared** synthetic CRM campaign; separate briefs, approved/pending image records and a beta video project. Test double forbids external provider calls.

1. Foreign direct image download 404 with no private bytes; owner still downloads.
2. Workspace-scoped briefs, image lists, review queue and summary.
3. Foreign brief ID cannot call image generation or a provider.
4–6. Foreign approve, reject and regenerate cannot mutate state, score or delete file; own approve works.
7. A foreign approved image cannot be placed into a video; own image can.
8. Video explicit auto-assembly with a foreign image ID refuses.
9. Video automatic asset selection cannot pick another workspace's approved image.

Before any rollout, run the entire new file and existing imagery/video tests. The tests are *intended acceptance checks*, not current pass claims.

## Rerun after build budget is restored

On the pinned `develop` executable/test source (confirm head first), invoke the isolated review service `srv-db86p4u89jmc73cehns0` in workspace `tea-cspt7hggph6c739lq5j0`. Its `Dockerfile.review` includes:
```bash
uv run pytest -q tests/test_audit_a05_image_workspace_isolation.py
uv run pytest -q tests/test_audit_a05_video_workspace_isolation.py
uv run pytest -q tests/test_imagery.py tests/test_video_assembly.py
uv run pytest -q
# Additional isolated Render stages: real disposable PostgreSQL,
# frontend tests/build/audits, Chromium, Ruff, concurrency, board structure.
```
Do not use customer services as test runners. The existing board verifier has used `--skip-tests`; full Git-history DONE evidence replay remains a separate gate.

## Open release boundaries

S-06.02.69 stays BACKLOG during active audit S-06.02.23; A05 per-user roles and full CRM campaign ownership Q-27 remain unresolved. Independent penetration, actual customer acceptance, full Git-history verifier and production/main deployment remain OPEN. **No release or end-to-end security certification is supported by this record.**

References: D-373, DD-149, R-196, `docs/work-orders/S-06.02.69-image-workspace-ownership.md`.
