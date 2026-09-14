"""Tests for rule 5: unknown fields are ignored, never break a view.

A fixture carrying an extra key on the trip, an item and a balance renders
identically — rule 5, the guarantee that lets the backend ship first.
"""

import pytest
from playwright.sync_api import expect

from tests.frontend.conftest import TABS


@pytest.fixture
def fixture_data(fixture_data):
    """Add an unrecognized key to the trip, the first item and the first balance."""
    fixture_data["trip"]["trip"]["unknown_trip_field"] = "surprise"
    fixture_data["items"]["items"][0]["unknown_item_field"] = {"nested": True}
    fixture_data["balances"]["balances"][0]["unknown_balance_field"] = 12345
    return fixture_data


def test_page_errors_never_fire_with_unknown_fields(page, open_trip, open_tab):
    """No unhandled JS exception fires anywhere while browsing a fixture with extra keys."""
    errors = []
    page.on("pageerror", lambda exc: errors.append(exc))  # noqa: PLW0108 (bound method breaks Playwright's wrapper)

    open_trip()
    for name in TABS:
        open_tab(name)

    assert errors == []


@pytest.mark.parametrize(
    ("tab", "scope_selector", "real_field", "leaked"),
    [
        pytest.param(
            "items",
            "header",
            lambda page: page.get_by_role("heading", name="Iceland 2026"),
            "surprise",
            id="trip-header",
        ),
        pytest.param(
            "items",
            'a.list-group-item-action:has-text("Dinner at Messinn")',
            lambda page: page.locator("a.list-group-item-action", has_text="Dinner at Messinn"),
            "unknown_item_field",
            id="item-row",
        ),
        pytest.param(
            "balances",
            "main",
            lambda page: page.locator(".balances-content").first,
            "12345",
            id="balance-card",
        ),
    ],
)
def test_surface_renders_its_real_fields_and_not_the_unknown_one(
    open_trip, tab, scope_selector, real_field, leaked
):
    """The surface shows its real fields; the unknown key's value is neither shown nor breaks it."""
    page = open_trip(tab)

    expect(real_field(page)).to_be_visible()
    assert leaked not in page.locator(scope_selector).inner_text()
