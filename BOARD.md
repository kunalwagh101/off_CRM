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

- S-02.02.01 · A goal becomes a bounded sequence of actions
- S-02.02.02 · PLAN.md as the single source of truth
- S-02.02.03 · Interrupt, steer, resume
- S-02.02.04 · Safety countdowns before consequential actions
- S-03.02.03 · Revoke and forget
- S-04.01.01 · Companions: persisted agent profiles
- S-04.01.02 · Skills: procedures fetched on demand
- S-04.01.03 · Sub-agents for context isolation
- S-04.01.04 · The five roles, wired to what already exists
- S-05.01.01 · A crawler with a frontier, not a loop
- S-05.01.02 · Extraction packs as declared data
- S-05.01.03 · Take a competitor post apart and rebuild the shape
- S-06.01.01 · Workspaces with their own keys and their own logins
- S-06.01.02 · Three-level permissions
- S-06.01.03 · Cost estimated before a run and ledgered after
- S-06.01.04 · Routines that fire agent runs on a schedule or an event
- S-06.01.05 · Deployment, monitoring and rollback
- S-06.02.01 · No secret may enter a model prompt
- S-06.02.02 · Every endpoint authorises and validates
- S-06.02.03 · Cost and latency budgets per run
- S-06.02.04 · Data deletion and subject access
- S-06.02.05 · The UI is usable by keyboard and screen reader
- S-07.01.01 · An MCP client
- S-07.01.02 · Native OAuth integrations
- S-07.01.03 · Meeting transcription with no bot in the call
- S-07.01.04 · Reports and artifacts

## READY

*(Q-01, Q-02 and Q-03 were answered by the owner on 2026-08-25. The decisions
are recorded in `OPEN_QUESTIONS.md` rather than the questions being deleted, so
the reasoning survives the unblocking.)*

- S-03.02.01 · Sign in to a platform once, inside the box
- S-03.02.02 · A vault the model cannot read

## IN_PROGRESS

*(Empty.)*

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
