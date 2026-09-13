"""Tests for api.js's error envelope and how the app renders it.

Page.evaluate on api.js against stubbed
responses: 404, 409 and 422 each map to `{status, code, params, fields}`; a 500
with an HTML body still yields `{status: 500, code: 'internal_error', params:
{}}` instead of throwing; a `fields` entry reaches the matching input rendered
through `t()`, a field-less error reaches the flash; an unknown code renders as
code + params, never blank.
"""

import pytest
from playwright.sync_api import expect

from tests.frontend.conftest import FIXTURES, load_fixture


@pytest.fixture
def api_get_error(page, mockserver, stub):
    """Return `api_get_error(status, body, content_type="application/json")`.

    Stubs GET /trips/x with that response, calls `api.get('/trips/x')` in a document
    served by the mock and returns the error it throws (None if it resolves).
    """
    page.goto(f"{mockserver}/")

    def call(status, body, content_type="application/json"):
        stub("**/api/v1/trips/x", lambda request: (status, body, content_type))
        return page.evaluate(
            """async () => {
                const { api } = await import('/js/api.js');
                try {
                    await api.get('/trips/x');
                    return null;
                } catch (err) {
                    return err;
                }
            }"""
        )

    return call


@pytest.fixture
def save_snack_with_error(new_item_modal, stub):
    """Return `save_snack_with_error(status, body) -> page`.

    Answers POST /items with that error (GETs pass through to the mock), then fills
    name and amount in the open new-expense modal and clicks Save.
    """

    def submit(status, body):
        stub(
            "**/api/v1/trips/*/items",
            lambda request: (status, body) if request.method == "POST" else None,
        )
        new_item_modal.locator('input[name="name"]').fill("Snacks")
        new_item_modal.locator('input[name="amount"]').fill("500")
        new_item_modal.get_by_role("button", name="Save", exact=True).click()
        return new_item_modal.page

    return submit


@pytest.mark.parametrize(
    ("body", "status", "content_type", "expected"),
    [
        pytest.param(
            load_fixture("errors/404.json"),
            404,
            "application/json",
            {"status": 404, "code": "not_found", "params": {"resource": "trip"}, "fields": {}},
            id="not-found",
        ),
        pytest.param(
            load_fixture("errors/409_in_use.json"),
            409,
            "application/json",
            {
                "status": 409,
                "code": "conflict",
                "params": {},
                "fields": {"id": {"code": "in_use", "params": {"count": 4, "name": "Iceland"}}},
            },
            id="in-use",
        ),
        pytest.param(
            load_fixture("errors/422_shares.json"),
            422,
            "application/json",
            {
                "status": 422,
                "code": "validation_error",
                "params": {},
                "fields": {
                    "shares": {
                        "code": "sum_mismatch",
                        "params": {"diff": 3, "currency_code": "ISK"},
                    }
                },
            },
            id="sum-mismatch",
        ),
        pytest.param(
            (FIXTURES / "errors/500_html.html").read_text(),
            500,
            "text/html",
            {"status": 500, "code": "internal_error", "params": {}, "fields": {}},
            id="html-500",
        ),
    ],
)
def test_error_response_maps_to_the_envelope_shape(
    api_get_error, body, status, content_type, expected
):
    """An error response becomes {status, code, params, fields}; a non-JSON body falls back."""
    err = api_get_error(status, body, content_type)

    assert err == expected


def test_field_error_reaches_the_matching_input(new_item_modal, save_snack_with_error):
    """A fields.amount error renders under the amount input via the catalog; the modal stays."""
    error_body = {
        "error": {
            "code": "validation_error",
            "params": {},
            "fields": {"amount": {"code": "invalid_amount", "params": {}}},
        }
    }

    save_snack_with_error(422, error_body)

    amount_group = new_item_modal.locator('input[name="amount"]').locator("..")
    expect(amount_group.locator(".invalid-feedback")).to_have_text("Enter an amount.")
    expect(new_item_modal).to_have_count(1)


@pytest.mark.parametrize(
    ("status", "error_body", "text"),
    [
        pytest.param(
            500,
            {"error": {"code": "internal_error", "params": {"ref": "abc123"}}},
            "Something went wrong. Reference: abc123.",
            id="known-code",
        ),
        pytest.param(
            400,
            {"error": {"code": "brand_new_rule", "params": {"limit": 5}}},
            "brand_new_rule · limit 5",
            id="unknown-code",
        ),
    ],
)
def test_field_less_error_reaches_the_flash(save_snack_with_error, status, error_body, text):
    """An error with no fields shows in the flash: the catalog sentence, or code + params."""
    page = save_snack_with_error(status, error_body)

    expect(page.locator(".alert-danger")).to_have_text(text)
    expect(page.locator(".invalid-feedback")).to_have_count(0)
