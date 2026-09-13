"""Tests for views/Balances.js and components/BalanceCard.js.

One card per currency, each `net` formatted and signed correctly (credit `+`, debt
`-`, zero bare), suggestion rows in the API's order, bar widths derived from the
full-precision net while six-place `net` values render to two.
"""

import re

import pytest
from playwright.sync_api import expect


@pytest.fixture
def person_row(balances_page, card):
    """Return `person_row(currency_code, name)`: that person's <li> in the Balance card."""

    def find(currency_code, name):
        return card(f"Balance {currency_code}").locator("li").filter(has_text=name)

    return find


@pytest.mark.parametrize(
    "currency_code",
    [
        pytest.param("ISK", id="isk"),
        pytest.param("EUR", id="eur"),
        pytest.param("DKK", id="dkk"),
    ],
)
def test_one_balance_card_and_one_settle_up_card_per_currency(balances_page, card, currency_code):
    """Every currency in the fixture gets its own balance card and settle-up card."""
    expect(card(f"Balance {currency_code}")).to_have_count(1)
    expect(card(f"Settle up {currency_code}")).to_have_count(1)


@pytest.mark.parametrize(
    ("currency_code", "name", "expected"),
    [
        pytest.param("ISK", "Petr", "-15,603.57", id="isk-petr-debit"),
        pytest.param("ISK", "Ann", "-34,003.57", id="isk-ann-debit"),
        pytest.param("ISK", "Bob", "-26,103.57", id="isk-bob-debit"),
        pytest.param("ISK", "Eva", "+75,710.71", id="isk-eva-credit"),
        pytest.param("EUR", "Petr", "-13.33", id="eur-petr-debit"),
        pytest.param("EUR", "Ann", "+26.67", id="eur-ann-credit"),
        pytest.param("EUR", "Bob", "0", id="eur-bob-zero"),
        pytest.param("EUR", "Eva", "-13.33", id="eur-eva-debit"),
        pytest.param("DKK", "Petr", "-120", id="dkk-petr-debit"),
        pytest.param("DKK", "Ann", "+360", id="dkk-ann-credit"),
        pytest.param("DKK", "Bob", "-120", id="dkk-bob-debit"),
        pytest.param("DKK", "Eva", "-120", id="dkk-eva-debit"),
    ],
)
def test_net_value_is_signed_and_trimmed_to_two_places(person_row, currency_code, name, expected):
    """A credit renders with a leading +, a debt with -, zero bare; six places trim to two."""
    expect(person_row(currency_code, name).locator(".num")).to_have_text(expected)


@pytest.mark.parametrize(
    ("currency_code", "transfers"),
    [
        pytest.param("ISK", [("Ann", "Eva"), ("Bob", "Eva"), ("Petr", "Eva")], id="isk"),
        pytest.param("EUR", [("Petr", "Ann"), ("Eva", "Ann")], id="eur"),
        pytest.param("DKK", [("Petr", "Ann"), ("Bob", "Ann"), ("Eva", "Ann")], id="dkk"),
    ],
)
def test_suggestion_rows_follow_the_api_order(balances_page, card, currency_code, transfers):
    """Settle-up rows render payer then payee in the API's own order, with no extra rows."""
    rows = card(f"Settle up {currency_code}").locator("ul.list-group-flush li")

    expect(rows).to_have_text([re.compile(rf"^{payer}\s+{payee}") for payer, payee in transfers])


@pytest.mark.parametrize(
    ("currency_code", "name", "expected_style"),
    [
        pytest.param("ISK", "Eva", "width: 50%;", id="isk-eva-widest"),
        pytest.param("ISK", "Petr", "width: 10.3047%;", id="isk-petr"),
        pytest.param("EUR", "Ann", "width: 50%;", id="eur-ann-widest"),
        pytest.param("EUR", "Petr", "width: 25%;", id="eur-petr"),
        pytest.param("DKK", "Ann", "width: 50%;", id="dkk-ann-widest"),
        pytest.param("DKK", "Petr", "width: 16.6667%;", id="dkk-petr"),
    ],
)
def test_bar_width_is_derived_from_the_full_precision_net(
    person_row, currency_code, name, expected_style
):
    """The widest |net| bar is 50%; every other bar is its raw six-place ratio of that."""
    bar = person_row(currency_code, name).locator(".bal-bar i")

    expect(bar).to_have_attribute("style", expected_style)
