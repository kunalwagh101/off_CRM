FROM node:24-alpine AS frontend-build
WORKDIR /build/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.12-slim AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    OFFSETX_WEB_HOST=0.0.0.0 \
    OFFSETX_WEB_PORT=8766 \
    OFFSETX_DATA_DIR=/app/local_data \
    OFFSETX_OUTREACH_DB=/app/local_data/offsetx_outreach.db
WORKDIR /app
COPY . .
COPY --from=frontend-build /build/frontend/dist ./frontend/dist
RUN pip install --no-cache-dir .
RUN useradd --create-home --uid 10001 offsetx && chown -R offsetx:offsetx /app
USER offsetx
VOLUME ["/app/local_data"]
EXPOSE 8766
CMD ["python", "run_offsetx_web.py"]
