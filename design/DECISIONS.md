# Trip Accounter — Decisions

What was decided, and what it beat. A decision listed here is not re-litigated
casually: several of them are load-bearing for the others, and the dependency runs in
one direction.

```mermaid
flowchart TD
    a["<b>Pure JSON API</b><br/>no server-rendered HTML"]
    b["<b>No presentation<br/>server-side</b>"]
    c["<b>i18n is frontend-only</b><br/>errors are {code, params}"]
    d["<b>Static Preact frontend</b><br/>no build step"]
    e["<b>Integers inside,<br/>numbers at the edge</b>"]
    f["<b>No currency conversion<br/>server-side</b>"]
    g["<b>No 'current user'</b>"]
    h["<b>Paybacks not recorded</b>"]

    a --> b --> c
    a --> d
    b --> e
    e --> f
    g --> h

    style a fill:#e7f0ff,stroke:#4a7fd4
    style b fill:#e7f0ff,stroke:#4a7fd4
    style e fill:#e9f7ee,stroke:#3f9e5f
```

---

## 1. The locked set

| Topic | Decision |
|---|---|
| **Auth** | None. The VPN is the perimeter. A trip is reachable at `/t/{slug}`. |
| **Backend** | **Pure JSON REST under `/api/v1`.** No templates, no HTML fragments, no form posts. It knows nothing about the frontend; the frontend is one client among any. Static files are mounted at `/` as a deployment convenience only. |
| **Frontend** | **Static, client-rendered.** Preact + htm as ES modules through an import map, Bootstrap 5 for the modal and tabs, pinned versions with SRI hashes. No build step, no Node, no npm at runtime. Page width is Bootstrap's own `.container`: the 48 rem cap the first commit inlined into three containers is gone, so the balances and statistics grids get the room they were built for and the map gets the window. |
| **Currency** | Multi-currency, **zero conversion server-side**. Balances, settle-up and each currency's own stats are strictly per currency. Both the balances and statistics pages' Total section convert client-side with rates the user types, kept in `localStorage` and shared between the two pages, and only compute once every currency has one. |
| **i18n** | **Frontend-only, from the first commit.** `en` (source) and `cs` as flat ES modules; `t()` over `Intl.PluralRules` / `NumberFormat` / `DateTimeFormat`, no library. Adding a language is one file plus one line. **The API has no language at all**: errors are `{code, params}` with no message, amounts cross the wire in one canonical grammar, and `app/` contains no user-facing string. |
| **Money** | **Only typed values are stored, as integer hundredths, for every currency.** Computed shares are a SQL view in integer micro-units, never stored, never rounded per item. Balances and stats are `GROUP BY` over hundredths and that view. Input is a canonical decimal string; output is plain JSON numbers — typed to 2 places, computed to 6. **Rounded exactly once**, in settle-up, with a zero-sum correction. No `Currency.decimals`, no `*_display`, no `*_minor` on the wire. |
| **Statistics** | **One `GROUP BY` engine over a dimension registry**, not a fixed set of breakdowns. `?group_by=` takes any chain of `label`/`country`/`person`/`day`/`city`/`payer`/`wallet`, at any depth; `currency` is prepended to every chain and is never a choice. A chain is answered with its own prefixes, which is where a nested view's subtotals come from — `ROLLUP`/`GROUPING SETS` would do it in one query but SQLite has neither, and the client may not sum a column. |
| **Splits** | Equal by default; override to weighted shares or exact amounts. Computed server-side only; `preview-split` gives the form live numbers from the same expression that will be saved. |
| **Paybacks** | **A settle-up suggestion is never recorded as paid** — no "Mark paid". A wallet transfer is different: it is a real, typed movement of money, and one between two people's wallets is exactly the amendment this row used to reserve for later (§2, "Why paybacks are not recorded"). |
| **Wallets** | Every person gets one untracked, default wallet (`Card`) on creation, server-assigned. A wallet is either untracked (unlimited, no balance) or tracked (`received − sent − spent` per currency). Transfers between wallets have no stored exchange rate — both typed sides — and an exchange is same-owner only. |
| **Map** | **Leaflet 1.9.4 as one ESM module, OpenStreetMap's standard raster tiles, no key.** The map tab reads the coordinates the item feed already carries, filters them client-side, and never totals what a pin holds. Dark mode inverts the tile pane in CSS; there is no second tile provider and no geocoding. |
| **Viewer** | **No "current user" anywhere.** An item states who paid and what each person owes. Nothing is rendered relative to a viewer. |
| **Countries** | A strict per-trip list, **required on every item**. Managed in Setup like people and currencies; the item form only picks. Independent of currency. |
| **Labels** | Free-typed, many per item, trip-scoped, auto-created on first use. **Space-separated in the input**, so one label is one token — `street-food`, never `street food`. Always an array on the wire. |
| **Slug** | Generated from the trip name, `-2`/`-3` on collision, immutable afterwards. |
| **DB** | SQLite via SQLAlchemy 2.0 + Alembic, schema kept Postgres-compatible. Python ≥ 3.13. |
| **Tooling** | **uv** for dependencies and lockfile. **Makefile** as the only UX. **lefthook** hooks: ruff on staged files at commit, lint + backend tests at push. **GitHub Actions** runs the same make targets. |

---

## 2. Why not the obvious alternatives

### Why not Jinja or HTMX
Both make the backend render HTML for one specific frontend. That is exactly the
coupling this design removes: the API has to be usable by a script, a phone shortcut
or `curl`. HTMX in particular is hypermedia by definition and cannot sit on a pure
JSON API without a second template layer in the browser anyway.

### Why Preact + htm, not vanilla, Vue, or a Vite build
Real components for the modal, the split editor and the label chips, at about 5 KB,
with no toolchain. htm is HTML in tagged templates, so markup ports almost verbatim.
Vue's CDN build would also work and is heavier; vanilla is where 150 lines becomes
600 and state bugs live; a Vite build buys nothing at this size and costs a Node
dependency in every environment. Because the backend is decoupled, this choice is
swappable later without touching it.

### Why integers rather than `Decimal` all the way down
JSON has no decimal type, so the wire is float64 regardless. Storing integers means
the database and every sum are exact by construction, and the one place precision
could be lost — the division that makes a share — is pushed into a floored integer
expression whose error is bounded at 10⁻⁶ per share and never accumulates.

### Why a SQL view rather than an `allocate()` helper
An allocator has to hand the remainder cent to *somebody*, which is a policy decision
that then has to be stable across edits, exports and re-reads. A floored view has no
remainder to hand out: everybody is a few micro-units short, invisibly, and the money
is reconciled once at settle-up where a human is looking anyway. It is also set-based,
so balances and statistics stay one query as a trip grows.

### Why no currency conversion server-side
A stored rate is a lie with a timestamp. Rates are the user's own guess about what
they will actually pay, they differ per person and per card, and persisting one would
make every historical balance depend on when it was computed. Per-currency balances
are always true; the Total section's figures are explicitly the user's own arithmetic,
in their own browser, never sent back — and it shows nothing at all until every
currency has a rate, rather than a partial sum that silently drops the ones missing
one.

### Why no "current user"
There are no accounts, and a trip is shared by URL. Any "you owe" framing would have
to guess who is holding the phone. Stating who paid and what each person owes is both
simpler and correct for every viewer.

### Why paybacks are not recorded
A settlement table turns a holiday tracker into a ledger with its own reconciliation
problems, for a workflow that happens once. **Amended by wallets:** the
`SETTLEMENT(from, to, currency, amount)` entity this section used to describe as a
future, additive slot is exactly what a cross-owner `WALLET_TRANSFER` is — `net`
gains `+ sent − received` from it, precisely as anticipated (`ERD.md`). What stays
true is narrower than the original claim: a *settle-up suggestion* is still never
recorded as paid, and there is still no "Mark paid" button. A wallet transfer isn't a
payback record in that sense — it's Ann physically handing Bob cash for the
guesthouse, something that happened regardless of whether the app tracks it, and the
app tracking it is what keeps `net` honest afterwards.

### Why wallets are per-person pots, not one shared kitty
A trip's money doesn't move as a single pool — cash lives in one person's pocket,
a card in another's, and knowing which pot paid for what is what lets an overcharge
show up as a wallet running negative instead of a mystery in the balances. The
alternative — a `kind` column on `line_item`, or joined-table inheritance for
transfers — was rejected because it makes every existing `SUM(amount_minor)` in the
codebase (the statistics groupings, `day_totals`, `total_spent`, the CSV export, the
`share_owed` view) silently wrong until it starts filtering by kind, and both shapes
force a country and a fake split onto something that is not an expense. A separate
`wallet_transfer` table changes the meaning of nothing that already exists — see
`WALLETS.md` §1 for the full comparison, including why a wallet's currency is left
unset (a wallet holds any currency, like everything else in this app) and why the
migration was frozen to explicit `op.create_table` calls rather than
`metadata.create_all` while adding it.

### Why Leaflet and OSM tiles, not MapLibre, CARTO or a keyed provider
MapLibre GL is the better renderer and has real dark styles, but it is ESM-only across
three chunks pulled by dynamic import — which take no `integrity` attribute — plus a
worker and a WebGL context, about 1 MB for a page that draws a few dozen dots. Leaflet
ships one ESM file that the import map pins and hashes. On tiles: CARTO's keyless raster
basemaps started serving an `API KEY REQUIRED` watermark at the end of August 2026, and
Mapbox, Google, Stadia and MapTiler all want an account in an app whose premise is that
it has none. `tile.openstreetmap.org` needs nothing but visible attribution and casual,
viewport-only use, which is what a VPN-only trip tracker does. It has no dark variant, so
dark mode inverts the tile pane — one CSS rule instead of a second provider. If OSM ever
rate-limits us, OpenFreeMap is keyless too, and taking it means taking MapLibre with it.

### Why no authentication
The VPN is the perimeter and the trust boundary is a group of people who are already
on holiday together. This is a real limitation, not an oversight — see the warning in
[`ARCHITECTURE.md`](ARCHITECTURE.md) §7.

---

## 3. Deliberately out of scope

Receipt photos, recurring expenses, per-item comments, undo history, PWA/offline,
item-list pagination, more than two languages. The map tab draws the coordinates an
expense already carries and nothing more: no geocoding of a `city` (Nominatim's policy
forbids bulk lookups and there is no queue to do it politely), no per-location totals
(a `by_location` SQL aggregate, the day the question is asked) and no marker clustering
(`leaflet.markercluster` is UMD-only and could not enter the import map). The model and
the API leave room for each; none is needed to settle a holiday.
