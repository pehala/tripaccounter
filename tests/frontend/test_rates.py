"""Tests for the statistics combined view's user-typed rates (rates.js + Stats.js).

Typing a rate updates the combined totals and
survives a reload; a missing or zero rate leaves that currency out instead of
rendering NaN; the per-currency view is unaffected by any rate.
"""

from playwright.sync_api import expect


def rate_input(page, currency_code):
    """Locate the rate <input> for one non-primary currency, scoped by its code badge."""
    row = page.locator(".row").filter(has=page.locator(".badge", has_text=currency_code))
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


def test_typing_a_rate_updates_the_combined_total(page, mockserver, trip_url, fixture_data):
    """Typing a EUR rate folds EUR into the combined total at that rate; DKK stays out."""
    stats = fixture_data["stats"]["stats"]
    isk_total = next(s for s in stats if s["currency_code"] == "ISK")["total"]
    eur_total = next(s for s in stats if s["currency_code"] == "EUR")["total"]

    page.goto(f"{trip_url}#stats")
    rate_input(page, "EUR").fill("150")
    rate_input(page, "EUR").blur()

    expected_total = isk_total + convert(eur_total, 150)
    expected_text = f"{fmt_money(page, expected_total)} total"
    expect(page.locator(".card-header", has_text="By label").first).to_contain_text(expected_text)
    assert "NaN" not in page.locator(".card-header", has_text="By label").first.inner_text()


def test_rate_survives_a_reload(page, mockserver, trip_url, fixture_data):
    """The typed rate is written to localStorage and is still there after a reload."""
    stats = fixture_data["stats"]["stats"]
    isk_total = next(s for s in stats if s["currency_code"] == "ISK")["total"]
    eur_total = next(s for s in stats if s["currency_code"] == "EUR")["total"]

    page.goto(f"{trip_url}#stats")
    rate_input(page, "EUR").fill("150")
    rate_input(page, "EUR").blur()

    page.reload()

    expect(rate_input(page, "EUR")).to_have_value("150")
    expected_total = isk_total + convert(eur_total, 150)
    expected_text = f"{fmt_money(page, expected_total)} total"
    expect(page.locator(".card-header", has_text="By label").first).to_contain_text(expected_text)


def test_missing_or_zero_rate_excludes_that_currency_without_nan(
    page, mockserver, trip_url, fixture_data
):
    """DKK has no typed rate by default; it contributes nothing, not 0 and not NaN."""
    stats = fixture_data["stats"]["stats"]
    isk_total = next(s for s in stats if s["currency_code"] == "ISK")["total"]
    dkk_total = next(s for s in stats if s["currency_code"] == "DKK")["total"]

    page.goto(f"{trip_url}#stats")
    combined_header = page.locator(".card-header", has_text="By label").first
    expected_isk_only = f"{fmt_money(page, isk_total)} total"
    expect(combined_header).to_contain_text(expected_isk_only)
    assert "NaN" not in combined_header.inner_text()
    assert str(dkk_total) not in combined_header.inner_text()

    # Explicitly typing 0 behaves the same as leaving it blank — still excluded.
    rate_input(page, "DKK").fill("0")
    rate_input(page, "DKK").blur()
    expect(combined_header).to_contain_text(expected_isk_only)
    assert "NaN" not in combined_header.inner_text()


def test_per_currency_view_is_unaffected_by_any_typed_rate(
    page, mockserver, trip_url, fixture_data
):
    """DKK's own per-currency total stays the raw fixture value regardless of the EUR rate."""
    dkk_total = next(s for s in fixture_data["stats"]["stats"] if s["currency_code"] == "DKK")[
        "total"
    ]

    page.goto(f"{trip_url}#stats")
    dkk_header = page.locator(".card-header", has_text="total DKK")
    expected_text = f"{fmt_money(page, dkk_total)} total"
    expect(dkk_header).to_contain_text(expected_text)

    rate_input(page, "EUR").fill("150")
    rate_input(page, "EUR").blur()

    expect(dkk_header).to_contain_text(expected_text)
