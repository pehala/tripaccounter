.DEFAULT_GOAL := help
.PHONY: help install install_dev lock start_server start_dev_server seed test \
        test_backend test_frontend test_tools lint fmt lock-check migrate migration openapi \
        openapi-check clean

PW := --browser chromium --tracing retain-on-failure \
      --screenshot only-on-failure --output test-results

FILES ?= .

help:            ## list targets
	@grep -E '^[a-zA-Z_-]+:.*##' $(MAKEFILE_LIST) | awk -F':.*## ' '{printf "  %-16s %s\n", $$1, $$2}'

install:         ## uv sync, prod deps only, no dev group
	uv sync --frozen --no-dev

install_dev:     ## uv sync (dev group) + playwright chromium + git hooks
	uv sync --frozen --group dev
	uv run playwright install chromium
	uv run lefthook install

lock:            ## re-resolve uv.lock after editing pyproject.toml
	uv lock

start_server:    ## production: backend + static on :8000, no reload, trusts proxy headers
	uv run fastapi run app/main.py --port 8000 --forwarded-allow-ips '*'

start_dev_server: ## backend + static on :8000, reload
	uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

seed:            ## put the demo trip in the dev DB
	uv run python -m app.seed --demo

test: test_backend test_frontend test_tools   ## everything

test_backend:    ## pytest tests/backend
	uv run pytest tests/backend -q -n 4

test_frontend:   ## playwright suite against fixtures. No DB, no app.
	uv run pytest tests/frontend -q -n 4 $(PW)

test_tools:      ## the test tooling itself: the mock API engine
	uv run pytest tests/tools -q

lint:            ## ruff check + format check + lockfile check + i18n catalog check
	uv run ruff check $(FILES)
	uv run ruff format --check $(FILES)
	$(MAKE) lock-check
	uv run python -m tools.check_i18n

fmt:             ## ruff format + fix imports
	uv run ruff format $(FILES)
	uv run ruff check --fix $(FILES)

lock-check:      ## uv.lock matches pyproject.toml
	uv lock --check

migrate:         ## alembic upgrade head
	uv run alembic upgrade head

migration:       ## new autogenerate revision: make migration m="add foo"
	uv run alembic revision --autogenerate -m "$(m)"

openapi:         ## regenerate the committed openapi.json from app.openapi()
	uv run python -m tools.dump_openapi

openapi-check:   ## fail if the committed openapi.json is stale or untracked
	@$(MAKE) openapi
	@test -z "$$(git status --porcelain -- openapi.json)" || { \
	  git --no-pager diff -- openapi.json; \
	  echo "openapi.json is stale or untracked: run 'make openapi' and commit it"; \
	  exit 1; }

clean:
	rm -rf .venv .pytest_cache .ruff_cache **/__pycache__ dev.db
