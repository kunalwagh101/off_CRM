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

## CI

`.github/workflows/ci.yml` runs:

- locked Python dependency installation
- Python tests
- locked frontend dependency installation
- frontend tests
- production frontend build

## Kubernetes decision

Kubernetes is intentionally not included. This is a local single-user product with local credentials and SQLite. Kubernetes would conflict with the storage and OAuth model. A hosted multi-tenant edition must first move state to PostgreSQL, credentials to an encrypted vault and send work to a durable queue.
