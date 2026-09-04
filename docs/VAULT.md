# Browser Session Vault — S-03.02.02

## Problem and measurable success

An attended browser login leaves reusable session material behind. The browser needs that material to remain signed in, but a model must never be able to read it and one compromised platform account must not expose every other connected account.

Success is measurable:

- zero cookie/token/password payloads pass the shared AI egress scanner, including at `full` policy;
- two platform accounts produce different encryption-key fingerprints;
- plaintext session values are absent from vault files;
- the master source is OS-backed or passphrase-derived, never a raw key file beside the data;
- a failed vault capture cannot leave a public `connected` record;
- tampered ciphertext and a wrong passphrase fail closed.

This is a deterministic security/storage problem. AI is deliberately not used.

## Implementation task ledger

These are engineering tasks inside the already-approved story, not new scope or new board items.

| Task | Engineering step | Bound |
|---|---|---|
| `T-03.02.02.a` | Build the per-account encrypted envelope and OS-keychain/passphrase master source | <= 1 day |
| `T-03.02.02.b` | Wire trusted CDP capture/restore into sign-in with fail-closed connection recording | <= 1 day |
| `T-03.02.02.c` | Harden model egress for opaque browser credentials and add acceptance/failure tests | <= 1 day |
| `T-03.02.02.d` | Run release proof, repair verifier environment drift, update demo/change log/traceability/retro | <= 1 day |

## Approach chosen, and alternatives rejected

**Chosen:** envelope encryption with one random Fernet key per workspace/platform account, wrapped by an OS-backed master key. When the OS credential store is unavailable, derive the master from an explicit passphrase using scrypt.

**Rejected: reuse `ai/workspace.py`'s `.key` file.** It is simple, but directly violates Q-01 and AC3 because the master key would sit beside the encrypted data.

**Rejected: one shared data-encryption key for every platform.** It would make one exposed account-key boundary an all-accounts compromise and fail AC2.

**Rejected: let the model call a vault tool.** The model does not need session material to decide `click 7`; adding such a tool would turn containment into permission management around a secret-reading capability that should not exist.

**Rejected: build a new cryptography/service abstraction.** `cryptography` is already installed and the existing browser/CDP path is sufficient. A new service, RPC boundary or dependency would add failure modes without adding a security property.

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

## Data, privacy and bias assessment

There is no training dataset, embedding corpus or statistical inference in this slice, so model accuracy and bias are not applicable. The sensitive data is browser session material. The design minimises it by capturing only cookies belonging to the target platform and then only an explicit allow-list of CDP CookieParam fields. Other-domain cookies are dropped before encryption.

The acceptance suite uses synthetic secrets only. Real platform credentials are neither required nor appropriate for automated CI.

## Cost and latency

There is no AI/provider cost. Storage is one small encrypted JSON envelope per connected workspace/platform account plus one metadata file. CPU work is authenticated encryption plus scrypt only when a passphrase fallback is used; this happens at vault initialisation, not on every browser action. Network latency is unchanged except for local CDP `Storage.getCookies`/`Storage.setCookies` calls.

No numerical production latency SLA is invented here; `S-06.02.03` owns explicit cost/latency budgets.

## Monitoring and rollback

Failures are explicit `VaultError`/`VaultLocked` exceptions and sign-in converts vault failure into a user-facing `SignInRefused` without recording a connected state. No fallback silently stores plaintext.

Rollback is code-only for this increment: existing encrypted envelopes are versioned (`VAULT_VERSION = 1`) and no database migration is introduced. A release rollback does not require transforming database state. Destructive session deletion belongs to `S-03.02.03`.

## Acceptance evidence

Focused story proof:

```bash
uv run pytest tests/test_browser_vault.py tests/test_browser_vault_wiring.py -q
```

Regression proof around the two touched boundaries:

```bash
uv run pytest tests/test_browser_vault.py tests/test_browser_vault_wiring.py tests/test_browser_signin.py tests/test_ai_egress_wall.py -q
```

The full release gate is:

```bash
uv run pytest -q
uv run python scripts/verify_board.py
cd frontend && npm ci && npm test && npm run build
```

## Known limitations and scope boundary

`S-03.02.03 — Revoke and forget` owns destructive disconnect/key deletion. It is intentionally not absorbed into this story. The vault provides the protected storage boundary that story will delete from.

The broader adversarial guarantee `S-06.02.01 — No secret may enter a model prompt` remains its own backlog story. This increment strengthens the shared egress scanner and directly proves browser credential shapes, but does not silently claim the entire future adversarial suite is complete.

The vault currently manages cookie-based browser session material. It does not claim to export every possible browser-origin persistence mechanism such as arbitrary IndexedDB/localStorage application state. The supported platforms' current connection contract is cookie/session based; if a platform later requires another persistence mechanism, that is a new requirement and must enter change control rather than being silently added here.