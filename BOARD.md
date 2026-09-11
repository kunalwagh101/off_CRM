# Board

**The single source of truth for what is happening.** Chat is not state — if it
is not in this file, it did not happen.

`scripts/verify_board.py` parses this file. One fixed-format line per item:

```
- <ID> · <title>
```

`DONE` items carry an indented evidence block. `BLOCKED` items carry an
indented `blocked: <Q-nn or a named external dependency>`.

**WIP limit: `IN_PROGRESS` ≤ 2.** Nothing is pulled while an item sits in
`IN_PROGRESS` or `BLOCKED`.

---

## BACKLOG

*(E-11, waiting on an upstream story rather than on a decision. Each names it.)*

- S-11.01.04 · A run has a money ceiling, not only a step ceiling
- S-11.03.03 · Enter is gated like the button beside it

- S-02.02.03 · Interrupt, steer, resume
- S-04.01.02 · Skills: procedures fetched on demand
- S-04.01.03 · Sub-agents for context isolation
- S-04.01.04 · The five roles, wired to what already exists
- S-05.01.02 · Extraction packs as declared data
- S-05.01.03 · Take a competitor post apart and rebuild the shape
- S-06.01.02 · Three-level permissions
- S-06.01.05 · Deployment, monitoring and rollback
- S-06.02.03 · Cost and latency budgets per run
- S-06.02.04 · Data deletion and subject access
- S-07.01.01 · An MCP client
- S-07.01.02 · Native OAuth integrations

## READY

*(Q-01, Q-02, Q-03 and Q-06 were answered by the owner. The decisions are
recorded in `OPEN_QUESTIONS.md` rather than the questions being deleted, so the
reasoning survives the unblocking.)*

- S-03.02.05 · A platform is a row, not a code change

*(E-11 — the autonomous browsing epic. Only the stories whose upstream
dependencies are already DONE are READY; the rest wait in BACKLOG, because the
Definition of Ready is not a formality and an item whose shape can still change
is an item that gets built twice. S-11.02.01 through S-11.02.03 are DONE; the
remaining independent stories below stay READY.)*

- S-11.05.01 · Concurrent runs share one browser safely
- S-06.02.08 · One runner for every evidence command
- S-06.02.11 · The verifier catches a stale READY column

*(Moved out of BACKLOG on 2026-09-10 after an audit: every dependency these
declare is DONE, and no open question is filed against any of them. They had
been sitting in BACKLOG because nothing moves an item to READY when the story
it waited on finishes — that is a manual step and nobody was doing it.)*

- S-02.02.02 · PLAN.md as the single source of truth
- S-02.02.04 · Safety countdowns before consequential actions
- S-04.01.01 · Companions: persisted agent profiles
- S-05.01.01 · A crawler with a frontier, not a loop
- S-06.01.01 · Workspaces with their own keys and their own logins
- S-06.01.03 · Cost estimated before a run and ledgered after
- S-06.01.04 · Routines that fire agent runs on a schedule or an event
- S-06.02.01 · No secret may enter a model prompt
- S-06.02.02 · Every endpoint authorises and validates
- S-06.02.05 · The UI is usable by keyboard and screen reader
- S-07.01.03 · Meeting transcription with no bot in the call
- S-07.01.04 · Reports and artifacts
- S-11.03.01 · A wall the agent must not climb pauses the run and asks

## IN_PROGRESS

_nothing in flight_

## IN_REVIEW

- S-08.01.05 · Operators control delivery without hidden live sends
  tests: tests/test_email_delivery.py::test_email_delivery_api_and_public_one_click_unsubscribe, tests/test_email_delivery.py::test_live_ses_queue_requires_exact_operator_confirmation, frontend/src/components.test.tsx
  command: python -m pytest tests/test_email_delivery.py::test_email_delivery_api_and_public_one_click_unsubscribe tests/test_email_delivery.py::test_live_ses_queue_requires_exact_operator_confirmation -q && (cd frontend && npm test -- src/components.test.tsx)
  result: pending — Python API controls pass; this clean environment cannot install the uncached frontend dependency needed to re-run the dashboard test (2026-08-27)
  code: offsetx_apollo_builder/api/email_delivery.py, frontend/src/pages/Deliverability.tsx

## BLOCKED

- S-01.05.01 · Publish to YouTube through the official API
  blocked: external — a Google Cloud project with YouTube Data API v3 enabled, and OAuth consent for the channel. Only the owner can create it.
- S-01.05.02 · One adapter contract for the remaining platforms
  blocked: external — Meta app review, TikTok content-posting audit, LinkedIn partner programme. Weeks of calendar time, and none of it is engineering.
- S-01.05.03 · Read real engagement back from the platform
  blocked: external — depends on S-01.05.01, which is itself waiting on the Google Cloud project.

## DONE

- S-11.04.02 · Progress is visible while it happens
  tests: tests/test_agent_watch.py::test_a_watcher_sees_the_run_step_by_step, tests/test_agent_watch.py::test_a_read_answered_from_the_memo_still_reports_its_verb, tests/test_agent_watch.py::test_updates_arrive_during_the_run_not_in_a_batch_at_the_end, tests/test_agent_watch.py::test_an_update_carries_the_action_the_url_and_the_running_cost, tests/test_agent_watch.py::test_the_verb_comes_from_the_signature_not_from_the_prose, tests/test_agent_watch.py::test_a_listener_hears_only_what_is_already_durable, tests/test_agent_watch.py::test_a_watcher_that_throws_does_not_end_the_run, tests/test_agent_watch.py::test_a_run_with_nobody_watching_behaves_exactly_as_before
  command: python -m pytest tests/test_agent_watch.py tests/test_agent_run.py tests/test_agent_resume.py tests/test_agent_no_duplicate_effects.py tests/test_agent_progress.py tests/test_agent_provenance.py tests/test_agent_recovery.py tests/test_agent_report.py tests/test_browser_agent.py -q
  result: 132 passed (2026-09-11)
  live: python scripts/live/watch_a_run.py — real headless Chromium, real page served over HTTP, real trace on disk, a watcher attached through `on_progress`. Exits 0 only if the run completes AND its nine steps arrived spread over more than half a second rather than in a batch at the end; observed spread 1.6s, each line carrying its verb from the recorded signature (`action read`, `action click`), the live page URL, and the running cost climbing $0.0000 -> $0.0071. The refused step printed marked `!` the moment it happened, which is the case this story exists for. That refusal is the loopback rule in `policy.py` doing its job and was left alone — this container's egress proxy will not serve Chromium, so no public page was reachable to click instead.
  code: offsetx_apollo_builder/agent/watch.py, offsetx_apollo_builder/agent/run.py, offsetx_apollo_builder/browser/trace.py
  commit: ae6adcf

- S-11.04.01 · A run report a person can audit
  tests: tests/test_agent_report.py::test_every_returned_fact_appears_with_its_evidence, tests/test_agent_report.py::test_a_run_that_got_stuck_says_so_at_the_top, tests/test_agent_report.py::test_a_hostile_quote_comes_back_inert, tests/test_agent_report.py::test_a_screenshot_filename_that_tries_to_leave_the_directory_is_dropped, tests/test_agent_report.py::test_a_finished_run_writes_its_own_report
  command: python -m pytest tests/test_agent_report.py tests/test_agent_run.py tests/test_agent_injection.py tests/test_agent_resume.py tests/test_agent_structured_result.py -q
  result: 82 passed (2026-09-10)
  code: offsetx_apollo_builder/agent/report.py, offsetx_apollo_builder/agent/run.py
  commit: cd25d9d

- S-11.03.02 · A page that tries to give orders is reported, not obeyed
  tests: tests/test_agent_injection.py::test_an_attack_in_the_page_text_is_flagged_in_the_trace, tests/test_agent_injection.py::test_the_run_carries_on_under_the_owners_goal, tests/test_agent_injection.py::test_ordinary_page_text_is_left_alone, tests/test_agent_injection.py::test_an_attack_split_across_lines_is_still_caught, tests/test_agent_injection.py::test_the_quote_stays_out_of_the_audit_log
  command: python -m pytest tests/test_agent_injection.py tests/test_agent_run.py tests/test_agent_resume.py tests/test_agent_no_duplicate_effects.py tests/test_agent_progress.py -q
  result: 81 passed (2026-09-10)
  code: offsetx_apollo_builder/agent/injection.py, offsetx_apollo_builder/agent/run.py
  commit: 2f5c19e

- S-11.05.02 · Re-running does not duplicate what it already did
  tests: tests/test_agent_no_duplicate_effects.py::test_a_resumed_run_does_not_send_the_message_twice, tests/test_agent_no_duplicate_effects.py::test_pressing_enter_again_after_a_resume_does_not_submit_twice, tests/test_agent_no_duplicate_effects.py::test_navigating_back_to_where_it_was_still_works, tests/test_agent_no_duplicate_effects.py::test_within_one_run_the_guard_does_not_fire
  command: python -m pytest tests/test_agent_no_duplicate_effects.py tests/test_agent_resume.py tests/test_agent_run.py tests/test_agent_provenance.py tests/test_agent_progress.py tests/test_agent_recovery.py -q
  result: 59 passed (2026-09-10)
  code: offsetx_apollo_builder/agent/run.py
  commit: 1e1bd0d

- S-11.01.03 · A run survives the process dying
  tests: tests/test_agent_resume.py::test_a_resumed_run_keeps_the_facts_it_already_gathered, tests/test_agent_resume.py::test_resuming_continues_the_same_trace_and_marks_where, tests/test_agent_resume.py::test_a_finished_run_is_not_resumed, tests/test_agent_resume.py::test_a_fact_whose_artefact_is_gone_is_dropped_not_invented
  command: python -m pytest tests/test_agent_resume.py tests/test_agent_provenance.py tests/test_agent_run.py tests/test_agent_structured_result.py tests/test_agent_progress.py tests/test_agent_recovery.py -q
  result: 56 passed (2026-09-10)
  code: offsetx_apollo_builder/agent/run.py, offsetx_apollo_builder/agent/result.py
  commit: 8e759b9

- S-11.01.02 · A run that stops making progress is stopped
  tests: tests/test_agent_progress.py::test_filling_a_long_form_is_never_called_stalled, tests/test_agent_progress.py::test_a_search_and_browse_pattern_is_never_called_looping, tests/test_agent_progress.py::test_bouncing_between_two_pages_is_looping, tests/test_agent_progress.py::test_clicking_the_same_working_button_forever_is_stalled, tests/test_agent_progress.py::test_a_real_run_going_nowhere_is_stopped
  command: python -m pytest tests/test_agent_progress.py tests/test_agent_recovery.py tests/test_agent_run.py tests/test_agent_page_memo.py tests/test_agent_structured_result.py -q
  result: 51 passed (2026-09-10)
  code: offsetx_apollo_builder/agent/run.py
  commit: 1b3c519

- S-11.01.01 · A failed action is recovered from, not repeated
  tests: tests/test_agent_recovery.py::test_the_same_failing_action_reaches_the_browser_only_once, tests/test_agent_recovery.py::test_three_failures_in_a_row_stop_the_run, tests/test_agent_recovery.py::test_a_timeout_is_retried_with_backoff_and_recorded_as_a_retry, tests/test_agent_recovery.py::test_a_success_clears_the_failure_streak
  command: python -m pytest tests/test_agent_recovery.py tests/test_agent_run.py tests/test_agent_page_memo.py tests/test_agent_structured_result.py -q
  result: 37 passed (2026-09-09)
  code: offsetx_apollo_builder/agent/run.py
  commit: ce3a994

- S-11.02.04 · The same page is never read twice in one run
  tests: tests/test_agent_page_memo.py::test_reading_the_same_page_twice_asks_the_page_once, tests/test_agent_page_memo.py::test_acting_on_a_page_forgets_it, tests/test_agent_page_memo.py::test_a_parameter_that_changes_the_page_is_never_stripped, tests/test_agent_page_memo.py::test_a_real_page_is_read_once_through_the_real_loop
  command: python -m pytest tests/test_agent_page_memo.py tests/test_agent_run.py tests/test_agent_structured_result.py -q
  result: 25 passed (2026-09-09)
  code: offsetx_apollo_builder/agent/run.py
  commit: 4acf68e

- S-11.02.03 · A claim the page does not support is refused
  tests: tests/test_agent_claim_verification.py::test_number_inside_a_larger_number_is_refused_even_at_high_confidence, tests/test_agent_claim_verification.py::test_derived_finding_is_allowed_only_from_individually_verified_inputs, tests/test_agent_claim_verification.py::test_missing_support_in_a_truncated_capture_is_reported_as_inconclusive, tests/test_agent_claim_verification.py::test_real_chromium_page_refuses_a_plausible_but_unsupported_number
  command: uv run pytest tests/test_agent_claim_verification.py -q
  result: 8 passed (2026-09-06)
  code: offsetx_apollo_builder/agent/verify.py, offsetx_apollo_builder/agent/result.py, offsetx_apollo_builder/agent/run.py
  commit: ebd2556add2251e6663e24f6b7f66f0aa1b017f2

- S-11.02.02 · Every fact carries where it came from
  tests: tests/test_agent_provenance.py::test_returned_finding_resolves_url_time_step_and_screenshot_from_trace, tests/test_agent_provenance.py::test_an_unresolvable_source_is_refused_instead_of_returned, tests/test_agent_provenance.py::test_a_sourced_fact_survives_navigation_without_relying_on_model_memory, tests/test_agent_provenance.py::test_provenance_is_bound_to_real_chromium_evidence
  command: uv run pytest tests/test_agent_provenance.py -q
  result: 6 passed (2026-09-06)
  code: offsetx_apollo_builder/agent/result.py, offsetx_apollo_builder/agent/run.py, offsetx_apollo_builder/browser/trace.py
  commit: 1374d7e18a0028a40005192528bd5ed6902fe6e4

- S-11.02.01 · A run declares the shape of its answer and is held to it
  tests: tests/test_agent_structured_result.py::test_declared_schema_returns_a_valid_record_not_prose, tests/test_agent_structured_result.py::test_missing_required_field_makes_the_run_incomplete_and_names_it, tests/test_agent_structured_result.py::test_model_field_outside_schema_is_dropped_and_the_drop_is_recorded, tests/test_agent_structured_result.py::test_no_schema_keeps_the_existing_free_text_result_contract, tests/test_agent_structured_result.py::test_structured_result_flows_through_the_real_browser_loop
  command: uv run pytest tests/test_agent_structured_result.py -q
  result: 7 passed (2026-09-06)
  code: offsetx_apollo_builder/agent/result.py, offsetx_apollo_builder/agent/run.py
  commit: 4ffef3de8cd2f5e681e4d49d39cb6ae154e02dc0

- S-02.02.01 · A goal becomes a bounded sequence of actions
  tests: tests/test_agent_run.py::test_goal_stops_at_step_budget_and_reports_progress, tests/test_agent_run.py::test_every_decision_uses_broker_and_trace_records_provider_model_and_cost
  command: uv run pytest tests/test_agent_run.py -q
  result: 7 passed (2026-09-05)
  code: offsetx_apollo_builder/agent/run.py, offsetx_apollo_builder/browser/trace.py
  commit: 08eb2cd46e24f791a44a4aceca4f1e6272f803b0

- S-03.02.03 · Revoke and forget
  tests: tests/test_browser_revoke.py::test_disconnect_destroys_vault_clears_browser_forgets_record_and_traces, tests/test_browser_revoke.py::test_browser_failure_retains_encrypted_vault_and_connected_record_for_retry, tests/test_browser_revoke.py::test_real_browser_session_cookie_is_gone_after_disconnect
  command: uv run pytest tests/test_browser_revoke.py -q
  result: 6 passed (2026-09-04)
  code: offsetx_apollo_builder/browser/revoke.py, offsetx_apollo_builder/browser/vault.py, offsetx_apollo_builder/browser/identity.py, offsetx_apollo_builder/browser/trace.py
  commit: 5090be48801b2a776d89e5a05da7de3204a559aa

- S-03.02.02 · A vault the model cannot read
  tests: tests/test_browser_vault.py::test_cookie_token_and_password_fields_are_blocked_even_at_full_policy, tests/test_browser_vault.py::test_two_platforms_use_different_account_keys_and_plaintext_is_absent, tests/test_browser_vault.py::test_passphrase_derives_master_key_and_no_raw_key_file_is_written, tests/test_browser_vault_wiring.py::test_connected_state_is_vaulted_before_it_is_recorded, tests/test_browser_vault_wiring.py::test_vault_failure_refuses_the_connection_and_writes_no_green_state
  command: uv run pytest tests/test_browser_vault.py tests/test_browser_vault_wiring.py -q
  result: 15 passed (2026-09-04)
  code: offsetx_apollo_builder/browser/vault.py, offsetx_apollo_builder/browser/signin.py, offsetx_apollo_builder/ai/scanner.py
  commit: 008d4928ae8048d85a804b628d9e76f0ee1c8c77

- S-01.01.01 · A timeline that cannot represent an invalid edit
  tests: tests/test_video_timeline.py
  command: python -m pytest tests/test_video_timeline.py -q
  result: 49 passed (2026-08-25)
  code: offsetx_apollo_builder/video/timeline.py
  commit: d96ea9d

- S-01.01.02 · Two resolvers held to one answer by a fixture
  tests: tests/test_video_mixdown.py
  command: python -m pytest tests/test_video_mixdown.py -q
  result: 29 passed (2026-08-25)
  code: tests/fixtures/timeline_conformance.json
  commit: d96ea9d

- S-01.02.01 · Video, audio and footage in one exported file
  tests: tests/test_video_engine.py
  command: python -m pytest tests/test_video_engine.py -q
  result: 46 passed (2026-08-25)
  code: offsetx_apollo_builder/video/mixdown.py
  commit: d96ea9d

- S-01.02.02 · Time remapping as one integral
  tests: tests/test_video_retime.py
  command: python -m pytest tests/test_video_retime.py -q
  result: 34 passed (2026-08-25)
  code: offsetx_apollo_builder/video/presets.py
  commit: d96ea9d

- S-01.02.03 · 48 pixel primitives and a catalogue of looks
  tests: tests/test_video_effects.py
  command: python -m pytest tests/test_video_effects.py -q
  result: 49 passed (2026-08-25)
  code: offsetx_apollo_builder/video/effects.py
  commit: d96ea9d

- S-01.03.01 · Material in, finished timeline out
  tests: tests/test_video_assembly.py
  command: python -m pytest tests/test_video_assembly.py -q
  result: 94 passed (2026-08-25)
  code: offsetx_apollo_builder/video/assembly.py
  commit: d96ea9d

- S-01.03.02 · A topic in, a finished project out
  tests: tests/test_video_director.py
  command: python -m pytest tests/test_video_director.py -q
  result: 31 passed (2026-08-25)
  code: offsetx_apollo_builder/video/director.py
  commit: d96ea9d

- S-01.04.01 · Push, ignore, edit
  tests: tests/test_video_review.py
  command: python -m pytest tests/test_video_review.py -q
  result: 37 passed (2026-08-25)
  code: offsetx_apollo_builder/video/engine.py
  commit: d96ea9d

- S-01.04.02 · The owner's posting cap, and advice about the rate
  tests: tests/test_pacing_cap.py
  command: python -m pytest tests/test_pacing_cap.py -q
  result: 19 passed (2026-08-25)
  code: offsetx_apollo_builder/distribution/pacing.py
  commit: d96ea9d

- S-02.01.01 · A hand-written DevTools client
  tests: tests/test_browser_agent.py::test_a_command_the_browser_does_not_know_raises_rather_than_hangs
  command: python -m pytest tests/test_browser_agent.py -q
  result: 32 passed (2026-08-25)
  code: offsetx_apollo_builder/browser/cdp.py
  commit: d96ea9d

- S-02.01.02 · The page as an accessibility outline with stable handles
  tests: tests/test_browser_agent.py::test_a_snapshot_reads_in_document_order_and_not_cdps_order
  command: python -m pytest tests/test_browser_agent.py -q
  result: 32 passed (2026-08-25)
  code: offsetx_apollo_builder/browser/perceive.py
  commit: d96ea9d

- S-02.01.03 · Ten verbs, real input, no arbitrary code
  tests: tests/test_browser_agent.py::test_the_vocabulary_is_ten_verbs_and_none_of_them_runs_code
  command: python -m pytest tests/test_browser_agent.py -q
  result: 32 passed (2026-08-25)
  code: offsetx_apollo_builder/browser/page.py
  commit: d96ea9d

- S-02.01.04 · Per-domain policy, enforced in code
  tests: tests/test_browser_agent.py::test_the_machine_itself_is_never_reachable
  command: python -m pytest tests/test_browser_agent.py -q
  result: 32 passed (2026-08-25)
  code: offsetx_apollo_builder/browser/policy.py
  commit: d96ea9d

- S-02.01.05 · An append-only work trace
  tests: tests/test_browser_agent.py::test_a_trace_is_append_only_with_no_way_to_remove_a_step
  command: python -m pytest tests/test_browser_agent.py -q
  result: 32 passed (2026-08-25)
  code: offsetx_apollo_builder/browser/trace.py
  commit: d96ea9d

- S-03.01.01 · A browser box: network yes, host filesystem never
  tests: tests/test_browser_box.py::test_the_only_mount_is_a_docker_volume_and_not_a_path_on_your_disk, tests/test_browser_box.py::test_a_real_browser_cannot_reach_an_off_list_domain
  command: python -m pytest tests/test_browser_box.py -q
  result: 30 passed (2026-08-25)
  code: offsetx_apollo_builder/browser/box.py, offsetx_apollo_builder/browser/guard.py
  commit: 0be650d

- S-03.02.04 · Several accounts per platform, each with its own budget
  tests: tests/test_browser_budget.py::test_spending_one_account_does_not_spend_the_other, tests/test_browser_budget.py::test_real_browser_stops_when_the_account_is_spent, tests/test_browser_budget.py::test_looking_costs_nothing_and_acting_costs_one, tests/test_browser_budget.py::test_a_record_written_before_accounts_existed_still_reads
  command: python -m pytest tests/test_browser_budget.py tests/test_browser_agent.py tests/test_browser_signin.py -q
  result: 81 passed (2026-09-06)
  code: offsetx_apollo_builder/browser/budget.py, offsetx_apollo_builder/browser/identity.py, offsetx_apollo_builder/browser/page.py, offsetx_apollo_builder/browser/signin.py
  commit: fd5ad0b

- S-06.02.09 · Every database write goes through one guard
  tests: tests/test_security_audit.py::test_a_bare_write_is_not_rolled_back_by_someone_else_s_failure, tests/test_security_audit.py::test_a_bare_write_is_not_committed_early_by_someone_else, tests/test_security_audit.py::test_no_shared_connection_escapes_the_guard, tests/test_security_audit.py::test_the_guard_still_behaves_like_a_connection
  command: python -m pytest tests/test_security_audit.py tests/test_outreach_api.py tests/test_sales_tracker.py tests/test_email_delivery.py -q
  result: 53 passed (2026-09-09)
  code: offsetx_apollo_builder/outreach/store.py
  commit: 4acf68e

- S-06.02.10 · The local API is not open to whatever can reach the port
  tests: tests/test_security_audit.py::test_a_local_install_will_not_start_without_authentication, tests/test_security_audit.py::test_loopback_requires_the_token_like_everywhere_else, tests/test_security_audit.py::test_a_host_this_server_does_not_answer_to_is_refused, tests/test_security_audit.py::test_a_provisioned_token_is_strong_stable_and_private
  command: python -m pytest tests/test_security_audit.py tests/test_api_auth.py tests/test_outreach_api.py -q
  result: 33 passed (2026-09-08)
  code: offsetx_apollo_builder/api/config.py, offsetx_apollo_builder/api/app.py, offsetx_apollo_builder/web_cli.py
  commit: e4f91a4

- S-03.02.01 · Sign in to a platform once, inside the box
  tests: tests/test_browser_signin.py::test_the_whole_flow_and_the_password_is_nowhere_afterwards, tests/test_browser_signin.py::test_a_session_survives_the_browser_being_restarted, tests/test_browser_signin.py::test_no_function_in_the_sign_in_path_accepts_a_credential, tests/test_browser_agent.py::test_a_lock_left_behind_by_a_browser_that_died_is_not_a_lock, tests/test_browser_agent.py::test_a_handle_from_before_the_page_changed_is_refused
  command: python -m pytest tests/test_browser_signin.py tests/test_browser_agent.py tests/test_browser_box.py -q
  result: 87 passed (2026-08-28)
  code: offsetx_apollo_builder/browser/identity.py, offsetx_apollo_builder/browser/signin.py, offsetx_apollo_builder/browser/session.py, offsetx_apollo_builder/browser/page.py
  commit: 9bd1ee7

- S-03.01.02 · The existing code box keeps its no-network guarantee
  tests: tests/test_browser_box.py::test_the_box_asks_for_the_network_and_the_code_box_still_cannot_have_it, tests/test_browser_box.py::test_host_networking_cannot_be_asked_for_at_all
  command: python -m pytest tests/test_ai_sandbox.py tests/test_browser_box.py -q
  result: 72 passed, 1 skipped (2026-08-25)
  code: offsetx_apollo_builder/ai/sandbox.py
  commit: 0be650d

- S-06.02.07 · An answered question stops blocking
  tests: tests/test_verify_board.py::test_an_answered_question_stops_blocking_ready
  command: python -m pytest tests/test_verify_board.py -q
  result: 29 passed (2026-08-25)
  code: scripts/verify_board.py
  commit: 8b6876e

- S-06.02.06 · The delivery process is verifiable by the owner
  tests: tests/test_verify_board.py
  command: python -m pytest tests/test_verify_board.py -q
  result: 29 passed (2026-08-25)
  code: scripts/verify_board.py
  commit: d96ea9d

*Retrospective certification, 2026-08-27: the protected email implementation
arrived in `d96ea9d` before it had backlog IDs. The entries below certify the
current code and rerun evidence; they do not claim the earlier build followed
the pull-before-code process.*

- S-08.01.01 · Permission and suppression fail closed
  tests: tests/test_email_delivery.py::test_permission_marketing_fails_closed_and_suppression_is_global, tests/test_email_delivery.py::test_direct_sender_checks_global_suppression_before_provider_call, tests/test_email_delivery.py::test_transactional_lane_requires_relationship_basis_not_marketing_consent
  command: python -m pytest tests/test_email_delivery.py::test_permission_marketing_fails_closed_and_suppression_is_global tests/test_email_delivery.py::test_direct_sender_checks_global_suppression_before_provider_call tests/test_email_delivery.py::test_transactional_lane_requires_relationship_basis_not_marketing_consent -q
  result: 3 passed (2026-08-27)
  code: offsetx_apollo_builder/outreach/deliverability/preflight.py, offsetx_apollo_builder/outreach/deliverability/store.py
  commit: d96ea9d

- S-08.01.02 · Durable jobs survive crashes without duplicate sends
  tests: tests/test_email_delivery.py::test_durable_local_job_is_snapshotted_claimed_once_and_recorded, tests/test_email_delivery.py::test_ambiguous_delivery_is_quarantined_and_never_retried, tests/test_email_delivery.py::test_stale_claim_without_a_recorded_message_becomes_delivery_unknown, tests/test_email_delivery.py::test_job_cancellation_is_terminal_and_only_allowed_before_claim, tests/test_email_delivery.py::test_reply_cancels_an_already_queued_email_before_delivery, tests/test_email_delivery.py::test_worker_defers_outside_send_window_without_spending_a_provider_attempt
  command: python -m pytest tests/test_email_delivery.py::test_durable_local_job_is_snapshotted_claimed_once_and_recorded tests/test_email_delivery.py::test_ambiguous_delivery_is_quarantined_and_never_retried tests/test_email_delivery.py::test_stale_claim_without_a_recorded_message_becomes_delivery_unknown tests/test_email_delivery.py::test_job_cancellation_is_terminal_and_only_allowed_before_claim tests/test_email_delivery.py::test_reply_cancels_an_already_queued_email_before_delivery tests/test_email_delivery.py::test_worker_defers_outside_send_window_without_spending_a_provider_attempt -q
  result: 6 passed (2026-08-27)
  code: offsetx_apollo_builder/outreach/deliverability/service.py, offsetx_apollo_builder/outreach/deliverability/store.py
  commit: d96ea9d

- S-08.01.03 · Authenticated SES lanes carry bulk mail
  tests: tests/test_email_delivery.py::test_domain_auth_uses_dns_and_ses_identity_evidence, tests/test_email_delivery.py::test_ses_provider_builds_raw_mime_with_one_click_headers
  command: python -m pytest tests/test_email_delivery.py::test_domain_auth_uses_dns_and_ses_identity_evidence tests/test_email_delivery.py::test_ses_provider_builds_raw_mime_with_one_click_headers -q
  result: 2 passed (2026-08-27)
  code: offsetx_apollo_builder/outreach/deliverability/domain_auth.py, offsetx_apollo_builder/outreach/deliverability/ses.py
  commit: d96ea9d

- S-08.01.04 · Provider feedback stops unhealthy sending
  tests: tests/test_email_delivery.py::test_ses_feedback_is_idempotent_suppresses_and_auto_pauses, tests/test_email_delivery.py::test_sns_envelope_signature_is_verified_before_parsing, tests/test_email_delivery.py::test_public_feedback_paths_bypass_login_but_still_verify_their_tokens
  command: python -m pytest tests/test_email_delivery.py::test_ses_feedback_is_idempotent_suppresses_and_auto_pauses tests/test_email_delivery.py::test_sns_envelope_signature_is_verified_before_parsing tests/test_email_delivery.py::test_public_feedback_paths_bypass_login_but_still_verify_their_tokens -q
  result: 3 passed (2026-08-27)
  code: offsetx_apollo_builder/outreach/deliverability/events.py, offsetx_apollo_builder/outreach/deliverability/service.py
  commit: d96ea9d

## DEFERRED

*(Nothing is deferred. S-03.01.02's trigger fired when S-03.01.01 was pulled.)*