# 2026-11-21 — D-477/D-478 four-feature continuation

Source branch: develop. This file records exact code/test commits without claiming unobserved success.

| ID | Feature | First failing regression commit | Fix commit | Named test/QA |
|---|---|---|---|---|
| D-477 | F-04.01 / F-06.01 | 03d5ae62b90a1ecb86c356a4452f1c97bd3d098e | a14c8d9d952078f9897c826891921087f9a0d143 | tests/test_agent_companions.py::test_companion_registry_rejects_workspace_ids_auth_cannot_issue |
| D-478 | F-06.03 | dc22f87db43981274a28ee90124367664bbe4767 | d11eba50e495b2b55608c161e00822ab49d62776 | tests/test_hosted_backup.py::test_real_postgres_snapshot_survives_object_copy_and_restores_equal_counts |
| A05/A29 | F-06.02 / F-04.01 | existing browser script | a23209ae2fc2973e3e0db97a57dbd599e47628bc (QA gate) | uv run --no-sync python scripts/live/review_agent_team_browser.py |

Required exact-source release gates: uv run pytest -q; uv run python scripts/verify_board.py; uv run ruff check --select E9,F63,F7,F82 .; npm test; npm run build; real disposable PostgreSQL full suite; Render Dockerfile.review Chromium and PostgreSQL full build; separate owner-confirmed live provider/browser/manual QA; independent security assessment.

A successful review image only serves a QA marker. No real customer app deployment or irreversible workspace data migration is authorised.

D-477 is not a CRM tenancy cutover; D-478 is not proof of S3 backup availability. Keep original board statuses until each Definition of Done criterion passes, including external requirements.
