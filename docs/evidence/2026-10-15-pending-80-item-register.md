# off_CRM — complete outstanding work and test register
Date: 2026-10-15 · Repository: `kunalwagh101/off_CRM` · branch: `develop`

## Interpretation
This is an **evidence log**, not a replacement for `BOARD.md`; board statuses have not been silently promoted. There are **80 unfinished board items**: 57 IN_REVIEW (18 product-level F features + 39 S stories), 16 BACKLOG, 6 BLOCKED and 1 IN_PROGRESS. There are 70 DONE, 0 READY, 0 DEFERRED. A focused test PASS does **not** mean a feature is DONE: end-to-end, live PostgreSQL, privacy, migration recovery, dependencies and owner acceptance may still be open.

Test outcomes below are from completed Render QA-only run `dep-db8944m89jmc73cmoan0` on `develop` (`311f1ab`): **85 passed, 1 failed, 14 skipped, 2 warnings**, and earlier `dep-db892nij9qps73c46gvg` (`fc3f3d9`): **83 passed, 3 failed, 14 skipped**. Final F-06.19 retest `dep-db89530u01pc73f01t7g` on `e671607` **completed 86 passed, 14 skipped, 2 warnings**; no focused Python failure. The Docker build still **failed** at `npm audit --audit-level=high` with 5 development advisories (3 moderate, 2 high). Frontend separate run: 212 passed. Full Python broader run: 2,678 passed, 72 failed, 46 skipped (context-dependent verifier/CI failures included); see `docs/evidence/2026-10-15-all-in-review-audit.md`.

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
| 27 | S-06.02.43 | Logout revokes the copied browser session | `docs/work-orders/S-06.02.43-logout-revocation.md` | NOT INDIVIDUALLY VERIFIED (no mapped test outcome) | Full DoD: live user flow, applicable security/PG/browser/recovery/dependency tests |
| 28 | S-12.02.05 | The brain drafts against the expert corpus and the owner's winners | `docs/work-orders/S-12.02.05-plans-with-expert-references.md` | NOT INDIVIDUALLY VERIFIED (no mapped test outcome) | Full DoD: live user flow, applicable security/PG/browser/recovery/dependency tests |
| 29 | S-06.02.16 | Resolve frontend development dependency audit findings | `docs/work-orders/S-06.02.16-frontend-dependency-audit.md` | NOT INDIVIDUALLY VERIFIED (no mapped test outcome) | Full DoD: live user flow, applicable security/PG/browser/recovery/dependency tests |
| 30 | S-12.01.03 | The video director uses the product | `docs/work-orders/S-12.01.03-video-director-uses-the-product.md` | NOT INDIVIDUALLY VERIFIED (no mapped test outcome) | Full DoD: live user flow, applicable security/PG/browser/recovery/dependency tests |
| 31 | S-06.02.34 | Connectors show how much is left | `docs/work-orders/S-06.02.34-usage-remaining.md` | NOT INDIVIDUALLY VERIFIED (no mapped test outcome) | Full DoD: live user flow, applicable security/PG/browser/recovery/dependency tests |
| 32 | S-06.02.28 | A command-line tool locks the workspace it actually opens | `docs/work-orders/S-06.02.28-path-aware-workspace-lock.md` | NOT INDIVIDUALLY VERIFIED (no mapped test outcome) | Full DoD: live user flow, applicable security/PG/browser/recovery/dependency tests |
| 33 | S-06.02.36 | A second owner login is made on purpose | `docs/work-orders/S-06.02.36-explicit-owner-login.md` | NOT INDIVIDUALLY VERIFIED (no mapped test outcome) | Full DoD: live user flow, applicable security/PG/browser/recovery/dependency tests |
| 34 | S-05.01.04 | Public-page fetches connect only to checked destinations | `docs/work-orders/S-05.01.04-verified-destinations.md` | NOT INDIVIDUALLY VERIFIED (no mapped test outcome) | Full DoD: live user flow, applicable security/PG/browser/recovery/dependency tests |
| 35 | S-03.01.03 | Browser blocks internal network access | `docs/work-orders/S-03.01.03-network-isolation.md` | NOT INDIVIDUALLY VERIFIED (no mapped test outcome) | Full DoD: live user flow, applicable security/PG/browser/recovery/dependency tests |
| 36 | S-06.02.37 | Skip navigation keeps the current screen | `docs/work-orders/S-06.02.37-skip-keeps-current-page.md` | NOT INDIVIDUALLY VERIFIED (no mapped test outcome) | Full DoD: live user flow, applicable security/PG/browser/recovery/dependency tests |
| 37 | S-06.02.20 | The verifier tells a shallow clone apart from a missing commit | `docs/work-orders/S-06.02.20-shallow-git-history.md` | NOT INDIVIDUALLY VERIFIED (no mapped test outcome) | Full DoD: live user flow, applicable security/PG/browser/recovery/dependency tests |
| 38 | S-06.02.39 | Valid low-bitrate WebM exports pass verification | `docs/work-orders/S-06.02.39-low-bitrate-export.md` | NOT INDIVIDUALLY VERIFIED (no mapped test outcome) | Full DoD: live user flow, applicable security/PG/browser/recovery/dependency tests |
| 39 | S-12.02.06 | A plan's posting channel runs from the screens | `docs/work-orders/S-12.02.06-posting-channel-from-the-screens.md` | NOT INDIVIDUALLY VERIFIED (no mapped test outcome) | Full DoD: live user flow, applicable security/PG/browser/recovery/dependency tests |
| 40 | S-06.02.38 | Any error can be traced back the next day | `docs/work-orders/S-06.02.38-traceable-errors.md` | NOT INDIVIDUALLY VERIFIED (no mapped test outcome) | Full DoD: live user flow, applicable security/PG/browser/recovery/dependency tests |
| 41 | S-06.02.25 | Every screen opens at its top, its warnings in view | `docs/work-orders/S-06.02.25-screen-opens-at-top.md` | NOT INDIVIDUALLY VERIFIED (no mapped test outcome) | Full DoD: live user flow, applicable security/PG/browser/recovery/dependency tests |
| 42 | S-06.02.21 | Durable customer state and safe recovery (audit WP1) | `docs/work-orders/S-06.02.21-S-06.02.22-close-out.md` | NOT INDIVIDUALLY VERIFIED (no mapped test outcome) | Full DoD: live user flow, applicable security/PG/browser/recovery/dependency tests |
| 43 | S-06.02.22 | A created or selected campaign stays the active workspace | `docs/work-orders/S-06.02.21-S-06.02.22-close-out.md` | NOT INDIVIDUALLY VERIFIED (no mapped test outcome) | Full DoD: live user flow, applicable security/PG/browser/recovery/dependency tests |
| 44 | S-07.01.03 | Meeting transcription with no bot in the call | `See BOARD.md work order` | NOT INDIVIDUALLY VERIFIED (no mapped test outcome) | Full DoD: live user flow, applicable security/PG/browser/recovery/dependency tests |
| 45 | S-06.02.05 | The UI is usable by keyboard and screen reader | `See BOARD.md work order` | NOT INDIVIDUALLY VERIFIED (no mapped test outcome) | Full DoD: live user flow, applicable security/PG/browser/recovery/dependency tests |
| 46 | S-06.02.02 | Every endpoint authorises and validates | `See BOARD.md work order` | NOT INDIVIDUALLY VERIFIED (no mapped test outcome) | Full DoD: live user flow, applicable security/PG/browser/recovery/dependency tests |
| 47 | S-06.02.01 | No secret may enter a model prompt | `See BOARD.md work order` | NOT INDIVIDUALLY VERIFIED (no mapped test outcome) | Full DoD: live user flow, applicable security/PG/browser/recovery/dependency tests |
| 48 | S-06.01.04 | Routines that fire agent runs on a schedule or an event | `See BOARD.md work order` | NOT INDIVIDUALLY VERIFIED (no mapped test outcome) | Full DoD: live user flow, applicable security/PG/browser/recovery/dependency tests |
| 49 | S-06.01.01 | Workspaces with their own keys and their own logins | `See BOARD.md work order` | NOT INDIVIDUALLY VERIFIED (no mapped test outcome) | Full DoD: live user flow, applicable security/PG/browser/recovery/dependency tests |
| 50 | S-04.01.01 | Companions: persisted agent profiles | `See BOARD.md work order` | NOT INDIVIDUALLY VERIFIED (no mapped test outcome) | Full DoD: live user flow, applicable security/PG/browser/recovery/dependency tests |
| 51 | S-02.02.02 | PLAN.md as the single source of truth | `See BOARD.md work order` | NOT INDIVIDUALLY VERIFIED (no mapped test outcome) | Full DoD: live user flow, applicable security/PG/browser/recovery/dependency tests |
| 52 | S-03.02.05 | A platform is a row, not a code change | `See BOARD.md work order` | NOT INDIVIDUALLY VERIFIED (no mapped test outcome) | Full DoD: live user flow, applicable security/PG/browser/recovery/dependency tests |
| 53 | S-06.02.04 | Data deletion and subject access | `See BOARD.md work order` | NOT INDIVIDUALLY VERIFIED (no mapped test outcome) | Full DoD: live user flow, applicable security/PG/browser/recovery/dependency tests |
| 54 | S-05.01.03 | Take a competitor post apart and rebuild the shape | `See BOARD.md work order` | NOT INDIVIDUALLY VERIFIED (no mapped test outcome) | Full DoD: live user flow, applicable security/PG/browser/recovery/dependency tests |
| 55 | S-05.01.02 | Extraction packs as declared data | `See BOARD.md work order` | NOT INDIVIDUALLY VERIFIED (no mapped test outcome) | Full DoD: live user flow, applicable security/PG/browser/recovery/dependency tests |
| 56 | S-05.01.01 | A crawler with a frontier, not a loop | `See BOARD.md work order` | NOT INDIVIDUALLY VERIFIED (no mapped test outcome) | Full DoD: live user flow, applicable security/PG/browser/recovery/dependency tests |
| 57 | S-07.01.04 | Reports and artifacts | `See BOARD.md work order` | NOT INDIVIDUALLY VERIFIED (no mapped test outcome) | Full DoD: live user flow, applicable security/PG/browser/recovery/dependency tests |

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
