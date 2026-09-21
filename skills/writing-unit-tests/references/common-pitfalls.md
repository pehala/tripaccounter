# Backend Test Pitfalls

Concrete mistakes in `tests/backend/`, with before/after fixes.
See also: [anti-patterns.md](anti-patterns.md) and [review-conventions.md](review-conventions.md) for the broader shapes.

---

## P-1: Sharing a Database Between Tests

A module-level engine or `Session` leaks rows into the next test. Slugs collide,
`use_count` is wrong, and the failure lands in whichever test happens to run second.

❌ **Bad:**
```python
engine = create_engine("sqlite:///test.db")
Base.metadata.create_all(engine)
session = Session(engine)
client = TestClient(app)


def test_create_trip():
    client.post("/api/v1/trips", json=TRIP_BODY)
```

✅ **Good — the per-test fixtures from `conftest.py`:**
```python
def test_create_trip(client):
    """A trip posted with a full roster comes back with its slug and embedded lists."""
    response = client.post("/api/v1/trips", json=TRIP_BODY)

    assert response.status_code == 201
    assert response.json()["trip"]["slug"] == "iceland-2026"
```

`client` overrides `get_session` to the per-test `session`, which runs on a
transaction the fixture rolls back. When a test does reach for `session` directly —
checking that a `DELETE` really cascaded, say — `flush()` is usually enough: it
assigns primary keys and fires constraints without ending that transaction.

---

## P-2: Asserting Money With `approx` or Floats

Money is integer minor units everywhere but the serializer edge. An approximate
assertion cannot distinguish "correct" from "one minor unit lost in the remainder",
which is the single most likely bug in this app.

❌ **Bad:**
```python
assert total == pytest.approx(18400.0)
assert sum(share["owed"] for share in shares) == pytest.approx(184.0, rel=1e-6)
```

✅ **Good — the exact JSON the contract promises, including the type when a
zero-decimal currency is the point:**
```python
value = response.json()["item"]["amount"]
assert value == 18400
assert isinstance(value, int)  # not 18400.0

assert [share["owed"] for share in shares] == [4600, 4600, 4600, 4600]
```

In `test_money.py`, the same rule on minor units: `assert allocate(...) == [460000] * 4`.

---

## P-3: Recomputing the Expected Value With the Code's Own Algorithm

A test that calls `allocate` to build its expectation passes for any `allocate`,
including a broken one.

❌ **Bad:**
```python
def test_allocate_four_ways():
    expected = [total // 4] * 4
    expected[0] += total - sum(expected)
    assert allocate(total, [1, 1, 1, 1]) == expected
```

✅ **Good — literals, written out by hand:**
```python
@pytest.mark.parametrize(
    ("total", "weights", "expected"),
    [
        pytest.param(1840000, [1, 1, 1, 1], [460000, 460000, 460000, 460000], id="exact-quarters"),
        pytest.param(
            1000003, [1, 1, 1, 1], [250001, 250001, 250001, 250000], id="three-minor-remainder"
        ),
        pytest.param(1000, [1, 1, 1, 0.5], [286, 286, 286, 142], id="half-weight"),
    ],
)
def test_allocate(total, weights, expected):
    """The remainder goes to the earliest rows in weight order and the sum stays exact."""
    result = allocate(total, weights)
    assert result == expected
    assert sum(result) == total
```

The same rule at the wire: a functional test writes the four `owed` values out, it
does not divide `amount` by the roster size in the assertion.

---

## P-4: Depending on the Ambient Clock

`date.today()` in the test and `date.today()` in the code agree until the run crosses
midnight, and then they do not.

❌ **Bad:**
```python
def test_item_defaults_to_today(client, trip, item_body):
    response = client.post(f"/api/v1/trips/{trip['slug']}/items", json=item_body())
    assert response.json()["item"]["occurred_at"].startswith(date.today().isoformat())
```

✅ **Good — `occurred_at` is request data:**
```python
def test_item_keeps_the_given_wall_time(client, trip, item_body):
    """occurred_at is stored and echoed as naive local wall time, untouched."""
    response = client.post(
        f"/api/v1/trips/{trip['slug']}/items", json=item_body(occurred_at="2026-07-01T19:30:00")
    )

    assert response.json()["item"]["occurred_at"] == "2026-07-01T19:30:00"
```

When the default itself is the behaviour under test, inject the clock rather than
patching `datetime` module-wide:

```python
def test_item_defaults_to_the_injected_clock(client, trip, item_body, frozen_clock):
    """An item posted without occurred_at takes the clock's value, not the DB's."""
    frozen_clock.set(datetime(2026, 7, 1, 19, 30))

    response = client.post(f"/api/v1/trips/{trip['slug']}/items", json=item_body(occurred_at=None))

    assert response.json()["item"]["occurred_at"] == "2026-07-01T19:30:00"
```

---

## P-5: Relying on Unordered Results

SQLite returns rows in whatever order it likes unless the query says otherwise. A
test that asserts a list order without an `ORDER BY` in the code under test is
asserting an implementation accident.

❌ **Bad:**
```python
assert [person["person_id"] for person in balances[0]["people"]] == [1, 2, 3, 4]
```

✅ **Good — assert the order the contract promises, and let the failure name it:**
```python
# API.md: people are in roster order, always
roster = [person["id"] for person in trip["people"]]
assert [person["person_id"] for person in balances[0]["people"]] == roster
```

If the contract does not promise an order, compare as a set — but prefer adding the
`ORDER BY` to the production query, because the frontend renders these lists.

---

## P-6: Reaching for the Service When the Endpoint Is the Subject

The default here is the opposite of the usual advice: a behaviour is tested through
the endpoint that publishes it. A direct call to `balances.compute()` or
`splits.build()` skips serialization, validation and the session — the three layers
between the arithmetic and anything a client can see — and it has to be rewritten the
day the service is refactored.

❌ **Bad — the split rules, asserted where no client can observe them:**
```python
def test_equal_split(session, trip):
    shares = splits.build(1840000, people=[1, 2, 3, 4], mode="equal")
    assert shares == [460000] * 4
```

✅ **Good — the same rule, through `preview-split`:**
```python
def test_equal_split_pads_the_roster(client, trip, item_body):
    """Everyone listed gets an even cut, and the people left out come back as null."""
    response = client.post(
        f"/api/v1/trips/{trip['slug']}/items/preview-split",
        json=item_body(
            amount="18400",
            split_mode="equal",
            shares=[{"person_id": p["id"]} for p in trip["people"][:4]],
        ),
    )

    assert [share["owed"] for share in response.json()["split"]["shares"]] == [
        4600,
        4600,
        4600,
        4600,
    ]
```

**The exception is `test_money.py`** — `parse_amount`, `to_wire` and `allocate` are
called directly, because their interesting cases are combinatorial and HTTP would add
nothing but runtime. Any other direct service import in `tests/backend/` needs a
sentence in the PR saying what it buys.

---

## P-7: Settings Read at Import Time

`pydantic-settings` reads the environment when the object is constructed. A
module-level `settings = Settings()` is constructed at import, long before
`monkeypatch` runs.

❌ **Bad:**
```python
def test_debug(monkeypatch):
    monkeypatch.setenv("TA_DEBUG", "1")
    from app.config import settings

    assert settings.debug is True  # already built, still False
```

✅ **Good — construct it in the test:**
```python
from app.config import Settings


def test_debug(monkeypatch):
    monkeypatch.setenv("TA_DEBUG", "1")
    assert Settings().debug is True
```

If production genuinely needs a single settings object, make it an `lru_cache`d
factory and clear the cache in an autouse teardown fixture.

---

## P-8: Mutating a Fixture's Return Value

`trip` and the roster fixtures hand back the parsed response, and `item_body` hands
back a fresh dict per call but a nested list by reference. Edit a copy, so a later
assertion in the same test still sees what the API actually returned.

❌ **Bad:**
```python
def test_missing_country(trip, item_body):
    body = item_body()
    body.pop("country_id")
    assert trip["countries"]  # fine, but `body` is now what a later assert reads
    ...
```

✅ **Good — copy before you edit:**
```python
def test_missing_country(item_body):
    payload = copy.deepcopy(item_body())
    payload.pop("country_id")
    ...
```

---

## P-9: Inline Imports

An import inside a test body hides a dependency and costs a lookup per call. The one
excuse — a circular import — is a production problem to fix, not a test style.

❌ **Bad:**
```python
def test_trip_slug_collision(client):
    from app.services.slugs import slugify

    ...
```

✅ **Good — top of the file, and in a functional test usually not needed at all:**
```python
def test_trip_slug_collision(client):
    """Two trips with the same name get iceland-2026 and iceland-2026-2."""
    first = client.post("/api/v1/trips", json=TRIP_BODY).json()["trip"]
    second = client.post("/api/v1/trips", json=TRIP_BODY).json()["trip"]

    assert [first["slug"], second["slug"]] == ["iceland-2026", "iceland-2026-2"]
```

---

## P-10: Writing Outside `tmp_path`

Export tests that write `trip.csv` into the working directory leave droppings, race
each other, and fail on a read-only checkout.

❌ **Bad:**
```python
def test_export_csv(client, trip):
    Path("trip.csv").write_text(client.get(url).text)
```

✅ **Good:**
```python
def test_export_csv(tmp_path, client, trip):
    target = tmp_path / "trip.csv"
    target.write_text(client.get(url).text)
```

Most export assertions need no file at all — `response.text` and `response.headers`
carry everything the contract promises. The same applies to SQLite files: an on-disk
test DB belongs under `tmp_path`, never next to `dev.db`.

---

## P-11: Asserting a Fragment of an Error Envelope

`design/API.md` §1 fixes the envelope, and a client switches on `code` and renders
`params` through its own catalog. Checking only the status code passes while the
code, the params or the field key is wrong — and the frontend is the thing that
breaks.

❌ **Bad:**
```python
assert response.status_code == 409
assert "in_use" in response.text
```

✅ **Good — the whole envelope, as codes and params:**
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

**There is no `message` key** — not here, not anywhere in the backend. A test that
asserts one is pinning a contract violation in place; the assertion that no message
exists lives once, in `test_errors.py`.

---

## P-12: Caches Surviving the Test

`lru_cache` on a currency lookup, a slug set, or a compiled formatter holds state for
the whole process. Test A warms it with its own trip; test B reads the stale entry.

❌ **Bad:** no cleanup, and a failure that only appears when the two tests run in
the same process.

✅ **Good — autouse teardown, post-`yield` only:**
```python
@pytest.fixture(autouse=True)
def clear_currency_cache():
    """Drop the currency lookup cache after each test so rows do not outlive their DB."""
    yield
    lookup_currency.cache_clear()
```

Clear in teardown only. A pre-`yield` clear as well signals that the teardown is not
trusted, and hides whichever test is actually leaking.
