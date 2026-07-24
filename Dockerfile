FROM node:24-alpine AS frontend-build
WORKDIR /build/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.12-slim AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    OFF_CRM_WEB_HOST=0.0.0.0 \
    OFF_CRM_WEB_PORT=8766 \
    OFF_CRM_DATA_DIR=/app/local_data \
    OFF_CRM_DB=/app/local_data/off_crm.db
WORKDIR /app
COPY . .
COPY --from=frontend-build /build/frontend/dist ./frontend/dist
RUN pip install --no-cache-dir .
RUN useradd --create-home --uid 10001 offcrm \
    && mkdir -p /app/local_data/exports /app/local_data/mail \
    && chown -R offcrm:offcrm /app
USER offcrm
VOLUME ["/app/local_data"]
EXPOSE 8766
CMD ["python", "run_off_crm.py"]
