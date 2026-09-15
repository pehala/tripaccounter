"""Tests for views/Balances.js.

Currency is the top-level organizing unit: each currency gets its own heading,
and its two sections (net, settle-up) render in that order, collapsed by
default. A credit renders with a leading +, a debt with -, zero bare; six
places trim to two; suggestion rows follow the API's own order; bar widths are
derived from the full-precision net, the widest at 50%.
"""

import re

import pytest
from playwright.sync_api import expect


def expand(page, currency_id, group):
    """Open one balance section's collapse body, leaving an already-open one open."""
    body = page.locator(f"#sec-{currency_id}-{group}-body")
    if not body.is_visible():
        page.locator(f'[data-bs-target="#sec-{currency_id}-{group}-body"]').click()
    page.locator(f"#sec-{currency_id}-{group}-body.show").wait_for()


@pytest.fixture
def person_row(shared_balances_page, fixture_data):
    """Return `person_row(currency_code, name)`: that person's <li> in the net section."""
    currency_id_by_code = {
        b["currency_code"]: b["currency_id"] for b in fixture_data["balances"]["balances"]
    }

    def find(currency_code, name):
        expand(shared_balances_page, currency_id_by_code[currency_code], "net")
        return shared_balances_page.locator(
            f"#sec-{currency_id_by_code[currency_code]}-net-body li"
        ).filter(has_text=name)

    return find


@pytest.mark.parametrize(
    "currency_code",
    [
        pytest.param("ISK", id="isk"),
        pytest.param("EUR", id="eur"),
        pytest.param("DKK", id="dkk"),
    ],
)
def test_one_net_section_and_one_settle_up_section_per_currency(
    shared_balances_page, fixture_data, currency_code
):
    """Every currency in the fixture gets its own net section and settle-up section."""
    balance = next(
        b for b in fixture_data["balances"]["balances"] if b["currency_code"] == currency_code
    )
    section = shared_balances_page.locator(f"#cur-{balance['currency_id']}")

    titles = section.locator('[data-bs-toggle="collapse"]').all_inner_texts()
    assert "Balance" in titles[0]
    assert "Settle up" in titles[1]


@pytest.mark.parametrize(
    ("currency_code", "name", "expected"),
    [
        pytest.param("ISK", "Petr", "-15,603.57", id="isk-petr-debit"),
        pytest.param("ISK", "Ann", "-29,003.57", id="isk-ann-debit"),
        pytest.param("ISK", "Bob", "-31,103.57", id="isk-bob-debit"),
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
        pytest.param("ISK", [("Bob", "Eva"), ("Ann", "Eva"), ("Petr", "Eva")], id="isk"),
        pytest.param("EUR", [("Petr", "Ann"), ("Eva", "Ann")], id="eur"),
        pytest.param("DKK", [("Petr", "Ann"), ("Bob", "Ann"), ("Eva", "Ann")], id="dkk"),
    ],
)
def test_suggestion_rows_follow_the_api_order(
    shared_balances_page, fixture_data, currency_code, transfers
):
    """Settle-up rows render payer then payee in the API's own order, with no extra rows.

    Settle-up is open by default (unlike net), so no expand() click is needed.
    """
    balance = next(
        b for b in fixture_data["balances"]["balances"] if b["currency_code"] == currency_code
    )

    rows = shared_balances_page.locator(
        f"#sec-{balance['currency_id']}-settle_up-body ul.list-group-flush li"
    )

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


def test_net_is_collapsed_but_settle_up_is_open_by_default(balances_page, fixture_data):
    """The net section needs a click; settle-up — the figure worth seeing first — doesn't."""
    isk = next(b for b in fixture_data["balances"]["balances"] if b["currency_code"] == "ISK")

    net_body = balances_page.locator(f"#sec-{isk['currency_id']}-net-body")
    settle_up_body = balances_page.locator(f"#sec-{isk['currency_id']}-settle_up-body")
    expect(net_body).to_be_hidden()
    expect(settle_up_body).to_be_visible()

    expand(balances_page, isk["currency_id"], "net")
    expect(net_body).to_be_visible()


def test_sidebar_link_jumps_to_currency_section(balances_page, fixture_data):
    """Clicking a currency's sidebar link is a real anchor: it scrolls in and updates the hash."""
    eur = next(b for b in fixture_data["balances"]["balances"] if b["currency_code"] == "EUR")
    base_url = balances_page.url

    balances_page.locator(".side-nav a", has_text="EUR").click()

    expect(balances_page).to_have_url(f"{base_url}#cur-{eur['currency_id']}")
    expect(balances_page.locator(f"#cur-{eur['currency_id']}")).to_be_in_viewport()
