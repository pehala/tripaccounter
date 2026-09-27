"""Tests for the statistics Total section (Stats.js's TotalSection).

The rate gate it shares with the balances Total is in test_rates.py. Here: the Total
is one more option in the page's currency dropdown, it converts into the primary
currency unless another target is picked, and no currency's own total is ever touched
by it.
"""

import pytest
from playwright.sync_api import expect

from tests.frontend.conftest import CURRENCY_ID, set_rates


@pytest.fixture
def stats_page(stats_page):
    """Return the Statistics tab switched to the Total, which is where rates are typed."""
    stats_page.locator("#stats-currency").select_option(label="Total")
    stats_page.locator("#cur-total").wait_for()
    return stats_page


def test_total_sums_every_currency_at_its_typed_rate(stats_page):
    """122,300 ISK + 40 EUR at 150 + 480 DKK at 20 is one 137,900 ISK total."""
    set_rates(stats_page, EUR="150", DKK="20")

    expect(stats_page.locator("#cur-total h2")).to_contain_text("137,900 total")


def test_total_figure_survives_a_reload(stats_page):
    """After a reload the restored rates produce the same 137,900 ISK total, not just the inputs."""
    set_rates(stats_page, EUR="150", DKK="20")

    stats_page.reload()

    expect(stats_page.locator("#cur-total h2")).to_contain_text("137,900 total")


def test_per_currency_totals_are_unaffected_by_the_total_rates(stats_page):
    """A currency's own heading total stays the raw fixture value regardless of any rate."""
    set_rates(stats_page, EUR="150")

    stats_page.locator("#stats-currency").select_option(label="DKK")

    expect(stats_page.locator(f"#cur-{CURRENCY_ID['DKK']} h2")).to_contain_text("480 total")


def test_total_is_picked_from_the_same_dropdown_as_a_currency(stats_page):
    """The Total is reachable exactly like a currency: one more option in the dropdown."""
    expect(stats_page.locator("#cur-total")).to_be_visible()

    stats_page.locator("#stats-currency").select_option(label="DKK")

    expect(stats_page.locator("#cur-total")).to_have_count(0)


def test_total_converts_into_the_primary_currency_unless_another_is_picked(stats_page):
    """The target starts on ISK; picking EUR totals everything in EUR instead.

    40 EUR + 122,300 ISK at 0.0065 (794.95) + 480 DKK at 0.134 (64.32) = 899.27 EUR.
    """
    expect(stats_page.locator("#rates-target")).to_have_value(str(CURRENCY_ID["ISK"]))

    stats_page.locator("#rates-target").select_option(label="EUR")
    set_rates(stats_page, ISK="0.0065", DKK="0.134")

    heading = stats_page.locator("#cur-total h2")
    expect(heading).to_contain_text("899.27 total")
    expect(heading).to_contain_text("EUR")
