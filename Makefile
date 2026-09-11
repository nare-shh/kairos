# Kairos — Developer Commands
# Run: make <command>
# Example: make up  |  make seed  |  make logs

# ── Docker ────────────────────────────────────────────────────────────────────
up:
	docker-compose up -d

down:
	docker-compose down

build:
	docker-compose build api worker

rebuild:
	docker-compose build --no-cache api worker

logs:
	docker-compose logs -f api

worker-logs:
	docker-compose logs -f worker

frontend-logs:
	docker-compose logs -f frontend

restart:
	docker-compose restart api worker

# ── Seed Data ─────────────────────────────────────────────────────────────────
seed:
	# Demo users (admin / seller / customer), categories and products — idempotent
	docker-compose exec api python -m app.seed

create-admin:
	# Usage: make create-admin email="you@example.com" password="Secret123"
	docker-compose exec api python -m app.seed create-admin "$(email)" "$(password)"

# ── Alembic Migrations ────────────────────────────────────────────────────────
# These run INSIDE the api container where alembic is installed

migrate:
	# Apply all pending migrations
	docker-compose exec api alembic upgrade head

rollback:
	# Roll back the last migration
	docker-compose exec api alembic downgrade -1

migration-status:
	# Show current migration version and pending migrations
	docker-compose exec api alembic current
	docker-compose exec api alembic history --verbose

new-migration:
	# Auto-generate a migration from model changes
	# Usage: make new-migration name="add_user_phone"
	docker-compose exec api alembic revision --autogenerate -m "$(name)"

migration-sql:
	# Print the SQL that would be run (offline mode — for DBA review)
	docker-compose exec api alembic upgrade head --sql

# ── Database ──────────────────────────────────────────────────────────────────
db-shell:
	docker-compose exec postgres psql -U kairos_user -d kairos_db

db-reset:
	# WARNING: Drops and recreates the database. Dev only!
	docker-compose exec postgres psql -U kairos_user -d postgres -c "DROP DATABASE IF EXISTS kairos_db WITH (FORCE);"
	docker-compose exec postgres psql -U kairos_user -d postgres -c "CREATE DATABASE kairos_db;"
	make migrate

# ── Tests ─────────────────────────────────────────────────────────────────────
# API tests use a separate kairos_test database (created automatically)
TEST_DB = postgresql+asyncpg://kairos_user:kairos_pass@postgres:5432/kairos_test

test:
	docker-compose exec -e TEST_DATABASE_URL=$(TEST_DB) api pytest tests/ -v

test-coverage:
	docker-compose exec -e TEST_DATABASE_URL=$(TEST_DB) api pytest tests/ --cov=app --cov-report=html

# ── Utilities ─────────────────────────────────────────────────────────────────
health:
	curl -s http://localhost:8000/health | python -m json.tool

routes:
	curl -s http://localhost:8000/openapi.json | python -m json.tool | grep '"/' | sort

shell:
	docker-compose exec api python

.PHONY: up down build rebuild logs worker-logs frontend-logs restart seed create-admin \
        migrate rollback migration-status new-migration migration-sql db-shell db-reset \
        test test-coverage health routes shell
