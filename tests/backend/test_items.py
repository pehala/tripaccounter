"""Functional tests for item creation, reading, updating, and ordering."""

from datetime import UTC, datetime


def test_create_item_read_back_equal(client, trip_url, item_body):
    """A created item reads back with the same fields, split resolved equally."""
    response = client.post(f"{trip_url}/items", json=item_body(amount="18400"))
    assert response.status_code == 201, response.text
    item = response.json()["item"]

    assert item["amount"] == 18400
    assert item["currency_code"] == "ISK"
    assert [share["owed"] for share in item["split"]["shares"]] == [4600, 4600, 4600, 4600]

    read_back = client.get(f"{trip_url}/items/{item['id']}").json()["item"]
    assert read_back == item


def test_create_item_with_city_read_back(client, trip_url, item_body):
    """A freeform city is stored and echoed back as given."""
    response = client.post(f"{trip_url}/items", json=item_body(city="Reykjavík"))
    assert response.status_code == 201, response.text
    assert response.json()["item"]["city"] == "Reykjavík"


def test_create_item_omitted_city_is_null(client, trip_url, item_body):
    """An item written without a city reads back with `city: null`, not an error."""
    response = client.post(f"{trip_url}/items", json=item_body())
    assert response.status_code == 201, response.text
    assert response.json()["item"]["city"] is None


def test_patch_item_city_leaves_other_fields_untouched(client, trip_url, item_body, create):
    """PATCH with only `city` leaves name, amount and split untouched."""
    created = create("items", item_body(name="Dinner"))

    response = client.patch(f"{trip_url}/items/{created['id']}", json={"city": "Vík"})
    assert response.status_code == 200
    updated = response.json()["item"]
    assert updated["name"] == "Dinner"
    assert updated["city"] == "Vík"
    assert updated["split"] == created["split"]


def test_list_items_orders_by_occurred_at_desc_then_id_desc(
    client, trip_url, items_two_same_day_one_earlier, currencies
):
    """List order is occurred_at DESC, id DESC; day_totals sums each day, newest first."""
    items = client.get(f"{trip_url}/items").json()
    dates = [item["occurred_at"] for item in items["items"]]
    assert dates == ["2026-09-14T09:00:00", "2026-09-14T09:00:00", "2026-09-13T09:00:00"]
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


def test_before_trip_totals_sums_items_before_trip_start(
    client, trip_url, item_body, currencies, create
):
    """Items on two days before `start_date` (2026-09-12) sum into `before_trip_totals`."""
    for occurred_at in ("2026-09-09T09:00:00", "2026-09-10T09:00:00"):
        create("items", item_body(occurred_at=occurred_at))

    items = client.get(f"{trip_url}/items").json()

    assert items["day_totals"] == []
    assert items["before_trip_totals"] == [
        {"currency_code": "ISK", "currency_id": currencies[0]["id"], "amount": 200},
    ]


def test_patch_item_leaves_omitted_fields_untouched(client, trip_url, item_body, create):
    """PATCH with only `note` leaves name, amount, split untouched."""
    created = create("items", item_body(name="Dinner"))

    response = client.patch(f"{trip_url}/items/{created['id']}", json={"note": "Great place"})
    assert response.status_code == 200
    updated = response.json()["item"]
    assert updated["name"] == "Dinner"
    assert updated["note"] == "Great place"
    assert updated["split"] == created["split"]


def test_patch_item_shares_replaces_whole_split(client, trip_url, people, item_body, create):
    """Sending `shares` on PATCH replaces the entire split, not merges it."""
    created = create("items", item_body(amount="100.00"))

    response = client.patch(
        f"{trip_url}/items/{created['id']}",
        json={"shares": [{"person_id": people[0]["id"]}, {"person_id": people[1]["id"]}]},
    )
    assert response.status_code == 200
    shares = response.json()["item"]["split"]["shares"]
    active = [s for s in shares if s["owed"] is not None]
    assert len(active) == 2
    assert {s["person_id"] for s in active} == {people[0]["id"], people[1]["id"]}


def test_delete_item_returns_204_and_disappears(client, trip_url, item_body, create):
    """DELETE returns 204 and the item is gone from the list."""
    created = create("items", item_body())

    response = client.delete(f"{trip_url}/items/{created['id']}")
    assert response.status_code == 204
    assert response.content == b""

    items = client.get(f"{trip_url}/items").json()["items"]
    assert created["id"] not in [item["id"] for item in items]


def test_occurred_at_defaults_to_clock(client, trip_url, item_body, frozen_clock):
    """Omitting `occurred_at` uses the injected clock, not the ambient one."""
    frozen_clock(datetime(2026, 8, 1, 10, 30, tzinfo=UTC))
    body = item_body()
    del body["occurred_at"]

    response = client.post(f"{trip_url}/items", json=body)
    assert response.status_code == 201
    assert response.json()["item"]["occurred_at"] == "2026-08-01T10:30:00"


def test_map_url_parsed_when_coordinates_absent(client, trip_url, item_body):
    """A parseable @lat,lon in map_url fills lat/lon when they are not given."""
    response = client.post(
        f"{trip_url}/items",
        json=item_body(map_url="https://example.com/@64.1493,-21.9403,15z"),
    )
    item = response.json()["item"]
    assert item["lat"] == "64.1493"
    assert item["lon"] == "-21.9403"


def test_explicit_coordinates_win_over_map_url(client, trip_url, item_body):
    """Explicit lat/lon are not overridden by a parseable map_url."""
    response = client.post(
        f"{trip_url}/items",
        json=item_body(
            map_url="https://example.com/@64.1493,-21.9403,15z", lat="1.000000", lon="2.000000"
        ),
    )
    item = response.json()["item"]
    assert item["lat"] == "1.000000"
    assert item["lon"] == "2.000000"


def test_unparseable_map_url_is_stored_not_an_error(client, trip_url, item_body):
    """An unparseable map_url is stored as-is; parsing failure is not an error."""
    response = client.post(
        f"{trip_url}/items",
        json=item_body(map_url="https://example.com/somewhere"),
    )
    assert response.status_code == 201
    item = response.json()["item"]
    assert item["map_url"] == "https://example.com/somewhere"
    assert item["lat"] is None
    assert item["lon"] is None


def test_create_item_omitted_wallet_id_uses_payer_default(
    client, trip_url, person_id, default_wallet_of, item_body
):
    """Omitting `wallet_id` on create falls back to the payer's default wallet."""
    bob = person_id("Bob")
    response = client.post(f"{trip_url}/items", json=item_body(payer_id=bob))
    assert response.json()["item"]["wallet_id"] == default_wallet_of(bob)["id"]


def test_create_item_wallet_not_owned_by_payer_is_wallet_owner_mismatch(
    client, trip_url, person_id, default_wallet_of, item_body
):
    """A wallet id that belongs to someone else is rejected."""
    petr, ann = person_id("Petr"), person_id("Ann")
    response = client.post(
        f"{trip_url}/items",
        json=item_body(payer_id=ann, wallet_id=default_wallet_of(petr)["id"]),
    )
    assert response.status_code == 422
    assert response.json()["error"]["fields"]["wallet_id"] == {
        "code": "wallet_owner_mismatch",
        "params": {},
    }


def test_patch_item_payer_change_resets_wallet_to_new_payers_default(  # noqa: PLR0913, PLR0917 (the fixtures are the setup)
    client, trip_url, person_id, default_wallet_of, item_body, create
):
    """Changing `payer_id` with no `wallet_id` re-defaults to the new payer's wallet."""
    petr, ann = person_id("Petr"), person_id("Ann")
    created = create("items", item_body(payer_id=petr))

    response = client.patch(f"{trip_url}/items/{created['id']}", json={"payer_id": ann})
    assert response.status_code == 200
    assert response.json()["item"]["wallet_id"] == default_wallet_of(ann)["id"]


def test_patch_item_wallet_owner_mismatch_leaves_item_unchanged(  # noqa: PLR0913, PLR0917 (the fixtures are the setup)
    client, trip_url, person_id, default_wallet_of, item_body, create
):
    """A mismatched wallet_id on PATCH is rejected and the item is not touched."""
    petr, ann = person_id("Petr"), person_id("Ann")
    created = create("items", item_body(payer_id=ann, name="Original"))

    response = client.patch(
        f"{trip_url}/items/{created['id']}",
        json={"wallet_id": default_wallet_of(petr)["id"], "name": "Changed"},
    )
    assert response.status_code == 422
    assert response.json()["error"]["fields"]["wallet_id"]["code"] == "wallet_owner_mismatch"

    unchanged = client.get(f"{trip_url}/items/{created['id']}").json()["item"]
    assert unchanged == created


def test_patch_item_payer_and_wallet_together_is_accepted(  # noqa: PLR0913, PLR0917 (the fixtures are the setup)
    client, trip_url, person_id, default_wallet_of, item_body, create
):
    """A PATCH naming both the new payer and their wallet in one body succeeds."""
    petr, ann = person_id("Petr"), person_id("Ann")
    created = create("items", item_body(payer_id=ann))

    response = client.patch(
        f"{trip_url}/items/{created['id']}",
        json={"payer_id": petr, "wallet_id": default_wallet_of(petr)["id"]},
    )
    assert response.status_code == 200
    assert response.json()["item"]["wallet_id"] == default_wallet_of(petr)["id"]


def test_item_id_from_another_trip_is_404(client, item_body, trip_url):
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

    response = client.get(f"{trip_url}/items/{foreign_item['id']}")
    assert response.status_code == 404
    assert response.json() == {"error": {"code": "not_found", "params": {"resource": "item"}}}


def test_patch_item_amount_resplits_the_saved_roster(client, trip_url, item_body, create):
    """A PATCH carrying only a new amount re-splits it over the people already on the item."""
    created = create("items", item_body(amount="100.00"))

    updated = client.patch(f"{trip_url}/items/{created['id']}", json={"amount": "200.00"}).json()[
        "item"
    ]

    assert [share["owed"] for share in updated["split"]["shares"]] == [50, 50, 50, 50]


def test_patch_item_amount_keeps_the_saved_weights(client, trip_url, people, item_body, create):
    """A weighted item re-split by a new amount keeps each person's weight."""
    created = create(
        "items",
        item_body(
            amount="96000",
            split_mode="shares",
            shares=[
                {"person_id": people[0]["id"], "weight": "1"},
                {"person_id": people[1]["id"], "weight": "1"},
                {"person_id": people[2]["id"], "weight": "1"},
                {"person_id": people[3]["id"], "weight": "0.5"},
            ],
        ),
    )

    updated = client.patch(f"{trip_url}/items/{created['id']}", json={"amount": "48000"}).json()[
        "item"
    ]

    shares = updated["split"]["shares"]
    assert [share["weight"] for share in shares] == ["1", "1", "1", "0.5"]
    assert [share["owed"] for share in shares] == [
        13714.285714,
        13714.285714,
        13714.285714,
        6857.142857,
    ]


def test_occurred_at_sent_as_null_defaults_to_clock(client, trip_url, item_body, frozen_clock):
    """An explicit `occurred_at: null` falls back to the clock, as an absent key does."""
    frozen_clock(datetime(2026, 8, 1, 10, 30, tzinfo=UTC))

    response = client.post(f"{trip_url}/items", json=item_body(occurred_at=None))

    assert response.status_code == 201
    assert response.json()["item"]["occurred_at"] == "2026-08-01T10:30:00"


def test_patch_item_amount_on_an_exact_item_is_sum_mismatch(
    client, trip_url, people, item_body, create
):
    """An exact item keeps its saved rows on a re-amount, so a new total no longer adds up."""
    created = create(
        "items",
        item_body(
            amount="184.00",
            split_mode="exact",
            shares=[
                {"person_id": people[0]["id"], "amount": "92.00"},
                {"person_id": people[1]["id"], "amount": "92.00"},
            ],
        ),
    )

    response = client.patch(f"{trip_url}/items/{created['id']}", json={"amount": "200.00"})

    assert response.status_code == 422
    assert response.json()["error"]["fields"]["shares"] == {
        "code": "sum_mismatch",
        "params": {"diff": 1600, "currency_code": "ISK"},
    }


def test_patch_item_split_mode_on_an_exact_item_keeps_its_rows(
    client, trip_url, people, item_body, create
):
    """An exact item's saved amounts survive a write that omits `shares`, unrounded."""
    created = create(
        "items",
        item_body(
            amount="184.05",
            split_mode="exact",
            shares=[
                {"person_id": people[0]["id"], "amount": "92.05"},
                {"person_id": people[1]["id"], "amount": "92.00"},
            ],
        ),
    )

    response = client.patch(f"{trip_url}/items/{created['id']}", json={"split_mode": "exact"})

    assert response.status_code == 200
    assert response.json()["item"]["split"] == created["split"]
