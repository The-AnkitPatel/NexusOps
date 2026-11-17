.PHONY: help install dev init-db test eval lint fmt type check run-api run-ui docker-build docker-up clean

PY ?= python

help:
	@echo "install     install runtime deps (editable)"
	@echo "dev         install runtime + dev deps + pre-commit"
	@echo "init-db     (re)build the enterprise SQLite database"
	@echo "test        run the pytest suite"
	@echo "lint        ruff lint"
	@echo "fmt         ruff format"
	@echo "type        mypy type check"
	@echo "check       lint + type + test (what CI runs)"
	@echo "run-api     start the FastAPI gateway on :8000"
	@echo "run-ui      start the Streamlit cockpit on :8501"
	@echo "docker-up   build and run API + UI via docker compose"

install:
	$(PY) -m pip install -e .

dev:
	$(PY) -m pip install -e ".[dev,llm,otlp]"
	pre-commit install

init-db:
	$(PY) data/init_db.py

test:
	$(PY) -m pytest

eval:
	$(PY) -m evals.run_eval --update-readme

lint:
	ruff check .

fmt:
	ruff format .

type:
	mypy

check: lint type test

run-api:
	$(PY) -m uvicorn nexus.api.server:app --reload --port 8000

run-ui:
	streamlit run ui/app.py

docker-build:
	docker build -t nexusops:latest .

docker-up:
	docker compose up --build

clean:
	rm -rf .pytest_cache .ruff_cache .mypy_cache **/__pycache__
