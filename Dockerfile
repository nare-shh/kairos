# ── Stage 1: build the React frontend ─────────────────────────────────────────
# node:slim (glibc) — the lockfile's native Rollup binaries match it; alpine (musl) may not
FROM node:22-slim AS frontend
WORKDIR /frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY frontend/ ./
RUN npm run build

# ── Stage 2: the API (also serves the built frontend) ─────────────────────────
FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

COPY requirements.txt .

RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir --retries 5 --timeout 120 -r requirements.txt

COPY . .
# One service serves the SPA + API from the same origin (see app/main.py)
COPY --from=frontend /frontend/dist ./frontend/dist

EXPOSE 8000

# Run migrations, optionally seed demo data, then start the API
# Using sh -c avoids ALL shell script / CRLF / permission issues
# - SEED_DEMO_DATA=true → idempotent demo store (hosts like Render's free tier have no shell)
# - --forwarded-allow-ips: trust the platform proxy's X-Forwarded-For so rate limits see real client IPs
# - $PORT is injected by Railway/Render; RELOAD=1 (docker-compose dev) enables hot reload
CMD ["sh", "-c", "alembic upgrade head && if [ \"$SEED_DEMO_DATA\" = true ]; then python -m app.seed; fi && exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --forwarded-allow-ips='*' ${RELOAD:+--reload}"]
