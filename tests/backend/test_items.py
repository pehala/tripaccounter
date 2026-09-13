"""Functional tests for item creation, reading, updating, and ordering."""

from datetime import UTC, datetime


def test_create_item_read_back_equal(client, trip, item_body):
    """A created item reads back with the same fields, split resolved equally."""
    response = client.post(f"/api/v1/trips/{trip['slug']}/items", json=item_body(amount="18400"))
    assert response.status_code == 201, response.text
    item = response.json()["item"]

    assert item["amount"] == 18400
    assert item["currency_code"] == "ISK"
    assert [share["owed"] for share in item["split"]["shares"]] == [4600, 4600, 4600, 4600]

    read_back = client.get(f"/api/v1/trips/{trip['slug']}/items/{item['id']}").json()["item"]
    assert read_back == item


def test_list_items_orders_by_occurred_at_desc_then_id_desc(
    client, trip, items_two_same_day_one_earlier
):
    """List order is occurred_at DESC, id DESC."""
    items = client.get(f"/api/v1/trips/{trip['slug']}/items").json()["items"]
    dates = [item["occurred_at"] for item in items]
    assert dates == ["2026-07-02T09:00:00Z", "2026-07-02T09:00:00Z", "2026-07-01T09:00:00Z"]
    assert items[0]["id"] > items[1]["id"]


def test_patch_item_leaves_omitted_fields_untouched(client, trip, item_body):
    """PATCH with only `note` leaves name, amount, split untouched."""
    created = client.post(
        f"/api/v1/trips/{trip['slug']}/items", json=item_body(name="Dinner")
    ).json()["item"]

    response = client.patch(
        f"/api/v1/trips/{trip['slug']}/items/{created['id']}", json={"note": "Great place"}
    )
    assert response.status_code == 200
    updated = response.json()["item"]
    assert updated["name"] == "Dinner"
    assert updated["note"] == "Great place"
    assert updated["split"] == created["split"]


def test_patch_item_shares_replaces_whole_split(client, trip, people, item_body):
    """Sending `shares` on PATCH replaces the entire split, not merges it."""
    created = client.post(
        f"/api/v1/trips/{trip['slug']}/items", json=item_body(amount="100.00")
    ).json()["item"]

    response = client.patch(
        f"/api/v1/trips/{trip['slug']}/items/{created['id']}",
        json={"shares": [{"person_id": people[0]["id"]}, {"person_id": people[1]["id"]}]},
    )
    assert response.status_code == 200
    shares = response.json()["item"]["split"]["shares"]
    active = [s for s in shares if s["owed"] is not None]
    assert len(active) == 2
    assert {s["person_id"] for s in active} == {people[0]["id"], people[1]["id"]}


def test_delete_item_returns_204_and_disappears(client, trip, item_body):
    """DELETE returns 204 and the item is gone from the list."""
    created = client.post(f"/api/v1/trips/{trip['slug']}/items", json=item_body()).json()["item"]

    response = client.delete(f"/api/v1/trips/{trip['slug']}/items/{created['id']}")
    assert response.status_code == 204
    assert response.content == b""

    items = client.get(f"/api/v1/trips/{trip['slug']}/items").json()["items"]
    assert created["id"] not in [item["id"] for item in items]


def test_occurred_at_defaults_to_clock(client, trip, item_body, frozen_clock):
    """Omitting `occurred_at` uses the injected clock, not the ambient one."""
    frozen_clock(datetime(2026, 8, 1, 10, 30, tzinfo=UTC))
    body = item_body()
    del body["occurred_at"]

    response = client.post(f"/api/v1/trips/{trip['slug']}/items", json=body)
    assert response.status_code == 201
    assert response.json()["item"]["occurred_at"] == "2026-08-01T10:30:00Z"


def test_map_url_parsed_when_coordinates_absent(client, trip, item_body):
    """A parseable @lat,lon in map_url fills lat/lon when they are not given."""
    response = client.post(
        f"/api/v1/trips/{trip['slug']}/items",
        json=item_body(map_url="https://maps.google.com/@64.1493,-21.9403,15z"),
    )
    item = response.json()["item"]
    assert item["lat"] == "64.1493"
    assert item["lon"] == "-21.9403"


def test_explicit_coordinates_win_over_map_url(client, trip, item_body):
    """Explicit lat/lon are not overridden by a parseable map_url."""
    response = client.post(
        f"/api/v1/trips/{trip['slug']}/items",
        json=item_body(
            map_url="https://maps.google.com/@64.1493,-21.9403,15z", lat="1.000000", lon="2.000000"
        ),
    )
    item = response.json()["item"]
    assert item["lat"] == "1.000000"
    assert item["lon"] == "2.000000"


def test_unparseable_map_url_is_stored_not_an_error(client, trip, item_body):
    """An unparseable map_url is stored as-is; parsing failure is not an error."""
    response = client.post(
        f"/api/v1/trips/{trip['slug']}/items",
        json=item_body(map_url="https://example.com/somewhere"),
    )
    assert response.status_code == 201
    item = response.json()["item"]
    assert item["map_url"] == "https://example.com/somewhere"
    assert item["lat"] is None
    assert item["lon"] is None


def test_item_id_from_another_trip_is_404(client, trip, item_body):
    """An item id that belongs to a different trip is not_found, not leaked."""
    other = client.post(
        "/api/v1/trips",
        json={
            "name": "Other trip",
            "people": [{"name": "X"}],
            "currencies": [{"code": "USD"}],
            "countries": [{"name": "Nowhere"}],
        },
    ).json()["trip"]
    foreign_item = client.post(
        f"/api/v1/trips/{other['slug']}/items",
        json=item_body(
            currency_id=other["currencies"][0]["id"],
            payer_id=other["people"][0]["id"],
            country_id=other["countries"][0]["id"],
        ),
    ).json()["item"]

    response = client.get(f"/api/v1/trips/{trip['slug']}/items/{foreign_item['id']}")
    assert response.status_code == 404
    assert response.json() == {"error": {"code": "not_found", "params": {"resource": "item"}}}
