# off_CRM — complete outstanding work and test register
Date: 2026-10-15 · Repository: `kunalwagh101/off_CRM` · branch: `develop`

## Latest active review update — 2026-10-16

Two independent, dependency-free review stories are the current detailed closure targets: **S-06.02.41** (authenticated 503-persisted-contact pagination) and **S-06.02.42** (formula-safe report exports). On Render `dep-db93t2mi0phs73c6msq0` (source `f7ba9f3`), `uv run pytest -v --tb=short tests/test_contacts_filters_export.py tests/test_spreadsheet_exports.py tests/test_existing_poi_enrichment.py tests/test_apollo_rejection_ledger.py` **actually passed 19 tests**, plus 3 fail-closed access tests. The 67 Git/CI fixture tests passed. A complete full Python/PG/React build continues in that same run; its final outcome must be read from Render logs before any claim.

For S-06.02.41 a disposable real FastAPI+SQLite flow imported and paged 503 contacts and checked that row 502 was reachable; this does **not** equal completed Chromium UI/keyboard and reload validation. For S-06.02.42 tests opened the generated XLSX with `openpyxl`, found escaped text rather than formula cells across accepted/rejected/raw/audit/metadata tabs, and confirmed inputs remained unchanged; real spreadsheet-application and independent review remain open.

**Authoritative board at this checkpoint remains 57 IN_REVIEW, 70 DONE**. This is a deliberate DoD decision, not 57 failing automated tests. Refer to `docs/evidence/2026-10-16-S-06.02.41-42-validation.md`; D-271 and D-272 are updated with this exact new evidence. Historic comments further down describe earlier states and are not the latest pass/fail summary. npm dependency audits were already cleared (0 vulnerabilities) in the 2026-10-15 verified Render build.

## Interpretation
This is an **evidence log**, not a replacement for `BOARD.md`; board statuses have not been silently promoted. There are **80 unfinished board items**: 57 IN_REVIEW (18 product-level F features + 39 S stories), 16 BACKLOG, 6 BLOCKED and 1 IN_PROGRESS. There are 70 DONE, 0 READY, 0 DEFERRED. A focused test PASS does **not** mean a feature is DONE: end-to-end, live PostgreSQL, privacy, migration recovery, dependencies and owner acceptance may still be open.

Test outcomes below are from completed Render QA-only run `dep-db8944m89jmc73cmoan0` on `develop` (`311f1ab`): **85 passed, 1 failed, 14 skipped, 2 warnings**, and earlier `dep-db892nij9qps73c46gvg` (`fc3f3d9`): **83 passed, 3 failed, 14 skipped**. Final F-06.19 retest `dep-db89530u01pc73f01t7g` on `e671607` **completed 86 passed, 14 skipped, 2 warnings**; no focused Python failure. The Docker build still **failed** at `npm audit --audit-level=high` with 5 development advisories (3 moderate, 2 high). Frontend separate run: 212 passed. Full Python broader run: 2,678 passed, 72 failed, 46 skipped (context-dependent verifier/CI failures included); see `docs/evidence/2026-10-15-all-in-review-audit.md`.

## 57-item prioritised review queue — operational order

The source of status remains `BOARD.md`; this is a review execution order, **not** 57 concurrent active stories. Only two records are active at a time. Each listed item remains IN_REVIEW until all its own Definition of Done gates pass; a focused unit test cannot silently close it.

### P0 — active, two-item WIP (2)

| Order | Item | Specific review target |
|---:|---|---|
| 1 | S-06.02.16 — Resolve frontend development dependency audit findings | Registry-backed npm audit + lockfile + npm ci + 212 frontend tests/build |
| 2 | S-06.02.20 — The verifier tells a shallow clone apart from a missing commit | Real Git history fixture, full CI tests, full repository verifier |

### P1 — security and durable data (11)

| Order | Item | Specific review target |
|---:|---|---|
| 3 | S-06.02.43 — Logout revokes the copied browser session | Copied session must remain revoked after restart |
| 4 | S-06.01.01 — Workspaces with their own keys and their own logins | Named acceptance tests and remaining live integration/recovery gates |
| 5 | S-06.02.36 — A second owner login is made on purpose | Named acceptance tests and remaining live integration/recovery gates |
| 6 | S-06.02.02 — Every endpoint authorises and validates | Named acceptance tests and remaining live integration/recovery gates |
| 7 | S-06.02.01 — No secret may enter a model prompt | Named acceptance tests and remaining live integration/recovery gates |
| 8 | S-06.02.04 — Data deletion and subject access | Named acceptance tests and remaining live integration/recovery gates |
| 9 | S-06.02.21 — Durable customer state and safe recovery (audit WP1) | Durable Postgres/test DB migration, recovery and restore |
| 10 | S-06.02.38 — Any error can be traced back the next day | Named acceptance tests and remaining live integration/recovery gates |
| 11 | S-03.01.03 — Browser blocks internal network access | Real browser block of private IP, WebSockets and redirects |
| 12 | S-05.01.04 — Public-page fetches connect only to checked destinations | Named acceptance tests and remaining live integration/recovery gates |
| 13 | S-06.02.28 — A command-line tool locks the workspace it actually opens | Named acceptance tests and remaining live integration/recovery gates |

### P2 — complete CRM user journeys (26)

| Order | Item | Specific review target |
|---:|---|---|
| 14 | F-06.19 — CRM Data Quality Centre | Real CRM end-to-end UI/API with permissions and persistence |
| 15 | F-06.20 — Campaign Comparison Dashboard | Real CRM end-to-end UI/API with permissions and persistence |
| 16 | F-06.21 — Follow-up Performance Centre | Real CRM end-to-end UI/API with permissions and persistence |
| 17 | F-06.16 — Unified CRM Search | Real CRM end-to-end UI/API with permissions and persistence |
| 18 | F-06.17 — Account Intelligence Workspace | Real CRM end-to-end UI/API with permissions and persistence |
| 19 | F-06.18 — Campaign-to-Revenue Attribution | Real CRM end-to-end UI/API with permissions and persistence |
| 20 | F-06.13 — Qualified Reply-to-Sales Conversion | Real CRM end-to-end UI/API with permissions and persistence |
| 21 | F-06.14 — Contact 360 Workspace | Real CRM end-to-end UI/API with permissions and persistence |
| 22 | F-06.15 — Daily Action Command Center | Real CRM end-to-end UI/API with permissions and persistence |
| 23 | F-06.10 — Reply Inbox & Human Triage | Real CRM end-to-end UI/API with permissions and persistence |
| 24 | F-06.11 — Contact Communication History | Real CRM end-to-end UI/API with permissions and persistence |
| 25 | F-06.12 — Human Follow-up Task Manager | Real CRM end-to-end UI/API with permissions and persistence |
| 26 | F-06.07 — Audience Management Workspace | Real CRM end-to-end UI/API with permissions and persistence |
| 27 | F-06.08 — Campaign Launch Readiness Center | Real CRM end-to-end UI/API with permissions and persistence |
| 28 | F-06.09 — Campaign Activity & Audit Timeline | Real CRM end-to-end UI/API with permissions and persistence |
| 29 | F-06.04 — Campaign Management | Real CRM end-to-end UI/API with permissions and persistence |
| 30 | F-06.05 — Campaign Blueprint Reuse | Real CRM end-to-end UI/API with permissions and persistence |
| 31 | F-06.06 — Campaign Performance Intelligence | Real CRM end-to-end UI/API with permissions and persistence |
| 32 | S-06.02.47 — Large send queues are paginated | Named acceptance tests and remaining live integration/recovery gates |
| 33 | S-06.02.48 — Campaign-wide queue counters do not mislead | Named acceptance tests and remaining live integration/recovery gates |
| 34 | S-06.02.49 — Queue views focus on actionable cohorts | Named acceptance tests and remaining live integration/recovery gates |
| 35 | S-06.02.44 — Download all filtered Contacts rows | Named acceptance tests and remaining live integration/recovery gates |
| 36 | S-06.02.45 — Category and variant filters for contacts | Named acceptance tests and remaining live integration/recovery gates |
| 37 | S-06.02.46 — Marked-only contacts remain reachable | Named acceptance tests and remaining live integration/recovery gates |
| 38 | S-06.02.41 — Contacts beyond row 500 are reachable | Named acceptance tests and remaining live integration/recovery gates |
| 39 | S-06.02.42 — Enrichment exports cannot run spreadsheet formulas | Named acceptance tests and remaining live integration/recovery gates |

### P3 — AI, agents, GTM, media, accessibility and other remaining items (18)

| Order | Item | Specific review target |
|---:|---|---|
| 40 | S-12.02.05 — The brain drafts against the expert corpus and the owner's winners | Named acceptance tests and remaining live integration/recovery gates |
| 41 | S-12.01.03 — The video director uses the product | Named acceptance tests and remaining live integration/recovery gates |
| 42 | S-06.02.34 — Connectors show how much is left | Named acceptance tests and remaining live integration/recovery gates |
| 43 | S-06.02.37 — Skip navigation keeps the current screen | Named acceptance tests and remaining live integration/recovery gates |
| 44 | S-06.02.39 — Valid low-bitrate WebM exports pass verification | Named acceptance tests and remaining live integration/recovery gates |
| 45 | S-12.02.06 — A plan's posting channel runs from the screens | Named acceptance tests and remaining live integration/recovery gates |
| 46 | S-06.02.25 — Every screen opens at its top, its warnings in view | Named acceptance tests and remaining live integration/recovery gates |
| 47 | S-06.02.22 — A created or selected campaign stays the active workspace | Named acceptance tests and remaining live integration/recovery gates |
| 48 | S-07.01.03 — Meeting transcription with no bot in the call | Named acceptance tests and remaining live integration/recovery gates |
| 49 | S-06.02.05 — The UI is usable by keyboard and screen reader | Named acceptance tests and remaining live integration/recovery gates |
| 50 | S-06.01.04 — Routines that fire agent runs on a schedule or an event | Named acceptance tests and remaining live integration/recovery gates |
| 51 | S-04.01.01 — Companions: persisted agent profiles | Named acceptance tests and remaining live integration/recovery gates |
| 52 | S-02.02.02 — PLAN.md as the single source of truth | Named acceptance tests and remaining live integration/recovery gates |
| 53 | S-03.02.05 — A platform is a row, not a code change | Named acceptance tests and remaining live integration/recovery gates |
| 54 | S-05.01.03 — Take a competitor post apart and rebuild the shape | Named acceptance tests and remaining live integration/recovery gates |
| 55 | S-05.01.02 — Extraction packs as declared data | Named acceptance tests and remaining live integration/recovery gates |
| 56 | S-05.01.01 — A crawler with a frontier, not a loop | Named acceptance tests and remaining live integration/recovery gates |
| 57 | S-07.01.04 — Reports and artifacts | Named acceptance tests and remaining live integration/recovery gates |


## IN_REVIEW — every implemented feature/story requiring certification
| # | ID | Description | Focused test evidence | Last completed outcome | Remaining gate |
|---:|---|---|---|---|---|
| 1 | F-06.19 | CRM Data Quality Centre | `tests/test_crm_operations.py::test_quality_filters_exact_saved_records_and_no_private_fields` | PASS focused after correcting UUID-tie test flake (86-pass rerun, dep-db89530u01pc73f01t7g) | Full DoD: live user flow, applicable security/PG/browser/recovery/dependency tests |
| 2 | F-06.20 | Campaign Comparison Dashboard | `tests/test_crm_operations.py::test_comparison_counts_unique_memberships_not_message_fanout` | PASS focused | Full DoD: live user flow, applicable security/PG/browser/recovery/dependency tests |
| 3 | F-06.21 | Follow-up Performance Centre | `tests/test_crm_operations.py::test_followup_performance_groups_labels_and_preserves_global_totals` | PASS focused | Full DoD: live user flow, applicable security/PG/browser/recovery/dependency tests |
| 4 | F-06.16 | Unified CRM Search | `tests/test_crm_insights.py::test_unified_search_filters_privately_and_returns_consistent_campaign_links` | PASS focused | Full DoD: live user flow, applicable security/PG/browser/recovery/dependency tests |
| 5 | F-06.17 | Account Intelligence Workspace | `tests/test_crm_insights.py::test_accounts_group_casefolded_company_with_no_join_fanout` | PASS focused | Full DoD: live user flow, applicable security/PG/browser/recovery/dependency tests |
| 6 | F-06.18 | Campaign-to-Revenue Attribution | `tests/test_crm_insights.py::test_revenue_attribution_first_link_and_global_totals_not_double_counted` | PASS focused | Full DoD: live user flow, applicable security/PG/browser/recovery/dependency tests |
| 7 | F-06.13 | Qualified Reply-to-Sales Conversion | `tests/test_relationship_intelligence.py::test_qualified_promotion_is_explicit_idempotent_and_reuses_email; test_relationship_action_apis_enforce_auth_and_promote_once` | PASS focused after HTTP422-contract correction | Full DoD: live user flow, applicable security/PG/browser/recovery/dependency tests |
| 8 | F-06.14 | Contact 360 Workspace | `tests/test_relationship_intelligence.py::test_contact_360_only_exposes_campaign_data_and_safe_projection` | PASS focused | Full DoD: live user flow, applicable security/PG/browser/recovery/dependency tests |
| 9 | F-06.15 | Daily Action Command Center | `tests/test_relationship_intelligence.py::test_daily_action_center_filters_prioritises_and_deduplicates_leads` | PASS focused | Full DoD: live user flow, applicable security/PG/browser/recovery/dependency tests |
| 10 | F-06.10 | Reply Inbox & Human Triage | `tests/test_relationship_workflows.py::test_reply_inbox_triage_is_campaign_scoped_and_preserves_send_stop` | PASS focused | Full DoD: live user flow, applicable security/PG/browser/recovery/dependency tests |
| 11 | F-06.11 | Contact Communication History | `tests/test_relationship_workflows.py::test_conversation_history_is_bounded_and_excludes_raw_provider_json` | PASS focused | Full DoD: live user flow, applicable security/PG/browser/recovery/dependency tests |
| 12 | F-06.12 | Human Follow-up Task Manager | `tests/test_relationship_workflows.py::test_followup_tasks_due_assignment_revision_and_persistence; test_existing_sqlite_crm_receives_additive_relationship_tables` | PASS focused after migration-version expectation correction | Full DoD: live user flow, applicable security/PG/browser/recovery/dependency tests |
| 13 | F-06.07 | Audience Management Workspace | `tests/test_audience_launch_activity.py::test_manual_audience_entry_deduplicates_and_never_mutates_existing_profile; test_bulk_selection_mark_stop_atomicity_and_terminal_protection` | PASS focused | Full DoD: live user flow, applicable security/PG/browser/recovery/dependency tests |
| 14 | F-06.08 | Campaign Launch Readiness Center | `tests/test_audience_launch_activity.py::test_launch_readiness_identifies_gates_without_calling_send` | PASS focused | Full DoD: live user flow, applicable security/PG/browser/recovery/dependency tests |
| 15 | F-06.09 | Campaign Activity & Audit Timeline | `tests/test_audience_launch_activity.py::test_event_timeline_facets_filters_pagination_and_authentication` | PASS focused | Full DoD: live user flow, applicable security/PG/browser/recovery/dependency tests |
| 16 | F-06.04 | Campaign Management | `tests/test_campaign_product_features.py::test_campaign_settings_save_and_timezone_is_rejected_before_database_write` | PASS focused after HTTP422-contract correction | Full DoD: live user flow, applicable security/PG/browser/recovery/dependency tests |
| 17 | F-06.05 | Campaign Blueprint Reuse | `tests/test_campaign_product_features.py::test_configuration_clone_is_paused_empty_idempotent_and_preserves_source` | PASS focused | Full DoD: live user flow, applicable security/PG/browser/recovery/dependency tests |
| 18 | F-06.06 | Campaign Performance Intelligence | `tests/test_campaign_product_features.py::test_performance_denominator_is_unique_contacted_and_excludes_unsent_replies` | PASS focused | Full DoD: live user flow, applicable security/PG/browser/recovery/dependency tests |
| 19 | S-06.02.47 | Large send queues are paginated | `tests/test_queue_views.py::test_queue_api_requires_auth_and_returns_paged_counts` | PASS focused | Full DoD: live user flow, applicable security/PG/browser/recovery/dependency tests |
| 20 | S-06.02.48 | Campaign-wide queue counters do not mislead | `tests/test_queue_views.py::test_queue_counts_come_from_every_contact_not_the_visible_page` | PASS focused | Full DoD: live user flow, applicable security/PG/browser/recovery/dependency tests |
| 21 | S-06.02.49 | Queue views focus on actionable cohorts | `tests/test_queue_views.py::test_queue_rejects_invalid_limit_offset_and_view` | PASS focused | Full DoD: live user flow, applicable security/PG/browser/recovery/dependency tests |
| 22 | S-06.02.44 | Download all filtered Contacts rows | `tests/test_contacts_filters_export.py::test_filters_facets_marked_only_and_export_are_authenticated` | PASS focused | Full DoD: live user flow, applicable security/PG/browser/recovery/dependency tests |
| 23 | S-06.02.45 | Category and variant filters for contacts | `tests/test_contacts_filters_export.py::test_filters_facets_marked_only_and_export_are_authenticated` | PASS focused | Full DoD: live user flow, applicable security/PG/browser/recovery/dependency tests |
| 24 | S-06.02.46 | Marked-only contacts remain reachable | `tests/test_contacts_filters_export.py::test_filters_facets_marked_only_and_export_are_authenticated` | PASS focused | Full DoD: live user flow, applicable security/PG/browser/recovery/dependency tests |
| 25 | S-06.02.41 | Contacts beyond row 500 are reachable | `tests/test_contacts_filters_export.py::test_download_covers_503_rows_and_never_executes_spreadsheet_formulas` | PASS focused | Full DoD: live user flow, applicable security/PG/browser/recovery/dependency tests |
| 26 | S-06.02.42 | Enrichment exports cannot run spreadsheet formulas | `tests/test_contacts_filters_export.py::test_download_covers_503_rows_and_never_executes_spreadsheet_formulas` | PASS focused | Full DoD: live user flow, applicable security/PG/browser/recovery/dependency tests |
| 27 | S-06.02.43 | Logout revokes the copied browser session | `docs/work-orders/S-06.02.43-logout-revocation.md` | PASS disposable PG two-instance cookie replay/restart plus digest check; 215 storage + 2772 PG-mode full PASS; live Chromium and old-db migration open | Full DoD: live user flow, applicable security/PG/browser/recovery/dependency tests |
| 28 | S-12.02.05 | The brain drafts against the expert corpus and the owner's winners | `docs/work-orders/S-12.02.05-plans-with-expert-references.md` | PASS focused GTM/template code; owner expert corpus, 30 judged real cases and live A/B NOT RUN | Full DoD: live user flow, applicable security/PG/browser/recovery/dependency tests |
| 29 | S-06.02.16 | Resolve frontend development dependency audit findings | `docs/work-orders/S-06.02.16-frontend-dependency-audit.md` | PASS current audits 0 vulnerabilities, npm ci, 212 React tests, frontend build; prior 5 advisories FIXED | Full DoD still requires repository verifier with real history, CI and independent review |
| 30 | S-12.01.03 | The video director uses the product | `docs/work-orders/S-12.01.03-video-director-uses-the-product.md` | PASS focused; no live video provider verification | Full DoD: live user flow, applicable security/PG/browser/recovery/dependency tests |
| 31 | S-06.02.34 | Connectors show how much is left | `docs/work-orders/S-06.02.34-usage-remaining.md` | PASS simulated usage parsing; real balance vendor and header capture NOT VERIFIED | Full DoD: live user flow, applicable security/PG/browser/recovery/dependency tests |
| 32 | S-06.02.28 | A command-line tool locks the workspace it actually opens | `docs/work-orders/S-06.02.28-path-aware-workspace-lock.md` | PASS focused; live concurrent restore pending | Full DoD: live user flow, applicable security/PG/browser/recovery/dependency tests |
| 33 | S-06.02.36 | A second owner login is made on purpose | `docs/work-orders/S-06.02.36-explicit-owner-login.md` | PASS focused after owner-auth test alignment | Full DoD: live user flow, applicable security/PG/browser/recovery/dependency tests |
| 34 | S-05.01.04 | Public-page fetches connect only to checked destinations | `docs/work-orders/S-05.01.04-verified-destinations.md` | PASS safe HTTP/DNS pinning fixtures; Crawl4AI blocked pending egress isolation | Full DoD: live user flow, applicable security/PG/browser/recovery/dependency tests |
| 35 | S-03.01.03 | Browser blocks internal network access | `docs/work-orders/S-03.01.03-network-isolation.md` | PASS code tests; real sandbox/network proof pending | Full DoD: live user flow, applicable security/PG/browser/recovery/dependency tests |
| 36 | S-06.02.37 | Skip navigation keeps the current screen | `docs/work-orders/S-06.02.37-skip-keeps-current-page.md` | PASS frontend component suite; real Chrome skip-link interaction NOT RUN | Full DoD: live user flow, applicable security/PG/browser/recovery/dependency tests |
| 37 | S-06.02.20 | The verifier tells a shallow clone apart from a missing commit | `docs/work-orders/S-06.02.20-shallow-git-history.md` | PASS: 67 real Git-fixture + CI contract tests; complete historical ancestry not available in QA Docker | Full-history checkout board verifier and CI run remain required |
| 38 | S-06.02.39 | Valid low-bitrate WebM exports pass verification | `docs/work-orders/S-06.02.39-low-bitrate-export.md` | PASS general video gates; low-bitrate browser export not independently verified | Full DoD: live user flow, applicable security/PG/browser/recovery/dependency tests |
| 39 | S-12.02.06 | A plan's posting channel runs from the screens | `docs/work-orders/S-12.02.06-posting-channel-from-the-screens.md` | PASS core GTM apply; live screen-to-provider posting not verified | Full DoD: live user flow, applicable security/PG/browser/recovery/dependency tests |
| 40 | S-06.02.38 | Any error can be traced back the next day | `docs/work-orders/S-06.02.38-traceable-errors.md` | PASS focused failure-reference logs; hosted 5xx trace not live verified | Full DoD: live user flow, applicable security/PG/browser/recovery/dependency tests |
| 41 | S-06.02.25 | Every screen opens at its top, its warnings in view | `docs/work-orders/S-06.02.25-screen-opens-at-top.md` | PASS static accessibility; real Chromium acceptance pending | Full DoD: live user flow, applicable security/PG/browser/recovery/dependency tests |
| 42 | S-06.02.21 | Durable customer state and safe recovery (audit WP1) | `docs/work-orders/S-06.02.21-S-06.02.22-close-out.md` | PASS 3 security/GTM targeted; full SQLite 2754 and CRM-on-PG 2774; D-313 fixed with RED proof; independent/browser/backup recovery gates still OPEN | Full DoD: live user flow, applicable security/PG/browser/recovery/dependency tests |
| 43 | S-06.02.22 | A created or selected campaign stays the active workspace | `docs/work-orders/S-06.02.21-S-06.02.22-close-out.md` | PASS campaign persistence unit test; full active-workspace UI check open | Full DoD: live user flow, applicable security/PG/browser/recovery/dependency tests |
| 44 | S-07.01.03 | Meeting transcription with no bot in the call | `tests/test_meeting_transcription.py` | PASS local meeting regression; real mic/tab capture/provider NOT RUN | Full DoD: live user flow, applicable security/PG/browser/recovery/dependency tests |
| 45 | S-06.02.05 | The UI is usable by keyboard and screen reader | `tests/test_frontend_accessibility_contract.py` | PASS static frontend contract; real keyboard/screen-reader still open | Full DoD: live user flow, applicable security/PG/browser/recovery/dependency tests |
| 46 | S-06.02.02 | Every endpoint authorises and validates | `tests/test_api_boundary_contract.py` | PASS protected API validation tests | Full DoD: live user flow, applicable security/PG/browser/recovery/dependency tests |
| 47 | S-06.02.01 | No secret may enter a model prompt | `tests/test_ai_egress_wall.py` | PASS egress wall regression; external provider egress remains limited | Full DoD: live user flow, applicable security/PG/browser/recovery/dependency tests |
| 48 | S-06.01.04 | Routines that fire agent runs on a schedule or an event | `tests/test_agent_routines.py` | PASS focused routines; hosted unattended run not verified | Full DoD: live user flow, applicable security/PG/browser/recovery/dependency tests |
| 49 | S-06.01.01 | Workspaces with their own keys and their own logins | `tests/test_workspace_isolation.py` | PASS focused workspace isolation; customer tenancy Q-27 remains | Full DoD: live user flow, applicable security/PG/browser/recovery/dependency tests |
| 50 | S-04.01.01 | Companions: persisted agent profiles | `tests/test_agent_companions.py` | PASS focused companion privacy | Full DoD: live user flow, applicable security/PG/browser/recovery/dependency tests |
| 51 | S-02.02.02 | PLAN.md as the single source of truth | `tests/test_agent_plan.py` | PASS focused PLAN contract; live steering pending | Full DoD: live user flow, applicable security/PG/browser/recovery/dependency tests |
| 52 | S-03.02.05 | A platform is a row, not a code change | `tests/test_browser_platform_registry.py` | PASS registry tests; live platform integration open | Full DoD: live user flow, applicable security/PG/browser/recovery/dependency tests |
| 53 | S-06.02.04 | Data deletion and subject access | `tests/test_privacy.py` | PASS focused privacy; hosted subject deletion on real database not verified | Full DoD: live user flow, applicable security/PG/browser/recovery/dependency tests |
| 54 | S-05.01.03 | Take a competitor post apart and rebuild the shape | `tests/test_competitor_teardown.py` | PASS competitor teardown focused | Full DoD: live user flow, applicable security/PG/browser/recovery/dependency tests |
| 55 | S-05.01.02 | Extraction packs as declared data | `tests/test_extraction_packs.py` | PASS extraction pack focused | Full DoD: live user flow, applicable security/PG/browser/recovery/dependency tests |
| 56 | S-05.01.01 | A crawler with a frontier, not a loop | `tests/test_crawler_frontier.py` | PASS frontier focused; real robots/DNS/browser egress integration open | Full DoD: live user flow, applicable security/PG/browser/recovery/dependency tests |
| 57 | S-07.01.04 | Reports and artifacts | `tests/test_agent_artifacts.py` | PASS focused agent artifacts; final user report/browser route pending | Full DoD: live user flow, applicable security/PG/browser/recovery/dependency tests |

## Not started or otherwise outstanding

### IN_PROGRESS (1)

| ID | Work | Action/status |
|---|---|---|
| S-06.02.23 | Re-check the 7 September production audit on `develop` | Production audit re-check remains active |

### BLOCKED (6)

| ID | Work | Action/status |
|---|---|---|
| S-06.02.19 | One working branch holds everything built, and it is green | external — the old branches must be kept as `archive/<branch>` tags and then deleted, and GitHub refused both to this session (HTTP 403, 2026-09-23; it may push commits, not tags or deletions). The owner runs `bash scripts/archive_old_branches.sh --delete` from a clone with push rights (`docs/BRANCHING.md`). The rest of the story is met: `develop` holds everything and is green. |
| S-06.01.06 | Campaigns, contacts and drafts belong to a workspace | Q-27 — built only if the owner chooses option 2, workspace-owned CRM rows (`D-135`). |
| S-06.02.18 | Restore executable CI runner capacity | external — GitHub-hosted `ubuntu-latest` jobs are created but fail before runner allocation with zero steps/no logs. Owner must inspect Actions billing/budgets/payment state and repository Actions policy; if those are clean, GitHub Support must resolve hosted-runner provisioning. |
| S-01.05.01 | Publish to YouTube through the official API | external — a Google Cloud project with YouTube Data API v3 enabled, and OAuth consent for the channel. Only the owner can create it. |
| S-01.05.02 | One adapter contract for the remaining platforms | external — Meta app review, TikTok content-posting audit, LinkedIn partner programme. Weeks of calendar time, and none of it is engineering. |
| S-01.05.03 | Read real engagement back from the platform | external — depends on S-01.05.01, which is itself waiting on the Google Cloud project. |

### BACKLOG (16)

| ID | Work | Action/status |
|---|---|---|
| S-06.02.40 | A durable email worker runs beside the deployed web app | docs/work-orders/S-06.02.40-durable-deployment-worker.md |
| S-02.02.03 | Interrupt, steer, resume | Needs work order/prerequisite before pull |
| S-04.01.02 | Skills: procedures fetched on demand | docs/work-orders/S-04.01.02-on-demand-agent-skills.md |
| S-04.01.03 | Sub-agents for context isolation | Needs work order/prerequisite before pull |
| S-04.01.04 | The five roles, wired to what already exists | Needs work order/prerequisite before pull |
| S-06.01.02 | Three-level permissions | Needs work order/prerequisite before pull |
| S-06.01.05 | Deployment, monitoring and rollback | Needs work order/prerequisite before pull |
| S-07.01.01 | An MCP client | Needs work order/prerequisite before pull |
| S-07.01.02 | Native OAuth integrations | Needs work order/prerequisite before pull |
| S-06.02.27 | The audit's live harness runs against `develop` | Needs work order/prerequisite before pull |
| S-06.02.35 | Drafts reach a model the owner set up on a screen | Needs work order/prerequisite before pull |
| S-06.03.04 | The hosted database is backed up outside itself | docs/work-orders/S-06.03.04-hosted-backup-and-restore.md |
| S-06.03.05 | Production refuses a half-hosted install | Needs work order/prerequisite before pull |
| S-06.03.06 | Every other store has a decided home | Needs work order/prerequisite before pull |
| S-06.03.07 | A local install's decision belongs to that install | Needs work order/prerequisite before pull |
| S-06.02.26 | CI runs the suite on every Python the package supports | docs/work-orders/S-06.02.26-python-matrix.md |

## Reproduced failures and treatment
| Reference | Error | Classification | Fix / next check |
|---|---|---|---|
| D-300, F-06.04 | Invalid timezone returned 422 while old test expected 400 | HTTP test/contract drift: ValueError handler explicitly returns 422 | Updated test to expect 422; still asserts rejected write and restart persistence; rerun passed focused |
| F-06.13 | Promotion before positive human triage returned 422 while old test expected 400 | Test/contract drift: ValueError handler deliberately returns 422 | Updated test to assert 422 **and** visible prerequisites; rerun passed focused |
| F-06.12 | Migrated SQLite user_version 11 vs old test expectation 10 | Stale schema-version assertion | Test now expects `SCHEMA_VERSION`; rerun passed focused |
| F-06.19 | First campaign UUID asserted for a contact with two campaigns; actual UUID order can differ on equal timestamps | Flaky test assumption, not proven backend regression | Assert consistent campaign/member pair, referential contact ID and stable repeated read. Commit `e671607`. Rerun PASS: 86 passed, 14 skipped (dep-db89530u01pc73f01t7g) |
| D-299, S-06.02.16 | npm audit found 5 development dependency findings (2 high, 3 moderate) | Open security/dependency vulnerability | Upgrade locked dependencies, retest npm audit, Vitest, production build |
| D-298, S-06.02.20 | Full Python test stage excludes .github and .git from Docker context; .github workflow and Git verifier tests fail in QA container | Review harness is not a complete repository checkout | Run these tests with real Git history and CI config; cannot claim they passed |
| Q-27 | CRM contact/campaign data is install-wide, no customer tenant ownership proof | Product/security blocker | Owner decision + verified isolation required before multi-tenant release |

## Test commands and run references
- Focused: `uv run pytest -v --tb=short tests/test_campaign_product_features.py tests/test_audience_launch_activity.py tests/test_relationship_workflows.py tests/test_relationship_intelligence.py tests/test_crm_insights.py tests/test_crm_operations.py tests/test_contacts_filters_export.py tests/test_queue_views.py tests/test_crm_hosted.py tests/test_api_boundary_contract.py`.
- Frontend: `cd frontend && npm test && npm run build` (**212 tests passed**, build succeeded).
- Lint: `uv run ruff check --select E9,F63,F7,F82 .` (**passed**).
- Dependency: `cd frontend && npm audit --omit=dev --audit-level=low` (**0 findings**); `npm audit --audit-level=high` (**failed**, 5 findings).
- Full Python: `uv run pytest -q`: **72 failed, 2678 passed, 46 skipped** on 2026-10-15. The full-suite result is a fail and not feature certification.
- Render QA review logs: https://dashboard.render.com/web/srv-db86p4u89jmc73cehns0
- Original app service is intentionally untouched; no external email was sent, no real customer data mutated.

## Required next verification
1. **COMPLETED:** focused rerun passed 86/86 Python checks; PostgreSQL-specific 14 skipped, and independent end-to-end acceptance remains open.
2. Fix/read through full Python failure traces separately (harness-context failures vs actual code), rerun with true repository metadata.
3. Update vulnerable frontend development dependencies without suppressing npm audit and rerun.
4. Execute actual PostgreSQL migrations, rollback/restore, hosted durability and concurrency tests **only** against disposable QA data.
5. Run browser accessibility/security/e2e checks, verify tenant boundary Q-27 and external integrations with explicit owner approvals.
6. Update `DEFECT_LOG.md`, `BOARD.md` and per-story evidence only after the required real gates pass.

## Wave 2 — security, browser, GTM, storage and privacy (completed)
Date: 2026-10-15. Runner: `dep-db896lqj9qps73c4hlb0` initially **346 passed, 6 failed, 15 skipped, 3 warnings**. Remediation commit `9ace6b0d08f039dba1c760964301967c3c2c04de` and earlier focused test changes produced runner `dep-db898aaj9qps73c4n530`: **352 passed, 0 failed, 15 skipped, 3 warnings**, across 16 explicit test modules.

Affected stories and invariants: S-06.02.36 workspace owner approval and no cross-workspace access; S-03.01.03 browser isolation; S-03.02.02 vault separation; S-03.02.03 revoke/forget; S-02.02.04 countdown; S-03.02.05 platform registry; S-06.02.01 AI data egress; S-06.02.04 privacy; S-12.01.02 product request classification; S-06.03.02 hosted storage/egress copy. Those modules' focused tests passed, but the board remains IN_REVIEW where it was already IN_REVIEW; Docker real-sandbox, external provider/browser and PostgreSQL release gates remain.

| Failure | Reproduced actual error | Cause and repair | Rerun |
|---|---|---|---|
| D-306 | Owner-creation request without credentials returned 401, old test expected 403 | Correct authentication boundary is 401; test updated, no access weakened | PASS |
| D-307 | Creating new 'local' owner account without explicit `confirm_install_owner` returned 400 | Correct security requirement, updated hosted-privacy test to express explicit confirmation | PASS |
| D-308 | Video direction tests failed `Unknown campaign kind 'video'` | `video` is not a registered campaign kind; valid media campaign kind is `image` | PASS |
| D-309 | Missing source DB produced network/DNS failure to dummy PostgreSQL before 'Nothing to copy' | True defect: `copy_egress_log` migrated the destination before checking source exists; now validates source first | PASS |
| D-310 | `test_the_copied_columns_match_the_schema` reported mismatch at `payload_summary`/`system_prompt` | True schema-copy contract drift: reordered explicit `EGRESS_COLUMNS` to match schema | PASS |

`uv run ruff check --select E9,F63,F7,F82 .` also passed. The frontend's 212 Vitest tests and build passed again. **The final Docker build remains FAILED solely at the unsuppressed development-dependency audit**, which still finds 5 vulnerabilities (2 high, 3 moderate). A pass of the Python wave does not erase that security release blocker.

PostgreSQL read-only metadata query through hosted Render connector was **BLOCKED** because the QA database has an empty external IP allowlist. This is intentional security isolation: do not open the allowlist to all IPs. The QA app itself previously established internal DB connections, but this does not prove live migration/backup correctness. PostgreSQL-specific test cases remain skipped pending a private-network execution path.


## Wave 3 — agent, GTM, email, media and API security (completed)
Date 2026-10-15. Render review runner `dep-db899srrjlhs73ckq4pg`, commit `42f6b48c0a59afbee92e6ca5e442825258ba2cc7`. Executed 24 Python modules: **559 passed, 2 skipped, 2 warnings; zero failed**. Independent 212-case Vitest/frontend build and Ruff checks also passed in the review image. The image intentionally failed the final npm dev dependency audit (same 5 advisories). No live external send was attempted.

New coverage includes S-02.02.02 PLAN, S-04.01.01 companions, S-06.01.04 routines, S-12.01.03 video direction, S-12.02.06 GTM apply, S-07.01.04 agent reports, core email suppression/retry/delivery tests, video gates, server-side security and authentication. A test pass remains limited to its simulated/local entry point, not proof of a real third-party or multi-tenant deployment.

### Cumulative targeted results, distinct build waves
| Wave | Python passed | Python failed | Python skipped | Reference |
|---|---:|---:|---:|---|
| CRM / audience / relationship / contacts / queue | 86 | 0 | 14 | `dep-db89530u01pc73f01t7g` |
| Workspace / privacy / browser containment / GTM / hosted storage | 352 | 0 | 15 | `dep-db898aaj9qps73c4n530` |
| Agent / email / video / GTM / API security | 559 | 0 | 2 | `dep-db899srrjlhs73ckq4pg` |
| **Total focused executions** | **997** | **0** | **31** | Modules are partly overlapping in purpose, not pass-proof of every release gate |

These focused runs followed the initial broader `pytest -q` failure of 72 cases; the broad full-suite output has **not** been rerun in a complete Git context, so the overall release remains RED, irrespective of the focused green tests.

## Wave 4 — finish mapping the remaining review stories (completed)
Render runner: `dep-db89bluq1p3s73a2oes0` on commit `b6257a8a317dd1e30968268b73b49e520142457e`. **187 passed, 0 failed, 45 warnings** in `uv run pytest -v --tb=short` across 13 modules: crawler frontier, extraction packs, competitor teardown, safe public discovery, meeting transcripts, usage report, traceable errors, AI/email expert, accessibility contracts and GTM strategy. Vitest 212, frontend build and Ruff passed on the same review image. Build ended FAILED at the already-open npm dev-dependency audit.

Warnings: FastAPI Starlette TestClient/httpx deprecation (one), Python browser Enter-script JS regular-expression escape warning (one), and `lxml.html.HTMLParser(strip_cdata)` deprecation warnings from extraction (42) and discovery (one), totaling 45. The first-party escape was separately fixed in `offsetx_apollo_builder/browser/page.py` with a raw JavaScript string (`024ef206`); verification rerun `dep-db89cl5g1s2s739hc8cg` completed **187 passed, 44 warnings**; the first-party Python SyntaxWarning is gone, and the npm development audit still fails. Third-party warnings are not passing security release gates or application exceptions.

### Cumulative focused verification
- Python: **86 + 352 + 559 + 187 = 1,184 passed**, with **31 skipped** and zero failed on the **latest successful focused suite for each wave**.
- Frontend: **212 tests passed** and TypeScript/Vite built; production dependency audit reported **0 vulnerabilities**.
- **Unresolved:** development-only npm audit **5 findings** (2 high, 3 moderate), full-suite Git/CI-context failures not independently rerun, real PostgreSQL migration/backup/restoration, live browser and external-provider cases, customer tenancy Q-27, and applicable upstream DONE dependencies.
- The 57 review items now each have a named focused test *or* explicitly unresolved live/dependency check; **none is promoted to DONE** solely from these runs.

## Verified browser script warning fix — final review run

Commit `024ef2064b72ac9ee6e5bec14caea31949dd848a` was tested in Render runner `dep-db89cl5g1s2s739hc8cg`. Results: 187 passed, zero failed, **44 warnings**, down from 45 before changing the `_WHAT_ENTER_WOULD_DO` Python triple string to a raw string. The remaining warnings were a Starlette TestClient/httpx deprecation and third-party lxml parser deprecations. Final build intentionally remained FAILED at development `npm audit` with its five published vulnerability findings.

## New repository-wide gate: 2026-10-15, clean npm audits and full Python

Render QA runner `dep-db8akqs9v7es73877d9g`, source snapshot `30f48cfca8d1e7d5b1f016d01860c9cd45e8d088` reached **live** after all its required build gates.

- `npm ci` (frontend) — PASS, 57 packages installed, 0 vulnerabilities.
- `npm test` (frontend) — **212 passed** across 18 files on patched Vitest 4.1.11.
- `npm run build` — PASS.
- `npm audit --omit=dev --audit-level=low` — **0 vulnerabilities**.
- `npm audit --audit-level=high` — **0 vulnerabilities**. This supersedes the previous five development advisories (D-299 fixed).
- `uv run ruff check --select E9,F63,F7,F82 .` — PASS.
- `uv run pytest -q tests/test_ci_verifier_environment.py tests/test_verify_board.py` — **67 passed** in 19.38 seconds. Real temporary Git repositories and shallow/full fixture tests were exercised.
- `uv run pytest -q` — **2,752 passed, 44 skipped, 44 warnings in 245.52 seconds**, no failures. This supersedes the prior *historical* full-suite failure of 72 tests.
- Original production service and the separate application QA service were not redeployed. This is an isolated review build, not a customer deployment.

Important limitations: the review image intentionally excludes `.git`, so historical commit-ancestry verification of the actual repo and full `scripts/verify_board.py` execution in an authenticated full-history checkout remain open. The 44 skipped tests include PostgreSQL-specific execution that was not configured in this run. Do not close unrelated items or call system-wide production readiness based on this green runner.

### Dedicated PostgreSQL verification underway

A subsequent isolated build `dep-db8aoopsrm7s73e0j1eg` configures disposable, container-local PostgreSQL with no credentials/data from the real Render/Neon environment. Its goals are a real Postgres storage suite and full suite with `OFF_CRM_TEST_CRM_ON_POSTGRES=1`, with destructive fixtures limited to this disposable database. PostgreSQL result must not be recorded as PASS until logs finish; any hosted backup/restore acceptance requires separate proof.

## 2026-10-15 PostgreSQL 17 build-verified storage and failure diagnosis

Review build `dep-db8aoopsrm7s73e0j1eg` started a **real disposable local PostgreSQL 17** cluster in Docker (not the user's Render database) and ran two real suites:

1. `OFF_CRM_TEST_POSTGRES_URL=<test-only local PostgreSQL> uv run pytest -q tests/test_crm_hosted.py tests/test_hosted_storage.py tests/test_db_backend.py tests/test_storage_inventory.py tests/test_video_postgres.py tests/test_crm_harness.py` → **214 passed, 1 warning, 0 failed in 50.24s**. This is a supported PostgreSQL-hosted storage validation, not a production/hosted backup certification.
2. `OFF_CRM_TEST_POSTGRES_URL=<test-only local PostgreSQL> OFF_CRM_TEST_CRM_ON_POSTGRES=1 uv run pytest -q` → **2,771 passed, 2 failed, 92 skipped, 44 warnings in 308.03s**. Both failures were explicitly SQLite-file migration tests with hardcoded `PRAGMA user_version` statements mistakenly exercised against PostgreSQL by the global CRM backend swap: `tests/test_relationship_intelligence.py::test_sqlite_v10_upgrade_adds_sales_links_without_touching_old_records` and `tests/test_relationship_workflows.py::test_existing_sqlite_crm_receives_additive_relationship_tables`. This is harness classification, not evidence that the real PG schema migration failed.

**Corrective action:** both tests were annotated with `@pytest.mark.crm_sqlite_only`, with per-test reasons. They stay in SQLite full-suite coverage; PostgreSQL schema upgrades have independent tests in `tests/test_crm_hosted.py` and related modules. D-312 in DEFECT_LOG. The rerun `dep-db8aujom7kps73do3jh0` was triggered with these fixes plus a new Postgres two-instance copied-cookie revocation/restart acceptance test, `tests/test_hosted_storage.py::test_postgres_logout_revocation_reaches_another_live_app_and_survives_restart`. **Do not claim the new test or full PG rerun passes until its logs finish.**

The standalone application QA deploy `dep-db8apipsrm7s73e0lbm0` is LIVE at updated `develop` commit `bcc831c`, and logs show Uvicorn startup, HTTP 200, and the linked QA database subsequently measured three active connections. It is distinct from these destructive tests.

## S-06.02.43 and S-06.02.21 — 2026-10-15 extended QA verification

**Previous confirmed PG run:** Render `dep-db8b26e89jmc73cssm00` on `d004362`: 1 passing PostgreSQL cross-instance copied-session logout/restart regression with SHA-256 digest persistence; 215 passing targeted PostgreSQL storage tests; **2772 passed, 94 skipped** in the full PostgreSQL-backed CRM suite. See `docs/evidence/S-06.02.43-validation.md`. This was a disposable local DB, not customer data. Live Chromium cookie replay and migration of an already-populated hosted PG remain open.

**New security finding D-313:** a cold review of WP1 identified that a missing context-variable principal was treated as privileged content-timer identity. Render `dep-db8cjmajnfac73f52o2g` reproduced unauthorised linked-product reads as an expected failing test. Code on `develop` now defaults to deny, with a narrowly scoped, resettable owner timer identity (DD-121). Render `dep-db8ckq5g1s2s739r6mog` confirmed the first **2 passing regressions**. A broadened run uncovered an outdated GTM expectation of unscoped owner access (2753 passed, 1 failed, 45 skipped), and that expectation was corrected to demand deny-by-default plus explicitly privileged timer access. Render `dep-db8cnnou01pc73fb3d8g` then passed **3 affected tests** plus **67 verifier checks**; its full Python and PostgreSQL suites were running at this checkpoint. See `docs/evidence/S-06.02.21-security-review-2026-10-15.md`.

Both items remain IN_REVIEW until comprehensive regression, real browser/recovery acceptance, independent review and full-history board verification meet Definition of Done.

## Final security verification and QA deployment — 2026-10-15

- New `D-313` high-severity security finding reproduced: absent request ContextVar gave linked-product reader installation-owner privileges. The RED test failed on old code; production implementation now defaults to deny and grants only an explicit, resettable install-timer scope across `asyncio.to_thread`. A legacy GTM test's unsafe unscoped expectation was corrected, not waived. `DD-121` records the explicit architectural trade-off.
- Code commit tested: Render `dep-db8cnnou01pc73fb3d8g`, source snapshot `76bc929240192120e7506a80f60039d15548e9f5`. This runner completed to **live**, with all hard build gates passed.
- `uv run pytest -q` in SQLite mode: **2754 passed, 45 skipped, 44 warnings**, no failures.
- `OFF_CRM_TEST_CRM_ON_POSTGRES=1 uv run pytest -q` with `OFF_CRM_TEST_POSTGRES_URL` set to a disposable PostgreSQL 17 instance: **2774 passed, 94 skipped, 44 warnings**, no failures.
- PostgreSQL-hosted storage-focused suite: **215 passed**; exact copied-session replay/restart test: **1 passed**. CI/board fixture regressions: **67 passed**; fail-closed access and privileged timer compatibility: **3 passed**.
- Frontend: prior verified clean `npm ci`, **212 Vitest passed**, Vite build passed, npm production and dev security audits both **0 vulnerabilities**. Changes here did not modify frontend code.
- No primary production service was changed. A separate QA app `srv-db86h3gm7kps73d8ud1g` deploy was triggered to pick up the tested security patch: `dep-db8cttm89jmc73d2ip00`; **Render confirmed LIVE** at commit `fff73e1f4bfa68d6ddff85a11ca8443b1e800ccd`: Uvicorn startup completed; HEAD / and GET / both returned HTTP 200. Direct `/health/ready` endpoint response and browser acceptance were not independently fetched.
- Latest GitHub Actions `develop` run `38738223007` returned quality and postgres **failure before any steps**, so it cannot replace real CI execution or certify historic Git ancestry. Original board verifier needs authenticated full-history checkout, not a mocked one.

**Authoritative board statuses unchanged:** 57 IN_REVIEW, 16 BACKLOG, 6 BLOCKED, 1 IN_PROGRESS, 70 DONE. The two actively reviewed stories `S-06.02.21` and `S-06.02.43` retain independent-review/browser/old-hosted-migration/recovery gates even after real local PostgreSQL green regression.
