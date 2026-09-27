"""Tests for the API call budget in design/FRONTEND.md §5.

Intercept network — opening a trip makes exactly 3 API calls, opening the edit
modal makes 0, saving makes 2, the stats tab 1, the balances tab 1, the map 0 — every row of
the table, asserted as equality, not a ceiling. Setup only needs `labels`, and Items
already loads those, so Setup's own cost only shows up when it opens before Items
ever does.
"""

import pytest
from playwright.sync_api import expect

from tests.frontend.conftest import fill_card_to_cash_transfer

API_CALLS = "*/api/v1/*"


@pytest.fixture
def visited_tabs_page(items_page, open_tab):
    """Return the page after Balances, Statistics and Wallets were each opened, Items reopened."""
    open_tab("Balances")
    open_tab("Statistics")
    open_tab("Wallets")
    return open_tab("Items")


@pytest.fixture
def filled_new_item_modal(page, new_item_modal):
    """Return the new-expense modal with name and amount typed and the split preview settled."""
    new_item_modal.locator('input[name="name"]').fill("Snacks")
    new_item_modal.locator('input[name="amount"]').fill("500")
    with page.expect_response(lambda response: "preview-split" in response.url):
        new_item_modal.locator('input[name="amount"]').blur()
    return new_item_modal


@pytest.mark.parametrize(
    ("tab", "expected_calls"),
    [
        pytest.param(None, 3, id="items-trip-items-labels"),
        pytest.param("setup", 2, id="setup-trip-labels"),
    ],
)
def test_cold_load_makes_exactly_the_calls_its_tab_needs(
    count_requests, open_trip, tab, expected_calls
):
    """store.load() fires trip + items + labels in parallel; landing on Setup skips items."""
    calls = count_requests(API_CALLS)

    open_trip(tab)

    assert len(calls) == expected_calls


def test_opening_the_edit_modal_makes_no_calls(items_page, count_requests, open_edit_modal):
    """The item is already in store.items — opening it for edit fetches nothing."""
    calls = count_requests(API_CALLS)

    open_edit_modal("Dinner at Messinn")

    assert len(calls) == 0


@pytest.mark.parametrize(
    ("tab", "expected_calls"),
    [
        pytest.param("Balances", 1, id="balances"),
        pytest.param("Statistics", 1, id="stats"),
        pytest.param("Wallets", 1, id="wallets"),
        pytest.param("Map", 0, id="map"),
        pytest.param("Setup", 0, id="setup"),
    ],
)
def test_first_visit_to_a_derived_tab_costs_only_its_own_resource(
    items_page, count_requests, open_tab, tab, expected_calls
):
    """Balances, Statistics and Wallets cost one GET each; Map and Setup reuse what Items loaded."""
    calls = count_requests(API_CALLS)

    open_tab(tab)

    assert len(calls) == expected_calls


def test_revisiting_derived_tabs_makes_no_further_calls(
    visited_tabs_page, count_requests, open_tab
):
    """Once loaded, balances, stats and wallets are cached — switching back refetches nothing."""
    calls = count_requests(API_CALLS)

    open_tab("Balances")
    open_tab("Statistics")
    open_tab("Wallets")

    assert len(calls) == 0


def test_saving_an_item_makes_exactly_two_calls(filled_new_item_modal, count_requests):
    """A save with no new label is POST + the re-read GET /items — two calls, no labels reload."""
    calls = count_requests(API_CALLS)

    filled_new_item_modal.get_by_role("button", name="Save", exact=True).click()
    expect(filled_new_item_modal).to_be_hidden()

    assert len(calls) == 2


def test_saving_a_transfer_makes_exactly_two_calls(new_item_modal, count_requests):
    """A transfer save is POST /transfers + the re-read GET /items — two calls, same as an item."""
    fill_card_to_cash_transfer(new_item_modal)
    calls = count_requests(API_CALLS)

    new_item_modal.get_by_role("button", name="Save", exact=True).click()
    expect(new_item_modal).to_be_hidden()

    assert len(calls) == 2
