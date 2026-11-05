FROM node:24-alpine AS frontend-build
WORKDIR /build/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
# The video tests type-check against the timeline fixture Python plans from.
# `tsc -b` checks them too, so without this file the image does not build.
COPY tests/fixtures/timeline_conformance.json /build/tests/fixtures/timeline_conformance.json
RUN npm run build

FROM python:3.12-slim AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    OFFSETX_WEB_HOST=0.0.0.0 \
    OFFSETX_WEB_PORT=8766 \
    OFFSETX_DATA_DIR=/var/lib/offcrm/local_data \
    OFFSETX_OUTREACH_DB=/var/lib/offcrm/local_data/offsetx_outreach.db
RUN apt-get update && apt-get install -y --no-install-recommends postgresql-client \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY . .
COPY --from=frontend-build /build/frontend/dist ./frontend/dist
# The lock, not whatever pip resolves today, and the extras the features use:
# `email` for SES delivery, `postgres` for OFFSETX_DATABASE_URL (audit A26).
COPY --from=ghcr.io/astral-sh/uv:0.8.17 /uv /usr/local/bin/uv
RUN uv sync --locked --no-dev --extra email --extra postgres
ENV PATH="/app/.venv/bin:$PATH"
RUN useradd --create-home --uid 10001 offsetx \
    && chown -R offsetx:offsetx /app \
    && mkdir -p /var/lib/offcrm && chown offsetx:offsetx /var/lib/offcrm
VOLUME ["/var/lib/offcrm"]
# Starts as root only to take ownership of a freshly mounted disk, then drops
# to uid 10001 before the app runs. See scripts/container_entrypoint.py.
ENTRYPOINT ["python", "scripts/container_entrypoint.py"]
EXPOSE 8766
CMD ["python", "run_offsetx_web.py"]
