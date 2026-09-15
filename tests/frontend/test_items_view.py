"""Tests for views/Items.js, components/DayGroup.js and components/ItemRow.js.

One row per fixture item, in order; one owed chip per participating person, in
roster order, and a person with no share (`owed: null`) gets no chip at all;
`owed: 0` is a chip with a literal 0; labels as badges; country flag shown;
`empty.json` shows the empty state and the FAB; the day separator shows
`items.day_totals`, one chip per currency, hidden while a filter is active.
"""

import re

import pytest
from playwright.sync_api import expect

ROW = "a.list-group-item-action"

ITEM_NAMES = [
    "Dinner at Messinn",
    "Fuel — N1 Selfoss",
    "Blue Lagoon tickets",
    "Guesthouse Vík, 2 nights",
    "Layover lunch — Kastrup",
]

ZERO_SHARE_ITEM = {
    "id": 9999,
    "name": "Split with a zero share",
    "note": None,
    "occurred_at": "2026-09-14T19:30:00Z",
    "currency_code": "ISK",
    "currency_id": 1,
    "amount": 1000,
    "payer_id": 1,
    "country_id": 1,
    "labels": [],
    "map_url": None,
    "lat": None,
    "lon": None,
    "split": {
        "mode": "exact",
        "shares": [
            {"person_id": 1, "weight": "1", "owed": 0},
            {"person_id": 2, "weight": None, "owed": None},
            {"person_id": 3, "weight": None, "owed": None},
            {"person_id": 4, "weight": None, "owed": None},
        ],
    },
    "created_at": "2026-09-14T19:30:00Z",
    "updated_at": "2026-09-14T19:30:00Z",
}

# The fixture's day_totals in feed order; 40.5 EUR shows as 41, rounded up.
DAY_TOTAL_CHIPS = ["26,300 ISK", "41 EUR", "96,000 ISK", "480 DKK"]


@pytest.fixture
def zero_share_page(stub, open_trip):
    """Return the Items tab with GET items answering only ZERO_SHARE_ITEM and no day totals."""
    stub(
        "**/api/v1/trips/*/items",
        lambda request: (
            (200, {"items": [ZERO_SHARE_ITEM], "day_totals": []})
            if request.method == "GET"
            else None
        ),
    )
    return open_trip()


def test_one_row_per_item_in_fixture_order(shared_items_page):
    """Items render in the fixture's own order, one row each, across their day groups."""
    expect(shared_items_page.locator(f"{ROW} span.d-block.fw-semibold")).to_have_text(ITEM_NAMES)


def test_owed_chips_skip_people_with_no_share(shared_items_page):
    """A row shows one owed chip per participating person: three of the four on Blue Lagoon."""
    row = shared_items_page.locator(ROW, has_text="Blue Lagoon tickets")

    expect(row.locator(".owed span")).to_have_count(3)


# Blue Lagoon's third chip is Eva's: Bob has no share there and gets no chip.
@pytest.mark.parametrize(
    ("item_name", "position", "chip_text"),
    [
        pytest.param("Blue Lagoon tickets", 0, "P13.33 EUR", id="fraction"),
        pytest.param("Blue Lagoon tickets", 2, "E13.33 EUR", id="skips-null-share"),
        pytest.param("Dinner at Messinn", 1, "A4,600 ISK", id="whole-grouped"),
    ],
)
def test_owed_chip_shows_initial_share_and_currency(
    shared_items_page, item_name, position, chip_text
):
    """A chip shows the person's initial, their formatted share and the item's currency."""
    row = shared_items_page.locator(ROW, has_text=item_name)

    expect(row.locator(".owed span").nth(position)).to_have_text(chip_text)


def test_owed_zero_renders_as_a_zero_and_null_share_gets_no_chip(zero_share_page):
    """A share with owed: 0 is a chip with a literal 0; the three null shares render no chip."""
    chips = zero_share_page.locator(ROW, has_text="Split with a zero share").locator(".owed span")

    expect(chips).to_have_text(["P0 ISK"])


@pytest.mark.parametrize(
    ("item_name", "text"),
    [
        pytest.param("Dinner at Messinn", "🇮🇸 Iceland", id="iceland"),
        pytest.param("Layover lunch", "🇩🇰 Denmark", id="denmark"),
    ],
)
def test_item_row_shows_country_flag_with_name(shared_items_page, item_name, text):
    """A row shows its country's flag next to the country name, not the name alone."""
    expect(shared_items_page.locator(ROW, has_text=item_name)).to_contain_text(text)


def test_labels_render_as_badges(shared_items_page):
    """An item's labels each render as their own badge element, in item order."""
    row = shared_items_page.locator(ROW, has_text="Dinner at Messinn")

    expect(row.locator(".badge")).to_have_text(["food", "restaurant"])


@pytest.mark.parametrize("fixture_name", [pytest.param("empty.json", id="empty")], indirect=True)
def test_empty_trip_shows_empty_state_and_fab(items_page):
    """A trip with no items shows the empty-state text, and the FAB is still there."""
    expect(items_page.get_by_text("No expenses yet.")).to_be_visible()
    expect(items_page.locator(".fab")).to_be_attached()
    expect(items_page.locator(ROW)).to_have_count(0)


def test_day_separators_show_one_total_chip_per_currency_rounded_up(shared_items_page):
    """Each day separator renders `items.day_totals` as one chip per currency, whole units."""
    expect(shared_items_page.locator(".day-sep .num span")).to_have_text(DAY_TOTAL_CHIPS)


def test_day_totals_hidden_while_filtering(items_page):
    """A day total covers the whole day, so it disappears once a filter hides part of it."""
    items_page.get_by_placeholder("filter by name or label").fill("Dinner")

    expect(items_page.locator(".day-sep .num span")).to_have_count(0)


# --- wallets and transfers -------------------------------------------------


def test_feed_merges_items_and_transfers_by_occurred_at(items_page):
    """Transfers sit between items in the merged feed, sorted by occurred_at like items are.

    Fixture order (WALLETS.md §5): 42, T2, 41, 40, T1, 39, T3, 38.
    """
    rows = items_page.locator(ROW)
    kinds = [
        "transfer" if "transfer-row" in (cls or "") else "item"
        for cls in rows.evaluate_all("els => els.map(e => e.className)")
    ]
    assert kinds == ["item", "transfer", "item", "item", "transfer", "item", "transfer", "item"]


def test_transfer_row_shows_both_wallets_and_the_amount(items_page):
    """A transfer row names both wallets and shows the moved amount, muted."""
    row = items_page.locator(f"{ROW}.transfer-row").filter(has_text="Cash")

    expect(row.first).to_contain_text("Card")
    expect(row.first).to_contain_text("Cash")
    expect(row.first).to_contain_text("20,000 ISK")


def test_transfer_row_shows_both_sides_of_an_exchange(items_page):
    """An exchange's row shows both amounts and currencies, with an arrow between them, no rate."""
    row = items_page.locator(f"{ROW}.transfer-row", has_text="20 EUR")

    expect(row).to_contain_text("20 EUR")
    expect(row).to_contain_text("150 DKK")


def test_filter_matches_a_transfer_by_wallet_name(items_page):
    """Filtering by a wallet's name shows only the transfers naming it, no items."""
    items_page.get_by_placeholder("filter by name or label").fill("cash")

    rows = items_page.locator(ROW)
    expect(rows).to_have_count(2)
    expect(rows).to_have_class([re.compile("transfer-row"), re.compile("transfer-row")])


def test_item_row_shows_wallet_name_when_not_the_payers_default(items_page):
    """Dinner is paid from Petr's Cash, not his default Card, so the row names the wallet."""
    row = items_page.locator(ROW, has_text="Dinner at Messinn")

    expect(row).to_contain_text("Cash")


def test_item_row_hides_wallet_name_when_it_is_the_payers_default(items_page):
    """Fuel is paid from Bob's default Card, so no wallet name clutters the row."""
    row = items_page.locator(ROW, has_text="Fuel")

    expect(row.locator("small").first).not_to_contain_text("Card")
