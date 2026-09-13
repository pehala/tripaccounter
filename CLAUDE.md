# Trip Accounter

Holiday expense tracker: a FastAPI JSON API plus a static Preact frontend, behind a
VPN, no accounts. Two tracks that share nothing but the contract.

Start with [`design/ARCHITECTURE.md`](design/ARCHITECTURE.md) — the system, the
layers, how money moves, and where the two halves meet.

| Document | What it fixes |
|---|---|
| [`design/ARCHITECTURE.md`](design/ARCHITECTURE.md) | process, layers, the money pipeline, the contract seam, test topology |
| [`design/DECISIONS.md`](design/DECISIONS.md) | every locked decision and the alternative it beat |
| [`design/API.md`](design/API.md) | the contract. Shared; changing it is a joint decision |
| [`design/ERD.md`](design/ERD.md) | entities, invariants, indexes |
| [`design/BACKEND.md`](design/BACKEND.md) | `app/` — what belongs in which layer, `tests/backend/` |
| [`design/FRONTEND.md`](design/FRONTEND.md) | `static/` — the seven rules, `tests/frontend/` |
| [`design/MOCKAPI.md`](design/MOCKAPI.md) | the mock API behind the Playwright suite — fixture grammar, what the engine does with it |
| [`tests/frontend/fixtures/trip.json`](tests/frontend/fixtures/trip.json) | the canned trip the Playwright suite renders |
| [`tests/backend/fixtures/sheet.csv`](tests/backend/fixtures/sheet.csv) | the example sheet `tools/import_sheet/` is tested against, and the format by example |

**API shapes are generated, never hand-written.** Fields, endpoints and statuses come
from `app/schemas.py` and the routers; `/docs` renders them and `make openapi` writes
the committed `openapi.json`. `design/API.md` holds only the rules a schema cannot
state. Changing a shape means regenerating the spec in the same commit —
`make openapi-check` is a CI job.

## Skills

Repository skills live in `skills/`, surfaced to Claude Code through the
`.claude/skills` symlink. Invoke them by name.

| Skill | Use it when |
|---|---|
| [`writing-unit-tests`](skills/writing-unit-tests/SKILL.md) | **every** change under `tests/` — writing, extending, debugging or reviewing |

**`writing-unit-tests` is mandatory for all unit tests.** Read it before touching
anything under `tests/`; there is no test small enough to skip it. It carries three
references:

| Reference | Content |
|---|---|
| [common-pitfalls.md](skills/writing-unit-tests/references/common-pitfalls.md) | P-1 … P-12 — the specific mistakes, with fixes |
| [anti-patterns.md](skills/writing-unit-tests/references/anti-patterns.md) | AP-1 … AP-6 — shapes that prove nothing |
| [review-conventions.md](skills/writing-unit-tests/references/review-conventions.md) | C-1 … C-28 — what a PR touching `tests/` is measured against |

Writing a test and reviewing it are one job, not two: apply the review conventions
before opening the PR.

## Rules that outrank convenience

1. **The backend emits no presentation.** No HTML, no display strings, no separators,
   no `+` signs, no split phrases. Plain numbers and structured data.
2. **Money is integers inside, plain JSON numbers at the edge.** `bigint` minor units
   in every column, sum, weight and remainder; `money.to_wire` converts once, in the
   serializer, and its output never feeds back in.
3. **No currency conversion server-side.** Balances and stats are per currency. The
   only conversion anywhere is the statistics page multiplying by rates the user
   typed, and it is never persisted.
4. **No "current user".** An item states who paid and what each person owes. Nothing
   is rendered relative to a viewer.
5. **The frontend tolerates unknown fields.** A response carrying a key it has never
   seen renders identically — this is what lets the backend ship first.
6. **The test split is by what a test needs.** `tests/backend/` owns the database and
   every computed number; `tests/frontend/` never starts a database, never imports
   `app.*` (ruff bans it), and never asserts that a number is correct.

## Commands

```bash
make help            # every target
make install         # uv sync --frozen, prod deps only
make install_dev     # uv sync --frozen --group dev + chromium + lefthook
make start_server     # production: backend + static on :8000, no reload
make start_dev_server # backend + static on :8000, reload
make test_backend    # pytest tests/backend -q
make test_frontend   # playwright against fixtures
make test_tools      # the mock API engine
make lint            # ruff check + format check + uv lock --check
make openapi         # regenerate the committed openapi.json from app.openapi()
make openapi-check   # what CI runs: fails if that file is stale
```

Dependencies are `uv` only: `pyproject.toml` + committed `uv.lock`, `uv sync
--frozen` everywhere. No `requirements.txt`, no manual venv, no Node, no npm.

Pre-merge gate is `make lint test_backend`; lefthook runs it on push and CI runs the
same targets.

PR titles follow the same convention as commit subjects: `type(scope): summary`,
lowercase, no trailing period.
