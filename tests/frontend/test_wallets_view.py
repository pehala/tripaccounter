"""Tests for views/Wallets.js: one card per person, tracked wallet balances, overcharge.

Every wallet's tracked/untracked text, one row per `balances[]` entry (received ·
sent · spent, balance right-aligned), and `.text-danger` plus the overcharge
sentence on a negative balance - not on a positive one. A person's card ends in
their average exchange rates, one line per pair.
"""

from playwright.sync_api import expect


def test_one_card_per_person_with_wallets(shared_wallets_page):
    """Each of the four people gets their own card, named after them."""
    for name in ("Petr", "Ann", "Bob", "Eva"):
        expect(shared_wallets_page.locator(".card-header", has_text=name)).to_have_count(1)


def test_untracked_wallet_shows_no_figures(shared_wallets_page):
    """Every Card is untracked: it shows the untracked text and no balance row."""
    card_row = shared_wallets_page.locator("li.list-group-item").filter(has_text="Card").first
    expect(card_row).to_contain_text("untracked")
    expect(card_row.locator(".num")).to_have_count(0)


def test_overcharged_wallet_is_flagged_and_the_healthy_one_is_not(shared_wallets_page):
    """Ann's Envelope (spent more than it ever received) is flagged; Petr's Cash ISK row is not."""
    envelope_row = shared_wallets_page.locator("li.list-group-item").filter(has_text="Envelope")
    expect(envelope_row.locator(".text-danger").first).to_be_visible()
    expect(envelope_row).to_contain_text("Spent more than this wallet ever received.")

    cash_row = shared_wallets_page.locator("li.list-group-item").filter(has_text="Cash")
    isk_line = cash_row.locator("div", has_text="ISK").first
    expect(isk_line.locator(".text-danger")).to_have_count(0)


def test_tracked_wallet_shows_a_balance_row_per_currency(shared_wallets_page):
    """Petr's Cash touched three currencies, so it shows three balance rows."""
    cash_row = shared_wallets_page.locator("li.list-group-item").filter(has_text="Cash")
    expect(cash_row.locator(".num.fw-semibold")).to_have_count(3)
    expect(cash_row).to_contain_text("1,600 ISK")
    expect(cash_row).to_contain_text("-20 EUR")
    expect(cash_row).to_contain_text("150 DKK")


def test_person_card_lists_average_exchange_rates(open_trip):
    """Petr's card prices spent and leftover currency per pair; Ann never exchanged."""
    page = open_trip("wallets")

    petr_card = page.locator(".card").filter(has=page.locator(".card-header", has_text="Petr"))
    expect(petr_card.locator(".exchange-rate")).to_have_text(
        [
            "1 ISK = 0.007 EUR · 1,600 ISK left, bought at 1 ISK = 0.007 EUR",
            "EUR → DKK: nothing spent yet · 150 DKK left, bought at 1 DKK = 0.133333 EUR",
        ]
    )
    ann_card = page.locator(".card").filter(has=page.locator(".card-header", has_text="Ann"))
    expect(ann_card.locator(".exchange-rate")).to_have_count(0)


def test_wallets_tab_first_open_is_two_calls_revisit_is_none(items_page, count_requests, open_tab):
    """The Wallets tab is the report plus the exchange rates on first open, none on a revisit."""
    calls = count_requests("*/api/v1/*")

    open_tab("Wallets")
    expect(items_page.locator(".exchange-rate").first).to_be_visible()
    assert len(calls) == 2

    open_tab("Items")
    open_tab("Wallets")
    assert len(calls) == 2
