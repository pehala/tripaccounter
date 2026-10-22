"""Functional tests for the per-trip statistics endpoint."""

import pytest


def groups_of(response):
    """Return a response's groupings keyed by their dimension chain."""
    return {tuple(group["by"]): group["rows"] for group in response.json()["groups"]}


def get_stats(client, trip_url, *chains):
    """GET the stats endpoint asking for each dimension chain, and key the groupings."""
    params = [("group_by", chain) for chain in chains]
    return groups_of(client.get(f"{trip_url}/stats", params=params))


def rows_for(rows, currency_id):
    """Return the rows belonging to one currency."""
    return [row for row in rows if row["keys"]["currency_id"] == currency_id]


def test_bare_request_answers_the_per_currency_total(
    client, trip, currency, scenario_items, trip_url
):
    """With no group_by, the one grouping is ["currency"] and it totals the trip."""
    groups = get_stats(client, trip_url)

    assert list(groups) == [("currency",)]
    assert groups[("currency",)] == [
        {
            "keys": {"currency_id": currency["id"]},
            "amount": sum(item["amount"] for item in scenario_items.values()),
            "item_count": len(scenario_items),
        }
    ]


def test_a_chain_is_answered_with_its_own_prefixes(client, trip_url, scenario_items):
    """group_by=day,person answers the whole prefix chain, shortest first."""
    groups = get_stats(client, trip_url, "day,person")

    assert list(groups) == [("currency",), ("currency", "day"), ("currency", "day", "person")]


def test_currency_leads_a_chain_that_never_asked_for_it(client, trip_url, scenario_items):
    """Every chain is grouped per currency, so no row ever spans two currencies."""
    for chain in get_stats(client, trip_url, "day,person"):
        assert chain[0] == "currency"


def test_separate_chains_are_answered_side_by_side(client, trip_url, scenario_items):
    """A repeated group_by asks for several breakdowns at once, prefixes deduped."""
    groups = get_stats(client, trip_url, "day", "country,label")

    assert list(groups) == [
        ("currency",),
        ("currency", "day"),
        ("currency", "country"),
        ("currency", "country", "label"),
    ]


def test_day_rows_sum_to_the_currency_total(client, trip, currency, scenario_items, trip_url):
    """A one-dimension chain partitions its parent: the days sum to the trip total."""
    groups = get_stats(client, trip_url, "day")

    total = rows_for(groups[("currency",)], currency["id"])[0]["amount"]
    assert sum(row["amount"] for row in groups[("currency", "day")]) == total


def test_nested_rows_sum_to_their_parent_row(client, trip_url, currency, scenario_items):
    """Each day's people sum to that day's own row — the subtotal a nested view renders."""
    groups = get_stats(client, trip_url, "day,person")

    per_day = {row["keys"]["date"]: row["amount"] for row in groups[("currency", "day")]}
    for date, day_total in per_day.items():
        people = [
            row for row in groups[("currency", "day", "person")] if row["keys"]["date"] == date
        ]
        assert sum(row["amount"] for row in people) == day_total


def test_day_rows_are_ordered_chronologically(client, trip_url, scenario_items):
    """Day groups on occurred_at from the request, ascending, not on the clock."""
    groups = get_stats(client, trip_url, "day")

    assert [row["keys"]["date"] for row in groups[("currency", "day")]] == [
        "2026-07-01",
        "2026-07-02",
    ]


def test_person_is_owed_not_paid(client, people, currency, item_body, trip_url, create):  # noqa: PLR0913, PLR0917 (the fixtures are the setup)
    """A person dimension sums the share view: what each owes, not what they paid."""
    create("items", item_body(amount="100.00", payer_id=people[0]["id"]))

    groups = get_stats(client, trip_url, "person")

    assert {row["keys"]["person_id"]: row["amount"] for row in groups[("currency", "person")]} == {
        person["id"]: 25 for person in people
    }


def test_label_rows_overlap_and_unlabelled_is_null(client, trip_url, currency, scenario_items):
    """An item with two labels counts in both; unlabelled items land under null."""
    groups = get_stats(client, trip_url, "label")

    rows = groups[("currency", "label")]
    by_label = {row["keys"]["label"]: row["amount"] for row in rows}
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
    total = rows_for(groups[("currency",)], currency["id"])[0]["amount"]
    assert sum(row["amount"] for row in rows) > total


def test_payer_is_paid_not_owed(client, trip_url, person_id, scenario_items):
    """A payer dimension sums typed amounts by who paid them out."""
    groups = get_stats(client, trip_url, "payer")

    by_payer = {row["keys"]["payer_id"]: row["amount"] for row in groups[("currency", "payer")]}
    assert by_payer[person_id("Eva")] == scenario_items["balance_eva_pays"]["amount"]
    assert by_payer[person_id("Bob")] == scenario_items["balance_bob_pays"]["amount"]


def test_wallet_groups_on_the_wallet_that_paid(
    client, trip_url, person_id, default_wallet_of, scenario_items
):
    """A wallet dimension attributes spend to the pot it was paid from."""
    groups = get_stats(client, trip_url, "wallet")

    by_wallet = {row["keys"]["wallet_id"]: row["amount"] for row in groups[("currency", "wallet")]}
    eva_wallet = default_wallet_of(person_id("Eva"))["id"]
    assert by_wallet[eva_wallet] == scenario_items["balance_eva_pays"]["amount"]


def test_city_groups_on_the_typed_string(client, item_body, trip_url, create):
    """A city dimension groups on the text as typed; an item with no city lands under null."""
    for city in ("Vik", "Vik", None):
        create("items", item_body(amount="10.00", city=city))

    groups = get_stats(client, trip_url, "city")

    assert {row["keys"]["city"]: row["amount"] for row in groups[("currency", "city")]} == {
        "Vik": 20,
        None: 10,
    }


def test_stay_groups_on_the_stay_an_item_belongs_to(client, item_body, stay_body, trip_url, create):
    """A stay dimension sums each stay's items; an item in no stay lands under null."""
    stay = create("stays", stay_body())
    for stay_id in (stay["id"], stay["id"], None):
        create("items", item_body(amount="10.00", stay_id=stay_id))

    groups = get_stats(client, trip_url, "stay")

    assert {row["keys"]["stay_id"]: row["amount"] for row in groups[("currency", "stay")]} == {
        stay["id"]: 20,
        None: 10,
    }


def test_a_currency_with_no_spend_has_no_rows(client, trip, currencies, scenario_items, trip_url):
    """The trip's second currency was never spent, so it appears in no grouping."""
    groups = get_stats(client, trip_url, "day")

    unspent = currencies[1]["id"]
    for rows in groups.values():
        assert rows_for(rows, unspent) == []


@pytest.mark.parametrize(
    ("chain", "dimension"),
    [
        pytest.param("nope", "nope", id="unknown-name"),
        pytest.param("day,day", "day", id="repeated-within-a-chain"),
        pytest.param("currency", "currency", id="currency-is-not-selectable"),
        pytest.param("day,currency", "currency", id="currency-is-not-selectable-anywhere"),
    ],
)
def test_bad_group_by_is_rejected(client, trip_url, chain, dimension):
    """A name outside the registry, one repeating within a chain, or currency, fails on group_by."""
    response = client.get(f"{trip_url}/stats", params={"group_by": chain})

    assert response.status_code == 422
    assert response.json() == {
        "error": {
            "code": "validation_error",
            "params": {},
            "fields": {
                "group_by": {"code": "unknown_dimension", "params": {"dimension": dimension}}
            },
        }
    }


def test_day_count_spans_trip_start_end(client, trip_url):
    """day_count spans the trip's start_date/end_date, inclusive."""
    stats = client.get(f"{trip_url}/stats").json()
    assert stats["day_count"] == 10


def test_day_count_is_null_without_trip_dates(client):
    """A trip with no start or end date reports day_count null, not zero."""
    slug = client.post(
        "/api/v1/trips",
        json={
            "name": "Undated trip",
            "people": [{"name": "Petr"}],
            "currencies": [{"code": "ISK"}],
            "countries": [{"name": "Iceland"}],
        },
    ).json()["trip"]["slug"]

    stats = client.get(f"/api/v1/trips/{slug}/stats").json()

    assert stats["day_count"] is None


def test_label_rows_have_no_null_key_when_every_item_is_labelled(
    client, item_body, trip_url, create
):
    """The unlabelled bucket is absent, not zero, when nothing is unlabelled."""
    item = create("items", item_body(labels=["food"]))

    groups = get_stats(client, trip_url, "label")

    assert groups[("currency", "label")] == [
        {
            "keys": {"currency_id": item["currency_id"], "label": "food"},
            "amount": item["amount"],
            "item_count": 1,
        }
    ]
