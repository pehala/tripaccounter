"""Functional tests for stays: CRUD, the items they group, and their totals per night."""

import pytest


@pytest.fixture()
def stay(client, trip, stay_body):
    """Create the default two-night stay and return its JSON."""
    response = client.post(f"/api/v1/trips/{trip['slug']}/stays", json=stay_body())
    assert response.status_code == 201, response.text
    return response.json()["stay"]


@pytest.fixture()
def other_trip(client):
    """Create a second trip, whose ids must never resolve under the first."""
    body = {
        "name": "Other trip",
        "people": [{"name": "X"}],
        "currencies": [{"code": "USD"}],
        "countries": [{"name": "Nowhere"}],
    }
    return client.post("/api/v1/trips", json=body).json()["trip"]


def test_create_stay_read_back(client, trip, country, stay):
    """A created stay reads back field for field, with its nights and no spend."""
    assert stay == {
        "id": stay["id"],
        "name": "Guesthouse Vik",
        "check_in": "2026-09-14",
        "check_out": "2026-09-16",
        "nights": 2,
        "url": "https://example.com/guesthouse-vik",
        "note": None,
        "country_id": country["id"],
        "city": "Vik",
        "map_url": None,
        "lat": None,
        "lon": None,
        "item_count": 0,
        "totals": [],
    }
    listed = client.get(f"/api/v1/trips/{trip['slug']}/stays").json()["stays"]
    assert listed == [stay]


def test_trip_embeds_stays_without_totals(client, trip, stay):
    """The trip read carries each stay's roster form, so the item form needs no extra call."""
    embedded = client.get(f"/api/v1/trips/{trip['slug']}").json()["trip"]["stays"]

    assert [s["id"] for s in embedded] == [stay["id"]]
    assert "totals" not in embedded[0]


def test_stays_list_orders_by_check_in_then_name(client, trip, stay_body):
    """Stays list by check-in date, and by name on the same date."""
    for name, check_in in (("Hut", "2026-09-18"), ("Camp", "2026-09-12"), ("Barn", "2026-09-18")):
        client.post(
            f"/api/v1/trips/{trip['slug']}/stays",
            json=stay_body(name=name, check_in=check_in, check_out="2026-09-19"),
        )

    listed = client.get(f"/api/v1/trips/{trip['slug']}/stays").json()["stays"]

    assert [s["name"] for s in listed] == ["Camp", "Barn", "Hut"]


def test_stay_totals_sum_its_items_per_currency_with_nightly_average(
    client, trip, currencies, item_body, stay_body
):
    """Each currency's total divides over the nights, floored at six places, never converted."""
    stay = client.post(
        f"/api/v1/trips/{trip['slug']}/stays",
        json=stay_body(check_in="2026-09-14", check_out="2026-09-17"),
    ).json()["stay"]
    isk, eur = currencies
    for amount, currency in (("24000", isk), ("6000", isk), ("100.00", eur)):
        client.post(
            f"/api/v1/trips/{trip['slug']}/items",
            json=item_body(amount=amount, currency_id=currency["id"], stay_id=stay["id"]),
        )
    client.post(f"/api/v1/trips/{trip['slug']}/items", json=item_body(amount="999"))

    listed = client.get(f"/api/v1/trips/{trip['slug']}/stays").json()["stays"]

    assert listed[0]["item_count"] == 3
    assert listed[0]["totals"] == [
        {"currency_code": "ISK", "currency_id": isk["id"], "amount": 30000, "per_night": 10000},
        {"currency_code": "EUR", "currency_id": eur["id"], "amount": 100, "per_night": 33.333333},
    ]


def test_same_day_stay_has_no_nightly_average(client, trip, item_body, stay_body):
    """A stay checked out the day it began has 0 nights and a `null` per-night figure."""
    stay = client.post(
        f"/api/v1/trips/{trip['slug']}/stays",
        json=stay_body(check_in="2026-09-14", check_out="2026-09-14"),
    ).json()["stay"]
    client.post(
        f"/api/v1/trips/{trip['slug']}/items", json=item_body(amount="50.00", stay_id=stay["id"])
    )

    listed = client.get(f"/api/v1/trips/{trip['slug']}/stays").json()["stays"]

    assert listed[0]["nights"] == 0
    assert listed[0]["totals"][0]["per_night"] is None


def test_stay_map_url_fills_coordinates(client, trip, stay_body):
    """A parseable maps link fills a stay's lat/lon, as it does an item's."""
    response = client.post(
        f"/api/v1/trips/{trip['slug']}/stays",
        json=stay_body(map_url="https://example.com/@63.4186,-19.0060,15z"),
    )

    assert response.json()["stay"]["lat"] == "63.4186"
    assert response.json()["stay"]["lon"] == "-19.0060"


@pytest.mark.parametrize(
    ("overrides", "expected"),
    [
        pytest.param(
            {"check_in": "2026-09-16", "check_out": "2026-09-14"},
            {"check_out": {"code": "invalid_date_range", "params": {}}},
            id="check-out-before-check-in",
        ),
        pytest.param(
            {"check_in": "14.9.2026"},
            {"check_in": {"code": "invalid_date", "params": {}}},
            id="not-iso-date",
        ),
        pytest.param({"name": "  "}, {"name": {"code": "required", "params": {}}}, id="blank-name"),
        pytest.param(
            {"url": "booking"}, {"url": {"code": "invalid_url", "params": {}}}, id="bad-url"
        ),
    ],
)
def test_create_stay_invalid_field_is_422(client, trip, stay_body, overrides, expected):
    """A stay write that breaks a field rule answers 422 with that field's code."""
    response = client.post(f"/api/v1/trips/{trip['slug']}/stays", json=stay_body(**overrides))

    assert response.status_code == 422
    assert response.json() == {
        "error": {"code": "validation_error", "params": {}, "fields": expected}
    }


def test_stay_country_from_another_trip_is_not_in_trip(client, trip, stay_body, other_trip):
    """A stay cannot sit in another trip's country."""
    response = client.post(
        f"/api/v1/trips/{trip['slug']}/stays",
        json=stay_body(country_id=other_trip["countries"][0]["id"]),
    )

    assert response.status_code == 422
    assert response.json()["error"]["fields"] == {
        "country_id": {"code": "not_in_trip", "params": {}}
    }


def test_patch_stay_null_clears_and_omitted_keeps(client, trip, stay):
    """PATCH clears an optional field sent as `null` and leaves omitted fields as they were."""
    response = client.patch(
        f"/api/v1/trips/{trip['slug']}/stays/{stay['id']}",
        json={"url": None, "country_id": None, "check_out": "2026-09-17"},
    )

    assert response.status_code == 200
    assert response.json()["stay"] == {
        **stay,
        "url": None,
        "country_id": None,
        "check_out": "2026-09-17",
        "nights": 3,
    }


def test_patch_stay_check_out_before_existing_check_in_is_422(client, trip, stay):
    """The date range is checked against the dates the stay settles on, not just those sent."""
    response = client.patch(
        f"/api/v1/trips/{trip['slug']}/stays/{stay['id']}", json={"check_out": "2026-09-13"}
    )

    assert response.status_code == 422
    assert response.json()["error"]["fields"] == {
        "check_out": {"code": "invalid_date_range", "params": {}}
    }


def test_delete_stay_detaches_its_items(client, trip, item_body, stay):
    """Deleting a stay keeps its items, no longer grouped under any stay."""
    item = client.post(
        f"/api/v1/trips/{trip['slug']}/items", json=item_body(stay_id=stay["id"])
    ).json()["item"]

    response = client.delete(f"/api/v1/trips/{trip['slug']}/stays/{stay['id']}")

    assert response.status_code == 204
    kept = client.get(f"/api/v1/trips/{trip['slug']}/items/{item['id']}").json()["item"]
    assert kept["stay_id"] is None
    assert client.get(f"/api/v1/trips/{trip['slug']}/stays").json()["stays"] == []


def test_patch_item_stay_id_null_detaches_and_omitted_keeps(client, trip, item_body, stay):
    """An item PATCH leaves its stay alone unless `stay_id` is sent, and `null` detaches it."""
    item = client.post(
        f"/api/v1/trips/{trip['slug']}/items", json=item_body(stay_id=stay["id"])
    ).json()["item"]
    url = f"/api/v1/trips/{trip['slug']}/items/{item['id']}"

    kept = client.patch(url, json={"name": "Breakfast"}).json()["item"]
    detached = client.patch(url, json={"stay_id": None}).json()["item"]

    assert kept["stay_id"] == stay["id"]
    assert detached["stay_id"] is None


def test_item_stay_from_another_trip_is_not_in_trip(client, trip, item_body, other_trip):
    """An item cannot be grouped under another trip's stay."""
    foreign = client.post(
        f"/api/v1/trips/{other_trip['slug']}/stays",
        json={"name": "Elsewhere", "check_in": "2026-09-14", "check_out": "2026-09-15"},
    ).json()["stay"]

    response = client.post(
        f"/api/v1/trips/{trip['slug']}/items", json=item_body(stay_id=foreign["id"])
    )

    assert response.status_code == 422
    assert response.json()["error"]["fields"] == {"stay_id": {"code": "not_in_trip", "params": {}}}
