# Mock API — `tests/frontend/mockapi.py`

The HTTP server the Playwright suite runs against. It serves the real `static/` and a
JSON API declared entirely by the fixture file it was started from. The engine is
generic: it resolves pointers, expands collections and maps methods to statuses, and
knows nothing about trips, splits or balances. **The fixture JSON is the source of
truth** for every path, body and error envelope the suite sees.

```
tests/
├── frontend/
│   ├── mockapi.py             the engine
│   ├── conftest.py            starts one server per test from a fixture (see §5)
│   └── fixtures/
│       ├── trip.json          the resting state: 4 people, 3 currencies, resolved splits
│       ├── empty.json         a trip with no items
│       ├── hostile.json       markup in every user-supplied string
│       └── errors/            envelopes stubbed per test through page.route (§5)
└── tools/
    └── test_mockapi.py        the engine, over HTTP, against an inline fixture
```

## 1. A fixture file

```jsonc
{
  "trip":     {"trip": {…}},          // response data, one envelope per block
  "labels":   {"labels": […]},
  "items":    {"items": […]},
  "balances": {"balances": […]},
  "stats":    {"stats": […], "day_count": 10},
  "trips":    {"trips": [{…}]},       // the literal GET /trips answer

  "routes": {                         // one key per URL
    "/api/v1/trips":                              {"GET": "#/trips", "POST": {"trip": "$echo"}},
    "/api/v1/trips/iceland-2026":                 {"GET": "#/trip", "PATCH": "#/trip"},
    "/api/v1/trips/iceland-2026/items":           {"collection": "#/items/items", "item": "item", "insert": "head"},
    "/api/v1/trips/iceland-2026/items/preview-split":
                                                  {"POST": {"$status": 200, "split": {…}, "total": 18400}},
    "/api/v1/trips/iceland-2026/labels":          {"collection": "#/labels/labels", "item": "label",
                                                   "defaults": {"color": "#6c757d", "use_count": 0}},
    "/api/v1/trips/iceland-2026/people":          {"collection": "#/trip/trip/people", "item": "person",
                                                   "defaults": {"active": true, "color": "#6c757d"}},
    "/api/v1/trips/iceland-2026/currencies":      {"collection": "#/trip/trip/currencies", "item": "currency"},
    "/api/v1/trips/iceland-2026/countries":       {"collection": "#/trip/trip/countries", "item": "country"},
    "/api/v1/trips/iceland-2026/balances":        {"GET": "#/balances"},
    "/api/v1/trips/iceland-2026/stats":           {"GET": "#/stats"}
  },

  "errors": {                         // the two envelopes the engine answers on its own
    "not_found":   {"error": {"code": "not_found",   "params": {"resource": "route"}}},
    "bad_request": {"error": {"code": "bad_request", "params": {}}}
  }
}
```

The data blocks are the exact response bodies of their `GET`s and are what the
Playwright tests index (`fixture_data["items"]["items"]`). `routes` says which URL
serves which block; `errors` supplies the bodies for a path nothing declares and for
a request body that is not a JSON object.

## 2. Route grammar

A route is `{method: value, …}` or a collection. Method keys are `GET`, `POST`,
`PATCH`, `DELETE`.

| Value | Serves |
|---|---|
| `"#/trip"` | the object an [RFC 6901](https://www.rfc-editor.org/rfc/rfc6901) JSON Pointer names in this file, **by identity**. `#/trip/trip/people` is the same list whether it arrives inside `GET /trips/{slug}` or from the `people` collection, so a write through one is visible through the other |
| any other JSON | that literal, as is |
| `null` | headers only |

Two directives can appear inside a literal:

| Directive | Effect |
|---|---|
| `"$echo"` (as a value) | replaced by the request body plus a counter `id` (the request's own `id` wins when present) |
| `"$status": 200` (as a key) | sets the status; the key is removed from what is served |

Status follows the method unless `$status` says otherwise:

| Method | Status | On a pointer value |
|---|---|---|
| `GET` | 200 | serves the target |
| `POST` | 201 | serves the target |
| `PATCH` | 200 | merges the request body into the target's payload first — the target has to be a one-key envelope `{key: payload}` |
| `DELETE` | 204 | serves the target |

### Collections

```json
{"collection": "#/items/items", "item": "item", "defaults": {…}, "insert": "head",
 "extra": {"day_totals": "#/items/day_totals"}}
```

| Field | Meaning |
|---|---|
| `collection` | pointer to the list of rows; its last token is the list's envelope key (`items`) |
| `item` | the envelope key of one row (`item`, `person`) |
| `defaults` | keys a created row gets when the request leaves them out (optional) |
| `insert` | `"head"` prepends a created row; the default appends (optional) |
| `extra` | sibling keys merged into the `GET` list response only — each value a pointer or a literal (optional) |

Any other field on a collection is refused at server build with a `KeyError`, so a
misspelt `defaults` cannot pass silently.

A collection expands into four operations:

| Request | Answer |
|---|---|
| `GET …` | 200 `{items: rows, **extra}` |
| `POST …` | 201 `{item: defaults + body + id}`, row stored |
| `PATCH …/{id}` | 200 `{item: row}` after `row.update(body)` |
| `DELETE …/{id}` | 204, row removed |

An `{id}` segment matches one path segment and is compared to `str(row["id"])`, so the
fixture's integer ids and the browser's string ids meet. A member request for an id no
row has answers `errors.not_found`. A path declared explicitly next to a collection
(`…/items/preview-split`) is matched before the collection's `{id}` route.

### Ids

Every server owns one counter starting at 1000, shared by `$echo` and every
collection's `POST`. Fixture ids stay small, so a created row never collides.

## 3. Requests nothing declares

1. The query string is dropped and the path matched against the routes.
2. A path with no route is looked up under `static/`; `/`, `/t/*` and `/trips/new`
   serve `index.html`, because those are the app's client-side routes.
3. Anything else answers `errors.not_found` as JSON with 404.

A request whose body parses to something other than a JSON object answers
`errors.bad_request` with 400. Both `errors` entries are required; a fixture without
them fails at server build with a `KeyError`, not at the first request.

## 4. Principles

**It does no arithmetic.** `preview-split` is a canned body, a resolved split is
typed into the fixture by hand, and `GET /trips` is the literal `trips` block rather
than a summary computed from `trip`. Every number the frontend renders was produced
by the backend once and copied in; a mock that allocated shares would be a second
implementation of the allocation rule, and the suite would pass against it.

**The engine knows nothing.** No path, key, status or envelope is written in Python.
Adding an endpoint is a line in `routes`; renaming a key is an edit to the block.

**Undeclared means absent.** A URL the fixture does not list answers `not_found`.
The suite can therefore assert the 404 view against a slug the mock never heard of,
and a typo in a route shows up as a failing test instead of an echoed body.

## 5. How tests use it

`tests/frontend/conftest.py` builds one server per test:

| Fixture | Gives |
|---|---|
| `fixture_name` | the file the server is built from, `trip.json` unless a module overrides it or a test parametrizes it indirectly |
| `fixture_data` | a fresh parse of `fixture_name`, private to the test; a module overrides it to mutate the copy before it is served |
| `mockserver` | base URL of a server built from `fixture_data`; stopped with the test |
| `trip_url` | `{mockserver}/t/{slug}` |
| `open_trip(hash)` / `items_page` … `setup_page` | the trip loaded on a tab, waited for; the factory form lets a test stub a baseline `GET` first |
| `stub(pattern, responder)` | a `page.route` interceptor; a responder returning `None` lets the request through to the mock |
| `count_requests(path_glob, method)` | a live list of the requests the page made, for the call budget |

**Two data mechanisms.** Baseline `GET`s and the round-trip writes of the Setup tab
come from the mock. Error envelopes, `preview-split` numbers a test asserts, and slow
or failing responses are stubbed per test with `stub`, reading their bodies from
`fixtures/errors/`. The test declares the exact response it wants; nothing has to be
manufactured in server state.

`MockServer(data)` is the seam: a context manager that serves that one dict on a free
port for the length of its `with` block, so servers never share rows or ids and a test
can mutate its copy before starting the server (`test_unknown_fields.py` overrides
`fixture_data` to add keys the frontend has never seen). `make_handler(data)` underneath builds the handler class
alone, for callers that bring their own server.

## 6. What keeps it honest

`tests/tools/test_mockapi.py` (`make test_tools`) drives the engine over HTTP with an inline fixture whose envelopes
are deliberately not the real API's: pointers by identity, `$echo`, `$status`, the
`PATCH` merge, all four collection operations, `insert`, the `not_found` and
`bad_request` bodies coming from the fixture, per-server isolation, static serving.
A passing run proves every shape came from the JSON.

The fixture values themselves are copied from what the backend produced; when the
contract changes, the fixture changes in the same commit (`API.md` §6).

## 7. Adding an endpoint

1. Put the response data in the fixture — a new block, or a pointer into an existing one.
2. Add the URL to `routes` with the method and value; copy the body shape from `/docs`
   or the committed `openapi.json`.
3. Write the Playwright test against the new URL.
