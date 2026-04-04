FROM node:20-bookworm-slim AS frontend-build

WORKDIR /app/Front
COPY Front/package.json Front/package-lock.json ./
RUN npm ci
COPY Front/ ./
RUN npm run build


FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    MADRIGAL_FRONTEND_DIST_PATH=/app/Front/dist \
    MADRIGAL_AUTO_REFRESH_ENABLED=1 \
    MADRIGAL_AUTO_REFRESH_INTERVAL_SECONDS=300 \
    MADRIGAL_AUTO_REFRESH_MAX_PER_SOURCE=4

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential curl git \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
RUN pip install --upgrade pip && pip install -r requirements.txt

COPY madrigal_assistant ./madrigal_assistant
COPY config ./config
COPY scripts ./scripts
COPY data/seed_rostov_last7d.json ./data/seed_rostov_last7d.json
COPY data/seed_tatarstan_last7d.json ./data/seed_tatarstan_last7d.json
COPY README.md ./
COPY --from=frontend-build /app/Front/dist ./Front/dist

EXPOSE 8000

CMD ["sh", "-c", "python scripts/bootstrap_seed.py && uvicorn madrigal_assistant.api.app:app --host 0.0.0.0 --port 8000"]
