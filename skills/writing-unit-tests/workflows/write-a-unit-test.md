# Writing a Backend Test

A 4-phase process for adding a test to `tests/backend/`. The default is a functional
test: a request through `client`, an assertion on the status and the JSON body.

Rule references: `P-n` → [common-pitfalls.md](../references/common-pitfalls.md),
`AP-n` → [anti-patterns.md](../references/anti-patterns.md), `C-n` →
[review-conventions.md](../references/review-conventions.md).

---

## Phase 1: Decide What to Test and Where

**Entry:** a behaviour of the API needs coverage.

**Actions:**

1. **Name the failure you are guarding against.** One sentence: "a minor unit goes
   missing when the split does not divide evenly." If you cannot write that sentence,
   the test is not worth adding (C-4).

2. **Find the endpoint that publishes the behaviour.** That is where the test goes —
   through `client`, with the state built by earlier requests. Services get no test
   file of their own; the only direct-call file is `test_money.py`, for `parse_amount`,
   `to_wire` and `allocate` (P-6).

3. **Find the existing file.** `design/BACKEND.md` §6 fixes the file per
   capability — `test_trips.py`, `test_items.py`, `test_splits.py`, `test_roster.py`,
   `test_labels.py`, `test_balances.py`, `test_stats.py`, `test_export.py`,
   `test_validation.py`, `test_errors.py`, `test_http.py`, `test_static.py`,
   `test_money.py`. Add to that file; do not create a second file on the same
   capability, and do not add a `test_<service>.py` (C-19).

4. **Check whether it is already covered.** A new test that duplicates an existing
   one with a different literal is a parametrize case on the existing test (C-8).

5. **Confirm it belongs in the backend at all.** Rendering, formatting, ordering on
   screen, and anything about `static/` is `tests/frontend/`.

**Exit:** you know the file, the endpoint, and the sentence the docstring will carry.

---

## Phase 2: Wire the Setup

**Entry:** Phase 1 done.

**Actions:**

1. **Read `tests/backend/conftest.py` first.** Reuse `client`, `trip`, `people`,
   `currency`, `country`, `item_body` rather than building equivalents (AP-5). `trip`
   is the wire JSON of one `POST /trips`, so read it like a client: `trip["slug"]`,
   `trip["people"][0]["id"]`.

2. **Build the rest of the state with requests, not ORM inserts** — the write path
   is the only thing that cannot construct a state the API would reject (AP-5).

3. **Request only the fixtures you use.** A `test_money.py` case takes plain
   arguments and neither `session` nor `client`.

4. **If setup is longer than the assertions, extract a fixture.** The target shape is
   two or three lines of arrange, one call, then the assertions. A variant fixture
   takes the base fixture as an argument instead of copying it.

5. **Put files under `tmp_path` and environment under `monkeypatch`** (P-10, P-7).

6. **Add no mocks unless you can say why.** The DB is in memory and the services are
   cheap; the legitimate boundaries are the clock, the filesystem and randomness.

**Exit:** the arrange block exists and reuses what is already there.

---

## Phase 3: Write the Test

**Actions:**

1. **Arrange–Act–Assert, in that order, with no interleaving.**

2. **Parametrize instead of writing near-duplicates**, with `pytest.param(id=...)`
   so a failure names the case:
   ```python
   @pytest.mark.parametrize(
       ("raw", "expected"),
       [
           pytest.param("18400.50", 1840050, id="canonical-two-decimals"),
           pytest.param("18 400,50", None, id="grouped-rejected"),
       ],
   )
   ```

3. **Write expected money as integer literals** you worked out by hand — never by
   calling the code under test (P-3).

4. **Assert everything the docstring promises.** If it says "and the remainder is
   exact", assert the sum as well as the rows (C-26).

5. **Assert whole objects, as codes and params**, not fragments: the full error
   envelope `{code, params, fields}`, the full shares list, the exact `code` from the
   `design/API.md` §4 table. **Never assert message text — there is none** (P-11, C-24).

6. **Cover the edges the subject actually has**: empty string, zero, a negative
   amount, a zero-decimal currency, one person, ten people, an amount that does not
   divide, a person excluded from the split (`owed: null`, distinct from `owed: 0`),
   a value from another trip.

7. **One-sentence docstring, no comments beside asserts.**

**Exit:** the test reads top to bottom without the reader hunting for setup.

---

## Phase 4: Run and Verify It Can Fail

**Actions:**

1. **Run it:**
   ```bash
   uv run python -m pytest tests/backend/test_splits.py::test_equal_split_pads_the_roster -v
   ```

2. **Make it fail on purpose.** Change one expected literal and confirm the test goes
   red for the reason you expect. A test that cannot fail is documentation, and a test
   whose failure message does not name the problem will waste someone's afternoon.

3. **Run the file, then the suite:**
   ```bash
   uv run python -m pytest tests/backend/test_splits.py -q
   make test
   ```

4. **Check isolation** — the test must pass alone and after everything else:
   ```bash
   uv run python -m pytest tests/backend/test_splits.py::test_equal_split_pads_the_roster -q
   uv run python -m pytest tests/backend -q
   ```

5. **Lint, then review your own diff** against
   [review-conventions.md](../references/review-conventions.md) — the parametrize,
   fixture, docstring and whole-object-assertion rules are what the PR gets measured
   against, and applying them now costs less than a round trip:
   ```bash
   make lint
   ```

6. **If the behaviour changed a response shape**, the contract moved: run
   `make openapi` so the committed spec carries the new shape, and update
   `design/API.md` and the frontend's fixtures in the same commit. `make
   openapi-check` fails in CI otherwise.

**Exit:** green in isolation and in the suite, red when the expectation is wrong,
`make lint` clean.
