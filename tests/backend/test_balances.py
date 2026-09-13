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
