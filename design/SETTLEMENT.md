# Trip Accounter — Settlement

> **Status: proposed.** The design record; once shipped, the rules themselves live in
> `ERD.md` §settlement, `API.md` §settlement and `DECISIONS.md`, which win where the
> documents differ.

At the end of a trip the group agrees on one currency to settle in and one rate per
other currency, hands the money over, and wants that agreement to stay put. **Settling
a trip** stores the agreed target currency and rates on the trip and locks every
field that feeds a balance. The Balances and Statistics Total sections then read the
stored rates, so the converted figures the group paid against stay exactly as they
were when they paid. Everything that leaves the balances unchanged — names, notes,
labels, countries, dates, locations — stays editable.

---

## What this lets you do

**1. Agree and settle.** An Iceland trip spent in EUR, ISK and CZK. On Balances, the
Total section is set to EUR with *1 ISK = 0.0073 EUR* and *1 CZK = 0.04 EUR*; the
settle-up list says *Bob → Ann 212.40 EUR*. Bob pays. Ann presses **Fix rates &
settle** and confirms. The trip is now settled: the badge reads *Settled on
14 Sep 2026*, the rate form shows EUR, 0.0073 and 0.04 read-only, and Statistics'
Total shows the same rates the same way.

**2. Keep tidying up.** A week later Ann relabels a dinner `restaurant`, fixes a typo
in a name and moves an item to the right country. All of it saves. Bob opens a
grocery item to change its amount: the amount, currency, payer and split fields are
disabled, with a hint that the trip is settled.

**3. Correct a mistake.** A forgotten 18 000 ISK receipt turns up. Ann presses
**Unlock**, confirms, adds the item, and settles again with the same or new rates.
Locking and unlocking repeat as often as needed; each settle records the agreement
of that moment.

---

## 1. Decisions

| Topic | Decision | Reason |
|---|---|---|
| **What is stored** | The target currency, one rate per other trip currency, and `settled_at`. | These are the facts the group typed and agreed. With the money fields locked, every balance and every Total figure is a pure function of stored data and these rates, so they reproduce exactly on every read. |
| **Where it is stored** | Two columns on `trip` (`settled_at`, `settlement_currency_id`) and one on `trip_currency` (`settlement_rate_scaled`). | A trip holds at most one settlement, so its fields depend on the trip key; a rate is one value per trip currency, so it depends on the currency key. Each fact sits on the row it describes, and `TripOut` already loads both. |
| **Where conversion happens** | In the browser, in `convert.js`, exactly as for the unsettled Total. The server stores and validates the rates. | One conversion path for settled and unsettled trips, so a settled Total equals the Total the group saw before pressing the button. |
| **What the lock covers** | Every field that enters `net`: item `amount`, `currency_id`, `payer_id`, `split_mode`, `shares`, item create and delete; every transfer, whole: create, update and delete. | These change a balance. A transfer is money moving, so it is frozen as a unit: moving one across owners shifts `net`, and an exchange's `occurred_at` sets its place in the exchange-rate queue. A transfer's note is frozen with it and is corrected by unlocking. Every item field outside `net` stays free, so a settled trip stays a living record. |
| **How the lock compares** | A locked field is rejected when its value differs from the stored one; resending the stored value succeeds. Shares compare after resolving. | `ItemModal` sends the full body on every edit, and so may any client; comparing values keeps every existing caller working. |
| **Where the lock lives** | `services/settlement.py`: `settle(...)`, `unlock(...)`, `assert_unchanged(...)` for the item fields, called from the item service, and `assert_unsettled(...)` for the whole-object locks, called from item create and delete, currency create and delete, and every transfer route. The settle-up suggestion module `services/settle.py` becomes `services/settle_up.py` in the same change. | One rule, one place; the API, the frontend and `curl` all meet the same check. Each module name says what it holds: `settle_up` the suggested payments, `settlement` the stored agreement and its lock. |
| **Lifecycle** | `PUT /settlement` writes the whole agreement, on an unsettled trip or over a settled one; `DELETE /settlement` unlocks. Both repeat any number of times. Every `PUT` replaces the target, every rate and `settled_at`; unlock clears all three, each in one transaction. | Mistakes surface after a trip too. A mistyped rate is corrected with one call, and every write starts from a clean slate, so nothing from an earlier agreement remains. `PUT` is the verb because the body is the whole agreement; `API.md` §settlement records this as the API's one `PUT`. |
| **Rate precision** | `RATE_SCALE` (10⁻⁹), typed as a canonical decimal string with up to 9 places, read as *1 this currency = rate target currency* — the reading the rate form already shows. A `Rate` field type in `schemas/fields.py`, beside `Amount` and `Weight`, parses it. | Matches `GET /exchange-rates`. The rate form prefills six significant digits from `fmt.rate`, and nine places hold any value typed or prefilled. |
| **Rates required** | One per trip currency other than the target, and currency create is locked while settled. | The rule the rate form and both pages' `allRatesSet` already apply, so the button is enabled exactly when the server will accept. `PUT /settlement` reads the roster alone and computes no balances. A currency created on a locked trip could carry nothing, so locking it keeps every currency rated. |
| **Frontend shape** | One hook, `useTotalRates`, and one component, `TotalRatesPanel`, rendered by both Balances and Statistics. | Both pages show the same Total controls and the same lock state; a change to either lands on both. |

---

## 2. Data model

Migration `0004`:

```
TRIP           + settled_at             datetime NULL
               + settlement_currency_id int NULL
               FK fk_trip_settlement_currency
                  (settlement_currency_id, id) -> trip_currency (id, trip_id)
                  ON DELETE NO ACTION
               CHECK ((settled_at IS NULL) = (settlement_currency_id IS NULL))

TRIP_CURRENCY  + settlement_rate_scaled bigint NULL    -- ×10⁹
```

- **The target references its own trip.** The composite key against the existing
  `trip_currency (id, trip_id)` unique constraint makes the target a currency of the
  same trip.
- **The key is named by hand.** The naming convention covers single-column keys, so
  the model declares a `ForeignKeyConstraint` named `fk_trip_settlement_currency`
  in `Trip.__table_args__`, and migration `0004` creates it under the same name.
  `trip_scoped_fk` serves keys whose trip column is `trip_id`; on `trip` that column
  is `id`, so this key is written out in full.
- **The key is circular.** `trip_currency.trip_id` already references `trip`. The
  model declares the new constraint with `use_alter=True`. With two keys between the
  two tables, `Trip.currencies` and `TripCurrency.trip` name their key with
  `foreign_keys=[TripCurrency.trip_id]`. The settlement columns are plain columns
  with no relationship of their own: `TripOut.settlement` reads
  `settlement_currency_id` and `settled_at` from the trip and the rates from
  `trip.currencies`, which it already loads.
- **Deleting a settled trip.** The cascade from `trip` to `trip_currency` is the
  ORM's, so the currencies are deleted in their own statement while the trip row
  still exists. `DELETE /trips/{slug}` therefore first calls `settlement.unlock`,
  which clears `settled_at`, `settlement_currency_id` and every
  `settlement_rate_scaled` together, and flushes; then it deletes the trip. The trip
  row names no currency by the time the currencies go, and the check holds at every
  step, on SQLite and Postgres alike.
- **Migration `0004` runs in batch mode.** SQLite cannot add a foreign key or a
  check constraint in place, and the backend suite upgrades to head on SQLite. The
  migration adds the three columns, then adds the key and the check inside
  `op.batch_alter_table("trip")`, as `0003` does for `item_label`.
- **The rates follow the trip's state.** The service maintains it, and a test over
  the seeded database asserts it:
  - a settled trip has a rate on every currency except the target;
  - the target has no rate;
  - an unsettled trip has no rate on any currency.

---

## 3. API

| Endpoint | Behaviour |
|---|---|
| `PUT /trips/{slug}/settlement` | Body `{target_currency_id, rates: [{currency_id, rate: "<decimal>"}]}`, the shape `TripOut.settlement` answers with, rates as strings on the way in like every decimal. Validates, replaces whatever is stored, sets `settled_at` from `ClockDep`, answers `200` with the trip. |
| `DELETE /trips/{slug}/settlement` | Clears the settlement, answers `200` with the trip. |
| `TripOut.settlement` | `null`, or `{target_currency_id, settled_at, rates: [{currency_id, rate}]}` with rates in trip currency order and `rate` a plain number to 9 places. |

`settlement_rate_scaled` stays internal: `CurrencyOut` keeps its shape, and the
settlement has one home on the wire.

**Error codes** (`API.md` §4, both i18n catalogs). Every one travels inside the
standard envelope: a `409 conflict` or `422 validation_error` whose `fields` is keyed
by the request field, so `FieldError` renders each under its input. `fields.id` is
the object-level slot, the one `in_use` and `is_default` already use; the setup
sections and `ItemModal` show it in the flash (§5).

| Code | Status | Under | `params` | When |
|---|---|---|---|---|
| `trip_settled` | 409 | `fields.<field>` | | A locked item field whose value differs from the stored one. |
| `trip_settled` | 409 | `fields.id` | | Item create or delete, any transfer write, and currency create or delete, on a settled trip. |
| `trip_not_settled` | 409 | `fields.id` | | `DELETE /settlement` on an unsettled trip. |
| `missing_rate` | 422 | `fields.rates` | `{currency_id}` | A trip currency other than the target has no rate. |
| `invalid_rate` | 422 | `fields.rates` | `{currency_id}` | A rate for the target or for a currency outside the trip, or a value `≤ 0` or off the `Rate` grammar. |
| `not_in_trip` | 422 | `fields.target_currency_id` | | The target is not a currency of this trip — the existing code. |

---

## 4. The lock

On a settled trip:

| Object | Locked | Editable |
|---|---|---|
| **Item** | create, delete; `amount`, `currency_id`, `payer_id`, `split_mode`, `shares` | `name`, `note`, `city`, `country_id`, `labels`, `map_url`, `lat`, `lon`, `occurred_at`, `wallet_id` within the payer's own wallets |
| **Transfer**, same-owner and cross-owner alike | create, update, delete | — |
| **Currency** | create, delete | `symbol`, `is_primary` |
| **Person, country, label, wallet** | — | everything (existing guards apply as today) |
| **Trip** | the settlement fields, which `/settlement` alone writes | `name`, dates, `note`, `archived` |

`preview-split` stays open: it saves nothing.

---

## 5. Frontend

**`useTotalRates(store)`** in `rates.js` — the one source of the Total's rates for
both pages. It returns `{target, values, ready, settlement, onTargetChange,
onRateChange}`:

- **Unsettled.** Target and values come from `localStorage`, as today.
- **Settled.** They come from `trip.settlement`, and both handlers are inert.
- **`ready`.** True once every trip currency other than the target has a rate — the
  rule `allRatesSet` applies today in `Balances.js` and `Stats.js`, moved into the hook
  so both pages share one copy. It is the server's `missing_rate` rule, so the settle
  button is enabled exactly when `PUT` will succeed.
- **`rateFor`.** Accepts a stored numeric rate alongside a typed string.
- **Settling.** The hook builds the `PUT` body: it parses each typed rate with the
  viewer's locale and sends it as a canonical decimal string, as every money input
  is sent today.

**`TotalRatesPanel`** in `components/` — wraps `RatesForm` and the two alerts that
both pages render today. Balances and Statistics each render it and keep only their
own combining step (`combineGroup`/`combineSuggestions` and `combineRows`).

- **Unsettled.** The form is editable. Once `ready`, a **Fix rates & settle** button
  opens a confirmation, sends `PUT`, and reloads the trip.
- **Settled.** The form shows the stored target and rates read-only, with a *Settled
  on {date}* badge and an **Unlock** button. Unlock opens a confirmation, sends
  `DELETE`, and reloads the trip.

**Elsewhere on a settled trip:**

- **Per-currency balance blocks.** They carry the same badge.
- **`ItemModal`, items.** The amount, currency, payer and split controls are
  disabled with a hint, and Delete is hidden.
- **`ItemModal`, transfers.** Every control is disabled with the same hint, and
  Delete is hidden.
- **`ItemModal`, errors.** `save` and `remove` send `fields.id` to the flash and the
  remaining `fields` to their inputs, so a `trip_settled` from a tab that still shows
  the trip unsettled reaches the user.
- **Feed.** *Add expense* and *Add transfer* are disabled.
- **Setup.** The currency add form and Delete on every currency are disabled. The
  trip section offers *Archive* next to the settled badge.

---

## 6. How it meets the rest of the app

| Feature | Behaviour on a settled trip |
|---|---|
| **Balances, per currency** | Computed live, as always; the inputs are frozen, so the figures are too. |
| **Balances and Statistics Total** | Stored target and rates through `TotalRatesPanel`; `localStorage` rates return when the trip is unlocked. |
| **Statistics, per currency** | Unchanged arithmetic; the figures stay fixed because amounts and currencies are locked. Label, country, city and day groupings follow the free fields. |
| **Wallets** | Transfers are locked, so a tracked wallet's balance moves only when an item is moved between the payer's own wallets. |
| **Exchange rates** | Computed live, as always. Exchanges are locked, and the queue also reads what each person still holds in tracked wallets, so moving an item between the payer's wallets updates `rate`, `leftover` and `leftover_rate`. Balances and the stored agreement stay as settled. The rate form keeps showing the live rates as links while unsettled. |
| **Map** | Follows `lat`/`lon`/`map_url`, which stay editable. |
| **Export** | The JSON export's `trip` object is `TripOut`, so it carries `settlement` with no change to the writer; the CSV keeps its header. |
| **Sheet import** | Writes into a trip it has just created, which starts unsettled. |
| **Archive** | Independent flag; settling and archiving combine freely. |

---

## 7. Amended decisions

- **`CLAUDE.md` rule 3 and `DECISIONS.md` §1 *Currency*.** Settling a trip stores
  its Total target and rates on the trip. The browser applies them; balances and
  statistics stay per currency on the server.
- **`DECISIONS.md` §2 "Why no currency conversion server-side".** An agreed
  settlement rate is a historical fact the group typed, like the two sides of an
  exchange, and it is stored as one.
- **`DECISIONS.md` §1 *Paybacks*.** A settlement records the agreement the group
  paid against. Payments themselves are cross-owner wallet transfers, as today.
- **`FRONTEND.md` §4.** The Total's rates come from `useTotalRates`: the trip's
  settlement when present, `localStorage` otherwise.

---

## 8. Tests

**Backend** (`tests/backend/test_settlement.py`, per `skills/writing-unit-tests`):

- **Settle.** `PUT` stores the target, the rates and `settled_at`, and `TripOut`
  echoes them.
- **The lock.**
  - Each locked field rejects a changed value with `trip_settled` under
    `fields.<field>`.
  - Each locked field accepts its stored value.
  - Item create and delete, currency create, and transfer create, update and
    delete, same-owner and cross-owner alike, are rejected with `trip_settled` under
    `fields.id`.
  - Every editable field saves.
- **Lock/unlock cycles.** Settle → unlock → settle with a different target and rates
  → unlock → settle. After every step:
  - `TripOut.settlement` holds exactly the latest agreement;
  - no rate from an earlier cycle remains on any currency;
  - locked edits fail while settled and succeed while unlocked;
  - `GET /balances` is identical before and after each settle and unlock.
- **Errors.**
  - a trip currency without a rate gives `missing_rate` under `fields.rates` with
    its `currency_id`; a rate for the target, for a foreign currency, `0`, a negative
    value and a non-canonical string each give `invalid_rate`; a target outside the
    trip gives `not_in_trip` under `fields.target_currency_id`;
  - a second `PUT` with a new target and rates replaces the first, and
    `TripOut.settlement` shows only the second; unlocking twice gives
    `trip_not_settled`;
  - deleting any currency on a settled trip gives `trip_settled`.
- **Schema.**
  - Deleting a settled trip succeeds and leaves no row of it behind, on SQLite and
    Postgres — the test that guards the delete route's unlock step.
  - The settlement invariant holds over the seeded database.

**Frontend** (Playwright, a settled variant of `fixtures/trip.json`):

- **Both Balances and Statistics, one parametrized test.** The Total shows the stored
  target and rates read-only, the badge, and Unlock.
- **Settle → unlock → settle**, with `page.route` stubs. The buttons switch and the
  form toggles between editable and read-only on every step.
- **Settled trip.** Item money controls and every transfer control are disabled,
  *Add expense* and *Add transfer* are disabled, Delete is hidden, and editable
  fields remain enabled.
- **Stale tab.** A `page.route` stub answers an item save with `trip_settled` under
  `fields.id`, and the flash shows it.

**Seed.** A second trip, seeded settled, so the demo and the invariant test cover
the state. `iceland-2026` stays unsettled, and `test_seed.py` keeps asserting on it.

---

## 9. Build order

1. Model: the three columns, the `use_alter` key `fk_trip_settlement_currency`, and
   `foreign_keys` on `Trip.currencies` and `TripCurrency.trip`. Migration `0004`:
   columns first, then the key and the check inside
   `op.batch_alter_table("trip")`. Verify the upgrade on SQLite and Postgres and the
   downgrade on both before moving on.
2. Rename `services/settle.py` to `services/settle_up.py` and its import in
   `balances.py`.
3. `services/settlement.py` — settle, unlock, `assert_unchanged`, `assert_unsettled`
   — wired into the item service, every transfer route, currency create and delete,
   and the trip delete route; the backend tests.
4. The `Rate` field type in `schemas/fields.py`; schemas and routers; `make openapi`.
5. Frontend:
   1. Extract `useTotalRates` and `TotalRatesPanel` with behaviour unchanged.
   2. Add the settled state.
   3. Add the item and transfer lock, and route `fields.id` to the flash in
      `ItemModal`.
   4. Write the Playwright tests.
6. `ERD.md`, `API.md` (including the note on `PUT`), `DECISIONS.md`,
   `FRONTEND.md`, `CLAUDE.md`; this document's status moves to *shipped*.
