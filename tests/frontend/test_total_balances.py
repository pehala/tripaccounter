"""Tests for the balances Total section (convert.js + Balances.js's TotalBalances).

The rate gate it shares with the statistics Total is in test_rates.py. Here: the
converted, summed net per person, and the settle-up list, which is not a fresh
minimum-transfer plan — it converts and nets each currency's own suggestions by
unordered person pair, so the same two people never show up owing each other in both
directions at once. No currency's own figures are ever touched by the rates. Each
person's average exchange rate is offered as a link that fills the rate input,
inverted when the pair runs the other way.
"""

import pytest
from playwright.sync_api import expect

from tests.frontend.conftest import CURRENCY_ID, rate_input, set_rates

SETTLE_UP_ROWS = "#sec-total-settle_up-body ul.list-group-flush li"


def rate_all_at_one(page):
    """Type a rate of 1 for every non-target currency (EUR, DKK against primary ISK)."""
    set_rates(page, EUR="1", DKK="1")


@pytest.fixture
def cancelling_pair_page(stub, fixture_data, open_trip):
    """Return the Balances tab where ISK and EUR have an opposite-and-equal Petr/Ann suggestion."""
    isk, eur, dkk = fixture_data["balances"]["balances"]
    isk["suggestions"] = [{"from_person_id": 1, "to_person_id": 2, "amount": 100}]
    eur["suggestions"] = [{"from_person_id": 2, "to_person_id": 1, "amount": 100}]
    dkk["suggestions"] = []
    stub("**/api/v1/trips/*/balances", lambda request: (200, {"balances": [isk, eur, dkk]}))

    return open_trip("balances")


def test_total_combines_nets_once_every_currency_has_a_rate(balances_page):
    """Eva's three nets, each converted at 1 and rounded, sum to one signed figure.

    75,710.71 ISK - 13.33 EUR - 120 DKK = +75,577.38.
    """
    rate_all_at_one(balances_page)

    balances_page.locator('[data-bs-target="#sec-total-net-body"]').click()
    row = balances_page.locator("#sec-total-net-body.show li").filter(has_text="Eva")
    expect(row.locator(".num")).to_have_text("+75,577.38")


def test_opposite_direction_suggestions_net_to_one_line(balances_page):
    """The same pair owing each other in opposite directions across currencies nets to one line.

    ISK has Ann owing Eva 29,003.57 (lower than her `owed` alone, since her wallet sent
    5000 ISK to Bob's — WALLETS.md §5); EUR and DKK both have Eva owing Ann (13.33 and
    120). At rate 1 that nets to Ann owing Eva 28,870.24 — one line, not two.
    """
    rate_all_at_one(balances_page)

    rows = balances_page.locator(SETTLE_UP_ROWS).filter(has_text="Ann").filter(has_text="Eva")

    expect(rows).to_have_count(1)
    expect(rows.first).to_contain_text("28,870.24")


def test_a_pair_that_cancels_out_across_currencies_is_omitted(cancelling_pair_page):
    """Two currencies with an exact opposite-and-equal suggestion for a pair drop it entirely."""
    rate_all_at_one(cancelling_pair_page)

    rows = cancelling_pair_page.locator(SETTLE_UP_ROWS).filter(has_text="Petr")

    expect(rows.filter(has_text="Ann")).to_have_count(0)


def test_per_currency_figures_are_unaffected_by_the_total_rates(balances_page):
    """A currency's own net figures stay the raw fixture values regardless of any rate."""
    dkk_id = CURRENCY_ID["DKK"]
    balances_page.locator(f'[data-bs-target="#sec-{dkk_id}-net-body"]').click()
    ann_row = balances_page.locator(f"#sec-{dkk_id}-net-body.show li").filter(has_text="Ann")
    expect(ann_row.locator(".num")).to_have_text("+360")

    set_rates(balances_page, EUR="1")

    expect(ann_row.locator(".num")).to_have_text("+360")


@pytest.mark.parametrize(
    ("target", "currency_code", "expected"),
    [
        pytest.param("ISK", "EUR", "142.857", id="inverted-pair"),
        pytest.param("EUR", "ISK", "0.007", id="pair-as-is"),
    ],
)
def test_average_rate_link_fills_the_rate_input(balances_page, target, currency_code, expected):
    """Petr's EUR→ISK average is offered under the matching input, and a click fills it."""
    balances_page.locator("#rates-target").select_option(label=target)
    row = balances_page.locator("#cur-total .row").filter(
        has=balances_page.locator(".badge", has_text=currency_code)
    )

    row.locator(".rate-average").click()

    expect(row.locator(".rate-average")).to_have_text(f"Petr {expected}")
    expect(rate_input(balances_page, currency_code)).to_have_value(expected)


def test_no_average_rate_link_without_a_spent_rate(balances_page):
    """Petr's EUR→DKK exchange has nothing spent yet, so DKK offers no link."""
    expect(balances_page.locator("#cur-total .rate-average")).to_have_count(1)
    row = balances_page.locator("#cur-total .row").filter(
        has=balances_page.locator(".badge", has_text="DKK")
    )
    expect(row.locator(".rate-average")).to_have_count(0)
