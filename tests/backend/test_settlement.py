"""Functional tests for settling a trip: the stored agreement, the lock, and unlocking.

The `trip` fixture has ISK (primary) and EUR; a settlement here targets EUR with an
ISK rate unless a test says otherwise. Rates come back in trip currency order:
primary first, then by code.
"""

from datetime import UTC, datetime

import pytest
from sqlalchemy import func, select

from app.models.roster import TripCurrency
from app.models.trip import Trip
from app.seed import seed_demo

SETTLED_AT = datetime(2026, 9, 22, 18, 0, tzinfo=UTC)


def trip_settled(field):
    """Return the 409 envelope a settled trip answers a locked write with, under `field`."""
    return {
        "error": {
            "code": "conflict",
            "params": {},
            "fields": {field: {"code": "trip_settled", "params": {}}},
        }
    }


def rate_error(code, currency_id):
    """Return the 422 envelope a settlement body with a bad or missing rate earns."""
    return {
        "error": {
            "code": "validation_error",
            "params": {},
            "fields": {"rates": {"code": code, "params": {"currency_id": currency_id}}},
        }
    }


@pytest.fixture()
def ids(currencies, person_id):
    """Return the ids these tests name: the trip's ISK and EUR, Petr and Ann."""
    return {
        "isk": currencies[0]["id"],
        "eur": currencies[1]["id"],
        "petr": person_id("Petr"),
        "ann": person_id("Ann"),
    }


@pytest.fixture()
def settle(client, trip, frozen_clock):
    """Return a function that PUTs a settlement on `trip` and returns the response."""
    frozen_clock(SETTLED_AT)

    def put(target_currency_id, rates):
        return client.put(
            f"/api/v1/trips/{trip['slug']}/settlement",
            json={
                "target_currency_id": target_currency_id,
                "rates": [{"currency_id": cid, "rate": rate} for cid, rate in rates.items()],
            },
        )

    return put


@pytest.fixture()
def item(client, trip, item_body):
    """Create one 100.00 ISK item Petr paid, split equally over all four people."""
    response = client.post(f"/api/v1/trips/{trip['slug']}/items", json=item_body())
    assert response.status_code == 201, response.text
    return response.json()["item"]


@pytest.fixture()
def transfers(client, trip, transfer_body, default_wallet_of, ids):
    """Create a same-owner exchange (Petr's Card, EUR to ISK) and a cross-owner payment."""
    petr_card = default_wallet_of(ids["petr"])["id"]
    same_owner = transfer_body(
        from_wallet_id=petr_card,
        from_currency_id=ids["eur"],
        from_amount="20",
        to_wallet_id=petr_card,
        to_currency_id=ids["isk"],
        to_amount="2800",
    )
    created = {}
    for name, body in (("same-owner", same_owner), ("cross-owner", transfer_body())):
        response = client.post(f"/api/v1/trips/{trip['slug']}/transfers", json=body)
        assert response.status_code == 201, response.text
        created[name] = response.json()["transfer"]
    return created


@pytest.fixture()
def settled(settle, item, transfers, ids):
    """Settle `trip` in EUR at 1 ISK = 0.0073 EUR, with `item` and `transfers` in place.

    Returns what a locked write needs: the settled trip, the item and the transfers.
    """
    response = settle(ids["eur"], {ids["isk"]: "0.0073"})
    assert response.status_code == 200, response.text
    return {"trip": response.json()["trip"], "item": item, "transfers": transfers}


@pytest.fixture()
def editable(client, trip, ids, stay_body):
    """Create a second country, a second wallet for Petr and a stay: where editable fields move."""
    country = client.post(
        f"/api/v1/trips/{trip['slug']}/countries", json={"name": "Denmark", "code": "DK"}
    ).json()["country"]
    wallet = client.post(
        f"/api/v1/trips/{trip['slug']}/wallets",
        json={"person_id": ids["petr"], "name": "Cash", "tracked": True},
    ).json()["wallet"]
    stay = client.post(f"/api/v1/trips/{trip['slug']}/stays", json=stay_body()).json()["stay"]
    return {"country_id": country["id"], "wallet_id": wallet["id"], "stay_id": stay["id"]}


@pytest.fixture()
def locked(settled, item_body, transfer_body, ids):
    """Return everything a whole-object write on the settled trip is built from."""
    return {**settled, **ids, "item_body": item_body, "transfer_body": transfer_body}


# --- settle -------------------------------------------------------------------


def test_put_settlement_stores_target_rates_and_settled_at(client, trip, settle, ids):
    """PUT answers with the trip carrying the agreement, and a later GET reads it back."""
    response = settle(ids["eur"], {ids["isk"]: "0.0073"})

    assert response.status_code == 200
    expected = {
        "target_currency_id": ids["eur"],
        "settled_at": "2026-09-22T18:00:00Z",
        "rates": [{"currency_id": ids["isk"], "rate": 0.0073}],
    }
    assert response.json()["trip"]["settlement"] == expected
    assert client.get(f"/api/v1/trips/{trip['slug']}").json()["trip"]["settlement"] == expected


def test_unsettled_trip_has_null_settlement(trip):
    """A trip nobody settled answers `settlement: null`."""
    assert trip["settlement"] is None


@pytest.mark.parametrize(
    ("typed", "wire"),
    [
        pytest.param("0.000000001", 1e-09, id="nine-places"),
        pytest.param("25", 25, id="whole-number-is-an-int"),
        pytest.param("123456789.5", 123456789.5, id="nine-integer-digits"),
    ],
)
def test_put_settlement_rate_round_trips_to_nine_places(settle, ids, typed, wire):
    """A typed rate comes back as the plain number it denotes, exact to 9 places."""
    response = settle(ids["eur"], {ids["isk"]: typed})

    rates = response.json()["trip"]["settlement"]["rates"]
    assert rates == [{"currency_id": ids["isk"], "rate": wire}]
    assert type(rates[0]["rate"]) is type(wire)


def test_second_put_replaces_the_first(settle, ids):
    """A PUT over a settled trip replaces the target and every rate; only the second remains."""
    settle(ids["eur"], {ids["isk"]: "0.0073"})

    response = settle(ids["isk"], {ids["eur"]: "137"})

    assert response.status_code == 200
    assert response.json()["trip"]["settlement"] == {
        "target_currency_id": ids["isk"],
        "settled_at": "2026-09-22T18:00:00Z",
        "rates": [{"currency_id": ids["eur"], "rate": 137}],
    }


# --- settlement errors --------------------------------------------------------


def test_put_settlement_without_a_rate_is_missing_rate(settle, ids):
    """Every trip currency other than the target needs a rate; the missing one is named."""
    response = settle(ids["eur"], {})

    assert response.status_code == 422
    assert response.json() == rate_error("missing_rate", ids["isk"])


@pytest.mark.parametrize(
    ("rates", "named"),
    [
        pytest.param({"isk": "0.0073", "eur": "1"}, "eur", id="rate-for-the-target"),
        pytest.param({"isk": "0.0073", 999999: "2"}, 999999, id="currency-outside-the-trip"),
        pytest.param({"isk": "0"}, "isk", id="zero"),
        pytest.param({"isk": "-0.0073"}, "isk", id="negative"),
        pytest.param({"isk": "0,0073"}, "isk", id="comma-decimal"),
        pytest.param({"isk": "7.3e-3"}, "isk", id="exponent"),
        pytest.param({"isk": "0.0000000001"}, "isk", id="ten-places"),
        pytest.param({"isk": "1234567890"}, "isk", id="ten-integer-digits"),
    ],
)
def test_put_settlement_bad_rate_is_invalid_rate(settle, ids, rates, named):
    """A rate for the target, for a foreign currency, or off the `Rate` grammar is invalid_rate."""
    response = settle(ids["eur"], {ids.get(key, key): rate for key, rate in rates.items()})

    assert response.status_code == 422
    assert response.json() == rate_error("invalid_rate", ids.get(named, named))


def test_put_settlement_naming_a_currency_twice_is_invalid_rate(client, trip, ids):
    """Two rates for one currency are no agreement; the repeated currency is named."""
    response = client.put(
        f"/api/v1/trips/{trip['slug']}/settlement",
        json={
            "target_currency_id": ids["eur"],
            "rates": [
                {"currency_id": ids["isk"], "rate": "0.0073"},
                {"currency_id": ids["isk"], "rate": "0.0074"},
            ],
        },
    )

    assert response.status_code == 422
    assert response.json() == rate_error("invalid_rate", ids["isk"])


def test_put_settlement_target_outside_the_trip_is_not_in_trip(settle, ids):
    """A target that is not one of this trip's currencies is not_in_trip under its field."""
    response = settle(999999, {ids["isk"]: "0.0073"})

    assert response.status_code == 422
    assert response.json() == {
        "error": {
            "code": "validation_error",
            "params": {},
            "fields": {"target_currency_id": {"code": "not_in_trip", "params": {}}},
        }
    }


def test_unlocking_twice_is_trip_not_settled(client, trip, settle, ids):
    """The first DELETE unlocks; a second has nothing to unlock and says so."""
    settle(ids["eur"], {ids["isk"]: "0.0073"})
    url = f"/api/v1/trips/{trip['slug']}/settlement"
    assert client.delete(url).status_code == 200

    response = client.delete(url)

    assert response.status_code == 409
    assert response.json() == {
        "error": {
            "code": "conflict",
            "params": {},
            "fields": {"id": {"code": "trip_not_settled", "params": {}}},
        }
    }


# --- the lock: item fields ----------------------------------------------------


@pytest.mark.parametrize(
    "change",
    [
        pytest.param(("amount", lambda ids: "200.00"), id="amount"),
        pytest.param(("currency_id", lambda ids: ids["eur"]), id="currency"),
        pytest.param(("payer_id", lambda ids: ids["ann"]), id="payer"),
        pytest.param(("split_mode", lambda ids: "shares"), id="split-mode"),
        pytest.param(("shares", lambda ids: [{"person_id": ids["petr"]}]), id="shares"),
    ],
)
def test_settled_item_rejects_a_changed_locked_field(client, trip, settled, ids, change):
    """A locked field whose value differs from the stored one is trip_settled under itself."""
    field, value = change

    response = client.patch(
        f"/api/v1/trips/{trip['slug']}/items/{settled['item']['id']}", json={field: value(ids)}
    )

    assert response.status_code == 409
    assert response.json() == trip_settled(field)


def test_settled_exact_item_new_amount_with_matching_shares_is_trip_settled(
    client, trip, item_body, settle, ids
):
    """A new amount with an exact split that adds up to it is the lock, not a sum mismatch."""
    created = client.post(
        f"/api/v1/trips/{trip['slug']}/items",
        json=item_body(
            split_mode="exact",
            shares=[
                {"person_id": ids["petr"], "amount": "60.00"},
                {"person_id": ids["ann"], "amount": "40.00"},
            ],
        ),
    )
    settle(ids["eur"], {ids["isk"]: "0.0073"})

    response = client.patch(
        f"/api/v1/trips/{trip['slug']}/items/{created.json()['item']['id']}",
        json={
            "amount": "200.00",
            "split_mode": "exact",
            "shares": [
                {"person_id": ids["petr"], "amount": "120.00"},
                {"person_id": ids["ann"], "amount": "80.00"},
            ],
        },
    )

    assert response.status_code == 409
    assert response.json() == trip_settled("amount")


def test_settled_item_restating_every_locked_field_saves(client, trip, settled, people):
    """The full body an edit form resends - stored amount, payer, mode and split - saves."""
    item = settled["item"]

    response = client.patch(
        f"/api/v1/trips/{trip['slug']}/items/{item['id']}",
        json={
            "name": "Renamed",
            "amount": "100.00",
            "currency_id": item["currency_id"],
            "payer_id": item["payer_id"],
            "split_mode": "equal",
            "shares": [{"person_id": person["id"]} for person in reversed(people)],
        },
    )

    assert response.status_code == 200, response.text
    assert response.json()["item"]["name"] == "Renamed"
    assert response.json()["item"]["split"] == item["split"]


def test_settled_item_restating_a_split_with_a_deactivated_sharer_saves(client, trip, settled, ids):
    """Resending the item as read back, inactive sharer included, passes the lock and saves."""
    client.patch(f"/api/v1/trips/{trip['slug']}/people/{ids['ann']}", json={"active": False})
    url = f"/api/v1/trips/{trip['slug']}/items/{settled['item']['id']}"
    split = client.get(url).json()["item"]["split"]

    response = client.patch(
        url,
        json={
            "name": "Renamed",
            "split_mode": split["mode"],
            "shares": [{"person_id": share["person_id"]} for share in split["shares"]],
        },
    )

    assert response.status_code == 200, response.text
    assert response.json()["item"]["split"] == split


def test_settled_item_restating_a_weighted_split_saves(client, trip, item_body, settle, ids):
    """Weights compare once resolved: "2" and "2.0" are the same stored split."""
    created = client.post(
        f"/api/v1/trips/{trip['slug']}/items",
        json=item_body(
            split_mode="shares",
            shares=[
                {"person_id": ids["petr"], "weight": "2"},
                {"person_id": ids["ann"], "weight": "1"},
            ],
        ),
    )
    settle(ids["eur"], {ids["isk"]: "0.0073"})

    response = client.patch(
        f"/api/v1/trips/{trip['slug']}/items/{created.json()['item']['id']}",
        json={
            "split_mode": "shares",
            "shares": [
                {"person_id": ids["ann"], "weight": "1.0000"},
                {"person_id": ids["petr"], "weight": "2.0"},
            ],
        },
    )

    assert response.status_code == 200, response.text


@pytest.mark.parametrize(
    "body",
    [
        pytest.param({"name": "Dinner"}, id="name"),
        pytest.param({"note": "with tip"}, id="note"),
        pytest.param({"city": "Vík"}, id="city"),
        pytest.param({"labels": ["food"]}, id="labels"),
        pytest.param({"lat": "64.1", "lon": "-21.9"}, id="coordinates"),
        pytest.param({"map_url": "https://example.test/map"}, id="map-url"),
        pytest.param({"occurred_at": "2026-09-15T08:00:00"}, id="occurred-at"),
        pytest.param({"occurred_tz": "Europe/Copenhagen"}, id="occurred-tz"),
        pytest.param({"stay_id": None}, id="stay"),
        pytest.param({"country_id": None}, id="country"),
        pytest.param({"wallet_id": None}, id="wallet-of-the-payer"),
    ],
)
def test_settled_item_editable_field_saves(client, trip, settled, editable, body):
    """Every item field outside `net` stays writable on a settled trip.

    A `None` in the case stands for the row `editable` created for that field.
    """
    sent = {key: editable[key] if value is None else value for key, value in body.items()}

    response = client.patch(
        f"/api/v1/trips/{trip['slug']}/items/{settled['item']['id']}", json=sent
    )

    assert response.status_code == 200, response.text
    saved = response.json()["item"]
    assert {key: saved[key] for key in sent} == sent


@pytest.mark.parametrize(
    "body",
    [
        pytest.param({"symbol": "€"}, id="symbol"),
        pytest.param({"is_primary": True}, id="is-primary"),
    ],
)
def test_settled_currency_editable_field_saves(client, trip, settled, ids, body):
    """A currency's symbol and primary flag leave every balance alone, so they stay writable."""
    response = client.patch(f"/api/v1/trips/{trip['slug']}/currencies/{ids['eur']}", json=body)

    assert response.status_code == 200, response.text
    assert {key: response.json()["currency"][key] for key in body} == body


def test_settled_trip_fields_save(client, trip, settled):
    """The trip's own name, dates, note and archived flag stay writable while settled."""
    response = client.patch(
        f"/api/v1/trips/{trip['slug']}",
        json={"name": "Iceland, done", "end_date": "2026-09-23", "note": "paid", "archived": True},
    )

    assert response.status_code == 200, response.text
    saved = response.json()["trip"]
    assert (saved["name"], saved["end_date"], saved["note"], saved["archived"]) == (
        "Iceland, done",
        "2026-09-23",
        "paid",
        True,
    )
    assert saved["settlement"] == settled["trip"]["settlement"]


def test_settled_trip_still_previews_a_split(client, trip, settled, ids):
    """`preview-split` saves nothing, so a settled trip answers it as usual."""
    response = client.post(
        f"/api/v1/trips/{trip['slug']}/items/preview-split",
        json={"amount": "40.00", "currency_id": ids["isk"], "split_mode": "equal"},
    )

    assert response.status_code == 200, response.text


# --- the lock: whole objects --------------------------------------------------


def transfer_url(slug, locked, kind):
    """Return the URL of one of the settled trip's transfers."""
    return f"/api/v1/trips/{slug}/transfers/{locked['transfers'][kind]['id']}"


@pytest.mark.parametrize(
    "write",
    [
        pytest.param(
            lambda c, slug, lk: c.post(f"/api/v1/trips/{slug}/items", json=lk["item_body"]()),
            id="item-create",
        ),
        pytest.param(
            lambda c, slug, lk: c.delete(f"/api/v1/trips/{slug}/items/{lk['item']['id']}"),
            id="item-delete",
        ),
        pytest.param(
            lambda c, slug, lk: c.post(f"/api/v1/trips/{slug}/currencies", json={"code": "DKK"}),
            id="currency-create",
        ),
        pytest.param(
            lambda c, slug, lk: c.delete(f"/api/v1/trips/{slug}/currencies/{lk['eur']}"),
            id="currency-delete-target",
        ),
        pytest.param(
            lambda c, slug, lk: c.delete(f"/api/v1/trips/{slug}/currencies/{lk['isk']}"),
            id="currency-delete-rated",
        ),
        pytest.param(
            lambda c, slug, lk: c.post(
                f"/api/v1/trips/{slug}/transfers", json=lk["transfer_body"]()
            ),
            id="transfer-create",
        ),
        *(
            pytest.param(
                lambda c, slug, lk, kind=kind: c.patch(
                    transfer_url(slug, lk, kind), json={"note": "fixed"}
                ),
                id=f"transfer-update-{kind}",
            )
            for kind in ("same-owner", "cross-owner")
        ),
        *(
            pytest.param(
                lambda c, slug, lk, kind=kind: c.delete(transfer_url(slug, lk, kind)),
                id=f"transfer-delete-{kind}",
            )
            for kind in ("same-owner", "cross-owner")
        ),
    ],
)
def test_settled_trip_rejects_a_whole_object_write(client, trip, locked, write):
    """Item create/delete, currency create/delete and every transfer write are trip_settled."""
    response = write(client, trip["slug"], locked)

    assert response.status_code == 409
    assert response.json() == trip_settled("id")


# --- lock / unlock cycles -----------------------------------------------------


def test_settle_unlock_cycles_keep_only_the_latest_agreement(client, trip, item, settle, ids):
    """Settle, unlock, settle anew, unlock, settle: each step holds exactly its own agreement.

    Balances never move across a settle or an unlock, a locked edit fails exactly
    while settled, and a currency's rate from an earlier agreement never survives.
    """
    isk, eur = ids["isk"], ids["eur"]
    dkk = client.post(f"/api/v1/trips/{trip['slug']}/currencies", json={"code": "DKK"}).json()[
        "currency"
    ]["id"]
    trip_url = f"/api/v1/trips/{trip['slug']}"

    def unlock():
        return client.delete(f"{trip_url}/settlement")

    steps = [
        (
            lambda: settle(eur, {isk: "0.0073", dkk: "0.134"}),
            {"target_currency_id": eur, "rates": [(isk, 0.0073), (dkk, 0.134)]},
        ),
        (unlock, None),
        (
            lambda: settle(isk, {eur: "137", dkk: "18.4"}),
            {"target_currency_id": isk, "rates": [(dkk, 18.4), (eur, 137)]},
        ),
        (unlock, None),
        (
            lambda: settle(dkk, {isk: "0.054", eur: "7.46"}),
            {"target_currency_id": dkk, "rates": [(isk, 0.054), (eur, 7.46)]},
        ),
    ]

    for amount, (step, agreement) in enumerate(steps, start=101):
        before = client.get(f"{trip_url}/balances").json()

        response = step()

        assert response.status_code == 200, response.text
        assert client.get(f"{trip_url}/balances").json() == before
        settlement = client.get(trip_url).json()["trip"]["settlement"]
        if agreement is None:
            assert settlement is None
        else:
            assert settlement == {
                "target_currency_id": agreement["target_currency_id"],
                "settled_at": "2026-09-22T18:00:00Z",
                "rates": [{"currency_id": cid, "rate": rate} for cid, rate in agreement["rates"]],
            }
        edit = client.patch(f"{trip_url}/items/{item['id']}", json={"amount": f"{amount}.00"})
        assert edit.status_code == (200 if agreement is None else 409)


# --- schema -------------------------------------------------------------------


def test_delete_settled_trip_leaves_no_row_behind(client, trip, settled, session):
    """A settled trip deletes cleanly; its currencies go too, which only the DB can show."""
    response = client.delete(f"/api/v1/trips/{trip['slug']}")

    assert response.status_code == 204
    assert client.get(f"/api/v1/trips/{trip['slug']}").status_code == 404
    remaining = session.execute(
        select(func.count()).select_from(TripCurrency).where(TripCurrency.trip_id == trip["id"])
    ).scalar_one()
    assert remaining == 0


def test_seeded_rates_follow_each_trip_settlement_state(session):
    """Over the seed, a settled trip rates every currency but its target, an open one none.

    Read off the rows: the rates are internal to `trip_currency`, so only the DB
    shows that no stray rate sits on a target or an unsettled trip.
    """
    seed_demo(session)

    states = {}
    for trip in session.execute(select(Trip)).scalars():
        rated = {c.code for c in trip.currencies if c.settlement_rate_scaled is not None}
        target = next(
            (c.code for c in trip.currencies if c.id == trip.settlement_currency_id), None
        )
        states[trip.slug] = (trip.settled_at is not None, target, rated)

    assert states == {
        "iceland-2026": (False, None, set()),
        "faroe-2025": (True, "EUR", {"DKK"}),
    }
