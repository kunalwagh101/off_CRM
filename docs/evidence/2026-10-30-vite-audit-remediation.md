# Vite patch-line security remediation — 2026-10-30

Actual Render review deploy `dep-dbhqbjpsrm7s738gnbq0` on commit `477a3fe` failed `npm audit --audit-level=high` at Dockerfile.review:12. Npm reported 3 advisories (2 moderate, 1 high) for Vite 8.1.4. The prior 2026-10-19 QA had 0 advisories; audit feeds changed after the earlier run. This gate **prevented the backend and upload tests from running**, so no claim of an application failure or success is made for that attempt.

## Scoped patch

- `frontend/package.json`: Vite 8.1.4 -> **8.1.6**, within the same minor line.
- `frontend/package-lock.json`: root spec, installed version, trusted npm tarball URL and SHA-512 integrity updated from public GitHub lockfile for `vite-8.1.6.tgz`. Dependencies `postcss ^8.5.17`, `rolldown ~1.1.5`. Existing installed postcss 8.5.30 and rolldown 1.1.5 satisfy them. No new runtime or other package upgrades.
- Independent public advisory history says security patches issued in Vite 8.1.6 (including GHSA-587h-7wmj-h5pm, GHSA-r825-w8mm-5pxw, GHSA-9jrq-w75r-8gcw, GHSA-rq7h-c2jc-7f22).
- Exact provenance: https://github.com/k-nut/github-license-check/blob/master/package-lock.json (public published lock entry with `vite@8.1.6` integrity), https://npmscan.io/package/npm/vite (affected version ranges). No npm audit bypass, no `npm audit fix --force`.

## To verify (not claimed until executed)

Render Dockerfile.review must complete `npm ci`, 212+ frontend tests, frontend build, both npm audits with no high advisories, all Python suites (SQLite and real disposable PostgreSQL), and Chromium UI. This entry is a dependency remediation record, not a finished security certification.

## Verified follow-up after Vite patch

Actual Render `dep-dbhqd96i0phs73f1vfrg` on `0c28d7c9be64d24a67f846142c5ff1dd56f50af3` completed `npm ci`, 212 frontend tests, build, and `npm audit --audit-level=high` successfully. Production-only audit found zero; **two moderate Vitest @vitest/mocker dev advisories remain**. Do not describe all npm advisories as cleared. Those are tracked as D-321; full QA evidence: `docs/evidence/2026-10-30-a15-video-upload-qa.md`.
