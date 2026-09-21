"""Tests for the statistics Total section (rates.js + Stats.js's TotalSection).

The Total is another option in the page's currency dropdown, gated
all-or-nothing: it shows nothing but the rate form until every currency has a
positive typed rate, never a partial sum quietly missing one; a completed rate
set survives a reload; and no currency's own total is ever touched by it.
"""

import pytest
from playwright.sync_api import expect


@pytest.fixture
def stats_page(stats_page):
    """Return the Statistics tab switched to the Total, which is where rates are typed."""
    stats_page.locator("#stats-currency").select_option(label="Total")
    stats_page.locator("#cur-total").wait_for()
    return stats_page


def rate_input(page, currency_code):
    """Locate the Total section's rate <input> for one non-primary currency."""
    row = page.locator("#cur-total .row").filter(has=page.locator(".badge", has_text=currency_code))
    return row.locator("input")


def fmt_money(page, value):
    """Compute the exact string fmt.js's money() produces for `value` in `en`."""
    return page.evaluate(
        "async ({ value }) => (await import('/js/fmt.js')).money(value, 'en')",
        {"value": value},
    )


def convert(amount, rate):
    """Mirror Stats.js's own currency conversion: round the product to 2 places."""
    return round(amount * rate * 100) / 100


def total_of(fixture_data, currency_code):
    """Return one currency's trip total — the row of the API's ["currency"] grouping."""
    trip = fixture_data["trip"]["trip"]
    currency_id = next(c["id"] for c in trip["currencies"] if c["code"] == currency_code)
    totals = next(g for g in fixture_data["stats"]["groups"] if g["by"] == ["currency"])
    return next(r["amount"] for r in totals["rows"] if r["keys"]["currency_id"] == currency_id)


def test_total_shows_only_the_rate_form_until_every_currency_has_a_rate(stats_page):
    """With no rates typed, the Total offers only the form — no stat sections, no figure."""
    expect(stats_page.locator("#cur-total")).to_contain_text(
        "Add a rate for every currency to see the total."
    )
    assert stats_page.locator("#breakdown-total").count() == 0


def test_total_stays_hidden_with_only_some_currencies_rated(stats_page):
    """Typing a rate for EUR but not DKK still leaves the Total showing just the form.

    This is the all-or-nothing behaviour: no partial total that silently
    drops the currency still missing a rate.
    """
    rate_input(stats_page, "EUR").fill("150")
    rate_input(stats_page, "EUR").blur()

    expect(stats_page.locator("#cur-total")).to_contain_text(
        "Add a rate for every currency to see the total."
    )
    assert stats_page.locator("#breakdown-total").count() == 0


def test_total_appears_once_every_currency_has_a_rate(stats_page, fixture_data):
    """Filling in the last missing rate reveals the Total's figure and its sections."""
    isk_total = total_of(fixture_data, "ISK")
    eur_total = total_of(fixture_data, "EUR")
    dkk_total = total_of(fixture_data, "DKK")

    rate_input(stats_page, "EUR").fill("150")
    rate_input(stats_page, "EUR").blur()
    rate_input(stats_page, "DKK").fill("20")
    rate_input(stats_page, "DKK").blur()

    expected_total = isk_total + convert(eur_total, 150) + convert(dkk_total, 20)
    heading = stats_page.locator("#cur-total h2")
    expect(heading).to_contain_text(f"{fmt_money(stats_page, expected_total)} total")
    assert stats_page.locator("#breakdown-total").count() == 1
    expect(stats_page.locator("#cur-total")).not_to_contain_text(
        "Add a rate for every currency to see the total."
    )


def test_total_rates_survive_a_reload(stats_page, fixture_data):
    """Once complete, the typed rates and the resulting total are still there after a reload."""
    isk_total = total_of(fixture_data, "ISK")
    eur_total = total_of(fixture_data, "EUR")
    dkk_total = total_of(fixture_data, "DKK")

    rate_input(stats_page, "EUR").fill("150")
    rate_input(stats_page, "EUR").blur()
    rate_input(stats_page, "DKK").fill("20")
    rate_input(stats_page, "DKK").blur()

    stats_page.reload()

    expect(rate_input(stats_page, "EUR")).to_have_value("150")
    expect(rate_input(stats_page, "DKK")).to_have_value("20")
    expected_total = isk_total + convert(eur_total, 150) + convert(dkk_total, 20)
    heading = stats_page.locator("#cur-total h2")
    expect(heading).to_contain_text(f"{fmt_money(stats_page, expected_total)} total")


def test_per_currency_totals_are_unaffected_by_the_total_rates(stats_page, fixture_data):
    """A currency's own heading total stays the raw fixture value regardless of any rate."""
    trip = fixture_data["trip"]["trip"]
    dkk_id = next(c["id"] for c in trip["currencies"] if c["code"] == "DKK")
    expected_text = f"{fmt_money(stats_page, total_of(fixture_data, 'DKK'))} total"

    rate_input(stats_page, "EUR").fill("150")
    rate_input(stats_page, "EUR").blur()
    stats_page.locator("#stats-currency").select_option(label="DKK")

    expect(stats_page.locator(f"#cur-{dkk_id} h2")).to_contain_text(expected_text)


def test_total_is_picked_from_the_same_dropdown_as_a_currency(stats_page):
    """The Total is reachable exactly like a currency: one more option in the dropdown."""
    expect(stats_page.locator("#cur-total")).to_be_visible()

    stats_page.locator("#stats-currency").select_option(label="DKK")

    expect(stats_page.locator("#cur-total")).to_have_count(0)


def test_total_defaults_to_converting_into_the_primary_currency(stats_page):
    """With nothing chosen yet, the target picker starts on the trip's primary currency."""
    expect(stats_page.locator("#rates-target")).to_have_value(
        "1"
    )  # ISK is currency id 1, the primary


def test_total_can_convert_into_any_currency_not_just_the_primary(stats_page, fixture_data):
    """Picking EUR as the target (ISK is the primary) totals everything in EUR instead."""
    isk_total = total_of(fixture_data, "ISK")
    eur_total = total_of(fixture_data, "EUR")
    dkk_total = total_of(fixture_data, "DKK")

    stats_page.locator("#rates-target").select_option(label="EUR")

    rate_input(stats_page, "ISK").fill("0.0065")
    rate_input(stats_page, "ISK").blur()
    rate_input(stats_page, "DKK").fill("0.134")
    rate_input(stats_page, "DKK").blur()

    expected_total = eur_total + convert(isk_total, 0.0065) + convert(dkk_total, 0.134)
    heading = stats_page.locator("#cur-total h2")
    expect(heading).to_contain_text(f"{fmt_money(stats_page, expected_total)} total")
    expect(heading).to_contain_text("EUR")


def test_switching_the_target_currency_clears_previously_typed_rates(stats_page):
    """A rate typed against one target means something else against another, so it can't carry."""
    rate_input(stats_page, "EUR").fill("150")
    rate_input(stats_page, "EUR").blur()

    stats_page.locator("#rates-target").select_option(label="EUR")

    # EUR is now the target itself; ISK's old value must not silently survive
    # as if it were an ISK-into-EUR rate.
    expect(rate_input(stats_page, "ISK")).to_have_value("")
    expect(stats_page.locator("#cur-total")).to_contain_text(
        "Add a rate for every currency to see the total."
    )
