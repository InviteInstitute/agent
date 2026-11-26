# Run `make` to list the targets. Where docker needs sudo: make dev COMPOSE='sudo docker compose'
COMPOSE ?= docker compose
TEST_DATABASE_URL ?= postgresql://agent:$(shell sed -n 's/^POSTGRES_PASSWORD=//p' .env 2>/dev/null)@127.0.0.1:5435/agent_test

.DEFAULT_GOAL := help
.PHONY: help install dev down test lint format

help: ## List the targets
	@grep -hE '^[a-z-]+:.*## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*## "}; {printf "  %-10s %s\n", $$1, $$2}'

install: ## Install the server for development (in server/.venv)
	cd server && uv venv -q && uv pip install -e ./vendor/agent-lm-packages -e '.[dev]'

dev: ## Start Postgres and the API with reload, on :8005
	$(COMPOSE) up --build

down: ## Stop the dev stack
	$(COMPOSE) down

test: ## Run the tests (the database ones use the dev Postgres's agent_test database)
	$(COMPOSE) exec -T db createdb -U agent agent_test 2>/dev/null || true
	cd server && TEST_DATABASE_URL=$(TEST_DATABASE_URL) .venv/bin/pytest -q

lint: ## Check the code with ruff
	cd server && .venv/bin/ruff check agent tests && .venv/bin/ruff format --check agent tests

format: ## Format the code with ruff
	cd server && .venv/bin/ruff check --fix agent tests && .venv/bin/ruff format agent tests
