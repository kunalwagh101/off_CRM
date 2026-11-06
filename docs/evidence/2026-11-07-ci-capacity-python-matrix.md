# CI capacity and supported Python matrix — 7 November 2026

S-06.02.18 and S-06.02.26. This closes CI capabilities only; the production audit, hosted recovery, customer tenancy and release gates remain open. CI timestamps below are UTC. The report date follows the owner's client calendar.

## Exact executed source and live path

Source: `450165b020225d5409356f63f3f42cee252dab62` on develop.

Actual GitHub-hosted push workflow: https://github.com/kunalwagh101/off_CRM/actions/runs/42250598322 . All five jobs completed SUCCESS; their runner setup, checkout, commands and logs were retrieved through the GitHub connector. No self-hosted runner, visibility change, billing change or customer deployment was performed.

| Job | Actual result | Job ID |
|---|---|---|
| Python3.10 | 3176 passed,54 skipped |128004335497|
| Python3.11 | 3176 passed,54 skipped |128004335376|
| Python3.12 | 3176 passed,54 skipped |128004335602|
| PostgreSQL16 |215 focused passed;3225 full passed,74 skipped|128004335465|
| quality |all70 recorded board commands passed;frontend234 passed/build passed;other configured gates passed|128004335115|

The PostgreSQL job also executed9 namespace tests through direct PostgreSQL and genuine PgBouncer1.22.0 in transaction mode, using one backend and forced session reset. This was actual execution, not a skipped/faked pooler target. Container workflow42250598201 on the same source also completed SUCCESS.

Representative raw log summaries retrieved this session:

```
3176 passed, 54 skipped, 44 warnings in 452.87s (0:07:32)
3176 passed, 54 skipped, 44 warnings in 437.40s (0:07:17)
3176 passed, 54 skipped, 44 warnings in 427.89s (0:07:07)
Disposable PgBouncer 1.22.0 ready: transaction mode, one backend, forced session reset
9 passed in 3.56s
215 passed, 1 warning in 63.56s (0:01:03)
3225 passed, 74 skipped, 44 warnings in 596.27s (0:09:56)
OK — the board matches the repository.
```

## Contract checks and review

`uv run pytest tests/test_supported_pythons.py tests/test_verify_board.py -q` executed locally:64 passed in5.11s. It checks declared/container version coverage, explicit locked interpreter installation, no allowed failures, fail-fast false, no pytest --version false gate, and the existing board/verifier contracts. Static tests complement the live runs; they do not prove runner allocation by themselves.

Independent review found the initial3.10 timeout incompatibility and a folded YAML version-command false proof during delivery; both were repaired with red/green checks before the final source. Final independent DONE-readiness review found no further CI-only technical gate; an independent local version/environment subset reported7 PASS. Current source preserves the full suite and historical evidence replay.

## Current public state and limits

The old S-06.02.18 premise said "current private repository." The repository was already public when this work inspected it; its visibility was not changed here. Evidence establishes runner capacity in that current state. It does not establish private-repository billing recovery, remaining private Actions quota, or the underlying historical account restriction's cause. Returning to private visibility requires its own capacity verification; no account-wide billing claim is made.

The canceled Render review build remains failed because of pipeline-minute exhaustion and supplied no tests. It is not passing evidence. Off_CRM services remain auto-deploy disabled, and no main/customer deploy occurred.

Backup verification tests added after450165b are separately identified in BUILD_STATE and are not attributed to this exact-source CI run.
