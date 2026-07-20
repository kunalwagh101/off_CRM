# Deployment

## Recommended local run

Use the source workflow in `README.md`. It has the fewest moving parts and is best for Gmail OAuth on a personal device.

## Container run

Generate a random API token with at least 32 characters, set it as `OFFSETX_LOCAL_API_TOKEN`, then run:

```text
docker compose up --build
```

The compose file exposes the app only on host loopback and persists SQLite under `local_data`.

Gmail OAuth is easier to authorize on the host first. If Gmail is needed inside the container, mount the client-secret and token files and set their container paths explicitly.

## Disposable Render demo

`render.yaml` defines a free Docker web service with `/health/ready` as its health check. For the manual Render form, use Docker, branch `main`, Singapore, an empty root directory and the Free plan.

Set these secrets in Render, never in Git:

- `OFFSETX_DEMO_USERNAME`: the temporary CRM username.
- `OFFSETX_DEMO_PASSWORD`: at least 12 characters.
- `OFFSETX_SESSION_SECRET`: use Render's Generate button; at least 32 characters.
- `OFFSETX_SESSION_HOURS`: `8`.

The application reads Render's injected `PORT`. The Docker image already binds to `0.0.0.0`.

Free Render instances have an ephemeral filesystem. This means SQLite, outbox files, provider profiles, automation settings and Gmail token files are disposable. Background automation also stops when a free instance sleeps. Use local outbox mode and synthetic contacts only.

## CI

`.github/workflows/ci.yml` runs:

- locked Python dependency installation
- Python tests
- locked frontend dependency installation
- frontend tests
- production frontend build

## Kubernetes decision

Kubernetes is intentionally not included. This is a local single-user product with local credentials and SQLite. Kubernetes would conflict with the storage and OAuth model. A hosted multi-tenant edition must first move state to PostgreSQL, credentials to an encrypted vault and send work to a durable queue.
