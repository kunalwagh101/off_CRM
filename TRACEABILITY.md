# Traceability

Snapshot of the combined integration branch, 9 September 2026. `BOARD.md` owns
status and runnable evidence. Input-branch results do not certify the combined
application; its verification is recorded in `docs/integration/MAIN_CONSOLIDATION.md`.

## Backlog

| Requirement | Story | Criteria | Evidence / scope | Code |
|---|---|---|---|---|
| R-79 | S-11.01.04 | 3 | A run has a money ceiling, not only a step ceiling | — |
| R-84 | S-11.03.01 | 3 | A wall the agent must not climb pauses the run and asks | — |
| R-86 | S-11.04.01 | 2 | A run report a person can audit | — |
| R-87 | S-11.04.02 | 1 | Progress is visible while it happens | — |
| R-89 | S-11.05.02 | 1 | Re-running does not duplicate what it already did | — |
| R-19 | S-02.02.03 | 1 | Interrupt, steer, resume | — |
| R-20 | S-02.02.04 | 1 | Safety countdowns before consequential actions | — |
| R-31, R-35 | S-04.01.01 | 1 | Companions: persisted agent profiles | — |
| R-32 | S-04.01.02 | 1 | Skills: procedures fetched on demand | — |
| R-33 | S-04.01.03 | 2 | Sub-agents for context isolation | — |
| R-34, R-35 | S-04.01.04 | 2 | The five roles, wired to what already exists | — |
| R-36, R-37, R-40 | S-05.01.01 | 3 | A crawler with a frontier, not a loop | — |
| R-38 | S-05.01.02 | 1 | Extraction packs as declared data | — |
| R-39 | S-05.01.03 | 2 | Take a competitor post apart and rebuild the shape | — |
| R-41, R-42 | S-06.01.01 | 1 | Workspaces with their own keys and their own logins | — |
| R-43 | S-06.01.02 | 2 | Three-level permissions | — |
| R-44 | S-06.01.03 | 2 | Cost estimated before a run and ledgered after | — |
| R-45, R-46 | S-06.01.04 | 2 | Routines that fire agent runs on a schedule or an event | — |
| R-47 | S-06.01.05 | 2 | Deployment, monitoring and rollback | — |
| R-29 | S-06.02.01 | 1 | No secret may enter a model prompt | — |
| R-48 | S-06.02.02 | 2 | Every endpoint authorises and validates | — |
| R-49 | S-06.02.03 | 1 | Cost and latency budgets per run | — |
| R-50 | S-06.02.04 | 1 | Data deletion and subject access | — |
| R-51 | S-06.02.05 | 1 | The UI is usable by keyboard and screen reader | — |
| R-53 | S-07.01.01 | 2 | An MCP client | — |
| R-54 | S-07.01.02 | 1 | Native OAuth integrations | — |
| R-55 | S-07.01.03 | 1 | Meeting transcription with no bot in the call | — |
| R-56 | S-07.01.04 | 1 | Reports and artifacts | — |

## Ready

| Requirement | Story | Criteria | Evidence / scope | Code |
|---|---|---|---|---|
| R-75 | S-03.02.05 | 2 | A platform is a row, not a code change | — |
| R-77 | S-11.01.02 | 3 | A run that stops making progress is stopped | — |
| R-78 | S-11.01.03 | 2 | A run survives the process dying | — |
| R-85 | S-11.03.02 | 2 | A page that tries to give orders is reported, not obeyed | — |
| R-88 | S-11.05.01 | 3 | Concurrent runs share one browser safely | — |
| R-90 | S-06.02.08 | 2 | One runner for every evidence command | — |

## In Progress

| Requirement | Story | Criteria | Evidence / scope | Code |
|---|---|---|---|---|

## In Review

| Requirement | Story | Criteria | Evidence / scope | Code |
|---|---|---|---|---|
| R-18 | S-02.02.02 | 2 | tests/test_agent_plan.py, tests/test_agent_consolidation.py | offsetx_apollo_builder/agent/plan.py, offsetx_apollo_builder/agent/run.py |
| R-63, R-71 | S-08.01.05 | 3 | tests/test_email_delivery.py::test_email_delivery_api_and_public_one_click_unsubscribe, tests/test_email_delivery.py::test_live_ses_queue_requires_exact_operator_confirmation, frontend/src/components.test.tsx | offsetx_apollo_builder/api/email_delivery.py, frontend/src/pages/Deliverability.tsx |

## Blocked

| Requirement | Story | Criteria | Evidence / scope | Code |
|---|---|---|---|---|
| R-58 | S-01.05.01 | 3 | external — a Google Cloud project with YouTube Data API v3 enabled, and OAuth consent for the channel. Only the owner can create it. | — |
| R-59 | S-01.05.02 | 2 | external — Meta app review, TikTok content-posting audit, LinkedIn partner programme. Weeks of calendar time, and none of it is engineering. | — |
| R-60 | S-01.05.03 | 2 | external — depends on S-01.05.01, which is itself waiting on the Google Cloud project. | — |

## Done

| Requirement | Story | Criteria | Evidence / scope | Code |
|---|---|---|---|---|
| R-76 | S-11.01.01 | 3 | tests/test_agent_recovery.py::test_the_same_failing_action_reaches_the_browser_only_once, tests/test_agent_recovery.py::test_three_failures_in_a_row_stop_the_run, tests/test_agent_recovery.py::test_a_timeout_is_retried_with_backoff_and_recorded_as_a_retry, tests/test_agent_recovery.py::test_a_success_clears_the_failure_streak | offsetx_apollo_builder/agent/run.py |
| R-95 | S-06.02.11 | 8 | tests/test_audit_wp1.py, tests/test_wp1_recovery_edges.py, tests/test_workspace_lock.py, verification/test_wp1_live.py | offsetx_apollo_builder/outreach/backup.py, offsetx_apollo_builder/outreach/sqlite_ownership.py, offsetx_apollo_builder/outreach/workspace_lock.py, offsetx_apollo_builder/api/production_runtime.py, offsetx_apollo_builder/api/config.py, frontend/src/pages/Settings.tsx, render.yaml |
| R-83 | S-11.02.04 | 3 | tests/test_agent_page_memo.py::test_reading_the_same_page_twice_asks_the_page_once, tests/test_agent_page_memo.py::test_acting_on_a_page_forgets_it, tests/test_agent_page_memo.py::test_a_parameter_that_changes_the_page_is_never_stripped, tests/test_agent_page_memo.py::test_a_real_page_is_read_once_through_the_real_loop | offsetx_apollo_builder/agent/run.py |
| R-82 | S-11.02.03 | 3 | tests/test_agent_claim_verification.py::test_number_inside_a_larger_number_is_refused_even_at_high_confidence, tests/test_agent_claim_verification.py::test_derived_finding_is_allowed_only_from_individually_verified_inputs, tests/test_agent_claim_verification.py::test_missing_support_in_a_truncated_capture_is_reported_as_inconclusive, tests/test_agent_claim_verification.py::test_real_chromium_page_refuses_a_plausible_but_unsupported_number | offsetx_apollo_builder/agent/verify.py, offsetx_apollo_builder/agent/result.py, offsetx_apollo_builder/agent/run.py |
| R-81 | S-11.02.02 | 2 | tests/test_agent_provenance.py::test_returned_finding_resolves_url_time_step_and_screenshot_from_trace, tests/test_agent_provenance.py::test_an_unresolvable_source_is_refused_instead_of_returned, tests/test_agent_provenance.py::test_a_sourced_fact_survives_navigation_without_relying_on_model_memory, tests/test_agent_provenance.py::test_provenance_is_bound_to_real_chromium_evidence | offsetx_apollo_builder/agent/result.py, offsetx_apollo_builder/agent/run.py, offsetx_apollo_builder/browser/trace.py |
| R-80 | S-11.02.01 | 3 | tests/test_agent_structured_result.py::test_declared_schema_returns_a_valid_record_not_prose, tests/test_agent_structured_result.py::test_missing_required_field_makes_the_run_incomplete_and_names_it, tests/test_agent_structured_result.py::test_model_field_outside_schema_is_dropped_and_the_drop_is_recorded, tests/test_agent_structured_result.py::test_no_schema_keeps_the_existing_free_text_result_contract, tests/test_agent_structured_result.py::test_structured_result_flows_through_the_real_browser_loop | offsetx_apollo_builder/agent/result.py, offsetx_apollo_builder/agent/run.py |
| R-17 | S-02.02.01 | 2 | tests/test_agent_run.py::test_goal_stops_at_step_budget_and_reports_progress, tests/test_agent_run.py::test_every_decision_uses_broker_and_trace_records_provider_model_and_cost | offsetx_apollo_builder/agent/run.py, offsetx_apollo_builder/browser/trace.py |
| R-30 | S-03.02.03 | 1 | tests/test_browser_revoke.py::test_disconnect_destroys_vault_clears_browser_forgets_record_and_traces, tests/test_browser_revoke.py::test_browser_failure_retains_encrypted_vault_and_connected_record_for_retry, tests/test_browser_revoke.py::test_real_browser_session_cookie_is_gone_after_disconnect | offsetx_apollo_builder/browser/revoke.py, offsetx_apollo_builder/browser/vault.py, offsetx_apollo_builder/browser/identity.py, offsetx_apollo_builder/browser/trace.py |
| R-27, R-28, R-29 | S-03.02.02 | 3 | tests/test_browser_vault.py::test_cookie_token_and_password_fields_are_blocked_even_at_full_policy, tests/test_browser_vault.py::test_two_platforms_use_different_account_keys_and_plaintext_is_absent, tests/test_browser_vault.py::test_passphrase_derives_master_key_and_no_raw_key_file_is_written, tests/test_browser_vault_wiring.py::test_connected_state_is_vaulted_before_it_is_recorded, tests/test_browser_vault_wiring.py::test_vault_failure_refuses_the_connection_and_writes_no_green_state | offsetx_apollo_builder/browser/vault.py, offsetx_apollo_builder/browser/signin.py, offsetx_apollo_builder/ai/scanner.py |
| R-01 | S-01.01.01 | 2 | tests/test_video_timeline.py | offsetx_apollo_builder/video/timeline.py |
| R-02 | S-01.01.02 | 1 | tests/test_video_mixdown.py | tests/fixtures/timeline_conformance.json |
| R-03, R-04 | S-01.02.01 | 2 | tests/test_video_engine.py | offsetx_apollo_builder/video/mixdown.py |
| R-05 | S-01.02.02 | 1 | tests/test_video_retime.py | offsetx_apollo_builder/video/presets.py |
| R-06 | S-01.02.03 | 2 | tests/test_video_effects.py | offsetx_apollo_builder/video/effects.py |
| R-07 | S-01.03.01 | 2 | tests/test_video_assembly.py | offsetx_apollo_builder/video/assembly.py |
| R-08 | S-01.03.02 | 2 | tests/test_video_director.py | offsetx_apollo_builder/video/director.py |
| R-09 | S-01.04.01 | 3 | tests/test_video_review.py | offsetx_apollo_builder/video/engine.py |
| R-10, R-11 | S-01.04.02 | 3 | tests/test_pacing_cap.py | offsetx_apollo_builder/distribution/pacing.py |
| R-12 | S-02.01.01 | 2 | tests/test_browser_agent.py::test_a_command_the_browser_does_not_know_raises_rather_than_hangs | offsetx_apollo_builder/browser/cdp.py |
| R-13 | S-02.01.02 | 2 | tests/test_browser_agent.py::test_a_snapshot_reads_in_document_order_and_not_cdps_order | offsetx_apollo_builder/browser/perceive.py |
| R-14 | S-02.01.03 | 2 | tests/test_browser_agent.py::test_the_vocabulary_is_ten_verbs_and_none_of_them_runs_code | offsetx_apollo_builder/browser/page.py |
| R-15, R-40 | S-02.01.04 | 2 | tests/test_browser_agent.py::test_the_machine_itself_is_never_reachable | offsetx_apollo_builder/browser/policy.py |
| R-16 | S-02.01.05 | 2 | tests/test_browser_agent.py::test_a_trace_is_append_only_with_no_way_to_remove_a_step | offsetx_apollo_builder/browser/trace.py |
| R-21, R-22, R-23 | S-03.01.01 | 2 | tests/test_browser_box.py::test_the_only_mount_is_a_docker_volume_and_not_a_path_on_your_disk, tests/test_browser_box.py::test_a_real_browser_cannot_reach_an_off_list_domain | offsetx_apollo_builder/browser/box.py, offsetx_apollo_builder/browser/guard.py |
| R-72, R-73, R-74 | S-03.02.04 | 3 | tests/test_browser_budget.py::test_spending_one_account_does_not_spend_the_other, tests/test_browser_budget.py::test_real_browser_stops_when_the_account_is_spent, tests/test_browser_budget.py::test_looking_costs_nothing_and_acting_costs_one, tests/test_browser_budget.py::test_a_record_written_before_accounts_existed_still_reads | offsetx_apollo_builder/browser/budget.py, offsetx_apollo_builder/browser/identity.py, offsetx_apollo_builder/browser/page.py, offsetx_apollo_builder/browser/signin.py |
| R-91 | S-06.02.09 | 3 | tests/test_security_audit.py::test_a_bare_write_is_not_rolled_back_by_someone_else_s_failure, tests/test_security_audit.py::test_a_bare_write_is_not_committed_early_by_someone_else, tests/test_security_audit.py::test_no_shared_connection_escapes_the_guard, tests/test_security_audit.py::test_the_guard_still_behaves_like_a_connection | offsetx_apollo_builder/outreach/store.py, offsetx_apollo_builder/outreach/sqlite_ownership.py |
| R-92, R-93, R-94 | S-06.02.10 | 3 | tests/test_security_audit.py::test_a_local_install_will_not_start_without_authentication, tests/test_security_audit.py::test_loopback_requires_the_token_like_everywhere_else, tests/test_security_audit.py::test_a_host_this_server_does_not_answer_to_is_refused, tests/test_security_audit.py::test_a_provisioned_token_is_strong_stable_and_private | offsetx_apollo_builder/api/config.py, offsetx_apollo_builder/api/app.py, offsetx_apollo_builder/web_cli.py |
| R-25, R-26, R-42 | S-03.02.01 | 2 | tests/test_browser_signin.py::test_the_whole_flow_and_the_password_is_nowhere_afterwards, tests/test_browser_signin.py::test_a_session_survives_the_browser_being_restarted, tests/test_browser_signin.py::test_no_function_in_the_sign_in_path_accepts_a_credential, tests/test_browser_agent.py::test_a_lock_left_behind_by_a_browser_that_died_is_not_a_lock, tests/test_browser_agent.py::test_a_handle_from_before_the_page_changed_is_refused | offsetx_apollo_builder/browser/identity.py, offsetx_apollo_builder/browser/signin.py, offsetx_apollo_builder/browser/session.py, offsetx_apollo_builder/browser/page.py |
| R-21, R-24 | S-03.01.02 | 1 | tests/test_browser_box.py::test_the_box_asks_for_the_network_and_the_code_box_still_cannot_have_it, tests/test_browser_box.py::test_host_networking_cannot_be_asked_for_at_all | offsetx_apollo_builder/ai/sandbox.py |
| R-57 | S-06.02.07 | 2 | tests/test_verify_board.py::test_an_answered_question_stops_blocking_ready | scripts/verify_board.py |
| R-52 | S-06.02.06 | 2 | tests/test_verify_board.py | scripts/verify_board.py |
| R-61, R-62 | S-08.01.01 | 3 | tests/test_email_delivery.py::test_permission_marketing_fails_closed_and_suppression_is_global, tests/test_email_delivery.py::test_direct_sender_checks_global_suppression_before_provider_call, tests/test_email_delivery.py::test_transactional_lane_requires_relationship_basis_not_marketing_consent | offsetx_apollo_builder/outreach/deliverability/preflight.py, offsetx_apollo_builder/outreach/deliverability/store.py |
| R-64, R-65, R-66 | S-08.01.02 | 3 | tests/test_email_delivery.py::test_durable_local_job_is_snapshotted_claimed_once_and_recorded, tests/test_email_delivery.py::test_ambiguous_delivery_is_quarantined_and_never_retried, tests/test_email_delivery.py::test_stale_claim_without_a_recorded_message_becomes_delivery_unknown, tests/test_email_delivery.py::test_job_cancellation_is_terminal_and_only_allowed_before_claim, tests/test_email_delivery.py::test_reply_cancels_an_already_queued_email_before_delivery, tests/test_email_delivery.py::test_worker_defers_outside_send_window_without_spending_a_provider_attempt | offsetx_apollo_builder/outreach/deliverability/service.py, offsetx_apollo_builder/outreach/deliverability/store.py |
| R-67, R-68 | S-08.01.03 | 3 | tests/test_email_delivery.py::test_domain_auth_uses_dns_and_ses_identity_evidence, tests/test_email_delivery.py::test_ses_provider_builds_raw_mime_with_one_click_headers | offsetx_apollo_builder/outreach/deliverability/domain_auth.py, offsetx_apollo_builder/outreach/deliverability/ses.py |
| R-69, R-70 | S-08.01.04 | 3 | tests/test_email_delivery.py::test_ses_feedback_is_idempotent_suppresses_and_auto_pauses, tests/test_email_delivery.py::test_sns_envelope_signature_is_verified_before_parsing, tests/test_email_delivery.py::test_public_feedback_paths_bypass_login_but_still_verify_their_tokens | offsetx_apollo_builder/outreach/deliverability/events.py, offsetx_apollo_builder/outreach/deliverability/service.py |

## Deferred

| Requirement | Story | Criteria | Evidence / scope | Code |
|---|---|---|---|---|
