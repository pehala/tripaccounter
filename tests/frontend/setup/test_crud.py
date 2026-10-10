"""Tests for views/Setup.js: people/currencies/countries/labels/wallets add and rename.

Deleting (confirmation, in-use refusals) lives in `test_delete.py`.
"""

import pytest
from playwright.sync_api import expect


@pytest.mark.parametrize(
    ("header", "row_selector", "fields", "shown"),
    [
        pytest.param("People", "li", [("Name", "Zoe")], "Zoe", id="people"),
        pytest.param(
            "Currencies", "li", [("ISK", "usd"), ("symbol (optional)", "$")], "USD", id="currencies"
        ),
        pytest.param("Countries", "li", [("Name", "Norway")], "Norway", id="countries"),
        pytest.param("Labels", ".badge", [("Label", "snacks")], "snacks", id="labels"),
        pytest.param("Wallets", "li", [("Name", "Backpack")], "Backpack", id="wallets"),
    ],
)
def test_add(setup_card, header, row_selector, fields, shown):
    """Filling the add form and saving appends a row showing the value, currency code upcased."""
    section = setup_card(header)
    section.get_by_role("button", name="+ Add").click()
    for placeholder, value in fields:
        section.get_by_placeholder(placeholder, exact=True).fill(value)

    section.get_by_role("button", name="Save", exact=True).click()

    expect(section.locator(row_selector).last).to_contain_text(shown)


@pytest.mark.parametrize(
    ("header", "row_selector", "current", "renamed"),
    [
        pytest.param("People", "li", "Petr", "Petr Renamed", id="people"),
        pytest.param("Currencies", "li", "€", "euro", id="currencies"),
        pytest.param("Countries", "li", "Iceland", "Ísland", id="countries"),
        pytest.param("Labels", ".badge", "drinks", "beer", id="labels"),
        pytest.param("Wallets", "li", "Envelope", "Purse", id="wallets"),
    ],
)
def test_rename(setup_card, header, row_selector, current, renamed):
    """Clicking a row's text opens an inline input; saving shows the new text on that row."""
    section = setup_card(header)
    row = section.locator(row_selector).filter(has_text=current)
    row.get_by_text(current).click()
    section.locator("input").fill(renamed)

    section.get_by_role("button", name="Save", exact=True).click()

    expect(section.locator(row_selector).filter(has_text=renamed)).to_have_count(1)


def test_trip_dates_edit_updates_the_shown_range(setup_card):
    """Editing the two date inputs and saving PATCHes both fields and shows the new range."""
    section = setup_card("Trip")
    section.get_by_text("12–21 Sep").click()
    inputs = section.locator('input[type="date"]')
    inputs.nth(0).fill("2026-09-10")
    inputs.nth(1).fill("2026-09-25")

    section.get_by_role("button", name="Save", exact=True).click()

    expect(section.get_by_text("10–25 Sep")).to_be_visible()


# --- wallets ----------------------------------------------------------------


def test_default_wallet_offers_no_delete(setup_card):
    """A person's default wallet (Card) never shows a Delete button - it can only fail."""
    card_row = setup_card("Wallets").locator("li").filter(has_text="Card").first

    expect(card_row.get_by_label("Delete")).to_have_count(0)


def test_untrack_then_track_flips_the_wallets_text_and_action(setup_card):
    """Untrack sends `PATCH {tracked: false}` and Track reverses it; the row's text follows."""
    row = setup_card("Wallets").locator("li").filter(has_text="Envelope")
    expect(row).to_contain_text("tracked")
    expect(row).not_to_contain_text("untracked")

    row.get_by_role("button", name="Untrack", exact=True).click()
    expect(row).to_contain_text("untracked")

    row.get_by_role("button", name="Track", exact=True).click()
    expect(row).to_contain_text("tracked")
    expect(row).not_to_contain_text("untracked")


def test_make_default_moves_the_default_flag(setup_card):
    """Make default on a non-default wallet promotes it; the old default loses its Delete-hiding."""
    row = setup_card("Wallets").locator("li").filter(has_text="Cash")

    row.get_by_role("button", name="Make default").click()

    expect(row).to_contain_text("default")
    expect(row.get_by_label("Delete")).to_have_count(0)
