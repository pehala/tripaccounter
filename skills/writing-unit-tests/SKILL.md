---
name: writing-unit-tests
description: >-
  The single reference for every test in Trip Accounter — use it for ALL work
  under tests/, without exception. Covers writing, extending, debugging and
  reviewing pytest tests: functional tests in tests/backend/ that drive the API
  through FastAPI's TestClient, the one direct-call exception (money
  arithmetic), SQLAlchemy session fixtures, in-memory DB isolation, the
  wire-JSON trip fixture, integer-money assertions, the code+params error
  envelope with no message text, the no-presentation rule, the
  backend/frontend test split, common pitfalls, anti-patterns, and the review
  conventions to apply before opening a PR.
---

# Writing Backend Tests

Trip Accounter is a FastAPI JSON API over SQLAlchemy 2.0 + SQLite, with a static
Preact frontend that shares nothing with it but the contract in `design/API.md`.

All backend tests go in `tests/backend/`. They run with no browser, no network, and
no frontend present: `make test_backend`.

**This skill governs every test in the repository.** Read it before writing,
extending, debugging or reviewing anything under `tests/` — there is no test small
enough to skip it, and the review conventions in
[review-conventions.md](references/review-conventions.md) are what a PR touching
`tests/` is measured against. The file-by-file map of what is covered where is
`design/BACKEND.md` §6.

## Essential Principles

### Functional First

**A backend test drives the app the way a client does**: a request through
`TestClient`, an assertion on the status code and the JSON body. The unit under test
is a *behaviour of the API*, not a Python function. `app/services/*` has no test file
of its own — a service is covered by the endpoints that use it, because that is the
only place its output is observable to anyone.

Why this is the default here:

1. **The contract is the deliverable.** `design/API.md` is a promise about requests
   and responses. A test that calls `splits.build()` proves nothing about whether
   `POST /items` honours it; a test that posts an item proves both.
2. **Services are expected to move.** Balances are SQL aggregates, `settle` is
   iterative, `stats` will grow groups. Tests written against the wire survive those
   rewrites; tests written against function signatures have to be rewritten
   alongside, which is how a suite becomes the thing nobody dares refactor.
3. **Setup goes through the write path.** A test that builds its trip with
   `POST /trips` and `POST /items` cannot construct a state the API itself would
   reject — no orphan share, no item without a country, no float in a column. ORM
   inserts in setup can, and then the test guards a state production never reaches.

**The one direct-call exception is `tests/backend/test_money.py`**: `parse_amount`,
`to_wire` and `allocate`, where the interesting cases are combinatorial — hundreds of
amount × decimals × weight combinations — and routing each through HTTP would buy
nothing but runtime. It is the only backend test file that imports a service.

**Not tested at all**: private helpers, SQL text, the shape of an ORM object, that a
service was called. If a behaviour cannot be observed in a response, in an export
file, or in the database after a request, it is not a behaviour.

### The Test Split Is by What a Test Needs

`tests/backend/` owns the database, the migrations, and every number the app
computes. `tests/frontend/` owns rendering and interaction, never starts a database
or imports `app.*`, and never asserts that a computed number is correct.

If you are about to assert that 18 400 ISK across four people is 4 600 each, that
assertion belongs here, in `tests/backend/`, and nowhere else. If you are about to
assert that a `+` sign appears in front of a credit, that is a frontend test — the
API emits no presentation at all.

### The Backend Has No Sentences

Every error is `{code, params}`. There is no `message` key, no template, no fallback
word, no locale — see `design/API.md` §1 and rule 1 of `CLAUDE.md`. So:

- Assert `error.code`, `fields[<name>].code` and `params`, never text.
- A test that greps a response for a phrase is asserting a regression; don't add a
  standing "no such phrase exists" test for it — assert the concrete shape (`code`,
  `params`) that would break instead.
- Codes are the stable identifiers clients switch on. `test_errors.py` holds
  `services/errors.py`, `design/API.md` §4 and the codes the suite actually
  triggered against each other, so a code cannot drift out of the contract.

### No Network, Ever

Backend tests make zero outbound calls. Nothing in `app/` legitimately needs the
network: no cloud SDK, no external API, no remote host. A test that is slow or hangs
is either hitting a real filesystem path it should not, or looping in `wait`-style
code.

The one external-shaped surface is `services/geo.py`, which *parses* a maps URL — it
must never fetch one, and it is exercised by posting an item with a `map_url`. If a
test for it would need `httpx` or `requests`, the production code took a wrong turn;
say so rather than mocking a fetch into place.

### Use pytest, Not unittest.TestCase, and No Test Classes

All tests are module-level `def test_*` functions using bare `assert`, pytest
fixtures, and `@pytest.mark.parametrize`. `unittest.TestCase` breaks fixture
injection, autouse fixtures, and parametrize. Grouping classes (`class TestMoney:`)
add nothing in pytest — group with a comment banner instead (see AP-4).

### Every Test Is Isolated

Each test gets its own database. The `session` fixture creates the schema in an
in-memory SQLite engine per test and drops it in teardown, so no test sees another
test's trip, and no test depends on ordering. Never write to `dev.db`, never reuse
a module-level `Session`, never let a test depend on the demo seed unless it
requested the seed fixture.

Environment is the other shared surface: `app/config.py` is `pydantic-settings`, so
it reads the process environment. Use `monkeypatch.setenv` and re-instantiate the
settings object; never assign to `os.environ` directly.

### Mock at the Boundary, Not the Logic

The boundary in this app is narrow: the clock, the filesystem, and randomness.
Everything else — the session, the services, the routers — is cheap to run for real,
so run it for real. Patching `services.splits.build` while testing a router means
the router test proves nothing about splits and will keep passing when `build`
breaks.

Never reimplement production logic inside a test helper. A `FakeAllocator` that
redoes largest-remainder, or a test that recomputes the expected split with the same
algorithm the code uses, tests the copy and not the code (AP-6). Write the expected
numbers as literals.

### Money Is Integers; Assert Integers

Every column, sum, weight and remainder is `bigint` minor units. `money.to_wire` is
the only place a number leaves integer form, and it is called once, at the
serializer edge.

So: assert the exact JSON value in functional tests, and exact minor units in
`test_money.py`. Never assert a float with `==` after arithmetic, never use
`pytest.approx` to paper over a rounding bug — an approximate money assertion is a
missing money assertion. `to_wire` with `decimals == 0` must yield an `int`;
`assert to_wire(18400, decimals=0) == 18400` passes for `18400.0` too, so assert the
type as well when that is the behaviour under test.

### The API Emits No Presentation

No key ending in `_display`, no thousands separators, no leading `+`, no split
phrase, no flag glyph in a place the contract says is an ISO code. There is no
standing static check for this — when you add a response field, assert its exact
value in the functional test that exercises it, so a formatted string shows up
there instead.

### Time and Randomness Are Inputs, Not Ambient

`occurred_at`, `created_at` and the `by_day` grouping all depend on a clock. Send the
datetime in the request body, or freeze it with a fixture — never assert against
`date.today()` computed inside the test as well as inside the code, because that
hides an off-by-one at midnight and makes the test pass for the wrong reason.

`money.allocate` has a deterministic tie-break by `sort_order`. Tests must pin that
order explicitly; a test that passes only because dict iteration happened to agree
is a flake waiting for a schema change.

### No Underscore-Prefixed Names

A test module has no external callers, so `_MODULE`, `_make_trip` and `_AMOUNT`
protect nothing and cost readability. If a test needs to import or patch an
underscore-prefixed name from `app/`, that name is public API in practice — rename
it public on the production side in the same change.

## When to Use

- Creating a new test file in `tests/backend/`
- Adding cases to an existing `tests/backend/` module
- Testing an endpoint in `app/routers/` through `client` — which is how every
  service in `app/services/` gets tested too
- Adding arithmetic cases to `test_money.py`
- Setting up or extending fixtures in `tests/backend/conftest.py`
- Debugging a backend test that fails, is slow, or is order-dependent

## When NOT to Use

- Writing Playwright tests for the UI — those live in `tests/frontend/`, run against
  canned fixtures and `tools/mockserver.py`, and are described in
  `design/FRONTEND.md` §7
- Asserting rendering, formatting or interaction — the backend has none
- Changing the contract — `design/API.md` moves first and `make openapi`
  regenerates the spec, in the same commit (see `design/ARCHITECTURE.md` §5)
- Fixing production bugs — edit `app/` directly

## Quick Reference: Test Infrastructure

Fixtures live in `tests/backend/conftest.py`. Check it before writing any setup —
the reuse rule below is the most-broken one in review.

| Fixture | Scope | Purpose |
|---|---|---|
| `engine` | session | In-memory SQLite engine with the models' metadata created |
| `session` | function | A `Session` on a per-test transaction, rolled back in teardown |
| `client` | function | `TestClient(app)` with the `get_session` dependency overridden to `session` |
| `trip` | function | **The trip JSON returned by one `POST /trips`** — 4 people, ISK + EUR, one country. A dict, not an ORM object |
| `people` / `currencies` / `countries` | function | `trip["people"]` / `["currencies"]` / `["countries"]` — request the narrow fixture instead of indexing `trip` when that's all a test needs |
| `currency` / `country` | function | The trip's primary currency (ISK) / its one country (Iceland) |
| `item_body` | function | Builder for a valid item write body against `trip`, so a test overrides only the field it is about |
| `error_codes` | session, autouse | Records every `code` seen in a `4xx`/`5xx` body; `test_errors.py` reads it at the end of the run |
| `frozen_clock` | function | The injected clock the app reads for `occurred_at`/`created_at` defaults; set it, never patch `datetime` |
| `monkeypatch` | function | pytest built-in — env vars, attributes |
| `tmp_path` | function | pytest built-in — export files, DB files, anything on disk |

Rules of use:

- **`trip` is wire JSON, so read it like a client**: `trip["slug"]`,
  `trip["people"][0]["id"]`. That is what makes `DetachedInstanceError` after a
  request impossible, and it keeps the setup honest — anything the fixture holds, a
  client could have got from the API.
- **A test that touches no database asks for no session.** `test_money.py` calls pure
  functions with plain inputs. Requesting `session` "just in case" makes a fast test
  slow and hides what it depends on.
- **Router tests use `client`, not `httpx.AsyncClient` by hand.** `client` already
  wires the session override, so the request and the assertions see one transaction.
- **Build the two or three rows the behaviour needs, through the API.** `trip` plus
  a couple of `POST /items` calls is the whole setup, and it keeps what the test
  depends on visible in the test.

## Quick Reference: Patterns

### Pattern 1: Arithmetic — parametrize, direct call

```python
import pytest

from app.services.money import parse_amount


@pytest.mark.parametrize(
    ("raw", "decimals", "expected"),
    [
        pytest.param("18400.50", 2, 1840050, id="canonical-two-decimals"),
        pytest.param("18400", 0, 18400, id="zero-decimal-currency"),
        pytest.param("0.05", 2, 5, id="sub-unit"),
    ],
)
def test_parse_amount(raw, decimals, expected):
    """A canonical decimal string becomes exact minor units for the currency's precision."""
    assert parse_amount(raw, decimals=decimals) == expected
```

`parse_amount` accepts `^-?[0-9]+(\.[0-9]+)?$` and nothing else. `"18 400,50"` and
`"18,400.50"` are **rejected**, not normalized — only the client knows the locale the
user typed in (`design/API.md` §1).

### Pattern 2: Rejection — assert the code and params, never text

```python
from app.services.errors import FieldError


def test_parse_amount_too_many_decimals_rejected():
    """ISK has no minor unit, so 18.005 is not a truncation, it is an error."""
    with pytest.raises(FieldError) as raised:
        parse_amount("18.005", decimals=2)

    assert raised.value.code == "invalid_amount"
    assert raised.value.params == {"decimals": 2}
```

The backend carries no sentences, so there is no message to match — `code` and
`params` are the contract, and `design/API.md` §4 is the authoritative list.

### Pattern 3: The default shape — a request through `client`

```python
def test_exact_split_off_by_one_is_rejected(client, trip, item_body):
    """An exact split that misses the total by a minor unit fails with the diff."""
    response = client.post(
        f"/api/v1/trips/{trip['slug']}/items",
        json=item_body(
            amount="18400",
            split_mode="exact",
            shares=[
                {"person_id": trip["people"][0]["id"], "amount": "9200"},
                {"person_id": trip["people"][1]["id"], "amount": "9199"},
            ],
        ),
    )

    assert response.status_code == 422
    assert response.json() == {
        "error": {
            "code": "validation_error",
            "params": {},
            "fields": {
                "shares": {"code": "sum_mismatch", "params": {"diff": 1, "currency_code": "ISK"}},
            },
        }
    }
```

Assert the whole envelope the contract promises — status, `error.code`, `params` and
every `fields` entry — not just the status code.

### Pattern 4: A computed number, through the endpoint that publishes it

```python
def test_balances_net_sums_to_zero(client, trip, item_body):
    """Every currency's net column sums to exactly zero; a non-zero sum is a lost minor unit."""
    client.post(f"/api/v1/trips/{trip['slug']}/items", json=item_body(amount="18400"))

    balances = client.get(f"/api/v1/trips/{trip['slug']}/balances").json()["balances"]

    for block in balances:
        assert sum(person["net"] for person in block["people"]) == 0
```

The state is built with a request, so the test exercises the same write path
production does. No ORM inserts, no `session` fixture, nothing to keep in sync with
`models.py`.

### Pattern 5: Dates are request data

```python
def test_by_day_groups_on_occurred_at(client, trip, item_body):
    """Grouping uses occurred_at, not the row's creation time."""
    for occurred_at in ("2026-07-01T09:00:00", "2026-07-01T20:00:00", "2026-07-02T09:00:00"):
        client.post(f"/api/v1/trips/{trip['slug']}/items", json=item_body(occurred_at=occurred_at))

    stats = client.get(f"/api/v1/trips/{trip['slug']}/stats").json()["stats"]

    assert [row["date"] for row in stats[0]["by_day"]] == ["2026-07-01", "2026-07-02"]
```

Dates go in the request. If the code under test defaults to "now" and that default is
the behaviour under test, inject the clock rather than patching `datetime` globally.

### Pattern 6: Files go to `tmp_path`

```python
def test_csv_export_one_row_per_share(tmp_path, client, trip, item_body):
    """The CSV is share-grained: four people on one item is four rows, not one."""
    client.post(f"/api/v1/trips/{trip['slug']}/items", json=item_body(amount="184.00"))
    response = client.get(f"/api/v1/trips/{trip['slug']}/export", params={"format": "csv"})
    target = tmp_path / "trip.csv"
    target.write_text(response.text)

    rows = list(csv.DictReader(target.read_text().splitlines()))
    assert len(rows) == 4
```

Only write under `tmp_path`, never next to `dev.db`, and pin the expected row count
as a literal rather than recomputing it from the trip.

### Pattern 7: Settings from the environment

```python
def test_debug_flag_from_env(monkeypatch):
    monkeypatch.setenv("TA_DEBUG", "1")
    assert Settings().debug is True
```

`Settings()` is re-instantiated inside the test; a module-level singleton read at
import time cannot see `monkeypatch` (see P-7).

## Debugging

### Test passes alone, fails in the suite

Shared state. In order of likelihood: a module-level `Session` or engine, a settings
object built at import time, a test that committed instead of letting the fixture
roll back, or a cached `lru_cache` on a service function that survives the test.
Clear caches in an autouse teardown fixture, post-`yield` only.

### `DetachedInstanceError` after the request

`TestClient` closed the session, and the test then touched a lazy relationship on an
ORM object. Assert on the response JSON, not on ORM objects — the response is what
the contract promises anyway, and the `trip` fixture already hands you JSON.

### Numbers are off by one minor unit

`allocate` distributes the remainder by `sort_order`; the expected values in the test
have to follow the same order. If they do and the sum is still wrong, the bug is
real — that is exactly what these tests exist to catch, so do not "fix" it by
loosening the assertion.

### A float appeared in the database

`to_wire` output fed back into a write path. Trace where the value re-entered; the
rule is one-way, integers in, numbers out.

## Test Naming

`test_<behaviour>_<scenario>_<expected>`:

```python
def test_parse_amount_empty_string_raises(): ...
def test_allocate_remainder_follows_sort_order(): ...
def test_delete_country_in_use_returns_409(): ...
def test_preview_split_matches_saved_item(): ...
```

Not `test_money()`, `test_it_works()`, `test_case_2()`.

Every test gets a one-sentence docstring stating the behaviour and expected outcome;
it is what `pytest -v` prints on failure. If you cannot state the failure the test
guards against, the test is not worth adding.

## Running Tests

```bash
make test_backend                                  # the whole backend suite
uv run pytest tests/backend/test_splits.py -q      # one file
uv run pytest tests/backend/test_splits.py::test_equal_split_pads_the_roster -v
uv run pytest tests/backend -q -x                  # stop at first failure
uv run pytest tests/backend --cov=app --cov-report=term-missing
make lint                                          # ruff check + format check + uv lock --check
```

`make test` also runs the Playwright suite; while iterating on backend tests, use
`make test_backend`.

## Reference Index

| File | Content | Read it when |
|---|---|---|
| [common-pitfalls.md](references/common-pitfalls.md) | Pitfalls P-1 … P-12, before/after | a test fails oddly, or the setup feels awkward |
| [anti-patterns.md](references/anti-patterns.md) | Anti-patterns AP-1 … AP-6, before/after | deciding the shape of a new test file |
| [review-conventions.md](references/review-conventions.md) | Review conventions C-1 … C-28 | before opening a PR that touches `tests/`, and when reviewing one |

| Workflow | Purpose |
|---|---|
| [write-a-unit-test.md](workflows/write-a-unit-test.md) | 4-phase process for writing a new backend test |

## Success Criteria

- [ ] Lives in `tests/backend/` as `test_*.py`, in the file `design/BACKEND.md`
      §6 assigns to that behaviour
- [ ] Drives the app through `client`; a direct service import is `test_money.py`
      only, or comes with a sentence saying why
- [ ] State built through API requests, not ORM inserts
- [ ] pytest style: module-level functions, bare `assert`, fixtures, parametrize
- [ ] Requests only the fixtures it uses; no `session` for a pure function
- [ ] Makes no network calls and writes no file outside `tmp_path`
- [ ] Asserts the whole error envelope as `{code, params, fields}` — never a message,
      never text
- [ ] Money asserted as exact integers or exact JSON values — no `approx`
- [ ] Dates and orderings pinned explicitly, never read from the ambient clock
- [ ] Passes in isolation and in any order
- [ ] All imports at the top of the file
- [ ] One-sentence docstring on every test
- [ ] `make lint test_backend` is clean
- [ ] Checked against [review-conventions.md](references/review-conventions.md)
      before the PR — that pass is part of writing the test, not a later step
