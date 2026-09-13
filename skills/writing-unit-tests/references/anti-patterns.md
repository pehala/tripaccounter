# Backend Test Anti-Patterns

Shapes that make a test suite look thorough and prove nothing.
See also: [common-pitfalls.md](common-pitfalls.md) and [review-conventions.md](review-conventions.md) for the specific mistakes.

## AP-1: Testing Implementation, Not Behaviour

❌ **Bad — asserts how the slug was built:**
```python
def test_slug_generation():
    with patch("app.services.slugs.re.sub") as mock_sub:
        slugify("Iceland 2026")
        assert mock_sub.call_count == 2
```

✅ **Good — asserts what a client gets back:**
```python
@pytest.mark.parametrize(
    ("name", "expected"),
    [
        pytest.param("Iceland 2026", "iceland-2026", id="spaces-to-hyphens"),
        pytest.param("Île de Ré", "ile-de-re", id="accents-folded"),
        pytest.param("!!!", "trip", id="punctuation-only-falls-back"),
    ],
)
def test_trip_slug(client, name, expected):
    """A trip name becomes a URL-safe slug with accents folded and spaces hyphenated."""
    response = client.post("/api/v1/trips", json={**TRIP_BODY, "name": name})

    assert response.json()["trip"]["slug"] == expected
```

`slugify` never appears in the test. It is covered, completely, by the endpoint that
exposes it — and the test stays green when the slug helper is rewritten or inlined.

## AP-2: Giant Test Functions

One function walking every branch stops at the first failed assertion and hides the
rest. Parametrize, with `pytest.param(id=...)` so the failure names the case.

❌ **Bad:**
```python
def test_all_validation_rules(client, trip):
    # 120 lines posting every invalid body from the API.md table
```

✅ **Good:**
```python
@pytest.mark.parametrize(
    ("payload", "field", "code", "params"),
    [
        pytest.param(
            {"amount": ""}, "amount", "invalid_amount", {"decimals": 0}, id="empty-amount"
        ),
        pytest.param({"amount": "-5"}, "amount", "invalid_amount", {"decimals": 0}, id="negative"),
        pytest.param({"country_id": None}, "country_id", "required", {}, id="no-country"),
    ],
)
def test_item_validation(client, trip, item_body, payload, field, code, params):
    """Each row of the API.md validation table fails with its own code and params."""
    response = client.post(f"/api/v1/trips/{trip['slug']}/items", json=item_body(**payload))

    assert response.status_code == 422
    assert response.json()["error"]["fields"][field] == {"code": code, "params": params}
```

This is the shape `test_validation.py` is built from, and the file's last test asserts
the parametrization covers every row of `design/API.md` §4.

## AP-3: Asserting on a Mocked Return Value

❌ **Bad — asserts `unittest.mock`, not the app:**
```python
def test_balances():
    with patch("app.services.balances.compute", return_value=[{"net": 0}]):
        assert compute() == [{"net": 0}]
```

✅ **Good — drop the mock and run the real thing through the endpoint:**
```python
def test_balances_endpoint_serializes_nets(client, trip, item_body):
    """Every net is published per currency and sums to zero."""
    client.post(f"/api/v1/trips/{trip['slug']}/items", json=item_body(amount="184.00"))
    response = client.get(f"/api/v1/trips/{trip['slug']}/balances")

    block = response.json()["balances"][0]
    assert sum(person["net"] for person in block["people"]) == 0
```

In this app almost nothing needs mocking: the services are pure or DB-backed, the DB
is in memory, and every one of them is reachable through a request. A mock in a
backend test deserves a sentence saying which boundary it stands for.

## AP-4: Test Classes Instead of Flat Functions

`class TestMoney:` buys nothing in pytest and breaks fixture injection patterns.

❌ **Bad:**
```python
class TestAllocate:
    def test_exact(self):
        assert allocate(400, [1, 1]) == [200, 200]

    def test_remainder(self):
        assert allocate(401, [1, 1]) == [201, 200]
```

✅ **Good — flat functions, grouped by a comment banner:**
```python
# --- allocate ---


def test_allocate_exact_division():
    assert allocate(400, [1, 1]) == [200, 200]


def test_allocate_remainder_to_first_row():
    assert allocate(401, [1, 1]) == [201, 200]
```

## AP-5: Building State by Hand Instead of Through the API

Six lines of ORM setup in nine files is nine places to edit when the model gains a
column — and worse, it can build a trip the API would have rejected, so the test
guards a state production never reaches.

❌ **Bad — the write path, reimplemented in the test:**
```python
def test_item_totals(session):
    trip = Trip(name="Iceland", slug="iceland")
    session.add(trip)
    people = [Person(trip=trip, name=n, sort_order=i) for i, n in enumerate("ABCD")]
    currency = Currency(trip=trip, code="ISK", decimals=0)
    session.add_all([*people, currency])
    session.flush()
    ...
```

✅ **Good — take the fixture and post to the API:**
```python
def test_item_totals(client, trip, item_body):
    client.post(f"/api/v1/trips/{trip['slug']}/items", json=item_body(amount="18400"))
    ...
```

Layer variants on top of the base fixture rather than copying it, and build them the
same way:

```python
@pytest.fixture()
def settled_trip(client, trip, item_body):
    """``trip`` with items arranged so every net is already zero."""
    for payer in trip["people"][:2]:
        client.post(
            f"/api/v1/trips/{trip['slug']}/items",
            json=item_body(amount="40000", payer_id=payer["id"]),
        )
    return trip
```

A helper needed by two test files moves to `tests/backend/conftest.py`. Test modules
are not libraries: never import a helper from one `test_*.py` into another.

## AP-6: Testing a Copy of the Code

The most dangerous one. The test builds a stand-in that re-implements the logic, then
asserts against the stand-in. The production path never runs, so a bug in it is
invisible. It happens most often when tests are written by reading the source and
mirroring it.

❌ **Bad — `fake_allocate` is the real `allocate`, retyped:**
```python
def fake_allocate(total, weights):
    # copied from app/services/money.py
    unit = total // sum(weights)
    rest = total - unit * len(weights)
    ...
    return shares


def test_equal_split():
    assert fake_allocate(1840000, [1, 1, 1, 1]) == [460000] * 4  # tests the copy
```

✅ **Good — call the real function with literal arguments and literal expectations:**
```python
from app.services.money import allocate


def test_allocate_equal_four_ways():
    """Four equal weights on 18 400.00 divide exactly, with no remainder to place."""
    assert allocate(1840000, [1, 1, 1, 1]) == [460000] * 4
```

The wire-level version of the same mistake: a functional test that computes its
expected `owed` values by dividing `amount` by the roster size. Write the numbers out.

**How to spot it:** grep the test file for function bodies that also appear in `app/`.
If a helper in the test directory has the same shape as one in `app/services/`, the
tests are checking the mirror.

**When the real thing is genuinely awkward to construct**, that is a signal about the
production code, not about the test: the dependency wants to become an argument. Say
so and make the seam, rather than building the mirror.
