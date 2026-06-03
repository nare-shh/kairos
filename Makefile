# Kairos — Developer Commands
# Run: make <command>
# Example: make up  |  make migrate  |  make logs

# ── Docker ────────────────────────────────────────────────────────────────────
up:
	docker-compose up -d

down:
	docker-compose down

build:
	docker-compose build api

rebuild:
	docker-compose build --no-cache api

logs:
	docker-compose logs -f api

restart:
	docker-compose restart api

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
	docker-compose exec postgres psql -U kairos_user -c "DROP DATABASE IF EXISTS kairos_db;"
	docker-compose exec postgres psql -U kairos_user -c "CREATE DATABASE kairos_db;"
	make migrate

# ── Tests ─────────────────────────────────────────────────────────────────────
test:
	docker-compose exec api pytest tests/ -v

test-coverage:
	docker-compose exec api pytest tests/ --cov=app --cov-report=html

# ── Utilities ─────────────────────────────────────────────────────────────────
health:
	curl -s http://localhost:8000/health | python -m json.tool

routes:
	curl -s http://localhost:8000/openapi.json | python -m json.tool | grep '"/' | sort

shell:
	docker-compose exec api python

.PHONY: up down build rebuild logs restart migrate rollback migration-status \
        new-migration migration-sql db-shell db-reset test test-coverage health routes shell
