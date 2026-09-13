# Trip Accounter

Holiday expense tracker for a group of people who share costs across several
countries and currencies, and settle up once at the end. A FastAPI JSON API plus a
static Preact frontend, served by one process, behind a VPN, with no user accounts.

A trip lives at `/t/{slug}`: add people, currencies and countries once, then log
items. The app tracks who paid and what each person owes, and tells you who should
pay whom when the holiday is over.

## What it does

- **Multi-currency, no conversion server-side.** Balances and settle-up are per
  currency. The statistics page is the only place anything is converted, client-side,
  with rates you type yourself.
- **Splits.** Equal by default; override per item to weighted shares or exact
  amounts. The item form previews the numbers live.
- **Settle-up.** Who pays whom, per currency, rounded exactly once with a zero-sum
  correction — the totals always balance.
- **Statistics.** Group by person, country, currency or label, optionally converted
  to one currency at your own rates.
- **Countries and labels.** Every item is located in one of the trip's countries;
  labels are free-typed, space-separated, auto-created on first use.
- **No "current user".** An item states who paid and what each person owes. Nothing
  is rendered relative to a viewer.
- **English and Czech**, entirely in the frontend. The API has no language at all:
  errors are `{code, params}` with no message text.

Paybacks are deliberately not recorded, and there is no auth — see
[`design/DECISIONS.md`](design/DECISIONS.md) for why.

## Stack

| Part | Choice |
|---|---|
| API | FastAPI under `/api/v1`, pure JSON, Python ≥ 3.13 |
| Storage | SQLAlchemy 2.0 + Alembic; SQLite or Postgres |
| Frontend | Preact + htm as ES modules, Bootstrap 5, **no build step, no Node, no npm** |
| Deps | `uv` only — `pyproject.toml` + committed `uv.lock` |
| Tests | pytest for the backend, Playwright against fixtures for the frontend |

Money is stored as integers in hundredths; computed shares are a SQL view in
micro-units and are never stored. The backend emits data, never presentation.

## Run it

### Docker + SQLite (quickest)

```bash
docker build -t tripaccounter:latest .

docker run -d --name tripaccounter \
  -p 8000:8000 \
  -v tripaccounter-db:/data \
  -e TA_DATABASE_URL=sqlite:////data/dev.db \
  tripaccounter:latest
```

Open <http://localhost:8000/>. The container runs `alembic upgrade head` on every
start, then serves the app; the named volume keeps the database across restarts.
Drop `-v ...` for a throwaway database that resets each run.

```bash
docker logs -f tripaccounter            # startup / migrations
docker stop tripaccounter && docker rm tripaccounter
```

For a Postgres-backed systemd/podman deployment, see [`deploy/README.md`](deploy/README.md).

### From source

```bash
make install_dev      # uv sync --frozen --group dev + playwright chromium + git hooks
make migrate          # alembic upgrade head
make seed             # optional: put the demo trip in the database
make start_dev_server # :8000, reload
```

`make start_ui` serves the frontend alone against JSON fixtures on `:8001` — no
database, no backend. `make help` lists every target.

### Configuration

Environment variables, all prefixed `TA_`:

| Variable | Default | Meaning |
|---|---|---|
| `TA_DATABASE_URL` | `sqlite:///./dev.db` | SQLAlchemy URL; `postgresql+psycopg://…` for Postgres |
| `TA_STATIC_DIR` | `./static` | directory mounted at `/` |

## Develop

```bash
make test_backend    # pytest tests/backend
make test_frontend   # playwright against fixtures, no DB
make lint            # ruff check + format check + uv lock --check + i18n catalogs
make fmt             # ruff format + import fixes
```

`make lint test_backend` is the pre-merge gate; lefthook runs it on push and CI runs
the same targets.

**The API is browsable at `/docs` on a running server**, and that is the shape
reference — every field, endpoint and status is generated from `app/schemas.py` and
the routers. `make openapi` writes the same schema to `openapi.json` at the repo
root; change a shape and regenerate in the same commit, or `make openapi-check`
fails in CI.

Tests split by what they need: `tests/backend/` owns the database and every computed
number, `tests/frontend/` never starts a database and never asserts a number is
correct. Anything under `tests/` follows
[`skills/writing-unit-tests`](skills/writing-unit-tests/SKILL.md).

## Layout

```
app/          FastAPI app — routers/, services/, models, schemas
static/       the frontend: index.html + js/{views,components,i18n}
alembic/      migrations
design/       the architecture (start with ARCHITECTURE.md)
openapi.json  generated from app.openapi(); `make openapi` rewrites it
tests/        backend/ (pytest) and frontend/ (playwright + fixtures)
tools/        mock server, OpenAPI snapshot, i18n catalog check
deploy/       podman quadlet units
```

| Document | What it fixes |
|---|---|
| [`design/ARCHITECTURE.md`](design/ARCHITECTURE.md) | the system: layers, the money pipeline, the contract seam |
| [`design/DECISIONS.md`](design/DECISIONS.md) | every locked decision and the alternative it beat |
| [`design/API.md`](design/API.md) | the contract between the two halves |
| [`design/ERD.md`](design/ERD.md) | entities, invariants, indexes |
| [`CLAUDE.md`](CLAUDE.md) | the rules that outrank convenience |

## Security

There is no authentication. Anyone who can reach the host can read and modify every
trip. That is acceptable only while a VPN is the sole path in — **do not expose the
port publicly.**
