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

For a Postgres-backed deployment — podman quadlets behind an nginx that terminates
TLS and caches the static assets — see [`DEPLOY.md`](DEPLOY.md).

### From source

```bash
make install_dev      # uv sync --frozen --group dev + playwright chromium + git hooks
make migrate          # alembic upgrade head
make seed             # optional: put the demo trip in the database
make start_dev_server # :8000, reload
```

`make test_frontend` runs the Playwright suite against JSON fixtures — no database,
no backend. `make help` lists every target.

### Configuration

Environment variables, all prefixed `TA_`:

| Variable | Default | Meaning |
|---|---|---|
| `TA_DATABASE_URL` | `sqlite:///./dev.db` | SQLAlchemy URL; `postgresql+psycopg://…` for Postgres |
| `TA_STATIC_DIR` | `./static` | directory mounted at `/` |

## Import an existing sheet

`tools/import_sheet/` turns a CSV expense sheet into a trip: it derives the roster,
currencies and countries from the file, works out each row's split, and writes the
whole sheet in **one transaction** — so it either lands complete or not at all.

```bash
# import it
uv run python -m tools.import_sheet SHEET.csv "Trip name" --people Ann Bob

# see what that would do first, without writing anything
uv run python -m tools.import_sheet SHEET.csv "Trip name" --people Ann Bob --dry-run
```

Both forms do the same work and print the same report; `--dry-run` rolls the
transaction back at the end instead of committing it. Because it takes the real path,
a dry run exercises every service call, foreign key and check constraint — what it
reports is what an import would do.

Read the report from the top: it opens with the **index map**, which shows each column
index, the header text found there, and the value it produced on the first row. That
is how you confirm the sheet lines up before trusting the rest.

| Option | Default | Meaning |
|---|---|---|
| `--people NAME...` | — | **required**; one name per owed column, left to right |
| `--start-date` / `--end-date` | — | the trip's dates |
| `--tz ZONE` | `Europe/Prague` | the zone the sheet's times are written in |
| `--dry-run` | off | roll back instead of committing |

[`tests/backend/fixtures/sheet.csv`](tests/backend/fixtures/sheet.csv) is the format
by example — an invented trip whose 24 rows carry no real data and cover every case
the importer distinguishes. The test suite imports that same file, so it cannot drift
from the behaviour it documents.

Columns are read **by index**, never by header text, because header wording is not
stable. Only the roster size moves anything:

| Index | Holds |
|---|---|
| `0`–`6` | name, date, category, payer, amount, currency, ISO-3166-1 alpha-2 country |
| `7`–`8` | ignored |
| `9 + 2i` | what `--people[i]` owes, each followed by a spreadsheet helper column |
| `9 + 2N` | note |
| beyond | ignored — the sheet's own summary and pivot block |

Amounts may be written the way a spreadsheet writes them (`1 162,00`, non-breaking
space and all). Dates may carry a time or not, and may omit the year, which is taken
from whatever the rest of the sheet agrees on. A row splits **equally** when everyone
who owes owes the same amount, and **exactly** otherwise; a person owing nothing is
left out of the split rather than recorded as owing zero.

Every run creates its own trip, so importing the same sheet twice gives two trips
rather than one with everything doubled. Anything unreadable — a missing date, a
country that is not an ISO code, shares adding up to neither the amount nor each
other — is collected, printed, and the run exits `2` **having written nothing**. Fix
the sheet and run again.

## Develop

```bash
make test            # everything: tests/backend, tests/frontend, tests/tools
make lint            # ruff check + format check + uv lock --check + i18n catalogs
make fmt             # ruff format + import fixes
make coverage        # tests/backend under coverage
```

`make lint test_backend` is the pre-merge gate; lefthook runs it on push and CI runs
the same targets.

`make coverage` runs `tests/backend` and `tests/tools` with branch coverage over
`app/` and `tools/`,
prints the missing lines, and writes a machine-readable `coverage.json`. On a pull
request CI measures the base commit the same way and `tools/coverage_delta.py` turns
the two reports into one comment — the total as `base → branch`, then a row per file
that moved more than 0.1 pp. The comment is rewritten on each push. It reports, it
never fails: there is no threshold and coverage is not part of the gate. `app/seed.py`
and the two checkers in `tools/` sit at 0% because `make lint` and `make openapi` run
them instead of a test.

**The API is browsable at `/docs` on a running server**, and that is the shape
reference — every field, endpoint and status is generated from `app/schemas/` and
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
tools/        CSV sheet importer, mock server, OpenAPI snapshot, i18n catalog check
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
