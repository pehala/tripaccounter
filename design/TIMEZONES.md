# Trip Accounter — Time zones

> **Status: planned.** The design record and the implementation plan, in two phases.
> Once a phase ships, its rules move into `API.md` §Time, `ERD.md` and
> `DECISIONS.md`, which then win where the two differ.

An item happened at a real moment, in a real place. A coffee bought in Tokyo at
17:00 reads "17:00" to everyone — to the person who bought it, to the person reading
the feed from Prague afterwards — and is counted under the day of the trip it
happened on.

Today the modal stores the browser's local time as a UTC instant while the feed,
`day_totals`, statistics and the before-trip split read the UTC digits back, so the
two disagree by the device's offset. This design gives every time one meaning,
end to end.

---

## The two phases

| | Phase 1 — trip time zone | Phase 2 — per-item time zone |
|---|---|---|
| **Adds** | `trip.timezone` | `occurred_tz` on items and transfers |
| **Times are shown in** | the trip's zone, every row | each row's own zone |
| **Days and order** | the trip's zone | the trip's zone |
| **Existing data** | kept as is; every trip starts on `UTC`, which matches today's feed | each row's zone copied from its trip — exactly what phase 1 showed |
| **Fixing an existing trip** | set its zone in Setup; every row follows | edit the row: pick its zone, type its time |

Phase 1 fixes every trip entered in one zone. Between the phases, each trip's zone
gets set and checked; phase 2's migration then records it on every row, so the
switch to per-item zones changes nothing anyone sees.

All times are rendered in the zone of the trip or the item — the same for every
viewer (rule 4). The wire form is the same in both phases; phase 2 only widens what
the server accepts.

---

## 1. Decisions

| Topic | Decision | Reason |
|---|---|---|
| **The wire form** | `occurred_at` is a **wall time without an offset**, `YYYY-MM-DDTHH:MM:SS`, in both directions. Input carries it with an IANA zone name in `occurred_tz`; output carries it in the row's zone with `occurred_tz` beside it. An input with an offset is `invalid_datetime`. | The client reads and writes the digits a person sees and types; every conversion happens once, on the server, through `zoneinfo`. |
| **What a day is** | **The trip's time zone** (`trip.timezone`, IANA name) cuts days for the whole trip: day groups, `day_totals`, `before_trip_totals`, statistics `day`. | One trip has one sequence of days, and every day total is the spending of exactly one of them. |
| **Ordering** | The server sorts by instant, `occurred_at DESC, id DESC`, the exchange-rate FIFO queue too. Every row carries `trip_occurred_at`, its wall time in the trip's zone; the client merges items and transfers on it. `day` is its date part. | One clock, the trip's, orders the feed and cuts its days, so a row always sits inside the day group its position implies. |
| **What a row stores** (phase 2) | The **instant** (`occurred_at`, UTC) plus the **IANA zone it happened in** (`occurred_tz`, e.g. `Asia/Tokyo`). `zoneinfo` derives the offset from the two whenever it is needed. | The zone carries its DST rules: an item edited across a clock change gets the right offset, and the picker shows the exact zone. |
| **Two columns** | `occurred_at` holds the instant, `occurred_tz` the zone. Postgres `timestamptz` "is stored internally as UTC, and the originally stated or assumed time zone is not retained" (PostgreSQL 17 manual, §8.5.1.3); SQLite stores text and SQLAlchemy writes it without `tzinfo`. | Each column holds one independent fact, and `occurred_at` keeps ordering, indexing and the date functions on both databases. |
| **Where the conversion lives** | One model mixin, `Occurred`, shared by `LineItem` and `WalletTransfer`: it declares the columns, resolves a wall time and a zone into the instant, and renders the instant back in a zone. Services and serializers call it; the two columns are read and written there only. | Items and transfers follow one rule because they run one piece of code. |
| **Resolving a wall time** | The zone is applied with `fold=0`. The result is rendered back to a wall time; a mismatch means the typed time falls in a spring-forward gap and is `invalid_datetime`. A time in the autumn repeat therefore takes the earlier instant. | `zoneinfo` resolves every wall time to some instant; the round trip is what detects the gap. |
| **Existing rows' zones** (phase 2) | **Copied from the trip's zone**, `NOT NULL`. | The trip zone was chosen and checked in phase 1, so the copy records a decision and every row renders as before. |
| **Zone of a write** | `POST`: `occurred_tz` defaults to the trip's zone. `PATCH`: an omitted `occurred_tz` leaves the row's zone as it is, and a wall time sent alone resolves in that zone; `occurred_tz` sent alone keeps the instant and changes the zone. | `POST` follows the trip, `PATCH` follows the API's rule that an omitted field is untouched. |
| **Omitted `occurred_at`** | Now, in the write's zone. | |
| **Trip time zone** | Required on the trip. The Setup form prefills the browser's zone on create; an API create that omits it gets `UTC`; existing trips get `UTC`. | Every trip has a zone from the moment it exists, and the value comes from the people on the trip. |
| **Zone rules** | `tzdata` (PyPI) is a runtime dependency from phase 1. A zone name is validated by constructing `ZoneInfo(name)`; `ZoneInfoNotFoundError` is `invalid_timezone`, and the instance, cached by `zoneinfo`, is what resolves input, renders output and computes days. | The image is Alpine, which ships `/usr/share/zoneinfo` only as an extra package; `tzdata` gives every environment the same rules. The instant is the stored truth; a row's wall time follows `tzdata`'s history for that date, and a `tzdata` update is an ordinary dependency bump. |
| **`day` and `day_totals`** | `trip_occurred_at` and `day` come from the mixin, in Python, for every response that carries a row. `day_totals` and statistics `day` group on `day_of(occurred_at, trip.timezone)` in SQL. The suite asserts that the two agree across a DST change, on both databases. | A row is serialized from the model after every write and read, and the aggregates are summed where the rows are; one implementation on each side, checked against each other at the boundary that matters. |

---

## 2. Phase 1 — trip time zone

### Data model

| Table | Column | Type | Rule |
|---|---|---|---|
| `trip` | `timezone` | `varchar(64)`, not null | an IANA name `ZoneInfo` loads |

**Migration `0004`** is one Alembic operation:
`op.add_column("trip", sa.Column("timezone", sa.String(64), nullable=False,
server_default="UTC"))`. Every existing trip gets `UTC`, which reproduces today's
feed exactly; each trip changes when someone sets its zone. `downgrade()` drops the
column.

### API

- `Trip` and the trip summary gain `timezone`, writable on `POST /trips` and
  `PATCH /trips/{slug}`. An unknown name is `invalid_timezone` (new code).
- **Input:** `occurred_at` is a wall time in the trip's zone (§1). An
  `occurred_at` carrying an offset is `invalid_datetime`. `occurred_tz` is read in
  phase 2; phase 1's request schemas leave it out, so a client that sends it is
  tolerated.
- **Output:** every item and transfer carries
  - `occurred_at` — the wall time in the trip's zone, `"2026-09-14T17:00:00"`
  - `occurred_tz` — the trip's zone, `"Asia/Tokyo"`
  - `trip_occurred_at` — the same wall time (in phase 1 the two are equal)
  - `day` — `YYYY-MM-DD`, the date part of `trip_occurred_at`, the key
    `day_totals` is summed under

  `created_at` / `updated_at` stay UTC instants with `Z`.
- **Export:** CSV and JSON read `ItemOut`, so the CSV header gains `occurred_tz`,
  `trip_occurred_at` and `day`, and `occurred_at` becomes the wall time.
- **Release:** `occurred_at` changes its wire form, so backend and frontend ship in
  one image tag, and the static cache policy (`DEPLOY.md` §6.2) serves the new
  bundle on first load after the upgrade.

### Backend

| Where | Change |
|---|---|
| `pyproject.toml` | add `tzdata` |
| `app/models/trip.py` | `timezone` |
| `app/models/occurred.py` | the `Occurred` mixin: `occurred_at` (UTC instant, declared with `sa_type` so each table gets its own column; the indexes stay declared on each model), `resolve(wall_time, zone)` and `wall_time_in(zone)`, which attaches UTC to the stored value before converting, since SQLite returns it naive |
| `app/models/items.py`, `wallets.py` | mix in `Occurred` |
| `app/schemas/fields.py` | `occurred_at` is a pydantic `NaiveDatetime`; an aware value is `invalid_datetime`; `iso_z` stays for `created_at` / `updated_at` |
| `app/schemas/requests.py` | item and transfer writes carry the wall time |
| `app/services/items.py`, `transfers.py` | call `resolve` with the trip's zone |
| `app/services/queries.py` | `day_of(column, tz)`: a SQLAlchemy construct compiled per dialect — Postgres `CAST((col AT TIME ZONE :tz) AS DATE)`, SQLite `tz_date(col, :tz)` |
| `app/db.py` | the SQLite `connect` listener registers `tz_date` (Python, `zoneinfo`, `deterministic=True`) next to `PRAGMA foreign_keys` |
| `app/routers/items.py`, `app/services/stats.py` | pass `trip.timezone` to `day_of`; the stats dimension registry becomes a per-request factory; before-trip compares that day with `start_date` |
| `app/schemas/responses.py` | `occurred_at`, `occurred_tz`, `trip_occurred_at`, `day` on items and transfers; `timezone` on the trip and its summary |
| `app/services/export.py` | the three new CSV columns |
| `app/seed.py` | the seed trip gets a zone |
| `openapi.json` | regenerated in the same commit |
| `design/` | `API.md` §Time, the CSV header line, `ERD.md`, `DECISIONS.md` |

### Frontend

| Where | Change |
|---|---|
| `static/js/fmt.js` | `wallClock(wall)` / `wallTime(wall)` read the date and time digits straight from the string. `toInputValue` returns the string's own `YYYY-MM-DDTHH:mm`; `fromInputValue` returns the typed value as it is. `nowIn(zone)` formats the current instant in a zone through `Intl` with `timeZone`. `date`/`dateRange` format a bare `YYYY-MM-DD` with `timeZone: 'UTC'`, so every viewer sees the same day. |
| `ItemRow.js`, `TransferRow.js` | time from `wallTime` |
| `views/Items.js` | groups by the row's `day`; merges items and transfers by `trip_occurred_at`, then items first, then id |
| `views/Map.js`, `DayGroup.js` | `day` and `wallClock` |
| `ItemModal.js` | prefills a new entry with `nowIn(trip.timezone)` and sends the typed wall time |
| `views/Trips.js` | shows each trip's zone, so a trip still on `UTC` stands out |
| Setup | trip time-zone field (`Intl.supportedValuesOf('timeZone')`), prefilled with the browser's zone on create |
| `i18n/en.js`, `cs.js` | the field label, `invalid_timezone` |
| `tests/frontend/fixtures/trip.json`, mock | `timezone` on the trip; wall times, `occurred_tz`, `trip_occurred_at` and `day` on rows |

### Fixing existing trips

Each row keeps its instant and is shown in the trip's zone. Set each trip's zone in
Setup according to how its entries were made:

| How it was entered | Set the trip zone to | Result |
|---|---|---|
| Phone clock followed the travel zone | the travel zone, e.g. `Asia/Tokyo` | real local times and days |
| Phone stayed on home time, or `import_sheet --tz Europe/Prague` | the zone the times were typed in, e.g. `Europe/Prague` | times and days exactly as typed |

A purchase at 03:00, or a row on the wrong side of `start_date`, means the zone needs
another look. A trip whose rows came from several zones gets its per-row zones in
phase 2.

---

## 3. Phase 2 — per-item time zone

### Data model

| Table | Column | Type | Rule |
|---|---|---|---|
| `line_item`, `wallet_transfer` | `occurred_tz` | `varchar(64)`, not null | an IANA name, validated like `trip.timezone` |

**Migration `0005`** is written in Alembic operations and SQLAlchemy Core, so
Alembic compiles it for each database. For `line_item` and `wallet_transfer`:

1. `op.add_column(table, sa.Column("occurred_tz", sa.String(64), nullable=True))`.
2. Copy the trip's zone with a Core statement over `sa.table()` stubs declared in
   the migration (the stubs pin the schema at this revision, independent of
   `app.models`):
   ```python
   op.execute(
       sa.update(rows).values(
           occurred_tz=sa.select(trip.c.timezone)
           .where(trip.c.id == rows.c.trip_id)
           .scalar_subquery()
       )
   )
   ```
3. `with op.batch_alter_table(table) as batch: batch.alter_column("occurred_tz",
   nullable=False)` — batch mode, as in `0003`, so SQLite rebuilds the table and
   Postgres alters it in place.

`downgrade()` drops the column through `batch_alter_table`. Every row renders exactly
as it did in phase 1.

**Release it once every trip's zone is set** — the trip list shows each trip's zone.
From then on, the trip zone cuts days and orders the feed, and each row's own zone
sets its time.

### API

- **Input:** `occurred_at` plus `occurred_tz`, both wall time and zone (§1).
  `POST` defaults the zone to the trip's; `PATCH` keeps the row's. An unknown zone
  is `invalid_timezone`.
- **Output:** `occurred_at` rendered in the row's own zone, `occurred_tz` the row's
  zone, `trip_occurred_at` and `day` in the trip's zone, as in phase 1.

### Backend

| Where | Change |
|---|---|
| `app/models/occurred.py` | `occurred_tz` joins the mixin; `occurred` becomes a property that resolves from and renders in the row's own zone |
| `app/schemas/requests.py` | `occurred_tz` on item and transfer writes |
| `app/services/items.py`, `transfers.py` | pass the write's zone: the body's, else the trip's on create, else the row's on update |
| `app/schemas/responses.py` | `occurred_at` and `occurred_tz` from the row |
| `app/seed.py`, `openapi.json`, `design/` | as in phase 1 |

### Frontend

| Where | Change |
|---|---|
| `ItemModal.js`, `TransferFields.js` | zone picker (`Intl.supportedValuesOf('timeZone')`), preselected with the row's `occurred_tz` when editing. A new entry defaults to the last zone picked in this trip (`localStorage`, a per-viewer convenience), else `trip.timezone`; its time prefills with `nowIn` of that zone. The modal sends the typed wall time with the picked zone. |
| `ItemRow.js`, `TransferRow.js` | show the zone next to the time when `occurred_tz` differs from `trip.timezone` |
| `i18n`, fixtures, mock | picker label; a multi-zone day and a row in a zone other than the trip's |

On a trip crossing zones, a row sits under the trip day its instant falls on, and its
zone marker shows its own local time: a 07:00 Tokyo breakfast in a `Europe/Prague`
trip sits under the previous Prague day, marked `Asia/Tokyo`.

### Fixing existing trips

Fix a row in the edit modal. Two repairs cover every case:

- **The instant is right, the zone is wrong** (the phone followed the travel zone):
  pick the zone; the modal sends `occurred_tz` alone and the row shows its real
  local time.
- **The typed time is right, the zone is wrong** (home time, or a sheet imported
  under one zone): pick the zone and keep the time; the modal sends both, and the row
  sorts in its real place.

For a trip with many such rows, a one-time bulk tool (`rezone --keep instant|wall`,
per trip and country, dry run by default) can be added when that trip comes up.

---

## 4. Tools

`tools/import_sheet`, in each phase's PR:

- **Phase 1:** `--tz` (default `Europe/Prague`) sets `trip.timezone`; each cell is
  posted as the wall time it holds, and the server resolves it in that zone. The
  tool's own `ZoneInfo` conversion goes away.
- **Phase 2:** each row is posted with `occurred_tz` set to that same zone.

---

## 5. Implementation steps

| # | PR | Contents |
|---|---|---|
| 0 | `docs(design): document postgres and sqlite support, add time zone plan` | `ARCHITECTURE.md`, `DECISIONS.md`, the skill intro, this file |
| 1 | `feat: add a trip time zone` | all of §2 — migration `0004`, the mixin, backend, frontend, `import_sheet`, `openapi.json`, design docs, tests on SQLite, Postgres and Playwright |
| — | **release; set every trip's zone in Setup** | |
| 2 | `feat: record a time zone per item` | all of §3 — migration `0005`, backend, frontend, `import_sheet`, `openapi.json`, design docs, the migration chain test covering `0004` and `0005`, tests |

Each phase is one PR. Phase 1 changes `occurred_at`'s wire form, so its backend and
frontend ship together; phase 2 adds the picker and the server's acceptance of
`occurred_tz` in one step so a picked zone is honoured from the first build that
shows the picker.

---

## 6. Verification

Every test follows `skills/writing-unit-tests`. Backend, on both databases:

**Migration chain — `tests/backend/test_migrations.py`** (phase 2)

One test walks the upgrade path a deployment lives through, at the database level
only. It runs on its own engine (in-memory SQLite, or a fresh Postgres database when
`TA_TEST_DATABASE_URL` is set) and reads and writes through `sa.table()` stubs
declared in the test, one set per revision it touches. Every `command.upgrade` /
`command.downgrade` targets a named revision. The test therefore keeps checking
exactly these two migrations as later revisions and model changes land.

1. `command.upgrade(cfg, "0003")`, then insert through the `0003` stubs: two trips,
   items and transfers in each, with instants on both sides of a DST change (Prague,
   25 Oct 2026) and around midnight UTC. Record every `occurred_at`.
2. **Migration a** — `command.upgrade(cfg, "0004")`. Assert every trip's `timezone`
   is `UTC` and every `occurred_at` equals step 1's.
3. **Set the trip zones**, as users do between the phases: trip one to
   `Asia/Tokyo`, trip two to `Europe/Prague`, with `sa.update` on the `0004` trip
   stub.
4. **Migration b** — `command.upgrade(cfg, "0005")`. Assert:
   - every item's and transfer's `occurred_tz` equals its own trip's zone
   - every `occurred_at` equals step 1's, on both sides of the DST change
   - an insert into each table without `occurred_tz` raises `IntegrityError`
5. `command.downgrade(cfg, "0003")`, then assert every `occurred_at` equals step 1's.

**Phase 1**
- a wall time written into a Tokyo trip reads back as the same digits with
  `occurred_tz` `Asia/Tokyo`, and follows `PATCH /trips/{slug}` when `timezone`
  changes; the instant stays the same
- an `occurred_at` with an offset is `invalid_datetime`; a spring-forward gap is
  `invalid_datetime`; an autumn repeat resolves to the earlier instant
- `day`, `day_totals`, `before_trip_totals` and statistics `day` cut days in the trip
  zone across a DST change, and `day` agrees with `day_totals` on both sides of it
- the feed orders by instant across a DST change, and `trip_occurred_at` orders the
  same way
- `invalid_timezone` on create and update; a create without `timezone` gets `UTC`
- the CSV header carries the three new columns and `occurred_at` as a wall time
- items and transfers answer the same four time fields from the one mixin

**Phase 2**
- `17:00` / `Asia/Tokyo` written into a Prague trip reads back as `17:00`,
  `Asia/Tokyo`; its `trip_occurred_at` and `day` are the Prague time and date of
  that instant
- a `PATCH` with `occurred_at` alone keeps the row's zone; one with `occurred_tz`
  alone keeps the instant
- an item moved by an edit across a DST change keeps its zone and resolves at the
  new offset
- migration `0005`: covered by the migration chain test
- the feed orders by instant across two zones

Frontend: each row prints the time from its own string; grouping follows `day`;
merging follows `trip_occurred_at`; the `DayGroup` header shows the right weekday in
a browser west of UTC; the modal sends the typed value unchanged; (phase 2) a row in
another zone shows that zone, the picker preselects the row's zone, and the modal
sends the typed wall time with the picked zone.
