"""Functional tests for the per-trip balances endpoint."""


def test_balances_net_sums_to_near_zero(client, trip, item_body):
    """Every currency's net column sums within floor-loss of zero."""
    client.post(f"/api/v1/trips/{trip['slug']}/items", json=item_body(amount="18400"))

    balances = client.get(f"/api/v1/trips/{trip['slug']}/balances").json()["balances"]
    block = next(b for b in balances if b["currency_code"] == "ISK")
    assert abs(sum(person["net"] for person in block["people"])) < 0.00001


def test_balances_net_equals_paid_minus_owed(client, trip, item_body):
    """Net = paid - owed for every person."""
    client.post(f"/api/v1/trips/{trip['slug']}/items", json=item_body(amount="100.00"))

    balances = client.get(f"/api/v1/trips/{trip['slug']}/balances").json()["balances"]
    block = next(b for b in balances if b["currency_code"] == "ISK")
    for person in block["people"]:
        assert person["net"] == person["paid"] - person["owed"]


def test_currency_with_no_items_is_absent(client, trip):
    """A currency nobody used does not appear in balances."""
    balances = client.get(f"/api/v1/trips/{trip['slug']}/balances").json()["balances"]
    assert balances == []


def test_already_even_trip_has_no_suggestions(client, trip, people, item_body):
    """A trip settled by construction (nobody owes anybody) yields no suggestions."""
    client.post(
        f"/api/v1/trips/{trip['slug']}/items",
        json=item_body(
            amount="100.00", payer_id=people[0]["id"], shares=[{"person_id": people[0]["id"]}]
        ),
    )
    balances = client.get(f"/api/v1/trips/{trip['slug']}/balances").json()["balances"]
    block = next(b for b in balances if b["currency_code"] == "ISK")
    assert block["suggestions"] == []


def test_same_owner_transfer_changes_no_net(client, trip, people, default_wallet_of, item_body):
    """A transfer between one person's own wallets moves nothing between people."""
    petr = people[0]["id"]
    client.post(f"/api/v1/trips/{trip['slug']}/items", json=item_body(amount="100.00"))
    before = client.get(f"/api/v1/trips/{trip['slug']}/balances").json()["balances"]

    cash = client.post(
        f"/api/v1/trips/{trip['slug']}/wallets",
        json={"person_id": petr, "name": "Cash", "tracked": True},
    ).json()["wallet"]
    client.post(
        f"/api/v1/trips/{trip['slug']}/transfers",
        json={
            "from_wallet_id": default_wallet_of(petr)["id"],
            "from_amount": "20000",
            "from_currency_id": trip["currencies"][0]["id"],
            "to_wallet_id": cash["id"],
        },
    )
    after = client.get(f"/api/v1/trips/{trip['slug']}/balances").json()["balances"]

    assert after == before


def test_same_owner_exchange_changes_no_net_in_either_currency(
    client, trip, people, default_wallet_of, item_body
):
    """An exchange inside one wallet moves nothing between people, in either currency."""
    petr = people[0]["id"]
    client.post(f"/api/v1/trips/{trip['slug']}/items", json=item_body(amount="100.00"))
    before = client.get(f"/api/v1/trips/{trip['slug']}/balances").json()["balances"]

    cash = client.post(
        f"/api/v1/trips/{trip['slug']}/wallets",
        json={"person_id": petr, "name": "Cash", "tracked": True},
    ).json()["wallet"]
    client.post(
        f"/api/v1/trips/{trip['slug']}/transfers",
        json={
            "from_wallet_id": cash["id"],
            "from_amount": "20",
            "from_currency_id": trip["currencies"][1]["id"],
            "to_wallet_id": cash["id"],
            "to_amount": "2800",
            "to_currency_id": trip["currencies"][0]["id"],
        },
    )
    after = client.get(f"/api/v1/trips/{trip['slug']}/balances").json()["balances"]

    assert after == before


def test_cross_owner_transfer_shifts_sent_and_received_and_net(
    client, trip, people, default_wallet_of, item_body
):
    """A handover between two people's wallets enters `sent`/`received` and shifts `net`."""
    ann, bob = people[1]["id"], people[2]["id"]
    client.post(f"/api/v1/trips/{trip['slug']}/items", json=item_body(amount="100.00"))

    client.post(
        f"/api/v1/trips/{trip['slug']}/transfers",
        json={
            "from_wallet_id": default_wallet_of(ann)["id"],
            "from_amount": "5000",
            "from_currency_id": trip["currencies"][0]["id"],
            "to_wallet_id": default_wallet_of(bob)["id"],
        },
    )

    balances = client.get(f"/api/v1/trips/{trip['slug']}/balances").json()["balances"]
    block = next(b for b in balances if b["currency_code"] == "ISK")
    by_person = {p["person_id"]: p for p in block["people"]}

    assert by_person[ann]["sent"] == 5000
    assert by_person[ann]["received"] == 0
    assert by_person[bob]["received"] == 5000
    assert by_person[bob]["sent"] == 0
    for person in block["people"]:
        expected_net = person["paid"] - person["owed"] + person["sent"] - person["received"]
        assert person["net"] == expected_net
    assert abs(sum(p["net"] for p in block["people"])) < 0.00001


def test_transfer_only_currency_appears_in_balances(client, trip, people, default_wallet_of):
    """A currency touched only by a cross-owner transfer, never an item, still shows a block."""
    ann, bob = people[1]["id"], people[2]["id"]
    eur = trip["currencies"][1]["id"]

    client.post(
        f"/api/v1/trips/{trip['slug']}/transfers",
        json={
            "from_wallet_id": default_wallet_of(ann)["id"],
            "from_amount": "20",
            "from_currency_id": eur,
            "to_wallet_id": default_wallet_of(bob)["id"],
        },
    )

    balances = client.get(f"/api/v1/trips/{trip['slug']}/balances").json()["balances"]
    block = next(b for b in balances if b["currency_code"] == "EUR")
    assert block["total_spent"] == 0
    by_person = {p["person_id"]: p for p in block["people"]}
    assert by_person[ann]["sent"] == 20
    assert by_person[bob]["received"] == 20


def test_suggestions_apply_to_zero_every_net(client, trip, people, scenario_items):
    """Replaying every suggestion against the nets zeroes everyone out."""
    balances = client.get(f"/api/v1/trips/{trip['slug']}/balances").json()["balances"]
    block = next(b for b in balances if b["currency_code"] == "ISK")

    nets = {p["person_id"]: p["paid"] - p["owed"] for p in block["people"]}
    for suggestion in block["suggestions"]:
        nets[suggestion["from_person_id"]] += suggestion["amount"]
        nets[suggestion["to_person_id"]] -= suggestion["amount"]

    for value in nets.values():
        assert abs(value) < 0.01
    assert len(block["suggestions"]) <= len(people) - 1
