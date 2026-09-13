"""Tests for api.js's error envelope and how the app renders it.

Page.evaluate on api.js against stubbed
responses: 404, 409 and 422 each map to `{status, code, params, fields}`; a 500
with an HTML body still yields `{status: 500, code: 'internal_error', params:
{}}` instead of throwing; a `fields` entry reaches the matching input rendered
through `t()`, a field-less error reaches the flash; an unknown code renders as
code + params, never blank.
"""

import json
from pathlib import Path

from playwright.sync_api import expect

ERRORS = Path(__file__).parent / "fixtures" / "errors"


def api_get_error(page, stub, status, body):
    """Stub GET /trips/x, call api.get through it, and return the caught error."""
    stub("**/api/v1/trips/x", lambda request: (status, body))
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


def test_404_maps_to_the_envelope_shape(page, mockserver, stub):
    """A 404 response becomes {status, code, params, fields}."""
    page.goto(f"{mockserver}/")
    body = json.loads((ERRORS / "404.json").read_text())
    err = api_get_error(page, stub, 404, body)
    assert err == {"status": 404, "code": "not_found", "params": {"resource": "trip"}, "fields": {}}


def test_409_maps_to_the_envelope_shape(page, mockserver, stub):
    """A 409 response's fields entry survives intact."""
    page.goto(f"{mockserver}/")
    body = json.loads((ERRORS / "409_in_use.json").read_text())
    err = api_get_error(page, stub, 409, body)
    assert err["status"] == 409
    assert err["code"] == "conflict"
    assert err["fields"] == {"id": {"code": "in_use", "params": {"count": 4, "name": "Iceland"}}}


def test_422_maps_to_the_envelope_shape(page, mockserver, stub):
    """A 422 validation error's fields entry survives intact."""
    page.goto(f"{mockserver}/")
    body = json.loads((ERRORS / "422_shares.json").read_text())
    err = api_get_error(page, stub, 422, body)
    assert err["status"] == 422
    assert err["code"] == "validation_error"
    assert err["fields"] == {
        "shares": {"code": "sum_mismatch", "params": {"diff": 3, "currency_code": "ISK"}}
    }


def test_500_with_html_body_yields_internal_error_without_throwing(page, mockserver):
    """A 500 whose body is HTML, not JSON, still yields a clean fallback envelope."""
    page.goto(f"{mockserver}/")
    # `stub`'s responder always JSON-encodes `body`; a genuinely non-JSON body
    # needs its own route, bypassing the shared fixture's JSON encoding.
    page.route(
        "**/api/v1/trips/y",
        lambda route: route.fulfill(
            status=500,
            content_type="text/html",
            body=(ERRORS / "500_html.html").read_text(),
        ),
    )
    err = page.evaluate(
        """async () => {
            const { api } = await import('/js/api.js');
            try {
                await api.get('/trips/y');
                return null;
            } catch (e) {
                return e;
            }
        }"""
    )
    assert err == {"status": 500, "code": "internal_error", "params": {}, "fields": {}}


def test_field_error_reaches_the_matching_input(page, mockserver, trip_url, stub):
    """A fields.amount error renders under the amount input via the catalog, not text."""
    stub(
        "**/api/v1/trips/*/items",
        lambda request: (
            (
                422,
                {
                    "error": {
                        "code": "validation_error",
                        "params": {},
                        "fields": {"amount": {"code": "invalid_amount", "params": {}}},
                    }
                },
            )
            if request.method == "POST"
            else None
        ),
    )

    page.goto(trip_url)
    page.get_by_role("button", name="Expense").click()
    page.locator(".modal.show").wait_for()
    page.locator('input[name="name"]').fill("Snacks")
    page.locator('input[name="amount"]').fill("500")
    page.get_by_role("button", name="Save", exact=True).click()

    amount_group = page.locator('input[name="amount"]').locator("..")
    expect(amount_group.locator(".invalid-feedback")).to_have_text("Enter an amount.")
    assert page.locator(".modal.show").count() == 1  # save failed, modal stays open


def test_field_less_error_reaches_the_flash(page, mockserver, trip_url, stub):
    """An error with no fields (a top-level failure) shows in the flash, not under a field."""
    stub(
        "**/api/v1/trips/*/items",
        lambda request: (
            (500, {"error": {"code": "internal_error", "params": {"ref": "abc123"}}})
            if request.method == "POST"
            else None
        ),
    )

    page.goto(trip_url)
    page.get_by_role("button", name="Expense").click()
    page.locator(".modal.show").wait_for()
    page.locator('input[name="name"]').fill("Snacks")
    page.locator('input[name="amount"]').fill("500")
    page.get_by_role("button", name="Save", exact=True).click()

    expect(page.locator(".alert-danger")).to_have_text("Something went wrong. Reference: abc123.")
    assert page.locator(".invalid-feedback").count() == 0


def test_unknown_error_code_renders_as_code_and_params_never_blank(
    page, mockserver, trip_url, stub
):
    """A code the catalog doesn't know still shows something readable, not a blank flash."""
    stub(
        "**/api/v1/trips/*/items",
        lambda request: (
            (400, {"error": {"code": "brand_new_rule", "params": {"limit": 5}}})
            if request.method == "POST"
            else None
        ),
    )

    page.goto(trip_url)
    page.get_by_role("button", name="Expense").click()
    page.locator(".modal.show").wait_for()
    page.locator('input[name="name"]').fill("Snacks")
    page.locator('input[name="amount"]').fill("500")
    page.get_by_role("button", name="Save", exact=True).click()

    expect(page.locator(".alert-danger")).to_have_text("brand_new_rule · limit 5")
