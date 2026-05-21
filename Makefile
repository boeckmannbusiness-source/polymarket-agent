.PHONY: help install dev db-upgrade db-migrate run-api run-workers lint test clean

help:
	@echo "Polymarket Intelligence Agent - Makefile"
	@echo ""
	@echo "Targets:"
	@echo "  install       Install Python dependencies"
	@echo "  dev           Install dev dependencies"
	@echo "  db-upgrade    Run Alembic migrations"
	@echo "  db-migrate    Create new Alembic migration"
	@echo "  run-api       Start FastAPI dev server"
	@echo "  run-ingester  Start data ingestion worker"
	@echo "  run-whale     Start whale tracking worker"
	@echo "  run-agent     Start agent orchestrator"
	@echo "  lint          Run linting"
	@echo "  test          Run tests"
	@echo "  clean         Clean cache and build artifacts"

install:
	pip install -e .

dev: install
	pip install -e ".[dev]"

db-upgrade:
	alembic upgrade head

db-migrate:
	alembic revision --autogenerate -m "$(name)"

run-api:
	uvicorn app.main:app --reload --port 8000

run-ingester:
	python -m app.ingesters.polymarket_ws

run-whale:
	python -m app.services.whale_service

run-agent:
	python -m app.agents.orchestrator

lint:
	ruff check backend/
	mypy backend/

test:
	pytest backend/app/tests/ -v --cov=app

clean:
	rm -rf __pycache__ .pytest_cache .coverage htmlcov *.egg-info
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
