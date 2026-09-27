# Trip Accounter — Average exchange rates

> **Status: shipped.** Issue #37. The design record; the rules themselves live in
> `API.md` §exchange rates, which wins where the two differ.

At the end of a trip, a person wants to know what their foreign money really cost:
every exchange they made into ISK, net of anything they changed back, divided by the
ISK they actually spent — so ISK still sitting in a wallet makes the rate worse, not
better. The app computes that **effective rate** per person and per currency pair,
shows it on the Wallets tab, and offers it as a one-click prefill for the Total
section's typed rates.

---

## What this lets you do

**1. See what your krónur cost.** Petr withdrew twice: `Card 100 EUR → Cash 14 000 ISK`
and `Card 50 EUR → Cash 7 200 ISK`. He spent 19 000 ISK; 2 200 ISK is still in *Cash*.
The Wallets tab, under Petr, says *1 ISK = 0.007894736 EUR* (150 EUR / 19 000 ISK).

**2. Change the leftover back.** On the last day he records `Cash 2 200 ISK → Card
14 EUR`. Both sides are netted out: 136 EUR for 19 000 ISK spent, 0 left. The rate
improves to 0.007157894.

**3. Use it for the Total.** On Balances or Statistics, the rate form under
*1 ISK = … EUR* shows *Petr 0.007157894* as a link; under *1 EUR = … ISK* it shows
the inverse, *Petr 139.706*. One click fills the input; it is now
an ordinary typed rate, stored in `localStorage` like any other.

**What it does not do.** No stored rate, no rate on a transfer row, no conversion of
any balance or statistic. The rate never enters a currency's own numbers.

---

## 1. Decisions

| Topic | Decision | What it beat |
|---|---|---|
| **What "rate" means** | FIFO lots: every exchange into a target is a lot, queued by `occurred_at`. Spent units take the oldest lots, changed-back units the next, held units (tracked-wallet leftover, capped at what was bought) the newest. `rate` prices the spent units, `leftover_rate` the held ones; a split lot is priced pro rata. | Loading the leftover's cost onto what was spent (the first build) — the user wants the leftover out of the trip rate. One average for both — says nothing once rates differ between withdrawals. |
| **Scope** | Per person, per unordered currency pair, over that person's exchanges (`from_currency_id <> to_currency_id`; always same-owner by rule). | Per wallet: an ATM withdrawal is `Card → Cash`, so the pair spans wallets and the leftover in one wallet says nothing about the other. Trip-wide: different people get different rates, and the Total prefill needs to name whose. |
| **Direction** | The funding currency is the side whose net flow out of the pair is positive; the other side is the target. The server ships one `rate` (1 target = x funding); the frontend takes `1 / rate` when the Total needs the other direction. | An `inverse_rate` field — a second number for a division float64 does exactly. |
| **Rate precision** | `rate` at 10⁻⁹ (`RATE_SCALE`), with `spent` kept in hundredths. 1 ISK = 0.007608695 EUR keeps 7 significant digits, so `1 / rate` is right to the displayed places; 1 IDR ≈ 0.0000571 EUR still keeps 5. | Micro-units, like every other computed figure: 0.007608 inverts to 131.44 instead of 131.43, and weak currencies lose almost all their digits. |
| **Response shape** | `{person_id, from_currency_code, to_currency_code, rate, leftover, leftover_rate}`. A code is unique per trip and immutable (`uq_currency_trip_code`, no `code` on `CurrencyUpdate`), so it identifies the currency as well as the id does, and it is what the Wallets tab prints and a `curl` reader understands. | Currency ids — every consumer would look the code up anyway. Shipping `paid`/`received`/`left`/`spent` — nothing renders them. |
| **Leftover** | `Σ max(balance, 0)` over the person's **tracked** wallets in the target currency. Untracked wallets have no balance, so their target currency counts as spent. Capped at what the exchanges bought: held currency is attributed to exchanges before any plain transfer or gift. | Proportional attribution between exchanged and non-exchanged ISK — cash is fungible, and the cap keeps the arithmetic in one queue. |
| **Several funding currencies into one target** | One lot queue per target; each pair is priced from its own lots in that queue. | The proportional leftover split of the first build — FIFO answers it for free. |
| **No rate** | `rate` is `null` when `spent ≤ 0` or the flows are not one-positive-one-negative (changed back more than bought). | Dropping the row — the Wallets tab would then say nothing about an exchange that happened. |
| **Where it is computed** | Hybrid, three queries: the trip's exchanges oldest first (currency ids only), `queries.wallet_flows` (shared with the wallet report) and `queries.currencies_for_trip` for codes and order. The lot queue runs in Python on integers and exact `Fraction`s, floored once at 10⁻⁹. | One 280-line SQL statement with seven CTEs — as fast, far harder to read; FIFO is a loop. |
| **Endpoint** | `GET /trips/{slug}/exchange-rates` → `{exchange_rates: [...]}`, its own route in `routers/reports.py`. | A sibling key in `GET /wallets` — that is a CRUD list envelope (`CRUD_ROUTES.md`), and Balances/Stats would have to load the whole wallet report for a rate. A key on `/balances` — Stats would have to load balances. |
| **Total tie-in** | A link per person under each rate input; a click writes the formatted rate as the typed value. Nothing is applied automatically. | Auto-filling empty inputs — a rate the user never chose would silently drive the Total. |
| **Migration** | None. No new column, no view. | A `person_exchange` SQL view — would need a `0002` migration for a query only one route reads. |

**Amended decisions.** `WALLETS.md` "Out of scope: a stored or displayed exchange
rate" and `DECISIONS.md` §1 *Wallets* ("no stored exchange rate"): a rate is now
**displayed, derived on read, never stored**. `DECISIONS.md` §2 "Why no currency
conversion server-side" still holds — the server computes a ratio of two typed sums;
it converts nothing.

---

## 2. Data model

No change. Everything is derived from `wallet_transfer`, `line_item` and `wallet`.

---

## 3. API

`GET /trips/{slug}/exchange-rates` → `{exchange_rates: [...]}`, one row per
`(person, currency pair)` with any exchange, people in roster order, then by
`from_currency` then `to_currency` in trip currency order:

```
{person_id,
 from_currency_code,   # funding side
 to_currency_code,     # target side
 rate,                 # 9 places or null: what 1 spent unit of `to` cost in `from`
 leftover,             # 2 places: `to` still held from this pair's lots
 leftover_rate}        # 9 places or null: what 1 held unit cost
```

Example: `20 EUR → 18 CHF`, spend 15 CHF, `5 EUR → 4 CHF`. The 15 spent come from
lot 1: `rate = 20/18 = 1.111111111`. Held 7 = the 3 left of lot 1 plus lot 2:
`(3 × 20/18 + 5) / 7 = 1.19047619`.

**The money.** Sums in SQL, the queue in Python:

```
query 1: exchanges (from ≠ to currency), owner + both currencies, ORDER BY occurred_at, id
query 2: queries.wallet_flows → held[p, c] = Σ max(received − sent − spent, 0) over tracked wallets

per (p, pair): funding = the side that net left; lots = exchanges funding → target, in order
per (p, target): bought = Σ got, sold = Σ target sent back, kept = min(held, bought − sold)
  queue: [0, spent) spent · [spent, bought − kept) changed back · [bought − kept, bought) held
per lot and part: cost += Fraction(paid × units, got)
rate = cost_spent × 10⁹ // spent_units      leftover_rate = cost_held × 10⁹ // held_units
```

No new error codes; a trip that does not exist is the usual `404`.

---

## 4. Frontend

Call budget grows by one lazy call, loaded once per trip, invalidated with the other
money views: Wallets 2 (parallel), Balances 2, Statistics unchanged until its Total is
shown.

| Piece | What it does |
|---|---|
| `store.js` | `exchangeRates` state and loader; reset in `load()`; `invalidateMoneyViews()` also nulls it. |
| `fmt.js` | `rate(value, locale)`: 6 significant digits, no grouping, so the output is also something `parse()` reads back. |
| `convert.js` | `rateBetween(row, code, targetCode)`: `row.rate` when `to = code, from = targetCode`, `1 / row.rate` when reversed, `null` otherwise. `RatesForm` already iterates `trip.currencies`, so it has both `c.code` for the match and `c.id` for `onRateChange`. |
| `views/Wallets.js` | Loads `exchangeRates` alongside `wallets`. Person card gains a footer: one line per row, `1 {to} = {rate} {from}`; `wallets.no_rate` when `rate` is `null`. |
| `components/RatesForm.js` | Loads `exchangeRates` on mount. Under the input for currency `c` into `target`: one `btn-link` per person whose row gives a `rateBetween`. Label `{person} {rate}`; click → `onRateChange(c.id, rate(value))`. Nothing rendered when no row matches. |
| `i18n/en.js`, `cs.js` | `wallets.rates`, `wallets.no_rate`, `rates.use_average`. |

`FRONTEND.md` rule 1 gains one sentence: inverting an exchange rate is allowed — it
is a ratio, not an amount, and nothing is summed. The prefill becomes an ordinary
typed value.

---

## 5. Fixtures and the mock

- `app/seed.py` and `trip.json`: T1 (`Petr Card → Cash`, 2026‑09‑14 12:00) becomes an
  exchange, `140 EUR → 20 000 ISK`. `Card` is untracked and the ISK side is unchanged,
  so the wallet report, balances and feed order stay as they are; T1's row now reads
  as an exchange.
- `routes`: `/api/v1/trips/iceland-2026/exchange-rates` → `#/exchange_rates`, with
  the values the seeded backend returns:
  - Petr EUR→ISK: 140 EUR / 18 400 ISK spent (1 600 left) → `rate` 0.007608695; the
    ISK-target prefill shows 131.429.
  - Petr EUR→DKK (T3): 150 DKK received, all 150 left → `rate` `null`, the no-rate
    rendering.
- `empty.json`, `hostile.json`: `exchange_rates: []` and the route.

---

## 6. Implementation steps

1. **Service** `app/services/exchange_rates.py`: `exchange_rates(session, trip_id)`
   builds the CTE statement in Core and maps rows through `to_wire`. Schema
   `ExchangeRateOut` in `schemas/responses.py`, envelope `ExchangeRatesEnvelope`.
2. **Route** `GET /trips/{slug}/exchange-rates` in `routers/reports.py`. `make openapi`.
3. **Backend tests** `tests/backend/test_exchange_rates.py`, built through the API:
   - one exchange, everything spent → `rate = paid / received`;
   - leftover in a tracked wallet lowers `spent` and raises `rate`;
   - changing back nets both sides;
   - target currency in an untracked wallet counts as spent;
   - negative wallet balance contributes 0 to `left`;
   - two funding currencies into one target split `left` by received;
   - everything left, or changed back more than bought → `rate` `null`;
   - plain and cross-owner transfers produce no row;
   - two people get separate rows;
   - `rate` floored at 9 places on a non-terminating ratio.
4. **Seed + fixtures** as in §5; `test_seed.py` keeps them identical.
5. **Frontend**: `fmt.rate`, store loader, Wallets footer, RatesForm links, i18n in
   both catalogs.
6. **Frontend tests**: `test_wallets_view.py` (rate line, no-rate line),
   `test_total_balances.py` / `test_total_stats.py` (link shows, click fills the input
   and the Total renders), `test_call_budget.py` (Wallets 2, Balances/Stats +1 on a
   multi-currency trip), `test_fmt.py` (`rate` output round-trips through `parse`),
   the reversed-direction link showing `1 / rate`,
   `test_unknown_fields.py` if it enumerates endpoints.
7. **Docs**: `API.md` (new *Exchange rates* section), `DECISIONS.md` (Wallets row,
   amendment note), `FRONTEND.md` (rule 1 sentence, layout, call budget table), `BACKEND.md` (service),
   `WALLETS.md` out-of-scope line.

## 7. Verification

`make lint test` green; `make openapi-check` clean; seeded dev server shows Petr's
EUR→ISK rate on the Wallets tab and the link fills the Balances Total.
