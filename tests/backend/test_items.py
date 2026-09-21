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


def test_create_item_with_city_read_back(client, trip, item_body):
    """A freeform city is stored and echoed back as given."""
    response = client.post(f"/api/v1/trips/{trip['slug']}/items", json=item_body(city="Reykjavík"))
    assert response.status_code == 201, response.text
    assert response.json()["item"]["city"] == "Reykjavík"


def test_create_item_omitted_city_is_null(client, trip, item_body):
    """An item written without a city reads back with `city: null`, not an error."""
    response = client.post(f"/api/v1/trips/{trip['slug']}/items", json=item_body())
    assert response.status_code == 201, response.text
    assert response.json()["item"]["city"] is None


def test_patch_item_city_leaves_other_fields_untouched(client, trip, item_body):
    """PATCH with only `city` leaves name, amount and split untouched."""
    created = client.post(
        f"/api/v1/trips/{trip['slug']}/items", json=item_body(name="Dinner")
    ).json()["item"]

    response = client.patch(
        f"/api/v1/trips/{trip['slug']}/items/{created['id']}", json={"city": "Vík"}
    )
    assert response.status_code == 200
    updated = response.json()["item"]
    assert updated["name"] == "Dinner"
    assert updated["city"] == "Vík"
    assert updated["split"] == created["split"]


def test_list_items_orders_by_occurred_at_desc_then_id_desc(
    client, trip, items_two_same_day_one_earlier, currencies
):
    """List order is occurred_at DESC, id DESC; day_totals sums each day, newest first."""
    items = client.get(f"/api/v1/trips/{trip['slug']}/items").json()
    dates = [item["occurred_at"] for item in items["items"]]
    assert dates == ["2026-09-14T09:00:00Z", "2026-09-14T09:00:00Z", "2026-09-13T09:00:00Z"]
    assert items["items"][0]["id"] > items["items"][1]["id"]

    assert items["day_totals"] == [
        {
            "date": "2026-09-14",
            "totals": [{"currency_code": "ISK", "currency_id": currencies[0]["id"], "amount": 200}],
        },
        {
            "date": "2026-09-13",
            "totals": [{"currency_code": "ISK", "currency_id": currencies[0]["id"], "amount": 100}],
        },
    ]


def test_before_trip_totals_sums_items_before_trip_start(client, trip, item_body, currencies):
    """Items on two days before `start_date` (2026-09-12) sum into `before_trip_totals`."""
    for occurred_at in ("2026-09-09T09:00:00", "2026-09-10T09:00:00"):
        client.post(f"/api/v1/trips/{trip['slug']}/items", json=item_body(occurred_at=occurred_at))

    items = client.get(f"/api/v1/trips/{trip['slug']}/items").json()

    assert items["day_totals"] == []
    assert items["before_trip_totals"] == [
        {"currency_code": "ISK", "currency_id": currencies[0]["id"], "amount": 200},
    ]


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


def test_create_item_omitted_wallet_id_uses_payer_default(
    client, trip, person_id, default_wallet_of, item_body
):
    """Omitting `wallet_id` on create falls back to the payer's default wallet."""
    bob = person_id("Bob")
    response = client.post(f"/api/v1/trips/{trip['slug']}/items", json=item_body(payer_id=bob))
    assert response.json()["item"]["wallet_id"] == default_wallet_of(bob)["id"]


def test_create_item_wallet_not_owned_by_payer_is_wallet_owner_mismatch(
    client, trip, person_id, default_wallet_of, item_body
):
    """A wallet id that belongs to someone else is rejected."""
    petr, ann = person_id("Petr"), person_id("Ann")
    response = client.post(
        f"/api/v1/trips/{trip['slug']}/items",
        json=item_body(payer_id=ann, wallet_id=default_wallet_of(petr)["id"]),
    )
    assert response.status_code == 422
    assert response.json()["error"]["fields"]["wallet_id"] == {
        "code": "wallet_owner_mismatch",
        "params": {},
    }


def test_patch_item_payer_change_resets_wallet_to_new_payers_default(
    client, trip, person_id, default_wallet_of, item_body
):
    """Changing `payer_id` with no `wallet_id` re-defaults to the new payer's wallet."""
    petr, ann = person_id("Petr"), person_id("Ann")
    created = client.post(
        f"/api/v1/trips/{trip['slug']}/items", json=item_body(payer_id=petr)
    ).json()["item"]

    response = client.patch(
        f"/api/v1/trips/{trip['slug']}/items/{created['id']}", json={"payer_id": ann}
    )
    assert response.status_code == 200
    assert response.json()["item"]["wallet_id"] == default_wallet_of(ann)["id"]


def test_patch_item_wallet_owner_mismatch_leaves_item_unchanged(
    client, trip, person_id, default_wallet_of, item_body
):
    """A mismatched wallet_id on PATCH is rejected and the item is not touched."""
    petr, ann = person_id("Petr"), person_id("Ann")
    created = client.post(
        f"/api/v1/trips/{trip['slug']}/items", json=item_body(payer_id=ann, name="Original")
    ).json()["item"]

    response = client.patch(
        f"/api/v1/trips/{trip['slug']}/items/{created['id']}",
        json={"wallet_id": default_wallet_of(petr)["id"], "name": "Changed"},
    )
    assert response.status_code == 422
    assert response.json()["error"]["fields"]["wallet_id"]["code"] == "wallet_owner_mismatch"

    unchanged = client.get(f"/api/v1/trips/{trip['slug']}/items/{created['id']}").json()["item"]
    assert unchanged == created


def test_patch_item_payer_and_wallet_together_is_accepted(
    client, trip, person_id, default_wallet_of, item_body
):
    """A PATCH naming both the new payer and their wallet in one body succeeds."""
    petr, ann = person_id("Petr"), person_id("Ann")
    created = client.post(
        f"/api/v1/trips/{trip['slug']}/items", json=item_body(payer_id=ann)
    ).json()["item"]

    response = client.patch(
        f"/api/v1/trips/{trip['slug']}/items/{created['id']}",
        json={"payer_id": petr, "wallet_id": default_wallet_of(petr)["id"]},
    )
    assert response.status_code == 200
    assert response.json()["item"]["wallet_id"] == default_wallet_of(petr)["id"]


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
