.DEFAULT_GOAL := help
.PHONY: help install install_dev lock start_server start_dev_server seed test \
        test_backend test_frontend test_tools lint fmt lock-check migrate migrate-check \
        migration openapi openapi-check clean

PW := --browser chromium --tracing retain-on-failure \
      --screenshot only-on-failure --output test-results

FILES ?= .

RUN := uv run python -m

help:            ## list targets
	@grep -E '^[a-zA-Z_-]+:.*##' $(MAKEFILE_LIST) | awk -F':.*## ' '{printf "  %-16s %s\n", $$1, $$2}'

install:         ## uv sync, prod deps only, no dev group
	uv sync --frozen --no-dev

install_dev:     ## uv sync (dev group) + playwright chromium + git hooks
	uv sync --frozen --group dev
	$(RUN) playwright install chromium
	uv run lefthook install

lock:            ## re-resolve uv.lock after editing pyproject.toml
	uv lock

start_server:    ## production: backend + static on :8000, no reload, trusts proxy headers
	$(RUN) fastapi run app/main.py --port 8000 --forwarded-allow-ips '*'

start_dev_server: ## backend + static on :8000, reload
	$(RUN) uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

seed:            ## put the demo trip in the dev DB
	$(RUN) app.seed --demo

test: test_backend test_frontend test_tools   ## everything

test_backend:    ## pytest tests/backend
	$(RUN) pytest tests/backend -q -n 4

test_frontend:   ## playwright suite against fixtures. No DB, no app.
	$(RUN) pytest tests/frontend -q -n 4 $(PW)

test_tools:      ## the test tooling itself: the mock API engine
	$(RUN) pytest tests/tools -q

lint:            ## ruff check + format check + lockfile check + i18n catalog check
	$(RUN) ruff check $(FILES)
	$(RUN) ruff format --check $(FILES)
	$(MAKE) lock-check
	$(RUN) tools.check_i18n

fmt:             ## ruff format + fix imports
	$(RUN) ruff format $(FILES)
	$(RUN) ruff check --fix $(FILES)

lock-check:      ## uv.lock matches pyproject.toml
	uv lock --check

migrate:         ## alembic upgrade head
	$(RUN) alembic upgrade head

migrate-check:   ## fail if models drifted from migrations (alembic check), against a scratch DB
	@tmp=$$(mktemp -u --suffix .db); \
	trap 'rm -f "$$tmp"' EXIT; \
	TA_DATABASE_URL="sqlite:///$$tmp" $(RUN) alembic upgrade head && \
	TA_DATABASE_URL="sqlite:///$$tmp" $(RUN) alembic check

migration:       ## new autogenerate revision: make migration m="add foo"
	$(RUN) alembic revision --autogenerate -m "$(m)"

openapi:         ## regenerate the committed openapi.json from app.openapi()
	$(RUN) tools.dump_openapi

openapi-check:   ## fail if the committed openapi.json is stale or untracked
	@$(MAKE) openapi
	@test -z "$$(git status --porcelain -- openapi.json)" || { \
	  git --no-pager diff -- openapi.json; \
	  echo "openapi.json is stale or untracked: run 'make openapi' and commit it"; \
	  exit 1; }

clean:
	rm -rf .venv .pytest_cache .ruff_cache **/__pycache__ dev.db
