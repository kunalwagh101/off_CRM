# Deployment

## Recommended local run

Use the source workflow in `README.md`. It has the fewest moving parts and is best for Gmail OAuth on a personal device.

## Container run

Generate a random API token with at least 32 characters, set it as `OFFSETX_LOCAL_API_TOKEN`, then run:

```text
docker compose up --build
```

The compose file exposes the app only on host loopback and persists SQLite under `local_data`.
That folder is mounted where the image keeps its data, `/var/lib/offcrm/local_data`, and on
start the container gives it to its own unprivileged user (uid 10001), which then writes there.

Gmail OAuth is easier to authorize on the host first. If Gmail is needed inside the container, mount the client-secret and token files and set their container paths explicitly.

## Disposable Render demo

`render.yaml` defines an intended pair of free Docker web services with `/health/ready` as their health check: `off-crm-demo` on `main` and `off-crm-develop` on `develop`. This is not the live inventory: the existing original `off-crm.onrender.com` and public visitor service both track `develop` with auto-deploy off. Check the actual service's live deploy commit after each manual deployment; a develop push alone does not update those URLs. The observed service table is in `docs/BRANCHING.md`. For the manual Render form, use Docker, the service's branch, Singapore, an empty root directory and the Free plan.

Set these secrets in Render, never in Git:

- `OFFSETX_DEMO_USERNAME`: the temporary CRM username.
- `OFFSETX_DEMO_PASSWORD`: at least 12 characters.
- `OFFSETX_SESSION_SECRET`: use Render's Generate button; at least 32 characters.
- `OFFSETX_SESSION_HOURS`: `8`.

The application reads Render's injected `PORT`. The Docker image already binds to `0.0.0.0`.

Free Render instances have an ephemeral filesystem. This means SQLite, outbox files, provider profiles, automation settings and Gmail token files are disposable. Background automation also stops when a free instance sleeps. Use local outbox mode and synthetic contacts only.

## Public visitor demo

The visitor installation is https://off-crm-public-demo.onrender.com/. Its sign-in screen displays the public credentials. This service is separate from owner and QA installations; it contains fictional sample contacts and permits read-only CRM access. The corrective AI release restores Chat, Compare, Plan and Image, with AI as the first screen after login. Consult `docs/evidence/2026-11-01-restore-demo-ai.md` for its deployment and verification status.

For a fresh dedicated Docker service, set `OFFSETX_PUBLIC_DEMO=1`, `OFFSETX_DEMO_USERNAME`, `OFFSETX_DEMO_PASSWORD`, a new `OFFSETX_DATA_DIR`, and `OFFSETX_OUTREACH_DB` inside that folder. Use the image's default command. Its entrypoint generates a private session signing secret when none is configured. Sessions expire after a container restart. Never copy the owner's or QA data folder, external database settings, provider credentials or Gmail integration into this service.

Public mode refuses existing unmarked data, escaped file paths, hosted databases, API tokens, production mode and private integrations. It starts no schedulers. Its explicit API allowlist permits existing broker-backed AI, provider setup and chat/project operations, while refusing sample CRM writes, external sending and owner/browser operations. One paused campaign and three fictional example.com contacts are created atomically. Empty storage recreates the sample; reopening existing sample storage does not duplicate records.

Each verified signed login session gets a separate AI workspace. Visitors connect their own provider through Connectors; the key is encrypted on the demo server, scoped to that session and removed when it logs out. A login in another browser does not inherit it. No owner key is copied, and a missing key produces a setup action rather than model output. Free Render storage and sessions remain disposable. The existing Plan mode distributes text tasks among models; arbitrary CRM action execution from chat is not implemented by this release.

Retire the separate visitor service to withdraw access. Do not disable public mode on a service that still has a publicly known account. Do not roll back the session isolation while continuing to serve visitor keys: withdraw access first. The visitor demo is disposable; it does not establish production tenancy or durability. Initial acceptance: `docs/evidence/2026-11-01-public-visitor-demo.md`; corrective AI acceptance: `docs/evidence/2026-11-01-restore-demo-ai.md`.

## CI

`.github/workflows/ci.yml` runs:

- locked Python dependency installation
- Python tests
- locked frontend dependency installation
- frontend tests
- production frontend build

## Kubernetes decision

Kubernetes is intentionally not included. This is a local single-user product with local credentials and SQLite. Kubernetes would conflict with the storage and OAuth model. A hosted multi-tenant edition must first move state to PostgreSQL, credentials to an encrypted vault and send work to a durable queue.
