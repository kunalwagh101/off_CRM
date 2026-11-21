# D-496 — operator key directory-swap security regression

**Scope:** off_CRM `develop`, F-06.02 / F-06.03 security hardening. Story S-06.03.04 remains BACKLOG.

## Test-first evidence

- RED test commit: `c6ac720f65e4609678cbca10ceedfa185c39817f`.
- `tests/test_hosted_storage.py::test_private_key_output_parent_swap_cannot_redirect_secret` parametrises both key generation commands. Monkeypatch changes the parent directory into a symlink exactly before final `O_CREAT` to model a concurrent local attacker.
- Faithful isolated old-code run reproduced `return=0 diverted_file_exists=True` and raised `AssertionError: RED: key was redirected to attacker-controlled parent`.
- Code changes: `adeb18ff29bc96ac47cb6b4324daf7ce8398c468`, then `7f182f36f2316661a7f8fbcdbb1daff9c83c9827` to keep directory-fd safety under the test's adversarial monkeypatch.
- An isolated corrected-code reproduction showed `return=0 diverted_file_exists=False`. It does **not** certify full application, CI or Render.

## Full acceptance still required

1. Run `uv run pytest -q tests/test_hosted_storage.py -k 'private_key_output or generated_hosted_keys'` against the final source.
2. Run full Python version matrix, real PostgreSQL, frontend/Chromium, secret leakage/security tests and complete board verifier.
3. Deploy **that exact code SHA** to Render and inspect actual build and app logs.
4. Test authorised operational key path under a private, non-user-writable directory; prove existing-file, linked-parent, race, permissions, stderr and no-key-stdout behaviour.
5. Independently assess POSIX portability and any concurrent attacker with write permission to a trusted directory.

**Release limitation:** existing Render `Dockerfile.review` only runs a disposable QA marker. It is not a CRM customer app; no live S3 destination, retention, offsite recovery or encrypted customer data was verified. Do not mark any parent feature DONE from this test alone.
