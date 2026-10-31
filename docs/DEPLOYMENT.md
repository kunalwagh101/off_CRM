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

`render.yaml` defines two free Docker web services with `/health/ready` as their health check: `off-crm-demo` on `main` and `off-crm-develop` on `develop` (`docs/BRANCHING.md`). For the manual Render form, use Docker, the service's branch, Singapore, an empty root directory and the Free plan.

Set these secrets in Render, never in Git:

- `OFFSETX_DEMO_USERNAME`: the temporary CRM username.
- `OFFSETX_DEMO_PASSWORD`: at least 12 characters.
- `OFFSETX_SESSION_SECRET`: use Render's Generate button; at least 32 characters.
- `OFFSETX_SESSION_HOURS`: `8`.

The application reads Render's injected `PORT`. The Docker image already binds to `0.0.0.0`.

Free Render instances have an ephemeral filesystem. This means SQLite, outbox files, provider profiles, automation settings and Gmail token files are disposable. Background automation also stops when a free instance sleeps. Use local outbox mode and synthetic contacts only.

## Public visitor demo

The live visitor installation is https://off-crm-public-demo.onrender.com/. Its sign-in screen displays the public credentials. This service is separate from owner and QA installations; it contains fictional sample contacts and permits read-only CRM access.

For a fresh dedicated Docker service, set `OFFSETX_PUBLIC_DEMO=1`, `OFFSETX_DEMO_USERNAME`, `OFFSETX_DEMO_PASSWORD`, a new `OFFSETX_DATA_DIR`, and `OFFSETX_OUTREACH_DB` inside that folder. Use the image's default command. Its entrypoint generates a private session signing secret when none is configured. Sessions expire after a container restart. Never copy the owner's or QA data folder, external database settings, provider credentials or Gmail integration into this service.

Public mode refuses existing unmarked data, escaped file paths, hosted databases, API tokens, production mode and private integrations. It starts no schedulers and refuses API writes except login/logout. One paused campaign and three fictional example.com contacts are created atomically. Empty storage recreates the sample; reopening existing sample storage does not duplicate records.

Retire the separate visitor service to withdraw access. Do not disable public mode on a service that still has a publicly known account. The visitor demo is disposable; it does not establish production tenancy or durability. Acceptance and rollback: `docs/evidence/2026-11-01-public-visitor-demo.md`.

## CI

`.github/workflows/ci.yml` runs:

- locked Python dependency installation
- Python tests
- locked frontend dependency installation
- frontend tests
- production frontend build

## Kubernetes decision

Kubernetes is intentionally not included. This is a local single-user product with local credentials and SQLite. Kubernetes would conflict with the storage and OAuth model. A hosted multi-tenant edition must first move state to PostgreSQL, credentials to an encrypted vault and send work to a durable queue.
