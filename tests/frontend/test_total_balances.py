"""Tests for the balances Total section (rates.js/convert.js + Balances.js's TotalBalances).

The Total is another entry in the currency switcher, gated all-or-nothing: it
shows nothing but the rate form until every currency has a positive typed
rate; a completed rate set survives a reload; no currency's own per-currency
figures are ever touched by it. Its settle-up list is not a fresh
minimum-transfer plan — it converts and nets each currency's own suggestions
by unordered person pair, so the same two people never show up owing each
other in both directions at once.
"""

import pytest
from playwright.sync_api import expect


def rate_input(page, currency_code):
    """Locate the Total section's rate <input> for one non-target currency."""
    row = page.locator("#cur-total .row").filter(has=page.locator(".badge", has_text=currency_code))
    return row.locator("input")


def expand_total(page, group):
    """Open the Total's net or settle_up section body."""
    page.locator(f'[data-bs-target="#sec-total-{group}-body"]').click()
    page.locator(f"#sec-total-{group}-body.show").wait_for()


def fmt_signed(page, value):
    """Compute the exact string fmt.js's signed() produces for `value` in `en`."""
    return page.evaluate(
        "async ({ value }) => (await import('/js/fmt.js')).signed(value, 'en')",
        {"value": value},
    )


def fmt_money(page, value):
    """Compute the exact string fmt.js's money() produces for `value` in `en`."""
    return page.evaluate(
        "async ({ value }) => (await import('/js/fmt.js')).money(value, 'en')",
        {"value": value},
    )


def convert(amount, rate):
    """Mirror convert.js's own currency conversion: round the product to 2 places."""
    return round(amount * rate * 100) / 100


def rate_all_at_one(page):
    """Type a rate of 1 for every non-target currency (EUR, DKK against primary ISK)."""
    for code in ("EUR", "DKK"):
        rate_input(page, code).fill("1")
        rate_input(page, code).blur()


def test_total_shows_only_the_rate_form_until_every_currency_has_a_rate(balances_page):
    """With no rates typed, the Total offers only the form — no sections, no figure."""
    expect(balances_page.locator("#cur-total")).to_contain_text(
        "Add a rate for every currency to see the total."
    )
    assert balances_page.locator('[data-bs-target="#sec-total-net-body"]').count() == 0


def test_total_stays_hidden_with_only_some_currencies_rated(balances_page):
    """Typing a rate for EUR but not DKK still leaves the Total showing just the form."""
    rate_input(balances_page, "EUR").fill("1")
    rate_input(balances_page, "EUR").blur()

    expect(balances_page.locator("#cur-total")).to_contain_text(
        "Add a rate for every currency to see the total."
    )
    assert balances_page.locator('[data-bs-target="#sec-total-net-body"]').count() == 0


def test_total_combines_nets_once_every_currency_has_a_rate(balances_page, fixture_data):
    """Filling in the last missing rate reveals a converted, summed net per person."""
    balances = fixture_data["balances"]["balances"]
    eva_nets = [
        next(b for b in balances if b["currency_code"] == code)["people"][3]["net"]
        for code in ("ISK", "EUR", "DKK")
    ]

    rate_all_at_one(balances_page)

    expected_net = sum(convert(net, 1) for net in eva_nets)
    expand_total(balances_page, "net")
    row = balances_page.locator("#sec-total-net-body li").filter(has_text="Eva")
    expect(row.locator(".num")).to_have_text(fmt_signed(balances_page, expected_net))
    assert balances_page.locator('[data-bs-target="#sec-total-net-body"]').count() == 1
    expect(balances_page.locator("#cur-total")).not_to_contain_text(
        "Add a rate for every currency to see the total."
    )


def test_opposite_direction_suggestions_net_to_one_line(balances_page):
    """The same pair owing each other in opposite directions across currencies nets to one line.

    In the fixture, ISK has Ann (2) owing Eva (4) 34003.57; EUR and DKK both have
    Eva (4) owing Ann (2) instead (13.33 and 120). With every rate set to 1, the
    combined pair nets to Ann owing Eva 34003.57 - 13.33 - 120 = 33870.24 — one
    line, in the direction the net favors, not two lines pointing both ways.

    Settle-up is open by default, so no expand click is needed.
    """
    rate_all_at_one(balances_page)

    rows = balances_page.locator("#sec-total-settle_up-body ul.list-group-flush li")
    ann_eva_rows = rows.filter(has_text="Ann").filter(has_text="Eva")

    expect(ann_eva_rows).to_have_count(1)
    expect(ann_eva_rows.first).to_contain_text(fmt_money(balances_page, 33870.24))


@pytest.fixture
def cancelling_pair_page(stub, fixture_data, open_trip):
    """Return the Balances tab where ISK and EUR have an opposite-and-equal Petr/Ann suggestion."""
    balances = fixture_data["balances"]["balances"]
    isk = next(b for b in balances if b["currency_code"] == "ISK")
    eur = next(b for b in balances if b["currency_code"] == "EUR")
    dkk = next(b for b in balances if b["currency_code"] == "DKK")

    isk["suggestions"] = [{"from_person_id": 1, "to_person_id": 2, "amount": 100}]
    eur["suggestions"] = [{"from_person_id": 2, "to_person_id": 1, "amount": 100}]
    dkk["suggestions"] = []
    stub("**/api/v1/trips/*/balances", lambda request: (200, {"balances": [isk, eur, dkk]}))

    return open_trip("balances")


def test_a_pair_that_cancels_out_across_currencies_is_omitted(cancelling_pair_page):
    """Two currencies with an exact opposite-and-equal suggestion for a pair drop it entirely."""
    rate_all_at_one(cancelling_pair_page)

    rows = cancelling_pair_page.locator("#sec-total-settle_up-body ul.list-group-flush li")
    petr_ann_rows = rows.filter(has_text="Petr").filter(has_text="Ann")

    expect(petr_ann_rows).to_have_count(0)


def test_total_rates_survive_a_reload(balances_page):
    """Once complete, the typed rates are still there after a reload."""
    rate_all_at_one(balances_page)

    balances_page.reload()

    expect(rate_input(balances_page, "EUR")).to_have_value("1")
    expect(rate_input(balances_page, "DKK")).to_have_value("1")
    expect(balances_page.locator("#cur-total")).not_to_contain_text(
        "Add a rate for every currency to see the total."
    )


def test_per_currency_figures_are_unaffected_by_the_total_rates(balances_page, fixture_data):
    """A currency's own net figures stay the raw fixture values regardless of any rate."""
    dkk = next(b for b in fixture_data["balances"]["balances"] if b["currency_code"] == "DKK")
    balances_page.locator(f'[data-bs-target="#sec-{dkk["currency_id"]}-net-body"]').click()
    dkk_body = balances_page.locator(f"#sec-{dkk['currency_id']}-net-body")
    dkk_body.wait_for(state="visible")
    ann_row = dkk_body.locator("li").filter(has_text="Ann")
    expect(ann_row.locator(".num")).to_have_text("+360")

    rate_input(balances_page, "EUR").fill("1")
    rate_input(balances_page, "EUR").blur()

    expect(ann_row.locator(".num")).to_have_text("+360")


def test_switching_the_target_currency_clears_previously_typed_rates(balances_page):
    """A rate typed against one target means something else against another, so it can't carry."""
    rate_input(balances_page, "EUR").fill("1")
    rate_input(balances_page, "EUR").blur()

    balances_page.locator("#rates-target").select_option(label="EUR")

    expect(rate_input(balances_page, "ISK")).to_have_value("")
    expect(balances_page.locator("#cur-total")).to_contain_text(
        "Add a rate for every currency to see the total."
    )
