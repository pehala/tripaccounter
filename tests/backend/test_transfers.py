"""Functional tests for wallet transfers: CRUD, the plain/exchange rules, and spend exclusion."""


def test_create_transfer_omitted_to_side_mirrors_the_from_side(client, trip, transfer_body):
    """A plain transfer only needs one amount; the to side defaults to it."""
    response = client.post(
        f"/api/v1/trips/{trip['slug']}/transfers", json=transfer_body(from_amount="150.00")
    )

    assert response.status_code == 201
    transfer = response.json()["transfer"]
    assert transfer["to_amount"] == 150
    assert transfer["to_currency_id"] == trip["currencies"][0]["id"]
    assert transfer["to_currency_code"] == "ISK"


def test_create_transfer_exchange_inside_one_wallet_is_accepted(
    client, trip, default_wallet_of, person_id, transfer_body
):
    """Two different currencies on the same person's own wallet is a valid exchange."""
    petr = person_id("Petr")
    wallet_id = default_wallet_of(petr)["id"]

    response = client.post(
        f"/api/v1/trips/{trip['slug']}/transfers",
        json=transfer_body(
            from_wallet_id=wallet_id,
            from_amount="20",
            from_currency_id=trip["currencies"][1]["id"],
            to_wallet_id=wallet_id,
            to_amount="2800",
            to_currency_id=trip["currencies"][0]["id"],
        ),
    )

    assert response.status_code == 201
    transfer = response.json()["transfer"]
    assert transfer["from_amount"] == 20
    assert transfer["to_amount"] == 2800


def test_create_transfer_same_wallet_same_currency_is_same_wallet(
    client, trip, default_wallet_of, people, transfer_body
):
    """The same wallet on both sides in the same currency is meaningless."""
    wallet_id = default_wallet_of(people[0]["id"])["id"]

    response = client.post(
        f"/api/v1/trips/{trip['slug']}/transfers",
        json=transfer_body(from_wallet_id=wallet_id, to_wallet_id=wallet_id),
    )

    assert response.status_code == 422
    assert response.json()["error"]["fields"]["to_wallet_id"] == {
        "code": "same_wallet",
        "params": {},
    }


def test_create_transfer_cross_owner_currency_change_is_cross_owner_exchange(
    client, trip, transfer_body
):
    """A transfer between two different people can't also change currency."""
    response = client.post(
        f"/api/v1/trips/{trip['slug']}/transfers",
        json=transfer_body(to_currency_id=trip["currencies"][1]["id"], to_amount="20"),
    )

    assert response.status_code == 422
    assert response.json()["error"]["fields"]["to_currency_id"] == {
        "code": "cross_owner_exchange",
        "params": {},
    }


def test_create_transfer_missing_wallet_is_required(client, trip, transfer_body):
    """`from_wallet_id` is required on create."""
    body = transfer_body()
    del body["from_wallet_id"]

    response = client.post(f"/api/v1/trips/{trip['slug']}/transfers", json=body)

    assert response.status_code == 422
    assert response.json()["error"]["fields"]["from_wallet_id"]["code"] == "required"


def test_create_transfer_wallet_not_in_trip_is_not_in_trip(client, trip, transfer_body):
    """A wallet id from outside this trip is rejected."""
    response = client.post(
        f"/api/v1/trips/{trip['slug']}/transfers", json=transfer_body(to_wallet_id=999999)
    )

    assert response.status_code == 422
    assert response.json()["error"]["fields"]["to_wallet_id"]["code"] == "not_in_trip"


def test_update_transfer_from_amount_follows_to_plain_transfer(client, trip, transfer_body):
    """Updating from_amount on a plain transfer mirrors to_amount along with it."""
    created = client.post(
        f"/api/v1/trips/{trip['slug']}/transfers", json=transfer_body(from_amount="100")
    ).json()["transfer"]

    response = client.patch(
        f"/api/v1/trips/{trip['slug']}/transfers/{created['id']}", json={"from_amount": "250"}
    )

    assert response.status_code == 200
    updated = response.json()["transfer"]
    assert updated["from_amount"] == 250
    assert updated["to_amount"] == 250


def test_update_transfer_exchange_keeps_to_amount_when_only_from_changes(
    client, trip, default_wallet_of, people, transfer_body
):
    """An exchange's to_amount stays put when from_amount changes and to_amount is omitted."""
    wallet_id = default_wallet_of(people[0]["id"])["id"]
    created = client.post(
        f"/api/v1/trips/{trip['slug']}/transfers",
        json=transfer_body(
            from_wallet_id=wallet_id,
            from_amount="20",
            from_currency_id=trip["currencies"][1]["id"],
            to_wallet_id=wallet_id,
            to_amount="2800",
            to_currency_id=trip["currencies"][0]["id"],
        ),
    ).json()["transfer"]

    response = client.patch(
        f"/api/v1/trips/{trip['slug']}/transfers/{created['id']}", json={"from_amount": "30"}
    )

    assert response.status_code == 200
    updated = response.json()["transfer"]
    assert updated["from_amount"] == 30
    assert updated["to_amount"] == 2800


def test_update_transfer_dropping_to_currency_becomes_plain_and_mirrors(
    client, trip, default_wallet_of, person_id, transfer_body
):
    """Setting to_currency_id back to the from side, with to_amount omitted, mirrors from_amount."""
    petr = person_id("Petr")
    card = default_wallet_of(petr)["id"]
    cash = client.post(
        f"/api/v1/trips/{trip['slug']}/wallets",
        json={"person_id": petr, "name": "Cash", "tracked": True},
    ).json()["wallet"]["id"]
    eur, isk = trip["currencies"][1]["id"], trip["currencies"][0]["id"]
    created = client.post(
        f"/api/v1/trips/{trip['slug']}/transfers",
        json=transfer_body(
            from_wallet_id=card,
            from_amount="20",
            from_currency_id=eur,
            to_wallet_id=cash,
            to_amount="2800",
            to_currency_id=isk,
        ),
    ).json()["transfer"]

    response = client.patch(
        f"/api/v1/trips/{trip['slug']}/transfers/{created['id']}",
        json={"to_currency_id": eur},
    )

    assert response.status_code == 200
    updated = response.json()["transfer"]
    assert updated["to_currency_id"] == eur
    assert updated["to_amount"] == 20


def test_delete_transfer_then_get_is_404(client, trip, transfer_body):
    """A deleted transfer is gone."""
    created = client.post(f"/api/v1/trips/{trip['slug']}/transfers", json=transfer_body()).json()[
        "transfer"
    ]

    delete_response = client.delete(f"/api/v1/trips/{trip['slug']}/transfers/{created['id']}")
    get_response = client.get(f"/api/v1/trips/{trip['slug']}/transfers/{created['id']}")

    assert delete_response.status_code == 204
    assert get_response.status_code == 404
    assert get_response.json()["error"] == {"code": "not_found", "params": {"resource": "transfer"}}


def test_transfers_are_absent_from_day_totals_stats_and_total_spent(
    client, trip, transfer_body, item_body
):
    """A transfer is movement, not spending: it touches none of the spend aggregates."""
    client.post(
        f"/api/v1/trips/{trip['slug']}/items",
        json=item_body(amount="100.00", occurred_at="2026-09-14T12:00:00"),
    )
    client.post(
        f"/api/v1/trips/{trip['slug']}/transfers",
        json=transfer_body(from_amount="99999", occurred_at="2026-09-14T12:00:00"),
    )

    items_response = client.get(f"/api/v1/trips/{trip['slug']}/items").json()
    day_total = next(d for d in items_response["day_totals"] if d["date"] == "2026-09-14")
    assert day_total["totals"] == [
        {"currency_code": "ISK", "currency_id": trip["currencies"][0]["id"], "amount": 100}
    ]
    assert len(items_response["transfers"]) == 1

    stats = client.get(f"/api/v1/trips/{trip['slug']}/stats").json()["stats"]
    isk_stats = next(s for s in stats if s["currency_code"] == "ISK")
    assert isk_stats["total"] == 100

    balances = client.get(f"/api/v1/trips/{trip['slug']}/balances").json()["balances"]
    isk_balances = next(b for b in balances if b["currency_code"] == "ISK")
    assert isk_balances["total_spent"] == 100


def test_items_envelope_merges_transfers_sorted_newest_first(client, trip, transfer_body):
    """Transfers ride the items envelope, sorted like items: occurred_at desc, id desc."""
    older = client.post(
        f"/api/v1/trips/{trip['slug']}/transfers",
        json=transfer_body(occurred_at="2026-09-13T09:00:00"),
    ).json()["transfer"]
    newer = client.post(
        f"/api/v1/trips/{trip['slug']}/transfers",
        json=transfer_body(occurred_at="2026-09-14T09:00:00"),
    ).json()["transfer"]

    transfers = client.get(f"/api/v1/trips/{trip['slug']}/items").json()["transfers"]

    assert [t["id"] for t in transfers] == [newer["id"], older["id"]]
