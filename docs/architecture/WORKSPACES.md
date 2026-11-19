# Workspace keys and browser sessions

S-06.01.01 provides separate credentials and browser sessions for local workspaces.
The server binds one identity at startup. Run a separate authenticated app instance
and port for each workspace. This is not a shared multi-tenant server or a process
sandbox: the host administrator, arbitrary trusted Python code and the OS account
can read local files. Do not share that account with untrusted users. Permissions
and chat-scoped grants remain S-06.01.02.

## Configure an instance

Set `OFFSETX_WORKSPACE_ID=alice` before `uv run offsetx-web`. IDs contain 1–64
lowercase letters, digits, dashes or underscores and start with a letter or digit.
Default `local` keeps existing paths and environment names. Legacy IDs outside
this canonical format need an owner-chosen valid identity and attended reconnect;
IDs are never silently normalized into another workspace. Headers, query strings
and request bodies cannot change the configured workspace. Authenticated
`GET /api/v1/workspace` reports the binding without any credentials.

For nonlocal IDs, data, export and database parent roots gain `workspaces/<id>`.
For example, `local_data/crm.db` becomes `local_data/workspaces/alice/crm.db`.
Generated API tokens live inside that workspace's data directory. A global
`OFFSETX_DATABASE_URL` is used only by the legacy local instance; nonlocal instances
use their scoped SQLite files. Choose unique listening ports for simultaneous apps.

Private environment variables use a collision-resistant namespace. Print the name
without printing its value:

```python
from offsetx_apollo_builder.workspaces import workspace_env
print(workspace_env('alice', 'AI_OPENAI_KEY'))
print(workspace_env('alice', 'LOCAL_API_TOKEN'))
```

The prefix is `OFFSETX_WORKSPACE_<uppercase full SHA256 of ID>_`. Use suffixes
`AI_<PROVIDER>_KEY`, `LOCAL_API_TOKEN`, `DEMO_USERNAME`, `DEMO_PASSWORD`,
`SESSION_SECRET`, `GMAIL_CLIENT_SECRETS`, `GMAIL_TOKEN`, `OWN_EMAIL`,
`UNSUBSCRIBE_SECRET` and `YOUTUBE_API_KEY` as needed. Nonlocal instances never
inherit local/global credentials for these paths. Demo cookies have separate
names and workspace-derived signatures, even if an operator reuses a secret.
Request-supplied provider profiles can see only their own `AI_*_KEY` variables.
Host-command provider profiles are supported only in the trusted `local` instance.
Stored profile API keys remain encrypted inside the scoped data directory.

## Provider key storage

`WorkspaceAISettingsStore(root, registry)` is the trusted owner SDK. It places
nonlocal records under `root/workspaces/<id>` with a separate encryption master,
settings file and encrypted key file. The API instead binds a store to its already
scoped data directory; it refuses every foreign identity. The broker binds its
credential resolver once and refuses foreign settings before any provider work.
Encrypted state that cannot be read or authenticated fails closed, without an
alternate environment-key fallback. An advisory OS file lock and an in-process
reentrant lock serialize read/modify/write across store instances and processes.
Private directories use mode 0700 and newly created key/state files use 0600.
Symbolic links are refused at the workspace directory and secret-file boundaries.
These checks do not provide protection against an administrator replacing ancestor
paths while a process runs; use separate OS accounts/containers for that threat.

## Browser sessions

Trusted host code obtains pages with `await session.workspace_page('alice')`.
Chrome allocates one isolated BrowserContext per identity. Context management is
not a model action; the closed ten-verb interface is unchanged. Concurrent requests
reuse one context for the same workspace. `close_workspace` disposes only that
workspace's context. Such contexts are ephemeral. Capture a connected session to
the vault before closing, then explicitly restore it into a newly allocated page.
Legacy unscoped `new_tab()` stays in the owner's default browser profile.

Capture/restore/revoke require the matching page identity and an attached CDP
session. Nonlocal pages also require an isolated context. Capture and restore use
page-scoped `Network.getCookies` / `Network.setCookies`; they do not use
browser-wide Storage commands. Only declared platform-domain cookies enter the
vault. Vault v2 derives the account-key wrapper from both canonical workspace and
platform identity. Copying ciphertext and relabelling either identity fails
authenticated decryption. Passing `workspace_id=` to `SessionVault` additionally
binds a trusted vault handle to one identity.

The OS master can serve several vault directories under one OS account. First
creation is serialized by a private per-user lock at
`~/.off_crm/browser_vault_keychain`. The backend is read again under that lock;
an existing valid master is reused. If the common lock cannot be acquired, no
new OS root is created. Supply the explicit passphrase or restore OS-user state
directory access. Already installed masters can be read without creating locks.

## Upgrade, rollback and disconnect

Stop writers and back up the complete old data directory, including encryption
master files, before upgrading. Protect backups like credentials.

The local/default provider store needs no move. To move one named record from an
old combined owner store, run trusted offline Python with the original root:

```python
from pathlib import Path
from offsetx_apollo_builder.ai.registry import ProviderRegistry
from offsetx_apollo_builder.ai.workspace import WorkspaceAISettingsStore
owner = WorkspaceAISettingsStore(Path('local_data'), ProviderRegistry(Path('config/providers.yaml')))
report = owner.migrate_legacy_workspace('alice')
```

Only Alice's settings and keys are copied. Existing destinations are refused.
The combined source stays unchanged as an owner-only rollback backup. A failed
copy removes newly created destination artifacts so it can be retried. Never
serve the combined backup through a nonlocal instance. For rollback, stop apps,
restore the complete original backup with the old executable, and verify login.
Archive/delete old combined backups once the operator accepts the migration.

Vault v1 did not authenticate identity labels. New code refuses to load it
silently. Prefer reconnecting with an attended browser login. If the owner can
verify the workspace and platform independently, use the original unlocked vault:

```python
vault.migrate_legacy('alice', 'linkedin',
    confirmation='MIGRATE VERIFIED WORKSPACE SESSION')
```

This writes v2 with a fresh account key and retains a private `.vault.json.v1.bak`
for owner rollback. It cannot prove a v1 label's origin retroactively. A failed
conversion restores the original active envelope. Preserve the backup before
retrying an unresolved failed migration; an existing backup is never overwritten.
For rollback, stop writers, restore the owned v1 backup as the active envelope and
use the old executable. Reconnect is safer when provenance is uncertain.

Disconnect removes cookies from the bound page, the active envelope, the owned
migration backup and the connection record, and records only metadata in the
trace. External backups and Chrome profiles outside this managed context remain
the owner's responsibility. Erasure cannot revoke copies an administrator made.

## Verification

`uv run pytest tests/test_workspace_isolation.py tests/test_workspace_api.py tests/test_workspace_browser.py -q`
checks parallel apps, real Chrome context cookies, persistence through explicit
vault restore, legacy migration/rollback, relabel attacks, spoofed identities,
cross-process writes, environment isolation and cross-workspace cookie replay.
No live provider account is required. These automated adversarial probes are
security tests, not an independent penetration assessment. CI also runs the full
regression suite, the board's historical evidence, frontend tests and build.
