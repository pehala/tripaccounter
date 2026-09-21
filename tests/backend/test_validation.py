"""Functional tests for the API.md §4 validation table, row by row, as real requests."""

import pytest


@pytest.mark.parametrize(
    ("overrides", "expected"),
    [
        pytest.param(
            {"name": "   "}, {"name": {"code": "required", "params": {}}}, id="blank-name"
        ),
        pytest.param(
            {"name": "x" * 201},
            {"name": {"code": "too_long", "params": {"max": 200}}},
            id="name-over-200",
        ),
        pytest.param(
            {"amount": None},
            {"amount": {"code": "invalid_amount", "params": {}}},
            id="no-amount-on-create",
        ),
        pytest.param(
            {"amount": "-5.00"},
            {"amount": {"code": "invalid_amount", "params": {}}},
            id="negative-amount",
        ),
        pytest.param(
            {"amount": "0.00"},
            {"amount": {"code": "invalid_amount", "params": {}}},
            id="zero-amount",
        ),
        pytest.param(
            {"amount": "1234567890123"},
            {"amount": {"code": "invalid_amount", "params": {}}},
            id="13-integer-digits",
        ),
        pytest.param(
            {"lat": "91.000000", "lon": "0.000000"},
            {"lat": {"code": "invalid_coordinates", "params": {}}},
            id="latitude-over-90",
        ),
        pytest.param(
            {"lat": "0.000000", "lon": "181.000000"},
            {"lon": {"code": "invalid_coordinates", "params": {}}},
            id="longitude-over-180",
        ),
        pytest.param(
            {"lat": "64.149300"},
            {"body": {"code": "invalid_coordinates", "params": {}}},
            id="latitude-without-longitude",
        ),
        pytest.param(
            {"map_url": "not-a-url"},
            {"map_url": {"code": "invalid_url", "params": {}}},
            id="unparseable-url",
        ),
        pytest.param(
            {"occurred_at": "yesterday"},
            {"occurred_at": {"code": "invalid_datetime", "params": {}}},
            id="unparseable-datetime",
        ),
        pytest.param(
            {"labels": ["x" * 41]},
            {"labels": {"code": "too_long", "params": {"max": 40}}},
            id="label-over-40",
        ),
        pytest.param(
            {"lat": "north", "lon": "west"},
            {
                "lat": {"code": "invalid_coordinates", "params": {}},
                "lon": {"code": "invalid_coordinates", "params": {}},
            },
            id="coordinate-not-a-number",
        ),
        pytest.param(
            {"currency_id": 999999},
            {"currency_id": {"code": "not_in_trip", "params": {}}},
            id="currency-from-another-trip",
        ),
        pytest.param(
            {"labels": [5]},
            {"labels": {"code": "label_whitespace", "params": {"value": 5}}},
            id="label-not-a-string",
        ),
    ],
)
def test_item_write_validation(client, trip, item_body, overrides, expected):
    """Each item write rule fails with its own code and params, on its own field."""
    response = client.post(f"/api/v1/trips/{trip['slug']}/items", json=item_body(**overrides))

    assert response.status_code == 422
    assert response.json() == {
        "error": {"code": "validation_error", "params": {}, "fields": expected}
    }


def test_item_payer_who_is_inactive_is_rejected(client, trip, people, item_body):
    """An item can't name a deactivated person as its payer."""
    payer = people[0]["id"]
    client.patch(f"/api/v1/trips/{trip['slug']}/people/{payer}", json={"active": False})

    response = client.post(f"/api/v1/trips/{trip['slug']}/items", json=item_body(payer_id=payer))

    assert response.status_code == 422
    assert response.json()["error"]["fields"]["payer_id"] == {"code": "inactive", "params": {}}


def test_person_default_weight_must_be_a_canonical_decimal_string(client, trip):
    """A weight sent as a JSON number, not the canonical string, is not_positive."""
    response = client.post(
        f"/api/v1/trips/{trip['slug']}/people", json={"name": "Zed", "default_weight": 1}
    )

    assert response.status_code == 422
    assert response.json()["error"]["fields"]["default_weight"] == {
        "code": "not_positive",
        "params": {},
    }


def test_omitted_required_field_is_required(client, trip, people):
    """A write body missing a field the schema declares fails as `required` on that field."""
    response = client.post(
        f"/api/v1/trips/{trip['slug']}/wallets", json={"person_id": people[0]["id"]}
    )

    assert response.status_code == 422
    assert response.json() == {
        "error": {
            "code": "validation_error",
            "params": {},
            "fields": {"name": {"code": "required", "params": {}}},
        }
    }


def test_wallet_person_from_another_trip_is_not_in_trip(client, trip):
    """A wallet can only be created for someone on this trip."""
    response = client.post(
        f"/api/v1/trips/{trip['slug']}/wallets", json={"person_id": 999999, "name": "Cash"}
    )

    assert response.status_code == 422
    assert response.json()["error"]["fields"]["person_id"] == {"code": "not_in_trip", "params": {}}


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        pytest.param("   ", {"code": "required", "params": {}}, id="blank"),
        pytest.param("x" * 61, {"code": "too_long", "params": {"max": 60}}, id="over-60"),
    ],
)
def test_wallet_name_length_rules(client, trip, people, name, expected):
    """A wallet name is required and capped at 60 characters."""
    response = client.post(
        f"/api/v1/trips/{trip['slug']}/wallets", json={"person_id": people[0]["id"], "name": name}
    )

    assert response.status_code == 422
    assert response.json()["error"]["fields"]["name"] == expected


def test_patch_item_blank_name_is_rejected(client, trip, item_body):
    """An update is validated like a create: a name that is only whitespace is required."""
    created = client.post(f"/api/v1/trips/{trip['slug']}/items", json=item_body()).json()["item"]

    response = client.patch(
        f"/api/v1/trips/{trip['slug']}/items/{created['id']}", json={"name": "   "}
    )

    assert response.status_code == 422
    assert response.json()["error"]["fields"]["name"] == {"code": "required", "params": {}}


def test_patch_transfer_wallet_not_in_trip_is_rejected(client, trip, transfer_body):
    """An update's references are checked against this trip, as a create's are."""
    created = client.post(f"/api/v1/trips/{trip['slug']}/transfers", json=transfer_body()).json()[
        "transfer"
    ]

    response = client.patch(
        f"/api/v1/trips/{trip['slug']}/transfers/{created['id']}", json={"to_wallet_id": 999999}
    )

    assert response.status_code == 422
    assert response.json()["error"]["fields"]["to_wallet_id"] == {
        "code": "not_in_trip",
        "params": {},
    }


def test_person_default_weight_past_four_decimals_is_too_precise(client, trip):
    """A default weight carrying a fifth decimal names the precision limit it broke."""
    response = client.post(
        f"/api/v1/trips/{trip['slug']}/people", json={"name": "Zed", "default_weight": "0.50001"}
    )

    assert response.status_code == 422
    assert response.json()["error"]["fields"]["default_weight"] == {
        "code": "too_precise",
        "params": {"max": 4},
    }
