# Recall ownership boundaries — 2026-11-07

Scope: F-06.02 security audit and S-06.01.06 prerequisite; not whole-feature isolation.

Actual RED3 in `work/three-features/recall-ownership-red.log` reproduced signed foreign message deletion, unscoped reply/contact mutation and same-ID replacement of another workspace's canonical/FTS text. Writer-fenced ownership checks now refuse collisions, search checks canonical owner, and deletion/reply mutations require workspace. Privacy passes its subject workspace. SQLite BEGIN IMMEDIATE makes canonical/FTS updates atomic, including failure rollback and two distinct concurrent registry instances.

Independent review found operation workspace still lost through the shared engine's archive/counter helpers. Parameterized actual local-outbox send/reply regression reproduced beta RED1/local PASS (`recall-engine-scope-red.log`), then both PASS after passing operation workspace without mutating engine.workspace_id. Template counts and reply flags stay in beta; no real mail sent.

Actual HTTP rebuild attempted reading the unowned shared source (`recall-rebuild-red.log`). Q-27 prohibits implicitly assigning it to local or the caller. HTTP409 now refuses before enumeration and gives ownership-migration guidance plus one matching safe log reference. Existing saved recall search remains available. Offline library rebuild requires a trusted already-scoped source. Re-enable HTTP only after native identity/workspace/install/generation and ready registry mapping agree. This is an explicit release gate, not completed tenancy.

Commands:

```bash
uv run pytest tests/test_recall_workspace_mutations.py tests/test_ai_recall.py tests/test_privacy.py tests/test_email_delivery.py tests/test_ai_context.py -q
OFF_CRM_TEST_CRM_ON_POSTGRES=1 OFF_CRM_TEST_POSTGRES_URL=<disposable-test-url> uv run pytest tests/test_recall_workspace_mutations.py tests/test_ai_recall.py tests/test_privacy.py tests/test_email_delivery.py tests/test_ai_context.py -q
```

Both affected bundles96 PASS. PostgreSQL maps actual CRM callers; recall remains SQLite, so this is not hosted-recall durability evidence. Eight new adversarial tests cover collision, scoped mutation/counts, actual signed requests, write rollback, damaged FTS ownership, two writers, privacy and rebuild refusal/logs. Independent reviewer37 recall/API PASS and a separate actual beta local-outbox check. Whole new-revision CI pending. No schema/file-format migration. Reverting would restore known security defects; prefer a forward fix. No customer data, paid/provider action, deployment or board DONE change.
