# Trip-scoped CRUD routes — `app/routers/crud.py`

**Owns**: the four list/create/update/delete routes that five roster entities publish
under `/trips/{slug}`, and the declaration format those entities are written in.

**Owns nothing else.** It holds no business rules. Every route body is one call into
`app/services/`; `crud.py` supplies the plumbing between the HTTP edge and that call —
path words, response envelopes, the OpenAPI identity of each handler, and the error
translation seam.

The five entities are people, currencies, countries, labels and wallets. Items and
transfers are not among them: their writes are not a single service call and they keep
hand-written routers.

---

## 1. The shape of a declaration

One entity is one subclass of `TripChildRoutes` and one module under `app/routers/`.
A handful of class attributes name the entity; a decorated method declares each route.

```python
from app.models.trip import Trip
from app.routers.crud import Route, TripChildRoutes, route


class CountryRoutes(TripChildRoutes):
    """The countries visited on a trip, each carrying its item count."""

    model = TripCountry
    resource = "country"
    collection = "countries"
    envelope = CountryEnvelope
    list_envelope = CountryListEnvelope

    def serialize(self, country: TripCountry, session: Session) -> CountryOut:
        """Return the country with the number of items recorded in it."""
        counts = country_item_counts(session, country.trip_id)
        return CountryOut.from_country(country, counts.get(country.id, 0))

    @route(Route.LIST)
    def rows(self, session: Session, trip: Trip) -> list[TripCountry]:
        """List a trip's countries with their item counts."""
        return trip.countries

    @route(Route.CREATE)
    def create(self, session: Session, trip: Trip, body: CountryCreate) -> TripCountry:
        """Add a new country to a trip."""
        return roster.create_country(session, trip, body.name, body.code, body.is_default)

    @route(Route.UPDATE)
    def update(self, session: Session, country: TripCountry, body: CountryUpdate) -> TripCountry:
        """Update a trip country's fields."""
        return roster.update_country(
            session, country, body.name, body.code, body.is_default, body.sort_order
        )

    @route(Route.DELETE)
    def delete_row(self, session: Session, country: TripCountry) -> None:
        """Delete a country from a trip."""
        roster.delete_country(session, country)


router = CountryRoutes().router()
```

Every route a module publishes is a decorated method in that module. Reading the file
top to bottom tells you which routes exist, what each one takes and what each one does.

### The class attributes

| Attribute | What it fixes |
|---|---|
| `model` | the SQLAlchemy model `fetch` scopes an id against |
| `resource` | the singular path and envelope word — `{country_id}`, `{"country": …}` |
| `collection` | the plural path and envelope word — `/countries`, `{"countries": […]}` |
| `envelope` | the response model of create and update |
| `list_envelope` | the response model of list |

Five, and each is a fact about the entity as a whole. Anything true of only one route
lives on that route's decorator.

### `serialize`

Abstract, and an instance method. Every subclass writes it, so the wire shape of a row
is stated in the entity's own module rather than reached through a class attribute.
The plain case is one line:

```python
def serialize(self, label: Label, session: Session) -> LabelOut:
    """Return the label's wire form."""
    return LabelOut.model_validate(label)
```

Countries and people build a derived field; wallets returns the report row that
`wallet_balances` already produced.

### What the base annotates

A subclass knows its model; `crud.py` does not. So the base annotates what it can name
- `session`, `trip`, the row id, the `BaseModel` every `serialize` returns - and leaves
the row itself bare rather than claiming a type it cannot determine. The subclasses
annotate fully, because there the model is known.

---

## 2. Routes

`Route` is an enum of four members, declared beside `TripChildRoutes` and imported with
it.

| Kind | Method by convention | Verb and path |
|---|---|---|
| `LIST` | `rows` | `GET /trips/{slug}/{collection}` |
| `CREATE` | `create` | `POST /trips/{slug}/{collection}` |
| `UPDATE` | `update` | `PATCH /trips/{slug}/{collection}/{resource}_id` |
| `DELETE` | `delete_row` | `DELETE /trips/{slug}/{collection}/{resource}_id` |

The method name is convention only. The decorator's first argument is what binds a
method to a route, so a module may name its methods whatever reads best.

### The decorator

`route()` is a module-level function, not a method — it reads nothing off the class and
has no reason to live on it.

```python
@route(kind, field=..., statuses=...)
```

| Argument | Applies to | Default | What it fixes |
|---|---|---|---|
| `kind` | all | — | which route this method implements |
| `field` | create, update | `"name"` | the request field a `FieldError` from the call is addressed to |
| `statuses` | delete | `(404, 409)` | the error responses the route documents |

The request model is **not** an argument. Create and update read it off the annotation
of the method's parameter named `body`, so the type is written once, where the method
uses it. That parameter must carry a resolvable annotation and must be named `body`; a
create or update declaring neither raises `TypeError` at import.

`field` is why currencies passes `field="code"`: `TripCurrency` has no `name`, so a
duplicate currency is a conflict on `code`. It is not inferrable — the obvious rule,
the body model's first required field, gives `person_id` for a wallet, whose conflicts
are on `name`. Delete fixes the field to `"id"`: what conflicts there is the row the
path names, not a body field.

The route's **description in the OpenAPI spec is the method's docstring**. There is no
separate doc attribute, and no docstring that describes the method's internals rather
than the route: these methods are the route. A decorated method with no docstring
raises `TypeError` at import.

### Missing routes

A kind with no decorated method is not published. The subclass simply carries fewer
routes, and nothing in the spec mentions them. All five current entities declare all
four.

Declaring one kind twice in a subclass raises `TypeError` at import.

---

## 3. How the routes get built

Three steps, in this order.

**Import time, class body.** `route()` takes the method's docstring, resolves its
annotations for the request model, attaches a frozen `RouteSpec` carrying both to the
function and returns it unchanged. It cannot do more than that: the class object does
not exist while its body runs.

**Import time, class creation.** `__init_subclass__` walks `vars(cls)`, collects every
function carrying a spec into `cls.routes: dict[Route, tuple[Callable, RouteSpec]]`,
and rejects a duplicate kind. That mapping is the answer to "what does this entity
publish", available without building a router. It holds the plain functions, which the
handlers call with an explicit `self`.

**`router()`.** Instantiates nothing further — it runs on the instance the module
creates — and walks the four kinds, handing each declared function and its spec to the
`add_list` / `add_create` / `add_update` / `add_delete` method that knows how to
register it. Those four are the only places a verb, a path or a status list appears,
and each takes its spec as an argument, so no handler can close over another route's.

### Handler identity

FastAPI reads a route's operationId, summary, description and parameters off the
function object. The generic handlers are closures, so `endpoint()` gives each one the
identity the generator expects:

| Read from | Set to |
|---|---|
| `__name__` | `list_countries`, `create_country`, … — the operationId and summary |
| `__doc__` | the declaring method's docstring — the description |
| `__signature__` | the real parameters, so the path reads `{country_id}`, never `{row_id}` |

This is the bulk of `crud.py` and the reason the handlers are built per subclass rather
than shared: `endpoint()` mutates the function object, so a shared one would have its
identity overwritten by the next entity to register.

### Error translation

Create, update and delete run their call inside `field_errors(field)`. Services raise
bare `FieldError` subclasses — they carry a code and params, no field name and no HTTP
status. The context manager attaches the field the decorator named and picks the
status: 409 for a `ConflictFieldError`, 422 otherwise.

```python
with field_errors("code"):
    roster.create_currency(session, trip, body.code, body.symbol, body.is_primary)
```

Nothing under `app/services/` imports a status code, and nothing outside the routers
knows which request field a service argument came from.

---

## 4. The five entities

| Module | Deviates from the plain case by |
|---|---|
| `people.py` | `serialize` adds the derived initial and weight |
| `currencies.py` | `field="code"` on create and update |
| `countries.py` | `serialize` adds the item count, re-querying the counts per row |
| `labels.py` | `rows` orders by use count, not sort order; `statuses=(404,)` — a label is never in use |
| `wallets.py` | `rows` returns the balances report; `serialize` passes it through; create resolves the owning person first |

`wallets.py` is the one entity whose list route answers with a different shape than its
create and update routes — hence the separately declared `list_envelope`.
One URL carries two jobs. `GET /trips/{slug}/wallets` is the balances report behind the
Wallets tab, so its rows are `WalletReportOut` — a `WalletOut` plus `balances`. Create
and update are roster CRUD behind Setup, and answer `WalletOut`.

A write does not carry balances because it has none to carry: a wallet is created with
no activity, so the field would always be `[]`, and `wallet_balances` is a trip-wide
aggregate — four grouped queries over every transfer and item on the trip — that a
single-row write has no reason to pay for. The client agrees: after any item or
transfer write it drops its cached wallets and refetches the report.

---

## 5. What this replaced

Five hand-written routers, then a base class carrying twelve to fourteen class
attributes per subclass. The attributes that were really per-route — the request
bodies, the four route descriptions, the conflict field, the delete statuses — sat in
one block at the top of the class where nothing said which route each served. They are
now arguments to the route they serve, and `out` is gone entirely because `serialize`
is written out.

The generated `openapi.json` is unchanged by the move. The four route descriptions come
from docstrings that repeat the previous `*_doc` strings verbatim.

---

## 6. Implementation plan

Two commits, in order.

**1. `refactor(errors): replace run_field with a field_errors context manager.`**
Independent of everything below. Add `field_errors` beside `wrap_field_error` in
`app/services/errors/api.py`, convert the nine call sites in `crud.py`, `items.py` and
`trips.py`, delete `run_field`. In `trips.py` the three loops move inside a single
`with` each rather than wrapping every iteration. No spec change, no test change.

**2. `refactor(routers): declare trip-scoped CRUD routes per route.`**

1. `crud.py`: add `Route`, `RouteSpec`, `route()`, `__init_subclass__`; make
   `serialize` abstract and the class instance-based; keep `endpoint()` as is; turn the
   base defaults into the `remove` helper.
2. Convert the five subclasses. Each ends with `router = XRoutes().router()`.
3. `make openapi-check` must pass untouched. If it does not, a docstring drifted from
   the `*_doc` string it replaced — fix the docstring, not the snapshot.
4. `make lint test_backend`.

No test changes. The suite drives the routes over HTTP and never imports these classes,
so a green run is the evidence that the declaration format did not move the contract.
