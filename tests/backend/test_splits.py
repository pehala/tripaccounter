"""Functional tests for item split modes and share resolution."""

import pytest


def test_equal_split_pads_the_roster(client, trip, item_body):
    """Equal split lists all four people; owed distributes evenly."""
    response = client.post(f"/api/v1/trips/{trip['slug']}/items", json=item_body(amount="18400"))
    shares = response.json()["item"]["split"]["shares"]
    assert [s["owed"] for s in shares] == [4600, 4600, 4600, 4600]
    assert [s["weight"] for s in shares] == ["1", "1", "1", "1"]


def test_equal_split_excludes_one_person_leaves_null(client, trip, people, item_body):
    """A person left out of `shares` gets weight null, owed null - not zero."""
    response = client.post(
        f"/api/v1/trips/{trip['slug']}/items",
        json=item_body(
            amount="90.00",
            split_mode="equal",
            shares=[
                {"person_id": people[0]["id"]},
                {"person_id": people[1]["id"]},
                {"person_id": people[3]["id"]},
            ],
        ),
    )
    shares = response.json()["item"]["split"]["shares"]
    excluded = next(s for s in shares if s["person_id"] == people[2]["id"])
    assert excluded["weight"] is None
    assert excluded["owed"] is None


def test_shares_split_by_weight(client, trip, people, item_body):
    """Weighted split: 1, 1, 1, 0.5 divides 96000 into thirds and a half-third."""
    response = client.post(
        f"/api/v1/trips/{trip['slug']}/items",
        json=item_body(
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
    shares = response.json()["item"]["split"]["shares"]
    owed = {s["person_id"]: s["owed"] for s in shares}
    assert owed[people[0]["id"]] == 27428.571428
    assert owed[people[1]["id"]] == 27428.571428
    assert owed[people[2]["id"]] == 27428.571428
    assert owed[people[3]["id"]] == 13714.285714


def test_exact_split_sums_to_amount(client, trip, people, item_body):
    """Exact split rows sum to `amount` exactly and are echoed as typed."""
    response = client.post(
        f"/api/v1/trips/{trip['slug']}/items",
        json=item_body(
            amount="184.00",
            split_mode="exact",
            shares=[
                {"person_id": people[0]["id"], "amount": "92.00"},
                {"person_id": people[1]["id"], "amount": "92.00"},
            ],
        ),
    )
    assert response.status_code == 201, response.text
    shares = response.json()["item"]["split"]["shares"]
    owed = {s["person_id"]: s["owed"] for s in shares if s["owed"] is not None}
    assert owed == {people[0]["id"]: 92, people[1]["id"]: 92}


def test_exact_split_off_by_one_is_rejected(client, trip, people, item_body):
    """An exact split that misses the total by a cent fails with the diff."""
    response = client.post(
        f"/api/v1/trips/{trip['slug']}/items",
        json=item_body(
            amount="184.00",
            split_mode="exact",
            shares=[
                {"person_id": people[0]["id"], "amount": "92.00"},
                {"person_id": people[1]["id"], "amount": "91.99"},
            ],
        ),
    )
    assert response.status_code == 422
    assert response.json() == {
        "error": {
            "code": "validation_error",
            "params": {},
            "fields": {
                "shares": {"code": "sum_mismatch", "params": {"diff": 1, "currency_code": "ISK"}}
            },
        }
    }


def test_shares_omitted_means_equal_over_active_people(client, trip, item_body):
    """Omitting `shares` entirely means equal over every active person."""
    body = item_body(amount="100.00")
    del body["shares"]
    response = client.post(f"/api/v1/trips/{trip['slug']}/items", json=body)
    shares = response.json()["item"]["split"]["shares"]
    assert all(s["owed"] is not None for s in shares)
    assert len(shares) == 4


def test_shares_duplicate_person_rejected(client, trip, people, item_body):
    """The same person_id twice in `shares` is a duplicate_person error."""
    pid = people[0]["id"]
    response = client.post(
        f"/api/v1/trips/{trip['slug']}/items",
        json=item_body(split_mode="equal", shares=[{"person_id": pid}, {"person_id": pid}]),
    )
    assert response.status_code == 422
    assert response.json() == {
        "error": {
            "code": "validation_error",
            "params": {},
            "fields": {"shares": {"code": "duplicate_person", "params": {}}},
        }
    }


@pytest.mark.parametrize(
    "weight",
    [
        pytest.param("0", id="zero"),
        pytest.param(1, id="json-number-not-a-string"),
        pytest.param("one", id="not-a-number"),
    ],
)
def test_shares_weight_not_positive_rejected(client, trip, people, item_body, weight):
    """A weight that is not a canonical decimal string greater than zero is not_positive."""
    pid = people[0]["id"]
    response = client.post(
        f"/api/v1/trips/{trip['slug']}/items",
        json=item_body(split_mode="shares", shares=[{"person_id": pid, "weight": weight}]),
    )
    assert response.status_code == 422
    assert response.json() == {
        "error": {
            "code": "validation_error",
            "params": {},
            "fields": {"shares": {"code": "not_positive", "params": {}}},
        }
    }


def test_preview_split_matches_saved_item(client, trip, item_body):
    """preview-split returns byte-identical split to the item created from the same body."""
    body = item_body(amount="18400")
    created = client.post(f"/api/v1/trips/{trip['slug']}/items", json=body).json()["item"]

    preview = client.post(f"/api/v1/trips/{trip['slug']}/items/preview-split", json=body).json()

    assert preview["split"] == created["split"]
    assert preview["total"] == created["amount"]


@pytest.mark.parametrize(
    "shares",
    [
        pytest.param([], id="no-rows"),
        pytest.param([{"weight": "1"}], id="row-without-a-person"),
    ],
)
def test_shares_without_a_usable_row_is_empty(client, trip, item_body, shares):
    """A `shares` array with no rows, or a row naming nobody, is `empty`."""
    response = client.post(f"/api/v1/trips/{trip['slug']}/items", json=item_body(shares=shares))

    assert response.status_code == 422
    assert response.json() == {
        "error": {
            "code": "validation_error",
            "params": {},
            "fields": {"shares": {"code": "empty", "params": {}}},
        }
    }


def test_shares_person_from_another_trip_is_not_in_trip(client, trip, item_body):
    """A share row naming someone on a different trip is rejected, not silently dropped."""
    other = client.post(
        "/api/v1/trips",
        json={
            "name": "Other trip",
            "people": [{"name": "X"}],
            "currencies": [{"code": "USD"}],
            "countries": [{"name": "Nowhere"}],
        },
    ).json()["trip"]

    response = client.post(
        f"/api/v1/trips/{trip['slug']}/items",
        json=item_body(shares=[{"person_id": other["people"][0]["id"]}]),
    )

    assert response.status_code == 422
    assert response.json()["error"]["fields"]["shares"] == {"code": "not_in_trip", "params": {}}


def test_preview_split_currency_from_another_trip_is_not_in_trip(client, trip, item_body):
    """preview-split checks the currency belongs to this trip before splitting anything."""
    response = client.post(
        f"/api/v1/trips/{trip['slug']}/items/preview-split", json=item_body(currency_id=999999)
    )

    assert response.status_code == 422
    assert response.json() == {
        "error": {
            "code": "validation_error",
            "params": {},
            "fields": {"currency_id": {"code": "not_in_trip", "params": {}}},
        }
    }
