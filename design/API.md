# Trip Accounter — API Contract (v1)

> **Shapes are generated, rules are written.** Every field, endpoint, status and
> example lives in the OpenAPI schema FastAPI derives from `app/schemas/` and the
> routers — browse it at **`/docs`** on a running server, or read the committed
> snapshot [`openapi.json`](../openapi.json) (`make openapi` regenerates it; CI
> fails when it is stale). This file holds only what a schema cannot say: what the
> numbers *mean*, how a split resolves, which rule produces which error code.
>
> A shape question is answered by `/docs`. A meaning question is answered here.

The single agreement between the backend and the frontend. Both sides code against
**this file plus the generated schema**, not against each other. Changes here are a
shared decision; everything else on either side is local business.

- Base path: **`/api/v1`**, JSON in, JSON out, UTF-8. **The backend serves nothing
  else** except static files. No server-rendered pages, no HTML fragments.
- No authentication (VPN perimeter). No cookies, no CSRF token, no session.
- A trip is addressed by its **slug**: `/api/v1/trips/{slug}/...`
- Every response is a single JSON object. Lists live under a named key, never a
  bare top-level array — that leaves room to add `meta` without breaking clients.
- The frontend is one client of this API. The API knows nothing about it. Anything a
  second client (a script, a phone shortcut, `curl`) would find odd is a bug here.

---

## 1. Conventions

### Money
**The API returns data, not presentation.** One field per amount, a plain JSON
number in the currency's own units:

```json
{ "amount": 18400.5, "currency_code": "ISK", "currency_id": 1 }
```

- **Two scales, and they are the whole story.** Anything a human typed — `amount`,
  an `exact` share, a suggestion — has at most **2 fraction digits**, for every
  currency (`18400`, `13.34`, `120`). Anything the server **computed** — a
  `shares`/`equal` `owed`, `net`, `by_person` — carries up to **6**:
  `27428.571428`. No currency metadata: ISK simply never has a fraction typed into
  it, and its computed thirds show up as `6133.333333` like anyone else's.
- There is **no** `*_display` field and **no** `*_minor` field. Formatting — digit
  grouping, decimal separator, symbol placement, showing 0–2 fraction digits — is the
  client's job.
- **Input is a canonical decimal string**: `"amount": "18400.50"`. Grammar
  `^-?[0-9]+(\.[0-9]{1,2})?$`, no grouping, `.` as the only separator, at most two
  fraction digits. Anything else is `422 invalid_amount`. **The server has no idea
  how the user typed it** — turning `18 400,50` or `18,400.50` into `18400.50` is the
  client's job, because only the client knows the locale. A string rather than a JSON
  number so no float ever touches an input.

**Precision, stated plainly.** JSON has no decimal type, so these are float64 on both
sides. Safe here because the magnitudes are small and the fraction is bounded, and
kept safe by four rules:

1. **The database stores only what was typed, as integers in hundredths.** `amount`,
   `exact` shares, weights. Never a computed share, never a float.
2. **Computed shares are a SQL view**, `owed_micro = amount × weight / Σweight` in
   integer arithmetic at micro-unit scale (10⁻⁶), floored. Deterministic on SQLite and
   Postgres alike, never stored, never rounded to a cent per item, so nobody
   systematically absorbs remainders.
3. **The backend aggregates in SQL** over hundredths and that view — balances and every
   statistics group arrive already summed. The client never adds up a column of money.
4. **Money is rounded exactly once**, in `suggestions`: nets to hundredths with a
   zero-sum correction, then the transfer plan. Everything else is shown as delivered,
   trimmed to two fraction digits by the client's formatter.

Floor division loses under one micro-unit per share, so `Σ net` per currency is
within `±(shares × 10⁻⁶)` of zero rather than exactly zero, and an item's computed
`owed` may sum to a few micro-units under `amount`. Invisible at two decimals and
irrelevant to the one rounded output, which sums to zero exactly.

**Stored vs. computed.** Persisted: `amount` (hundredths), `weight`, and `owed`
**only for `exact` mode** (hundredths). Computed per response, never stored:
`equal`/`shares` `owed` (view), balances, suggestions, statistics. Weights are what
was agreed, so a share cannot change afterwards; only the settle-up rounding rule
could, and that is deliberately the one place a rule lives.

**Split arithmetic stays server-side** — the view expression is the only definition
of a share, and `preview-split` evaluates the same expression on a request body. A
client copy would be a second implementation, and two rules is how a cent goes
missing.

**Three-decimal currencies** (KWD, BHD, OMR) cannot be entered to their last digit.
Out of scope for a holiday app; noted, not solved.

### Decimals as strings
Every decimal that is not an amount — `weight`, `default_weight`, `lat`, `lon` — is a
**string** in both directions (`"0.5"`, `"64.14930"`), canonical grammar, up to 4
fraction digits for weights (stored ×10⁴) and 6 for coordinates. Amounts are the one
number on output, because they are what clients format; everything else is passed
through untouched.

### Time
`occurred_at` is **always tz-aware, always UTC on output**: `"2026-09-14T19:30:00Z"`.
Input may carry an explicit offset (`+02:00`, `Z`, …) or omit one entirely — an
offset-less input is assumed to already be UTC, **never the server's own local
time**, so the stored value never depends on how a given deployment happens to
be configured. The server converts to UTC and always answers with `Z`.
`created_at` / `updated_at` are UTC with `Z` too — the same convention.

### IDs
Integers, unique per table. `slug` is the only external string identifier.

### Errors
Always HTTP status + this envelope:

```json
{ "error": {
    "code": "validation_error",
    "params": {},
    "fields": {
      "shares": { "code": "sum_mismatch",
                  "params": { "diff": 3, "currency_code": "ISK" } } } } }
```

**No sentences. Codes and parameters only.** The backend contains no natural
language: not a message, not a fallback, not a template. A client renders `code` +
`params` through its own catalog; `curl` reads §4.

| Status | `code` | `params` | When |
|---|---|---|---|
| 400 | `bad_request` | `{}` | malformed JSON, wrong content type |
| 404 | `not_found` | `{resource}` | unknown slug or id, or an id from another trip |
| 409 | `conflict` | `{}` | duplicate name, or delete blocked because the row is in use; details in `fields` |
| 422 | `validation_error` | `{}` | field-level failure; details in `fields` |
| 500 | `internal_error` | `{ref}` | bug. `ref` is the log correlation id, so a user can quote something |

`fields` is present on `409` and `422`, keyed by the request field name so a client
can attach each error to its own input without string matching. Each value is
`{code, params}`:

- `code` is the **stable identifier** the client switches on. Full list in §4.
  Renaming one is a breaking change, like renaming a field.
- `params` are the values the rendered sentence needs (`diff`, `currency_code`,
  `count`, `max`, `name`). Always present, `{}` when there are none. Numbers are
  plain numbers, strings are user data or codes — formatting is the client's job.

**Backend never sees `Accept-Language`** and never translates, because it has
nothing to translate.

### Versioning
Additive changes (a new optional field) ship without a version bump. Anything that
removes or retypes a field is `/api/v2`. Clients ignore unknown fields and must not
break when one appears.

---

## 2. What the fields mean

The schema says a field exists and what type it is. This section says what it
*means* — the part a client gets wrong if it guesses.

### The trip
The trip is the aggregate: its people, currencies and countries are part of it and
come embedded, in `sort_order`. They are also addressable on their own for writes
and for clients that want one list. The trip list replaces those embedded lists with
`people_count` and `item_count`, and orders by `end_date` descending — the trip that
ended most recently first; a trip with no `end_date` sorts after every dated one,
newest created first among themselves.

`slug` is generated from `name` at creation and **never changes**, so a pasted link
survives a rename. `PATCH` cannot move it. Deleting a trip cascades everything.

Creating a trip requires **at least one person, one currency and one country** —
otherwise the item form would be unusable. `labels` on create is optional and makes
those labels with `use_count 0`; **the server seeds nothing on its own.** The bundled
frontend offers a fixed starter set (`food lodging transport fun groceries drinks`,
the same words in every locale — labels are user data and are never translated) as
pre-ticked chips the user can untick. A `curl` client gets an empty label list.

### Roster
`initial` and `color` on a person are **server-assigned**, so every client draws the
same avatar from the same data. `default_weight` is what a new item prefills, not a
constraint on anything.

A currency has no `decimals` field and never will: every currency is typed to two
fraction digits and computed to six. `is_primary` on a currency and `is_default` on a
country are **form preselection hints**, nothing more.

A country's `flag` is derived from its ISO `code`; a country typed by hand with no
code has `null`. `item_count` tells a client in advance whether a delete will be
refused.

People, currencies, countries and labels share one CRUD shape. Lists come back in
`sort_order`; labels come back in `use_count DESC, name ASC` — the suggestion order,
which is the server's and is not re-sorted client-side. A trip has at most a few
dozen labels, so a suggestion box filters them locally rather than querying.

A `DELETE` refused because the row is still referenced answers `409` with
`fields.id.code = "in_use"` and `params {count, name}` — enough to say which items
hold it without a second request. **People are the exception worth knowing:** a
referenced person cannot be deleted either, and the answer is
`PATCH {"active": false}`, which hides them from new splits while every existing
item keeps their row.

### Labels
A label name is **one token** — no whitespace inside it, ever. Typing `street food`
yields two labels unless the user writes `street-food`; a token containing whitespace
is a `422`, not a silent join. Matching is case-insensitive, so `Food`, `food` and
`" food "` are one row, and `name` keeps the first-typed casing. Unknown labels on an
item write are created on the fly and the response echoes the normalized set. An
item's `labels` array is sorted alphabetically, deduplicated and lowercased.

Deleting a label leaves its items alone — only the association goes.

### An item and its split
`map_url`, `lat` and `lon` are written as themselves; the write shape is the read
shape. Given a `map_url` and no coordinates, the server tries to parse them out of
the URL (`@lat,lon`, `!3dlat!4dlon`, `?q=lat,lon`). Best effort — a URL it cannot
read is stored as given and is **not** an error. Explicit coordinates are validated
and win.

**The split comes out resolved, but as data.** The backend does the weighting and the
rounding; wording is the client's business.

- `split.shares` has **one entry per active person of the trip, in roster order**
  (`sort_order`). A person left out of the item has `"weight": null, "owed": null`.
  No filtering, no set difference, no "is this person in the list" check. `"owed": 0`
  is a different thing: they are in the split and rounding gave them nothing.
- `owed` is the share as a fraction, to six places, **never rounded to a cent per
  item** — `18400` four ways is `4600`, but `96000` at weights `1·1·1·0.5` is
  `27428.571428 ×3` and `13714.285714`. In `exact` mode it is what was typed and the
  rows sum to `amount` exactly; in `equal`/`shares` the rows may fall a few
  micro-units short of `amount` (floor). Nobody absorbs a remainder; the only
  rounding happens once, in settle-up.
- `split.mode` and `weight` are what an edit form prefills from. The API ships no
  presentation text — no "equally, 4 ways", no remainder sentence.
- `payer_id` need not appear with a non-null share: you can pay for a meal you did
  not eat.

### Wallets
A wallet is a pot of money a person spends from. Every person gets one on creation,
named `Card`, **untracked** and **default** — the server's own doing, so a plain
`curl` client that never mentions wallets still gets correct items. `is_default` is
not just a form hint here: it is the wallet an item write falls back to when it
omits `wallet_id`. A wallet is owned by exactly one person and only that person's
own items and transfers can name it.

**Tracked vs. untracked.** An untracked wallet (the default `Card`) has no balance
and no limit — nothing is computed for it, `GET /trips/{slug}/wallets` answers `[]`
for its `balances`. A tracked wallet's balance is `received − sent − spent` per
currency it has touched; negative means it was overcharged (spent, or sent out,
more than it ever received) — the client renders that sign, the server just reports
it. `wallet_id` on an item must belong to that item's `payer_id`, or `422
wallet_owner_mismatch`.

### Transfers
Money moved between two wallets, a different kind of row from an item: no country,
no split, no label. **A plain transfer** carries one amount and one currency —
`to_amount`/`to_currency_id` default to the from side when omitted, so a client
posting a plain transfer only ever sends one amount. **An exchange** has two typed
sides — what left the sending wallet, what arrived in the receiving one — with no
stored rate; it is allowed only between two wallets **the same person owns** (`422
cross_owner_exchange` otherwise), and the two wallets may be identical when the
currencies differ (exchanging inside one mixed-currency wallet). The same wallet on
both sides in the same currency is meaningless (`422 same_wallet`).

`GET /trips/{slug}/items` carries transfers too, under `transfers`, sorted the same
way items are (`occurred_at DESC, id DESC`) — a client merges the two lists by
timestamp to paint one feed. A transfer is **movement, not spending**: `day_totals`,
every statistics group and `total_spent` stay sums of items only.

A transfer between two different people's wallets is the one case that changes who
owes whom: it enters `sent`/`received` on the balances endpoint below and is always
single-currency (an exchange cannot cross owners). A transfer between one person's
own wallets, plain or exchange, moves nothing between people and never appears in
`sent`/`received` — only in the wallet report above.

---

## 3. What the operations promise

### Reading a trip
Everything needed to paint a trip is three parallel reads — the trip, its items, its
labels. Balances and statistics are fetched when their tab opens, not up front.

Items come back sorted `occurred_at DESC, id DESC`, all of them: a holiday does not
paginate. Filters and `limit` are a future additive change.

The item list also carries `day_totals`: one entry per day with items, newest first,
each holding one `{currency_code, currency_id, amount}` per currency that day —
summed server-side in the same query, so the feed's per-day total is never a
client-side accumulation (`design/FRONTEND.md` §4 rule 1).

### Writing an item
A `PATCH` leaves omitted fields untouched, but sending `shares` **replaces the whole
split** — there is no per-share patch.

**`shares` on input, by mode:**

| `split_mode` | each row | meaning |
|---|---|---|
| `equal` | `{person_id}` | weights ignored, everyone listed gets an even cut |
| `shares` | `{person_id, weight}` | `weight` a decimal string, `> 0` |
| `exact` | `{person_id, amount}` | decimal strings that **must** sum to `amount` |

Omitting `shares` entirely means "equal over all active people".

Note the asymmetry, and it is deliberate: **requests carry intent** (`split_mode` plus
weights or amounts), **responses carry the result** (resolved per-person figures). A
client states what the user meant and renders what came back; it never turns one into
the other.

**`preview-split` computes a split without saving anything.** It takes the same body
an item write does — only `amount`, `currency_id`, `split_mode` and `shares` are read,
the rest ignored rather than rejected — and answers with the same `split` shape an
item carries: roster order, nulls for the people left out. A form renders it exactly
as it renders a saved item. This is the endpoint that keeps a form's live numbers
identical to what will be saved, and the reason no client reimplements the split
arithmetic.

### Balances
`paid` and `total_spent` are sums of typed amounts: two places. `owed` and `net` are
sums over the share view: six places. `sent`/`received` are typed sums (two places)
of **cross-owner transfers only**, in that currency — a transfer between one
person's own wallets never appears here (see Transfers, above). `net = paid − owed +
sent − received`; positive means they are owed money. The sign is the data — the `+`
in front of a credit is the client's choice.

`suggestions` is **the one rounded output** in the whole system: nets rounded to
hundredths with a zero-sum correction (largest rounding error adjusted first, ties by
`sort_order`), then the greedy minimum-transfer plan — at most n−1 entries, amounts in
hundredths, summing to zero exactly. Who hands whom how much at the end of the trip.
**Nothing records that a settle-up suggestion was paid**: the trip is settled once,
when it is over, and the app is not a ledger of paybacks. A wallet transfer is
different — it is a real, recorded movement of money, which is exactly why a
cross-owner one is allowed to shift `net`.

One block per currency that has any item **or any cross-owner transfer**; a currency
neither spent nor moved between people is absent. **Nothing is converted between
currencies on this endpoint.** The one client-side exception, shared with the
statistics page, is this page's own Total switch: it converts and sums
`people[].net`, and nets `suggestions[]` by unordered person pair, only once every
currency has a positive typed rate — see "Statistics" below.
`|sum(people[].net)| < 0.00001` per currency — a client may assert it;
`sum(suggestions)` balances exactly.

### Statistics
Plain `GROUP BY` aggregates — per currency, never across them. The totals arrive
already summed, so a client never adds a column of floats over this API's own
response; all it does with these numbers otherwise is format them.

`by_person` is a sum over the share view (six places); every other group is a sum of
typed amounts (two). **`by_person[].amount` is what that person owes** in the period —
their share of everything — not what they paid out. The two are visibly different on
a trip where one person pays for everything.

**`by_label` rows overlap.** An item with two labels counts in both, so the rows sum
to more than `total`, and a client must say so on screen. Items with no label appear
under `"label": null`. `by_day` groups on `occurred_at`; `day_count` spans the trip.

**The Total is the single client-side exception, and it is all-or-nothing.** It sits
in the statistics page (and, the same way, the balances page) as another switch
alongside the currencies: the user types a rate per currency, and only once every
currency (not just some) has a positive rate does the client multiply each group
total by its rate, round to two places, and sum those rounded figures across
currencies — on the balances page this converts and sums `people[].net`, and nets
`suggestions[]` by unordered person pair, rather than re-running the settle-up
algorithm. Until then the Total shows nothing but the rate form — never a partial sum
quietly missing a currency. Those rates live in `localStorage`, shared between the two
pages (one rate set per trip), are never sent to this API, never stored, and never
touch a currency's own balance, settle-up figure, or statistics — only each page's own
Total.

### Export
`?format=csv|json`, both `Content-Disposition: attachment`, and **both identical
except for the format** — this is a file for a human or another app to read, not a
shape meant to rebuild the database. Both are **share-grained**: one row per
resolved share, so a four-person item is four rows, not one. `items` carries that
flat row, not `ItemOut` nested under a `split` — every field but the trailing
`person_name, weight, owed` triple is an `ItemOut` field verbatim, so a field added
there can't go stale here without a deliberate header change. `currency_id` and a
share's `person_id` are dropped in favor of the roster names a reader would
otherwise have to look up: no `currency_id` (`currency_code` already says it), and
`person_name` instead of `person_id`.

The CSV header row is part of the contract, because something parses it: `item_id,
name, note, occurred_at, currency_code, amount, payer_id, wallet_id, country_id,
labels, map_url, lat, lon, created_at, updated_at, person_name, weight, owed`. CSV
has no `null` or list type: `labels` joins with `;`, and an absent
`note`/`map_url`/`lat`/`lon` is an empty field, not the string `"None"`. JSON keeps
those as their native types — `labels` a list, an absent field `null`. Transfers are
not share-grained and stay out of the CSV entirely; JSON's `transfers` block is the
same `TransferOut` shape the live API returns. An empty trip exports a header and
nothing else, not a `500`.

---

## 4. Validation rules (authoritative)

`code` and `params` are the contract. The last column is **not on the wire** — it is
the reference wording the frontend's `en.js` catalog is written from, kept here so the
rule, its code and its intended meaning sit in one row.

| Field | Rule | `code` | `params` | reference wording (`en.js`, not sent) |
|---|---|---|---|---|
| `name` (item) | 1–200 chars after strip | `required` / `too_long` | `{max}` | "Give it a name." / "Keep it under 200 characters." |
| `amount` | canonical grammar, `> 0`, ≤ 12 integer digits, ≤ 2 fraction digits | `invalid_amount` | | "Enter an amount." |
| `currency_id` | belongs to this trip | `not_in_trip` | | "Unknown currency." |
| `payer_id` | belongs to this trip, `active` | `not_in_trip` / `inactive` | | "Pick who paid." |
| `country_id` | **required**, belongs to this trip | `required` / `not_in_trip` | | "Pick a country." |
| `occurred_at` | valid datetime, any offset or none (assumed UTC); default = now (UTC) | `invalid_datetime` | | "Check the date." |
| `labels[]` | each 1–40 chars, no whitespace | `label_whitespace` / `too_long` | `{value}` | "Labels can't contain spaces — use street-food." |
| `shares` | ≥1 entry, no duplicate `person_id` | `empty` / `duplicate_person` | | "Somebody has to owe something." |
| `shares` (exact) | each ≤ 2 fraction digits; sum exactly to `amount` | `sum_mismatch` | `{diff, currency_code}` | "Off by 0.03 ISK." |
| `shares` (weights) | each `> 0`, ≤ 4 fraction digits | `not_positive` / `too_precise` | `{max}` | "Shares must be positive." |
| `map_url` | absolute `http(s)` URL | `invalid_url` | | "Not a link." |
| `lat`, `lon` | both or neither; lat ∈ [-90,90], lon ∈ [-180,180] | `invalid_coordinates` | | "Not valid coordinates." |
| person `name` | unique per trip | `duplicate` | `{name}` | "Already somebody by that name." |
| currency `code` | 3 letters, unique per trip | `invalid_code` / `duplicate` | | "Currency already on the trip." |
| `default_weight`, `weight` | `> 0`, ≤ 4 fraction digits | `not_positive` / `too_precise` | `{max}` | "Shares must be positive." |
| country `name` | unique per trip | `duplicate` | `{name}` | "Country already on the trip." |
| any `DELETE` | row referenced | `in_use` | `{count, name}` | "Iceland is used by 4 items." |
| trip `people` / `currencies` / `countries` | ≥ 1 each on create | `empty` | | "Add at least one." |
| wallet `name` | 1–60 chars, unique per owner | `required` / `too_long` / `duplicate` | `{max}` / `{name}` | "Already a wallet by that name." |
| wallet `person_id` | belongs to this trip | `not_in_trip` | | "Unknown person." |
| item `wallet_id` | belongs to this trip; owned by `payer_id` | `not_in_trip` / `wallet_owner_mismatch` | | "That wallet isn't the payer's." |
| `from_wallet_id`, `to_wallet_id` | required, in trip; same wallet only when the currencies differ | `required` / `not_in_trip` / `same_wallet` | | "Pick two different wallets." |
| `from_amount`, `to_amount` | canonical grammar, `> 0` | `invalid_amount` | | "Enter an amount." |
| `from_currency_id`, `to_currency_id` | in trip; differ only when both wallets have one owner | `not_in_trip` / `cross_owner_exchange` | | "Exchange only between your own wallets." |
| `DELETE` default wallet | refused | `is_default` | | "Make another wallet the default first." |

A new rule adds a row here, the code to `services/errors/`, and an `err.<code>`
key to every frontend catalog **in the same commit** — `test_errors.py` and
`test_i18n.py` fail otherwise.

Last write wins on concurrent edits — no ETag, no optimistic locking. Two people
editing the same item in the same second is not a holiday problem worth solving.

---

## 5. Static files

The backend mounts `static/` at `/` as a deployment convenience so one process
serves everything on the VPN. It has no knowledge of what is in there. `GET /` and
`GET /t/{slug}` return `static/index.html`; routing inside the page is the
frontend's. Nothing under `/api/v1` ever returns HTML.

---

## 6. Fixtures

Fixtures are the frontend's, and they live in `tests/frontend/fixtures/`.
`trip.json` is a complete set of responses — `trip` + `labels` + `items` +
`balances` + `stats` — for a demo trip; the rest are purpose-built (an empty trip,
markup in every user-supplied string, one file per error envelope).

- `tests/frontend/mockapi.py` serves them under `/api/v1`, so the Playwright suite runs
  the real `static/` against canned responses with no backend and no database.
- Every value in them is copied from what the backend actually produced. The mock
  computes nothing: a resolved split in a fixture was written out by hand, because a
  mock that allocates shares is a second implementation of the allocation rule.

The backend's own suite drives the real app and builds its state through the API,
so it needs none of this.

When the contract changes, the fixtures change **in the same commit**. A fixture
that disagrees with this document is a bug in the fixture.
