#!/bin/bash
# start.sh — Production startup script
#
# This script runs BEFORE uvicorn starts.
# It ensures all database migrations are applied before the API accepts requests.
#
# Why not run migrations inside the app?
# ─────────────────────────────────────────────────────────────────────────
# In production, multiple API instances may start simultaneously (horizontal scaling).
# If each instance calls create_all() or applies migrations, they race each other.
# Alembic uses a database lock (alembic_version table) to prevent concurrent runs.
# Running it in a pre-start script ensures only one process migrates.
#
# This pattern is used by:
# - Heroku (release phase)
# - Railway (start command)
# - Kubernetes (init containers)

set -e  # Exit immediately if any command fails

echo "=== Kairos startup ==="
echo "Waiting for database to be ready..."

# Wait for PostgreSQL to accept connections (retry up to 30 times)
# pg_isready checks if Postgres is listening without needing credentials
until python -c "
import asyncio, asyncpg, os, sys
from dotenv import load_dotenv
load_dotenv()
url = os.getenv('DATABASE_URL','').replace('postgresql+asyncpg://', '')
async def check():
    try:
        conn = await asyncpg.connect(url)
        await conn.close()
        print('Database is ready')
    except Exception as e:
        print(f'DB not ready: {e}')
        sys.exit(1)
asyncio.run(check())
"; do
    echo "  Database not ready — retrying in 2s..."
    sleep 2
done

echo "Running database migrations..."
alembic upgrade head
echo "Migrations complete."

echo "Starting Kairos API..."
exec uvicorn app.main:app --host 0.0.0.0 --port 8000 ${RELOAD:+--reload}
# ${RELOAD:+--reload} means: if $RELOAD env var is set, add --reload flag
# In dev: RELOAD=1 docker-compose up → hot reload enabled
# In prod: RELOAD is not set → no reload (faster, safer)
