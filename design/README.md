# design/

The architecture of Trip Accounter: how it is put together, why it is put together
that way, and the contract the two halves meet at. No plans, no milestones, no
schedules — those described how the thing got built and were deleted when it was.

**Start with [`ARCHITECTURE.md`](ARCHITECTURE.md).**

| Document | What it fixes |
|---|---|
| [`ARCHITECTURE.md`](ARCHITECTURE.md) | the system: process, layers, how money moves, the contract seam, test topology |
| [`DECISIONS.md`](DECISIONS.md) | every locked decision and the alternative it beat |
| [`API.md`](API.md) | the contract — what the numbers mean, the error catalog, the authoritative validation rules |
| [`ERD.md`](ERD.md) | entities, invariants, the `share_owed` view, indexes |
| [`BACKEND.md`](BACKEND.md) | how `app/` is laid out and what belongs in which layer |
| [`FRONTEND.md`](FRONTEND.md) | how `static/` is laid out, and the rules that keep it from computing money |
| [`../tests/frontend/fixtures/`](../tests/frontend/fixtures/) | the canned responses the Playwright suite renders |

## Shapes are generated; rules are written

There is no hand-maintained copy of the API's shapes anywhere in here. Fields,
endpoints, statuses and schemas come from `app/schemas.py` and the routers:

```bash
make start_dev_server     # then open /docs
make openapi              # regenerate the committed openapi.json at the repo root
make openapi-check        # what CI runs: fails if that file is stale
```

`API.md` holds only what a schema cannot state — what a number *means*, how a split
resolves, which rule produces which error code. A shape question is answered by
`/docs`; a meaning question is answered by `API.md`.

The project did once carry a second, hand-encoded spec so the frontend could be built
against a clickable contract before the backend had routes. It was deleted the moment
both halves ran against the real app: two encodings of one contract is a drift
generator, not a safety net.

## The fixtures

[`tests/frontend/fixtures/`](../tests/frontend/fixtures/) holds canned responses —
a complete trip, an empty one, one full of markup, and one file per error envelope.
`tools/mockserver.py` serves them under `/api/v1` so the Playwright suite runs the
real `static/` with no backend and no database. They are test data, which is why they
live under `tests/` rather than here.

The backend's own suite drives the real app and builds its state through the API.

When the contract changes, the fixtures change **in the same commit**. A fixture that
disagrees with `API.md` is a bug in the fixture.
