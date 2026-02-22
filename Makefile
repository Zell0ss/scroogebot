PYTHON := .venv/bin/python
PYTEST := .venv/bin/pytest
ALEMBIC := .venv/bin/alembic

.PHONY: help run seed migrate test test-v test-cov lint install push logs

help:          ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*##' $(MAKEFILE_LIST) | awk 'BEGIN{FS=":.*##"} {printf "  \033[36m%-14s\033[0m %s\n", $$1, $$2}'

# ── Bot ───────────────────────────────────────────────────────────────────────

run:           ## Start the bot
	$(PYTHON) scroogebot.py

# ── Database ──────────────────────────────────────────────────────────────────

migrate:       ## Apply pending Alembic migrations
	$(ALEMBIC) upgrade head

seed:          ## Seed baskets and assets from config.yaml (idempotent)
	$(PYTHON) -m src.db.seed

db-setup: migrate seed  ## Full DB setup: migrate then seed

# ── Tests ─────────────────────────────────────────────────────────────────────

test:          ## Run test suite (quiet)
	$(PYTEST) tests/ -q

test-v:        ## Run test suite (verbose)
	$(PYTEST) tests/ -v

test-cov:      ## Run tests with coverage report
	$(PYTEST) tests/ --cov=src --cov-report=term-missing -q

# ── Dev ───────────────────────────────────────────────────────────────────────

install:       ## Install all dependencies (including dev + backtest extras)
	pip install -e ".[dev,backtest]"

lint:          ## Run ruff linter (if installed)
	@$(PYTHON) -m ruff check src/ tests/ 2>/dev/null || echo "ruff not installed — pip install ruff"

logs:          ## Tail the bot log
	tail -f scroogebot.log

push:          ## Push current branch to origin
	git push origin $(shell git rev-parse --abbrev-ref HEAD)
