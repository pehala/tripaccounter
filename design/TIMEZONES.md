# Trip Accounter — Time zones

> The design record for time handling. The rules themselves live in `API.md` §Time,
> `ERD.md` and `DECISIONS.md`, which win where they differ; this document explains
> how the pieces fit and where each one lives.

An item happened at a real moment, in a real place. A coffee bought in Tokyo at 17:00
reads "17:00" to everyone — to the person who bought it and to the person reading the
feed from Prague afterwards — and is counted under the day of the trip it happened on.

Every time has one meaning, end to end. The server stores an instant and the zone it
happened in; the wire carries the wall time a person sees; the trip's zone cuts days
and orders the feed. Rendering is the same for every viewer (rule 4).

---

## 1. The model

| Concept | Where | Meaning |
|---|---|---|
| **Instant** | `occurred_at` on `line_item` and `wallet_transfer` | the UTC moment the row happened |
| **Row zone** | `occurred_tz` on both tables | the IANA zone the row happened in, `NOT NULL` |
| **Trip zone** | `trip.timezone` | the IANA zone that cuts the trip's days and orders its feed |

The two row columns each hold one independent fact. Postgres `timestamptz` "is stored
internally as UTC, and the originally stated or assumed time zone is not retained"
(PostgreSQL 17 manual, §8.5.1.3), and SQLite stores text, so the zone is its own
column on both databases and `occurred_at` keeps ordering, indexing and the date
functions working the same on each.

`zoneinfo` derives the offset from the two whenever it is needed, so a row edited
across a clock change gets the right offset and the picker shows the exact zone.

---

## 2. The wire

`occurred_at` is a **wall time without an offset**, `YYYY-MM-DDTHH:MM:SS`, in both
directions. Every conversion happens once, on the server.

**Input**

| Field | Rule |
|---|---|
| `occurred_at` | a wall time read in the write's zone; an offset (`Z`, `+02:00`) is `invalid_datetime` |
| `occurred_tz` | an IANA name; unknown is `invalid_timezone` |
| omitted `occurred_at` | now |

The **write's zone** is the body's `occurred_tz`; when the body omits it, the row's own
zone on `PATCH` and the trip's zone on `POST`. On `PATCH`:

| Body carries | Result |
|---|---|
| neither | instant and zone stay |
| `occurred_at` only | the wall time is read in the row's zone |
| `occurred_tz` only | the instant stays; the row reads in the new zone |
| both | the typed time is stored in the given zone |

**Resolving a wall time.** The zone is applied with `fold=0`; the instant is rendered
back to a wall time, and a mismatch means the time falls in a spring-forward gap and is
`invalid_datetime`. A time in the autumn repeat takes the earlier instant. The gap is
checked in the write's zone.

**Output.** Every item and transfer carries four time fields:

| Field | Value |
|---|---|
| `occurred_at` | the wall time in the row's own zone |
| `occurred_tz` | the row's zone |
| `trip_occurred_at` | the wall time in the trip's zone — the key clients merge items and transfers on |
| `day` | the date part of `trip_occurred_at` — the key `day_totals` sums under |

`created_at` and `updated_at` are UTC instants with `Z`.

**Trip zone.** `Trip` and the trip summary carry `timezone`, writable on `POST /trips`
and `PATCH /trips/{slug}`. A create that omits it gets `UTC`; the Setup form prefills
the browser's zone. Changing it re-cuts the days and moves `trip_occurred_at` and
`day`; each row keeps its `occurred_tz`, its `occurred_at` and its instant.

**Export.** CSV and JSON read `ItemOut`, so the CSV header carries `occurred_at` (the
row's wall time), `occurred_tz`, `trip_occurred_at` and `day`.

---

## 3. Days and order

The trip's zone cuts days for the whole trip: item `day`, `day_totals`,
`before_trip_totals` and the statistics `day` dimension. One trip has one sequence of
days, and every day total is the spending of exactly one of them.

The server sorts by instant, `occurred_at DESC, id DESC`; the exchange-rate FIFO queue
sorts the same way. The client merges items and transfers on `trip_occurred_at`, then
items first, then id, so a row always sits inside the day group its position implies.

On a trip crossing zones, a row sits under the trip day its instant falls on and its
zone marker shows its own local time: a 07:00 Tokyo breakfast in a `Europe/Prague` trip
sits under the previous Prague day, marked `Asia/Tokyo`.

`trip_occurred_at` and `day` come from the `Occurred` mixin, in Python, for every
response that carries a row. `day_totals` and statistics `day` group on
`day_of(occurred_at, trip.timezone)` in SQL. The suite asserts that the two agree
across a clock change.

---

## 4. Backend

| Where | What |
|---|---|
| `pyproject.toml` | `tzdata` is a runtime dependency: the image is Alpine, which ships `/usr/share/zoneinfo` only as an extra package, so `tzdata` gives every environment the same rules. A `tzdata` update is an ordinary dependency bump. |
| `app/models/occurred.py` | the `Occurred` mixin, shared by `LineItem` and `WalletTransfer`: declares `occurred_at` and `occurred_tz`; `resolve(wall_time, zone)` turns a wall time into the instant (`NonexistentTimeError` for a gap); `wall_time_in(zone)` renders the instant, attaching UTC first because SQLite returns it naive; `zone` is the row's `ZoneInfo`; `wire_times()` builds the four fields. The indexes stay declared on each model. |
| `app/models/trip.py` | `timezone`, and `zone` as its `ZoneInfo` |
| `app/services/timezones.py` | `timezone_error(name)` (constructs `ZoneInfo`; failure is `invalid_timezone`), `write_zone(name, row, trip)` (the rule in §2), `time_errors(wall_time, name, row, trip)` (the `occurred_tz` and `occurred_at` field errors of one write) |
| `app/services/items.py`, `transfers.py` | `validate` takes the row being updated (none on create) and calls `time_errors`; `apply_write` resolves the wall time in the write's zone and records that zone on the row |
| `app/routers/items.py`, `transfers.py` | a create seeds the instant from the clock and passes `write_zone(body.occurred_tz, None, trip)`; an update passes the row |
| `app/schemas/fields.py`, `requests.py` | `occurred_at` is a pydantic `NaiveDatetime`, an aware value is `invalid_datetime`; item and transfer writes carry `occurred_tz` |
| `app/schemas/responses.py` | the four time fields on items and transfers; `timezone` on the trip and its summary |
| `app/services/queries.py` | `day_of(column, tz)`: a SQLAlchemy construct compiled per dialect — Postgres `CAST((col AT TIME ZONE :tz) AS DATE)`, SQLite `tz_date(col, :tz)` |
| `app/db.py` | the SQLite `connect` listener registers `tz_date` (Python, `zoneinfo`, `deterministic=True`) next to `PRAGMA foreign_keys` |
| `app/services/stats.py` | the dimension registry is a per-request factory taking the trip's zone; before-trip compares the trip day with `start_date` |
| `app/seed.py` | the demo trip and every seeded row carry `DEMO_TIMEZONE` |

---

## 5. Migrations

**`d431f6f93289`** adds `trip.timezone` (`varchar(64)`, not null, server default
`UTC`). Every trip existing at that point reads in `UTC`.

**`7c2e9a41b5d8`** adds `occurred_tz` (`varchar(64)`, not null) to `line_item` and
`wallet_transfer`, in Alembic operations and SQLAlchemy Core so each database compiles
it:

1. `add_column` as nullable.
2. Copy the trip's zone with a Core `UPDATE` whose value is a scalar subquery over a
   `sa.table()` stub of `trip`, so the migration is independent of `app.models`.
3. `alter_column(nullable=False)` in batch mode — SQLite rebuilds the table, Postgres
   alters it in place. The `share_owed` view selects from `line_item`, so the
   migration drops it before the rebuild and recreates it after; the edit carries a
   comment.

Every row renders exactly as it did before the migration. `downgrade()` drops the
columns through `batch_alter_table`, with the same view handling; the instants stay.

---

## 6. Frontend

| Where | What |
|---|---|
| `static/js/fmt.js` | `wallClock(wall)` / `wallTime(wall)` read the date and time digits straight from the string; `toInputValue` returns the string's own `YYYY-MM-DDTHH:mm`, `fromInputValue` returns the typed value as it is; `nowIn(zone)` formats the current instant in a zone through `Intl` with `timeZone`; `date` / `dateRange` format a bare `YYYY-MM-DD` with `timeZone: 'UTC'`, so every viewer sees the same day |
| `static/js/zones.js` | `lastZone(trip)` / `rememberZone(trip, zone)`: the last zone saved in this trip (`localStorage`, a per-viewer convenience), else `trip.timezone`; `whenBody(state, original, toInput, fromInput)` builds a write's time fields |
| `components/TimezoneSelect.js` | a text field over a `<datalist>` of `Intl.supportedValuesOf('timeZone')`, plus the zone the field started with |
| `components/ItemModal.js`, `TransferFields.js` | the zone picker beside the time. Editing preselects the row's `occurred_tz`; a new entry starts in `lastZone(trip)` with its time from `nowIn` of that zone. Saving remembers the picked zone. |
| `ItemRow.js`, `TransferRow.js` | time from `wallTime(occurred_at)`; the row's `occurred_tz` follows it when it differs from the trip's |
| `views/Items.js` | groups by the row's `day`; merges items and transfers by `trip_occurred_at`, then items first, then id |
| `views/Map.js`, `DayGroup.js` | `day` and `wallClock` |
| `views/TripNew.js`, `setup/TripSection.js`, `TripList.js` | the trip time-zone field, prefilled with the browser's zone on create; the trip list shows each trip's zone |
| `i18n/en.js`, `cs.js` | the field labels and `invalid_timezone` |

`whenBody` sends `occurred_tz` alone when a row's zone changed and its time is as it
was, which keeps the instant; any other edit sends the typed wall time with the zone.

---

## 7. Fixing existing rows

**By trip.** Each row keeps its instant and its recorded zone; the trip's zone decides
`trip_occurred_at` and the days. Set the trip's zone in Setup according to how its
entries were made:

| How it was entered | Set the trip zone to | Result |
|---|---|---|
| Phone clock followed the travel zone | the travel zone, e.g. `Asia/Tokyo` | real local times and days |
| Phone stayed on home time, or `import_sheet --tz Europe/Prague` | the zone the times were typed in, e.g. `Europe/Prague` | times and days exactly as typed |

A purchase at 03:00, or a row on the wrong side of `start_date`, means the zone needs
another look.

**By row.** Fix a row in the edit modal. Two repairs cover every case:

- **The instant is right, the zone is wrong** (the phone followed the travel zone):
  pick the zone; the modal sends `occurred_tz` alone and the row shows its real local
  time.
- **The typed time is right, the zone is wrong** (home time, or a sheet imported under
  one zone): pick the zone and edit the time; the modal sends both, and the row sorts
  in its real place.

---

## 8. Tools

`tools/import_sheet` takes `--tz` (default `Europe/Prague`), sets `trip.timezone` to
it, and stores each cell as the wall time it holds, resolved in that zone. Every
imported row records that zone as its `occurred_tz`.

---

## 9. Verification

Every test follows `skills/writing-unit-tests`.

**Backend** (`tests/backend/test_timezones.py`, on both databases)

- a wall time written into a Tokyo trip reads back as the same digits with
  `occurred_tz` `Asia/Tokyo`; moving the trip re-cuts `trip_occurred_at` and leaves the
  row's `occurred_at` and zone as they are
- an `occurred_at` with an offset is `invalid_datetime`; a spring-forward gap is
  `invalid_datetime` on items and transfers; an autumn repeat resolves to the earlier
  instant
- `day`, `day_totals`, `before_trip_totals` and statistics `day` cut days in the trip
  zone across a clock change, and `day` agrees with `day_totals` on both sides of it
- the feed orders by instant across a clock change and across two zones, and
  `trip_occurred_at` orders the same way
- `invalid_timezone` on trip create and update, and on `occurred_tz` for items and
  transfers; a trip created without `timezone` gets `UTC`
- `17:00` / `Asia/Tokyo` written into a Prague trip reads back as `17:00`,
  `Asia/Tokyo`, with `trip_occurred_at` and `day` in Prague
- `PATCH` with `occurred_at` alone reads the time in the row's zone; with
  `occurred_tz` alone keeps the instant; with both stores the typed time in the new
  zone; a `PATCH` across a clock change keeps the zone and resolves at the new offset
- a gap time is checked in the item's own zone
- the CSV header carries the time columns, with `occurred_at` as a wall time
- items and transfers answer the same four time fields from the one mixin

**Migrations** (`tests/backend/migrations/timezones/`; the generic fixtures live in `tests/backend/migrations/conftest.py`)

Each migration has its own module. The package's `conftest.py` runs the real Alembic
revisions on a scratch database (in-memory SQLite, or a fresh Postgres database when
`TA_TEST_DATABASE_URL` is set). A module names its source and target revisions in
`migration_target` and inserts its rows in `create_old_data`, which runs at the source
revision; the migration then runs once, and the tests read the migrated database.
The `timezones/conftest.py` beside the modules holds the trip, item and transfer
inserts they share. Tables are reflected from the database as it is, so no test
carries a copy of a schema.

- `test_trip_timezone.py` (`d431f6f93289`): every trip that existed before reads in
  `UTC`, and every instant is unchanged.
- `test_occurred_tz.py` (`7c2e9a41b5d8`): trips set to `Asia/Tokyo` and
  `Europe/Prague` before the migration, with instants on both sides of the Prague
  clock change (25 Oct 2026) and around midnight UTC. Afterwards every item and
  transfer carries its own trip's zone and its original instant; an insert without
  `occurred_tz` raises `IntegrityError`; the downgrade drops the column from both
  tables and keeps the instants.

**Frontend** (Playwright, canned fixtures and the mock API)

- each row prints the time from its own string; grouping follows `day`; merging
  follows `trip_occurred_at`; the `DayGroup` header shows the right weekday in a
  browser west of UTC
- a row in another zone shows that zone beside its time
- the modal sends the typed value unchanged, with the zone; the picker preselects the
  row's zone, starts a new entry in the trip's zone, and remembers the last zone saved
- changing only the zone sends `occurred_tz` alone; changing the zone and the time
  sends both
