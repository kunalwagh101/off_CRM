FROM node:24-alpine AS frontend-build
WORKDIR /build/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
COPY tests/fixtures/timeline_conformance.json /build/tests/fixtures/timeline_conformance.json
RUN npm run build

FROM python:3.12-slim AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    OFFSETX_WEB_HOST=0.0.0.0 \
    OFFSETX_WEB_PORT=8766 \
    OFFSETX_DATA_DIR=/var/lib/offcrm/local_data \
    OFFSETX_OUTREACH_DB=/var/lib/offcrm/local_data/offsetx_outreach.db
WORKDIR /app
COPY . .
COPY --from=frontend-build /build/frontend/dist ./frontend/dist
COPY --from=ghcr.io/astral-sh/uv:0.12.8 /uv /usr/local/bin/uv
RUN uv sync --locked --no-dev --extra email --extra postgres
ENV PATH="/app/.venv/bin:$PATH"
RUN useradd --create-home --uid 10001 offsetx \
    && mkdir -p /app/local_data/exports /app/local_data/mail \
    && chown -R offsetx:offsetx /app
RUN mkdir -p /var/lib/offcrm && chown offsetx:offsetx /var/lib/offcrm
VOLUME ["/var/lib/offcrm"]
ENTRYPOINT ["python", "scripts/container_entrypoint.py"]
EXPOSE 8766
CMD ["python", "run_offsetx_web.py"]
