"""Tests for the statistics combined view's user-typed rates (rates.js + Stats.js).

Typing a rate updates the combined totals and survives a reload; a missing or zero
rate leaves that currency out instead of rendering NaN; the per-currency view is
unaffected by any rate.
"""

import pytest
from playwright.sync_api import expect

ISK_ONLY_TOTAL = "122,300 total"
ISK_PLUS_EUR_AT_150 = "128,300 total"
DKK_OWN_TOTAL = "480 total"


@pytest.fixture
def rate_input(stats_page):
    """Return `rate_input(currency_code)`: the rate <input> of that non-primary currency."""

    def find(currency_code):
        row = stats_page.locator(".row").filter(
            has=stats_page.locator(".badge", has_text=currency_code)
        )
        return row.locator("input")

    return find


@pytest.fixture
def type_rate(rate_input):
    """Return `type_rate(currency_code, text)`: fill that rate input and blur to commit it."""

    def fill(currency_code, text):
        rate_input(currency_code).fill(text)
        rate_input(currency_code).blur()

    return fill


@pytest.fixture
def combined_header(stats_page):
    """Return the combined view's By label header, which carries the folded total."""
    return stats_page.locator(".card-header", has_text="By label").first


@pytest.mark.parametrize(
    ("currency_code", "rate", "expected_total"),
    [
        pytest.param("EUR", "150", ISK_PLUS_EUR_AT_150, id="eur-150-folded-in"),
        pytest.param("DKK", "", ISK_ONLY_TOTAL, id="dkk-blank-left-out"),
        pytest.param("DKK", "0", ISK_ONLY_TOTAL, id="dkk-zero-left-out"),
    ],
)
def test_typed_rate_folds_a_currency_in_or_leaves_it_out(
    combined_header, type_rate, currency_code, rate, expected_total
):
    """A positive rate folds a currency into the combined sum; blank or 0 leaves it out, no NaN."""
    type_rate(currency_code, rate)

    expect(combined_header).to_contain_text(expected_total)
    assert "NaN" not in combined_header.inner_text()


def test_rate_survives_a_reload(stats_page, rate_input, type_rate, combined_header):
    """The typed rate is written to localStorage and is still there after a reload."""
    type_rate("EUR", "150")

    stats_page.reload()

    expect(rate_input("EUR")).to_have_value("150")
    expect(combined_header).to_contain_text(ISK_PLUS_EUR_AT_150)


def test_per_currency_view_is_unaffected_by_any_typed_rate(stats_page, type_rate):
    """DKK's own per-currency total stays the raw fixture value regardless of the EUR rate."""
    dkk_header = stats_page.locator(".card-header", has_text="total DKK")

    type_rate("EUR", "150")

    expect(dkk_header).to_contain_text(DKK_OWN_TOTAL)
