# Revoke and Forget — S-03.02.03

## Problem

A protected login is not safe enough if leaving the platform still leaves a reusable browser session behind. Disconnect must remove both copies off_CRM can rely on: the live browser session cookies and the encrypted vault envelope.

This is deterministic security/storage work. AI is not used.

## Contract

Given a connected platform, disconnecting it must:

1. require an attached browser page and its CDP session id;
2. open the encrypted session only inside trusted host code;
3. refuse if the vault contains material for another platform;
4. ask Chromium to delete every vaulted cookie through `Network.deleteCookies` on that attached page target;
5. destroy the per-account vault envelope containing the wrapped account key;
6. remove the public connection record;
7. append the attempt and the final result to the existing append-only browser trace;
8. never write cookie values, tokens or passwords into that trace.

If Chromium refuses the deletion, the encrypted vault and connection record are retained so the owner can retry. off_CRM does not paint a disconnected state over a still-usable session.

## Why the boundary is cookies

`S-03.02.02` deliberately vaults browser cookies and nothing else. This story therefore destroys exactly that managed session material rather than claiming to erase unrelated website databases that off_CRM never captured. Broader browser-site data removal would be a different requirement and must get its own story.

## Why deleting the vault envelope is the security boundary

Each account's session is encrypted under a random per-account key. That account key exists at rest only wrapped inside that account's vault envelope. Deleting the envelope removes both the ciphertext and the only persisted wrapped copy of the account key. The shared master key alone is insufficient to reconstruct the deleted random account key.

This is cryptographic erasure at the application boundary. It does not claim that a filesystem or SSD has physically overwritten every historical block.

## Data flow

```text
Disconnect requested
      |
      v
require attached page/session id
      |
      v
open encrypted vault session in trusted code
      |
      v
validate every cookie belongs to target platform
      |
      v
append trace intent
      |
      v
Chromium Network.deleteCookies (page CDP session)
      |
      v
destroy per-account vault envelope
      |
      v
ConnectionStore.forget
      |
      v
append successful revocation to trace
```

On a browser failure the path stops before vault deletion and records a failed revocation attempt.

## Evidence

Focused acceptance and live-browser proof:

```bash
uv run pytest tests/test_browser_revoke.py -q
```

The live test launches real Chromium, plants a persistent session cookie, confirms Chromium has it, attaches to a real page target, runs disconnect, then asks Chromium whether the cookie survived. It also confirms the vault can no longer decrypt that account and the trace contains no cookie value.

Full release gate:

```bash
uv run pytest -q
uv run python scripts/verify_board.py
cd frontend && npm ci && npm test && npm run build
```

The implementation commit passed the full gate on 2026-09-04 UTC: 1,542 Python tests passed, 116 frontend tests passed, the production frontend build passed, and the board verifier passed all 24 pre-existing DONE evidence commands.

## Scope boundary

This story destroys one platform's browser session material managed by off_CRM. It does not revoke a platform's server-side sessions on every other device, rotate passwords, delete the account itself, erase unrelated browser-site storage, or implement general data-subject deletion. Those are different capabilities and must not be silently absorbed into this story.