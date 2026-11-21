# D-472 — D-451 audit regression compatibility (2026-11-21)

**RED evidence:** Render QA deploy `dep-dc0o7ee1egvs738i1amg` on `7b8c167` ended `build_failed` at `Dockerfile.review` WP1 regression. `test_lost_request_context_cannot_read_other_workspaces_product` and `test_only_explicit_timer_scope_can_read_linked_product_without_a_request` each failed in fixture setup: nonlocal `POST /api/v1/gtm/products` correctly returned 403 under D-451; the fixture then treated its JSON error as a product and indexed `product['id']`. The third targeted product-link test passed.

**Root cause:** the historical D-125 test assumed shared campaigns and drafts remained accessible to nonlocal users; this contradicts the newer deliberate D-451 fail-closed boundary. This is a test setup defect, not permission to reopen the customer-facing route.

**Source correction:** Create the fixture's private product through `app.state.gtm_store.create_product("acme", ...)` and its campaign link directly. Keep the two runtime context assertions, install-timer access and tenant-specific product reads. Explicitly assert 403 on nonlocal GTM and campaign-draft API calls; confirm beta cannot reach acme's offer even through a direct product-reader call with beta context. Owner/token operations stay unchanged.

**Gates:** Focused real Render QA, full Python/frontend, disposable PostgreSQL, Chromium, `uv run python scripts/verify_board.py` and manual adversarial acceptance have not been run on this correction. No DONE/customer/main claim.
