# S-06.03.06 — Legacy timer cutover QA evidence

Recorded 2026-11-02 (IST). Branch \`develop\`; source of truth: live GitHub + actual isolated Render review logs.

## TDD run
- RED \`095c1a624d717ec5f8437b12afd0a2ebe9a4ff45\` on Render \`dep-dbjrc2h42hec73ds2qr0\`: early \`uv run pytest -q tests/test_timer_migration.py\` failed **during collection**, because \`db/timer_import.py\` did not exist. No test cases executed. This is not a fabricated 9-test RED result.
- Implementation \`3e9b87cf363fbd9dcbffdca4700391f83231bf9b\` on Render \`dep-dbjrd3p42hec73ds5j40\`: **9 migration tests passed**, **6 hosted timer persistence tests passed**, **7 readiness tests passed**, plus the early authentication/security and agent permission gates. Other full-suite results must be recorded separately when verified.
- Additional security patch \`fe93aad867f83fab86ee0ff76e070657a18a23fd\` changes migration to an exclusive workspace lease and adds 3 regressions. Render full source verification pending at this checkpoint; earlier 3e9b87c green is not evidence for fe93aad.

## What is checked
Manual import or skip with protected archive; no silent overwrites; defaults disable unsupervised email/content/Gmail permission; malformed JSON rejection; symbolic link and path traversal refusal; rollback of a partial database write; repeatability after interruption; and an actual CLI entrypoint (last three tested only after fe93aad is reviewed).

## Remaining limits
This tool does not automatically migrate customer data. A chosen archive path must actually be durable, and operators must stop all application and worker instances. No customer database or third-party service was accessed. Full independent security/penetration, external encrypted backup/restore, workflow-level multi-install controls, and media/outbox durability remain open. A successful timer import alone does not certify the hosted application.
