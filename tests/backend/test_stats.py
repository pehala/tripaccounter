"""Functional tests for the per-trip statistics endpoint."""


def test_group_totals_equal_trip_total(client, trip, scenario_items):
    """by_country, by_person, by_day totals each equal the trip total per currency."""
    stats = client.get(f"/api/v1/trips/{trip['slug']}/stats").json()["stats"]
    block = next(b for b in stats if b["currency_code"] == "ISK")

    assert block["total"] == sum(row["amount"] for row in block["by_country"])
    assert block["total"] == sum(row["amount"] for row in block["by_person"])
    assert block["total"] == sum(row["amount"] for row in block["by_day"])


def test_by_label_overlaps_and_unlabelled_is_null(client, trip, scenario_items):
    """An item with two labels counts in both; unlabelled items land under null."""
    stats = client.get(f"/api/v1/trips/{trip['slug']}/stats").json()["stats"]
    block = next(b for b in stats if b["currency_code"] == "ISK")

    by_label = {row["label"]: row["amount"] for row in block["by_label"]}
    labelled = scenario_items["day1_labelled"]
    unlabelled = [
        scenario_items["day1_evening"],
        scenario_items["day2_unlabelled"],
        scenario_items["balance_eva_pays"],
        scenario_items["balance_bob_pays"],
    ]

    assert by_label["dining"] == labelled["amount"]
    assert by_label["fun"] == labelled["amount"]
    assert by_label[None] == sum(item["amount"] for item in unlabelled)
    assert sum(row["amount"] for row in block["by_label"]) > block["total"]


def test_by_person_is_owed_not_paid(client, trip, people, item_body):
    """by_person[].amount is what they owe, not what they paid."""
    client.post(
        f"/api/v1/trips/{trip['slug']}/items",
        json=item_body(amount="100.00", payer_id=people[0]["id"]),
    )

    stats = client.get(f"/api/v1/trips/{trip['slug']}/stats").json()["stats"]
    block = next(b for b in stats if b["currency_code"] == "ISK")
    by_person = {row["person_id"]: row["amount"] for row in block["by_person"]}
    assert all(amount == 25 for amount in by_person.values())


def test_by_day_groups_on_occurred_at(client, trip, scenario_items):
    """Grouping uses occurred_at from the request, not the clock."""
    stats = client.get(f"/api/v1/trips/{trip['slug']}/stats").json()["stats"]
    block = next(b for b in stats if b["currency_code"] == "ISK")
    assert [row["date"] for row in block["by_day"]] == ["2026-07-01", "2026-07-02"]


def test_day_count_spans_trip_start_end(client, trip):
    """day_count spans the trip's start_date/end_date, inclusive."""
    stats = client.get(f"/api/v1/trips/{trip['slug']}/stats").json()
    assert stats["day_count"] == 10
