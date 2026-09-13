# Test Review Conventions

What gets asked for when a test file in this repository is reviewed. Read this before
opening a PR that touches `tests/`, and when reviewing someone else's test file —
each rule is cheaper to apply than to be asked for.

The [SKILL](../SKILL.md) covers how to write the test; this covers whether it earns
its place. See also [common-pitfalls.md](common-pitfalls.md) and
[anti-patterns.md](anti-patterns.md).

---

## 1. What Not to Test

### C-1: Do not test configuration or constants

Settings defaults, a currency's `decimals`, the page-size constant, a sort order
literal: these change on purpose, and a test that pins them only forces an edit to
the assertion when they do.

❌ **Bad:**
```python
def test_settings_defaults():
    assert Settings().debug is False
    assert Settings().database_url == "sqlite:///dev.db"
```

✅ **Good:** delete it. If the constant drives a branch — a zero-decimal currency
taking a different rounding path — test the branch with the constant both ways.

### C-2: Do not test the framework

Pydantic rejecting a string where an `int` is declared, SQLAlchemy persisting a
column, FastAPI returning 405 for the wrong method, `TestClient` parsing JSON: all
tested upstream, none of it ours. Test the rule *we* added — a row of the
`design/API.md` §4 table with its `code` and `params`, the `409 in_use` guard, the
`country_id` requirement being enforced before the DB gets a chance.

❌ **Bad:**
```python
def test_item_amount_must_be_a_number(client, trip):
    response = client.post(url, json={"amount": {"nested": "object"}})
    assert response.status_code == 422
```

✅ **Good:** spend the lines on `"18.005"` for a 2-decimal currency, on `"-5"`, on
`""`, on `"18 400,50"` — the inputs a client actually sends, and the exact `code` and
`params` it switches on.

### C-3: Do not test a copy of the code

A helper in the test directory that re-implements a service, an expected value
computed by calling the code under test, or a functional test that derives its
expected `owed` figures by dividing `amount` by the roster size — all verify the
mirror. Write literal expectations. If that is impossible without rebuilding the setup
by hand, the production code needs a seam first; say so and defer the test.

### C-4: Every test names the failure it guards against

If the one-line docstring cannot state what breaks when this test goes red, do not
add the test. Tests that get removed in review for lacking one: a subclass "inherits
the parent method", a dataclass "has the fields it declares", a route "is
registered", a docstring describing the opposite of the body.

### C-5: No sleeping, no elapsed-time assertions

`time.sleep(0.2)` then `assert calls >= 2`, or `assert elapsed < 1`, depends on
scheduler luck and flakes in CI. Nothing in this app is concurrent enough to need it.
If a timeout or interval is the subject, inject it as an argument.

### C-6: No real paths, no real hosts, no production data

`sqlite:///dev.db`, a path under `~`, a live maps URL fetched instead of parsed, the
deployment host: all couple a test to a machine. Use `tmp_path`, the in-memory
engine, and obviously-fake hosts in the `geo` corpus.

### C-7: Do not assert presentation

The API emits no `_display` keys, no separators, no `+` signs, no split phrases and
no flag glyphs where the contract says ISO code. A backend test asserting a formatted
string is asserting a bug. Formatting is `tests/frontend/test_fmt.py`; here, catch a
regression by asserting the exact field value in the functional test that covers it,
not with a standing static scan.

---

## 2. Deduplication and Parametrization

### C-8: Parametrize instead of near-duplicate functions

Same body, different literals: one test with `pytest.param(..., id=...)` per case.
A boolean `if` inside a test body is a sign the branch should be another parametrize
argument.

❌ **Bad:**
```python
def test_trip_slug_spaces(client):
    assert (
        client.post("/api/v1/trips", json={**TRIP_BODY, "name": "Iceland 2026"}).json()["trip"][
            "slug"
        ]
        == "iceland-2026"
    )


def test_trip_slug_accents(client):
    assert (
        client.post("/api/v1/trips", json={**TRIP_BODY, "name": "Île de Ré"}).json()["trip"]["slug"]
        == "ile-de-re"
    )
```

✅ **Good:**
```python
@pytest.mark.parametrize(
    ("name", "expected"),
    [
        pytest.param("Iceland 2026", "iceland-2026", id="spaces-to-hyphens"),
        pytest.param("Île de Ré", "ile-de-re", id="accents-folded"),
    ],
)
def test_trip_slug(client, name, expected):
    """A trip name becomes a URL-safe slug with accents folded and spaces hyphenated."""
    response = client.post("/api/v1/trips", json={**TRIP_BODY, "name": name})

    assert response.json()["trip"]["slug"] == expected
```

### C-9: One scenario per case

Four independent `assert parse_amount(...) == ...` lines in one function stop at the
first failure and hide the other three. Make them parametrize cases. If shared setup
motivated the grouping, move the setup into a fixture so it still runs per case.

### C-10: Merge near-duplicates; fold single-assert tests into their neighbour

"How is this different from the test above?" is the most common review question on a
new test file. Same setup and call with one extra assertion: add the assertion to the
existing test. A standalone test asserting one thing about state the previous test
already produced belongs at the end of that test. Keep a look-alike only when a real
branch differs, and say which in the docstring.

---

## 3. Fixtures and Setup

### C-11: Setup longer than the assertions means extract a fixture

When arrange dominates, the behaviour under test is buried. Target shape: two or
three lines of arrange, one call, the assertions.

### C-12: Repeated setup becomes a fixture; layer fixtures

The same three lines building a trip in two tests is a fixture. A variant takes the
base fixture as an argument rather than copying its body.

```python
@pytest.fixture()
def zero_decimal_trip(client):
    """A trip whose only currency is ISK, so every amount is whole minor units."""
    body = {**TRIP_BODY, "currencies": [{"code": "ISK", "decimals": 0, "is_primary": True}]}
    return client.post("/api/v1/trips", json=body).json()["trip"]
```

### C-13: `make_*` helpers are fixtures

`def make_item(): ...` called from every test should be an `item` fixture, or a
factory fixture when the tests need several. Fixtures compose, get teardown, and can
take `session`, `tmp_path` or `monkeypatch` — a bare function cannot.

```python
@pytest.fixture()
def post_item(client, trip, item_body):
    def post(amount, payer_id=None, occurred_at="2026-07-01T19:30:00", **overrides):
        body = item_body(
            amount=amount,
            occurred_at=occurred_at,
            payer_id=payer_id or trip["people"][0]["id"],
            **overrides,
        )
        response = client.post(f"/api/v1/trips/{trip['slug']}/items", json=body)
        assert response.status_code == 201
        return response.json()["item"]

    return post
```

### C-14: Reuse the existing infrastructure before adding any

Check `tests/backend/conftest.py` before writing a fixture, and
`tests/frontend/conftest.py` before writing a page helper. A helper needed by two
files moves to the `conftest.py` under a public name. Test modules are not
libraries — never import a helper from one `test_*.py` into another.

### C-15: `monkeypatch` for environment, `tmp_path` for files

`os.environ[...] = ...` leaks into the next test; a hard-coded path leaks into the
next run. Also delete the setting the code *writes*: if the code under test sets an
environment variable, add `monkeypatch.delenv(..., raising=False)` for it.

---

## 4. Naming, Layout, and Documentation

### C-16: No underscore-prefixed names in tests, or in anything a test imports

A test module has no external callers, so `_MODULE`, `_make_trip` and `_AMOUNT`
protect nothing. When a test needs to import or patch an underscore-prefixed name
from `app/`, that name is public API in practice: rename it public on the production
side in the same change. Testability beats a nominal private API.

❌ **Bad:**
```python
from app.services.money import _round_half_up

_AMOUNT = 1840000
```

✅ **Good:**
```python
from app.services.money import round_half_up

AMOUNT = 1840000
```

### C-17: Imports, constants, helpers, fixtures, then tests

Reading order, top to bottom. A fixture defined between two groups of tests forces
the reader to hunt for it. Group tests with a comment banner (`# --- allocate ---`),
never with a class.

### C-18: A docstring on every test; no comments beside asserts

One sentence stating the behaviour and the expected outcome — it is what `pytest -v`
prints on failure. An inline comment next to an `assert` puts the same information
where nobody looks. Delete stale drafting comments and comments describing code that
is gone.

### C-19: One file per subject

`design/BACKEND.md` §6 fixes the mapping, and it is by **capability, not by
module**: `test_trips.py`, `test_items.py`, `test_splits.py`, `test_roster.py`,
`test_labels.py`, `test_balances.py`, `test_stats.py`, `test_export.py`,
`test_validation.py`, `test_errors.py`, `test_http.py`, plus the
one arithmetic file `test_money.py`. There is no `test_api_<router>.py` and no
`test_<service>.py` — a new subject gets the file §6 assigns it, or a new row in that table
in the same PR, rather than a fourth section in a 500-line one. Backend tests never land in
`tests/frontend/`, and a frontend test that wants the database is a backend test in
the wrong directory — `ruff` bans `app.*` imports there, so it fails `make lint`, not
review.

### C-20: Small nits that still get raised

- One parenthesised `with (...)` group instead of nested `with` blocks.
- Name the variable after the fixture (`trip`, not `t`).
- Never `pytest.importorskip` a first-party module; if `app/` exists the test runs.
- Link the issue a regression test guards with a full URL, not a bare number.
- `pytest.param(id=...)` on every case — an unnamed case reports as `test[0]`.

---

## 5. Test Doubles

### C-21: Build the real object; mock only the clock, the filesystem and randomness

Pydantic models, ORM rows, exceptions and dataclasses are cheap to construct for
real, and the real constructor catches a signature change. `MagicMock` with
`__bool__` or `__str__` patched in is a sign the real thing was never tried.

❌ **Bad:**
```python
item = MagicMock()
item.amount_minor = 1840000
item.currency.decimals = 0
```

✅ **Good:**
```python
item = LineItem(name="Dinner", amount_minor=1840000, currency=isk, country=iceland)
```

The database is in memory, the services are pure or DB-backed, and every one of them
is reachable through a request; a mock anywhere in `tests/backend/` should come with a
sentence explaining what boundary it stands for. `types.SimpleNamespace` and a
hand-rolled `FakeParams(dict)` are the same smell — post the real body and assert the
real response.

### C-22: Do not over-mock into a state the app never reaches

A fixture that patches four collaborators and hand-populates a session identity map
produces a state no request can produce, so whatever it proves is not about
production. The same goes for ORM setup that skips validation. Add the seam to the
code, or build the scenario the way a client would, through `client`.

---

## 6. Assertions

### C-23: `assert_called_once_with` over `call_count` or `call_args` indexing

Counting calls or reading `call_args_list[0].kwargs["x"]` checks a fragment and
passes while the rest of the call is wrong.

❌ **Bad:**
```python
assert mock_writer.write.call_count == 1
assert mock_writer.write.call_args[1]["delimiter"] == ","
```

✅ **Good:**
```python
mock_writer.write.assert_called_once_with(rows, delimiter=",", lineterminator="\n")
```

For several calls, compare `mock_calls` against a full list of `call(...)` objects —
that also pins the order.

### C-24: Assert whole envelopes, as codes and params

Compare the full error body, not just `status_code`. Name the exact `code` and the
exact `params` from the `design/API.md` §4 table: a client switches on the code and
renders the params through its own catalog, so either one changing is a user-visible
change.

**There is no `message` key anywhere in the backend.** A test that asserts one — or
greps a response for a phrase — is pinning a contract violation in place. The single
assertion that no such key exists lives in `test_errors.py`.

❌ **Bad:**
```python
assert response.status_code == 409
assert "in_use" in response.text
```

✅ **Good:**
```python
assert response.status_code == 409
assert response.json() == {
    "error": {
        "code": "conflict",
        "params": {},
        "fields": {"id": {"code": "in_use", "params": {"count": 4, "name": "Iceland"}}},
    }
}
```

### C-25: Money is asserted exactly

The exact JSON value in functional tests; integer minor units with `==` in `test_money.py`.
No `pytest.approx`, no float equality, no rounding in the test to match the code. An
approximate money assertion cannot tell a correct split from one that lost a minor
unit in the remainder — which is the bug the test exists to catch.

### C-26: Cover every effect the docstring promises

A test named `..._creates_and_attaches_labels` that never checks the attachment, or a
value computed and never asserted, is documentation that lies. Row written, count
incremented, cascade applied, remainder exact: each needs its assertion. When order
matters, assert it.

### C-27: Delete every line no assertion depends on

A prepared amount never used, a loop over a single-element list, a `print`, a second
item added "for realism". Every line should arrange, act, or assert.

---

## 7. Functional Discipline

### C-28: Build the state with requests, and assert what a client would see

The default backend test drives the app through `client`. Setup is `POST /trips`,
`POST /items`, `PATCH …` — not ORM inserts — because the write path is the only thing
that cannot construct a state the API itself would reject, and because a test built
from requests survives a refactor of `models.py`.

Two things follow, and both get raised in review:

- **A direct import from `app.services.*` needs a justification**, and there is
  exactly one standing exception: `test_money.py`, where the cases are combinatorial
  and HTTP would add only runtime. Anything else — `splits.build`, `balances.compute`,
  `settle.suggest`, `stats.by_day` — is covered by the endpoint that publishes it
  (P-6, AP-1).
- **Assert the response, not the ORM.** After a request, the session is closed;
  reaching into `trip.items[0].shares` invites `DetachedInstanceError` and asserts a
  shape no client ever sees. Reach for `session` only when the behaviour is invisible
  on the wire — that a `DELETE` really cascaded, that no orphan share survived — and
  say so in the docstring.

❌ **Bad — the endpoint's own rules, asserted where no client can reach them:**
```python
def test_split_excludes_inactive_people(session, trip):
    trip.people[3].active = False
    session.flush()
    shares = splits.build(1840000, people=trip.people, mode="equal")
    assert len(shares) == 3
```

✅ **Good — the same rule, as a client meets it:**
```python
def test_split_excludes_inactive_people(client, trip, item_body):
    """An inactive person is left out of a new equal split and comes back as owed: null."""
    person = trip["people"][3]
    client.patch(f"/api/v1/trips/{trip['slug']}/people/{person['id']}", json={"active": False})

    response = client.post(f"/api/v1/trips/{trip['slug']}/items", json=item_body(amount="18400"))

    shares = {
        share["person_id"]: share["owed"] for share in response.json()["item"]["split"]["shares"]
    }
    assert shares[person["id"]] is None
    assert sorted(value for value in shares.values() if value is not None) == [6133, 6133, 6134]
```
