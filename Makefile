.PHONY: help init up down restart build logs db-only \
        migrate makemigrations seed superuser \
        shell bash dbshell test lint format clean

.DEFAULT_GOAL := help

help: ## Show available commands
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

# ---------------------------------------------------------------------------
# Setup
# ---------------------------------------------------------------------------

init: ## First-time setup: create .env, build, start, migrate
	@if [ ! -f .env ]; then \
		cp .env.example .env; \
		echo "Created .env from .env.example"; \
	fi
	docker compose up --build -d
	@echo ""
	@echo "  API:     http://localhost:8000/api/v1/"
	@echo "  Admin:   http://localhost:8000/admin/"
	@echo ""

# ---------------------------------------------------------------------------
# Docker
# ---------------------------------------------------------------------------

up: ## Start the stack
	docker compose up -d

down: ## Stop the stack
	docker compose down

restart: ## Restart the stack
	docker compose restart

build: ## Rebuild the images
	docker compose build

logs: ## Follow the logs
	docker compose logs -f

db-only: ## Start only Postgres, for running manage.py in the virtualenv
	docker compose up -d db

# ---------------------------------------------------------------------------
# Django
# ---------------------------------------------------------------------------

migrate: ## Apply migrations
	docker compose exec web python manage.py migrate

makemigrations: ## Create new migrations
	docker compose exec web python manage.py makemigrations

seed: ## Load demo data (idempotent)
	docker compose exec web python manage.py seed_demo_data

superuser: ## Create an admin user
	docker compose exec web python manage.py createsuperuser

shell: ## Open a Django shell
	docker compose exec web python manage.py shell

bash: ## Open a shell in the web container
	docker compose exec web bash

dbshell: ## Open psql on the database
	docker compose exec web python manage.py dbshell

# ---------------------------------------------------------------------------
# Quality
# ---------------------------------------------------------------------------

test: ## Run the test suite
	docker compose run --rm web pytest

lint: ## Check code with ruff
	docker compose run --rm web ruff check .

format: ## Format code with ruff
	docker compose run --rm web ruff format .

# ---------------------------------------------------------------------------
# Housekeeping
# ---------------------------------------------------------------------------

clean: ## Stop the stack and drop the database volume
	docker compose down -v
