# F-06.02 A12/A13 — factual cache integrity and truthful model attribution

Date: 2026-11-03. Repository: `kunalwagh101/off_CRM`. Working branch: `develop` only. Remediation stories `S-06.02.58` and `S-06.02.59`. This is not the whole `S-06.02.23` audit or a customer release.

## Original risk, reproduced in the actual isolated QA image

- **A12 / D-360:** A long document containing "42 million" produced a **near-cache** answer after the value changed to "420 million". Likewise "is approved" produced the old "Approved" response after adding "not". Both cases returned incorrect cached facts instead of starting a new model call.
- **A13 / D-361:** The cache lookup omitted model identity; it also did not accept the system instructions as a cache key input. A response could be credited to a model or prompt that never ran.
- **TDD test-only commit:** `1593a427d088c53f723bd394b9967cb62590e3f5`. Early fail-fast Docker gate: `3e06faa360c2f429f15d7a1249785f94d42979d2`.
- **Actual Render RED:** service `srv-db86p4u89jmc73cehns0`, deploy `dep-dbkrmik9v7es73f6gj1g`, `build_failed` 2026-11-03 10:46:10 UTC. `uv run pytest -q tests/test_ai_cache_integrity.py` **4 failed in 1.87s**. The first two were stale near-cache results; the other two lacked a model-ID lookup and system-prompt store contract. These expected RED failures were not treated as successful QA.

## Code changes and tests

- `offsetx_apollo_builder/ai/cache.py`: factual cache hits now require exact canonical payload identity; the old near-match flag cannot bypass that. Partition includes workspace, policy, data class, task, provider, model and hashes of the system instructions and generation options.
- `offsetx_apollo_builder/ai/broker.py`: the single permitted provider egress gate supplies the current model, system prompt and request options/expected JSON format to both cache reads and writes. Scanner still executes before cache lookup.
- `tests/test_ai_cache_integrity.py`: numeric, negation, model and prompt isolation.
- `tests/test_ai_cache.py`: legacy near-hit assumptions replaced with exact-fact requirements, end-to-end broker tests added for changed model and changed system instructions, original identical-payload hit/egress audit retained.
- `Dockerfile.review`: early cache-integrity and broker `-k A13` gates, followed by existing full SQLite, PostgreSQL, Chromium, frontend, static, concurrency and board-structural stages.
- No new external dependency, customer account access, model call, database schema, new AI provider pathway, data migration, or `main` promotion.

## GREEN evidence, with exact-source limitation

- Isolated Render review `dep-dbkrodt9fdbs73c5vik0` on source `25f882c3534c1fddcd6a42e1bdbe9e88ce9e8d0a`: the first `uv run pytest -q tests/test_ai_cache_integrity.py` gate returned **4 passed in 1.76s**; legacy near expectations updated.
- **This deployment did not contain** the later two `EgressBroker.call` integration tests and their early Docker gate. An exact-source follow-up review is required; its outcome must be recorded separately. Do not carry older success counts to newer code.

## Security and operational review

- Privacy: no mailbox content becomes cacheable; workspace/policy boundaries stay distinct; raw system instruction text is hashed instead of stored in a partition key.
- Correctness: a near-identical input can no longer be accepted as equal to a different fact; cached result origin is tied to actual model ID, instructions and generation options.
- Recovery: existing SQLite schema and TTL/eviction are unchanged. Legacy cached entries remain but become misses under newer generation partitions; no irreversible migration.
- Cost: stricter cache matching increases model usage relative to unsafe near hits. The separate AI spend-cap and cross-process quota-reservation findings A10/A11 remain **open** and are not fixed by this work.
- Rollback: reverting cache/provenance protection would reopen two reproducible security/correctness failures. Do not deploy a rollback that restores unsafe near-cache or cross-model reuse.

## Open evidence gates

Independent penetration and hostile concurrency, real provider/model acceptance, operational cost monitoring, full-history `uv run python scripts/verify_board.py`, complete latest-source Render SQLite/PostgreSQL/Chromium and frontend review, owner/customer-path acceptance and `main` production rollout. The applicable board items remain **IN_REVIEW**, not DONE.
