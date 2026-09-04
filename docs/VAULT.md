# Browser Session Vault — S-03.02.02

## Problem

An attended browser login leaves reusable session material behind. The browser needs that material to remain signed in, but a model must never be able to read it and one compromised platform account must not expose every other connected account.

This is a deterministic security/storage problem. AI is deliberately not used.

## Security contract

1. A model-facing prompt containing a cookie, token or password is refused even when the provider policy is `full`.
2. Each workspace/platform account has its own randomly generated data-encryption key.
3. Account keys are wrapped by a master key obtained from the operating system credential store. If that store is unavailable, an explicitly supplied passphrase derives the master key with scrypt. The passphrase and raw master key are never stored beside vault data.
4. Session plaintext exists only inside trusted host code while moving between Chrome DevTools and authenticated encryption. Vault methods return metadata, not cookie values.
5. A platform is not recorded as `connected` unless vault capture succeeds. Vault failure is fail-closed.
6. Vault capture is not a browser-agent verb and is not exposed as a model tool. The ten-verb browser vocabulary remains unchanged.

## Data flow

```text
person signs in inside isolated Chromium
        |
        v
browser/signin.py detects connected state
        |
        v
trusted SessionVault.capture()
        |
        +--> CDP Storage.getCookies
        |       |
        |       +--> filter to target platform domains
        |       +--> copy only declared CookieParam fields
        |
        +--> random per-account Fernet key
        |       |
        |       +--> encrypt session material
        |
        +--> master key from OS credential store
        |       |
        |       +--> wrap per-account key
        |       +--> passphrase+scrypt fallback when OS store unavailable
        |
        v
encrypted envelope on disk
        |
        v
ConnectionStore records "connected"

restore path:
encrypted envelope -> unwrap account key -> authenticated decrypt
                  -> CDP Storage.setCookies -> metadata-only return
```

## Master-key sources

- Windows: DPAPI bound to the current OS user. Only the DPAPI-protected blob is written under `%LOCALAPPDATA%/off_CRM/browser_vault/`; the raw key is not.
- macOS: Login Keychain through the native `security` command.
- Linux desktop: Secret Service through `secret-tool`.
- Fallback: caller-supplied passphrase, minimum 12 characters, scrypt `N=32768, r=8, p=1`, with a random stored salt. The passphrase itself is not stored.

If neither an OS credential store nor a passphrase is available, vault creation refuses to continue.

## Stored envelope

The vault file contains only:

- format version
- workspace id
- platform id
- non-secret key fingerprint
- key-source label
- wrapped per-account key
- authenticated ciphertext
- cookie count

Cookie names and values are inside the ciphertext. Workspace/platform identifiers are validated before being used to derive a file path.

## Failure behaviour

The vault refuses:

- missing keychain and missing passphrase
- a short fallback passphrase
- path-like workspace/platform identifiers
- non-cookie payload shapes
- empty captured sessions
- cookies belonging to another platform during restore
- tampered ciphertext
- a wrapped account key that cannot be opened by the current master source

A vault error during sign-in means no green `connected` record is written.

## Acceptance evidence

Run from the repository root:

```bash
uv run pytest tests/test_browser_vault.py tests/test_browser_vault_wiring.py tests/test_browser_signin.py tests/test_ai_egress_wall.py -q
```

The full release gate is:

```bash
uv run pytest -q
uv run python scripts/verify_board.py
cd frontend && npm ci && npm test && npm run build
```

## Scope boundary

`S-03.02.03 — Revoke and forget` owns destructive disconnect/key deletion. It is intentionally not absorbed into this story. The vault provides the protected storage boundary that story will delete from.

The broader adversarial guarantee `S-06.02.01 — No secret may enter a model prompt` remains its own backlog story. This increment strengthens the shared egress scanner and directly proves browser credential shapes, but does not silently claim the entire future adversarial suite is complete.
