# WP1 acceptance scope

S-06.02.09/10 closes A01, A02, A03, A04 and A17 together. Run
`.github/workflows/wp1-verification.yml` for every Python test with real
PostgreSQL/Chrome/Docker, frontend tests/build, browser backup/restore and a
production container kill/recreate on the same persistent volume.

The original `test_live.py` assertions are preserved. Its six failing checks
for A09/A32/A33/A34/A35 are outside WP1 and remain open. See the 7 September
audit and `docs/architecture/WP1_OPERATIONS.md` for the exact recovery boundary.
