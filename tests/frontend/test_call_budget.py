"""Tests for the API call budget in design/FRONTEND.md §5.

Intercept network — opening a trip makes exactly 3 API calls, opening the edit
modal makes 0, saving makes 2, the stats tab 1, the balances tab 1 — every row of
the table, asserted as equality, not a ceiling.
"""

import pytest
from playwright.sync_api import expect

API_CALLS = "*/api/v1/*"


@pytest.fixture
def visited_tabs_page(items_page, open_tab):
    """Return the page after Balances and Statistics were each opened once and Items reopened."""
    open_tab("Balances")
    open_tab("Statistics")
    return open_tab("Items")


@pytest.fixture
def filled_new_item_modal(page, new_item_modal):
    """Return the new-expense modal with name and amount typed and the split preview settled."""
    new_item_modal.locator('input[name="name"]').fill("Snacks")
    new_item_modal.locator('input[name="amount"]').fill("500")
    with page.expect_response(lambda response: "preview-split" in response.url):
        new_item_modal.locator('input[name="amount"]').blur()
    return new_item_modal


def test_opening_a_trip_makes_exactly_three_calls(count_requests, open_trip):
    """store.load() fires trip + items + labels in parallel — three calls, no more."""
    calls = count_requests(API_CALLS)

    open_trip()

    assert len(calls) == 3


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
    ],
)
def test_first_visit_to_a_derived_tab_makes_exactly_one_call(
    items_page, count_requests, open_tab, tab, expected_calls
):
    """Opening Balances or Statistics for the first time is one GET of that resource."""
    calls = count_requests(API_CALLS)

    open_tab(tab)

    assert len(calls) == expected_calls


def test_revisiting_balances_and_stats_makes_no_further_calls(
    visited_tabs_page, count_requests, open_tab
):
    """Once loaded, store.balances/store.stats are cached — switching back refetches nothing."""
    calls = count_requests(API_CALLS)

    open_tab("Balances")
    open_tab("Statistics")

    assert len(calls) == 0


def test_saving_an_item_makes_exactly_two_calls(filled_new_item_modal, count_requests):
    """A save with no new label is POST + the re-read GET /items — two calls, no labels reload."""
    calls = count_requests(API_CALLS)

    filled_new_item_modal.get_by_role("button", name="Save", exact=True).click()
    expect(filled_new_item_modal).to_be_hidden()

    assert len(calls) == 2
