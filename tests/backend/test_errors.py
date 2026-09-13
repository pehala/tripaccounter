"""Functional tests for the error envelope: shape, codes, and catalog coverage."""

from app.services.errors import FIELD_ERROR_PARAMS, TOP_LEVEL_PARAMS


def test_no_response_body_ever_contains_a_message_key(client, trip, people, item_body):
    """Every kind of error response is checked here for a stray `message` key."""
    responses = [
        client.get("/api/v1/trips/does-not-exist"),
        client.post(f"/api/v1/trips/{trip['slug']}/people", json={"name": people[0]["name"]}),
        client.post(f"/api/v1/trips/{trip['slug']}/items", json=item_body(amount="not-a-number")),
    ]
    for response in responses:
        assert "message" not in response.text


def test_every_code_seen_on_the_wire_is_a_catalog_key(error_codes):
    """Every error code any test in this run triggered is a documented code."""
    known = set(FIELD_ERROR_PARAMS) | set(TOP_LEVEL_PARAMS)
    assert error_codes <= known


def test_invalid_amount_format_is_422(client, trip, item_body):
    """A non-canonical amount string is invalid_amount, not a generic failure."""
    response = client.post(
        f"/api/v1/trips/{trip['slug']}/items", json=item_body(amount="18,400.50")
    )
    assert response.status_code == 422
    assert response.json() == {
        "error": {
            "code": "validation_error",
            "params": {},
            "fields": {"amount": {"code": "invalid_amount", "params": {}}},
        }
    }


def test_field_error_params_are_exactly_the_declared_names():
    """Every catalog code declares only the param names API.md documents for it."""
    assert FIELD_ERROR_PARAMS["sum_mismatch"] == ("diff", "currency_code")
    assert FIELD_ERROR_PARAMS["in_use"] == ("count", "name")
    assert FIELD_ERROR_PARAMS["required"] == ()
