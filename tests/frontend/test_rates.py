"""Tests for rates.js as both Totals use it: Balances.js TotalBalances, Stats.js TotalSection.

Each Total is gated all-or-nothing: it shows nothing but the rate form until every
currency has a positive typed rate, never a partial figure quietly missing one; a
completed rate set survives a reload; and a rate typed against one target currency
never carries over to another.
"""

import pytest
from playwright.sync_api import expect

from tests.frontend.conftest import RATES_NEEDED, rate_input, set_rates

# What each tab renders once the rate set is complete.
TOTAL_FIGURES = {
    "balances": '[data-bs-target="#sec-total-net-body"]',
    "stats": "#breakdown-total",
}


@pytest.fixture(params=[pytest.param(tab, id=tab) for tab in TOTAL_FIGURES])
def total_tab(request):
    """Return the tab whose Total the test drives: Balances or Statistics."""
    return request.param


@pytest.fixture
def total_page(open_trip, total_tab):
    """Return that tab with its Total on screen; Statistics picks it from the currency dropdown."""
    page = open_trip(total_tab)
    if total_tab == "stats":
        page.locator("#stats-currency").select_option(label="Total")
    page.locator("#cur-total").wait_for()
    return page


@pytest.mark.parametrize(
    "rates",
    [
        pytest.param({}, id="no-rates"),
        pytest.param({"EUR": "150"}, id="eur-but-not-dkk"),
    ],
)
def test_total_shows_only_the_rate_form_until_every_currency_has_a_rate(
    total_page, total_tab, rates
):
    """With a rate missing, the Total offers only the form — no partial figure, no sections."""
    set_rates(total_page, **rates)

    expect(total_page.locator("#cur-total")).to_contain_text(RATES_NEEDED)
    expect(total_page.locator(TOTAL_FIGURES[total_tab])).to_have_count(0)


def test_total_appears_once_every_currency_has_a_rate(total_page, total_tab):
    """Filling in the last missing rate replaces the form with the Total's figures."""
    set_rates(total_page, EUR="150", DKK="20")

    expect(total_page.locator(TOTAL_FIGURES[total_tab])).to_have_count(1)
    expect(total_page.locator("#cur-total")).not_to_contain_text(RATES_NEEDED)


def test_total_rates_survive_a_reload(total_page, total_tab):
    """Once complete, the typed rates and the Total they unlock are still there after a reload."""
    set_rates(total_page, EUR="150", DKK="20")

    total_page.reload()

    expect(rate_input(total_page, "EUR")).to_have_value("150")
    expect(rate_input(total_page, "DKK")).to_have_value("20")
    expect(total_page.locator(TOTAL_FIGURES[total_tab])).to_have_count(1)
    expect(total_page.locator("#cur-total")).not_to_contain_text(RATES_NEEDED)


def test_switching_the_target_currency_clears_previously_typed_rates(total_page):
    """A rate typed against one target means something else against another, so it can't carry."""
    set_rates(total_page, EUR="150")

    total_page.locator("#rates-target").select_option(label="EUR")

    expect(rate_input(total_page, "ISK")).to_have_value("")
    expect(total_page.locator("#cur-total")).to_contain_text(RATES_NEEDED)
