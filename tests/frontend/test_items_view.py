"""Tests for views/Items.js, components/DayGroup.js and components/ItemRow.js.

One row per fixture item, in order; one owed chip per participating person, in
roster order, and a person with no share (`owed: null`) gets no chip at all;
`owed: 0` is a chip with a literal 0; labels as badges; country flag shown;
`empty.json` shows the empty state and the FAB; the day separator shows
`items.day_totals`, one chip per currency, hidden while a filter is active;
items dated before the trip's start date merge into one "Before the trip"
group, its total chip from the separate `items.before_trip_totals`.
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

# The fixture's day_totals in feed order; 40.5 EUR shows as 41, rounded up.
DAY_TOTAL_CHIPS = ["26,300 ISK", "41 EUR", "96,000 ISK", "480 DKK"]


@pytest.fixture
def zero_share_item(fixture_data):
    """Return Dinner at Messinn re-split exactly: Petr owes 0, the other three have no share."""
    return {
        **fixture_data["items"]["items"][0],
        "id": 9999,
        "name": "Split with a zero share",
        "split": {
            "mode": "exact",
            "shares": [
                {"person_id": 1, "weight": "1", "owed": 0},
                *({"person_id": pid, "weight": None, "owed": None} for pid in (2, 3, 4)),
            ],
        },
    }


@pytest.fixture
def before_trip_page(serve_items, zero_share_item, open_trip):
    """Return the Items tab served two items from before the 2026-09-12 start."""
    serve_items(
        [
            {**zero_share_item, "id": 9998, "occurred_at": "2026-09-10T08:00:00Z"},
            {**zero_share_item, "id": 9997, "occurred_at": "2026-09-11T20:00:00Z"},
        ],
        day_totals=[],
        transfers=[],
        before_trip_totals=[{"currency_code": "ISK", "currency_id": 1, "amount": 2000}],
    )
    return open_trip()


def test_one_row_per_item_in_fixture_order(shared_items_page):
    """Items render in the fixture's own order, one row each, across their day groups."""
    expect(shared_items_page.locator(f"{ROW} span.d-block.fw-semibold")).to_have_text(ITEM_NAMES)


@pytest.mark.parametrize(
    ("item_name", "chips"),
    [
        pytest.param(
            "Blue Lagoon tickets",
            ["P13.33 EUR", "A13.33 EUR", "E13.33 EUR"],
            id="fraction-skips-null-share",
        ),
        pytest.param(
            "Dinner at Messinn",
            ["P4,600 ISK", "A4,600 ISK", "B4,600 ISK", "E4,600 ISK"],
            id="whole-grouped",
        ),
    ],
)
def test_owed_chips_show_initial_share_and_currency(shared_items_page, item_name, chips):
    """One chip per participating person: initial, formatted share, currency; no share, no chip."""
    row = shared_items_page.locator(ROW, has_text=item_name)

    expect(row.locator(".owed span")).to_have_text(chips)


def test_owed_zero_renders_as_a_zero_and_null_share_gets_no_chip(
    serve_items, zero_share_item, open_trip
):
    """A share with owed: 0 is a chip with a literal 0; the three null shares render no chip."""
    serve_items([zero_share_item], day_totals=[], transfers=[])
    page = open_trip()

    chips = page.locator(ROW, has_text="Split with a zero share").locator(".owed span")
    expect(chips).to_have_text(["P0 ISK"])


@pytest.mark.parametrize(
    ("item_name", "meta"),
    [
        pytest.param("Dinner at Messinn", r"^🇮🇸 Iceland · Reykjavík · \d", id="with-city"),
        pytest.param("Fuel — N1 Selfoss", r"^🇮🇸 Iceland · \d", id="no-city"),
        pytest.param("Layover lunch", r"^🇩🇰 Denmark · \d", id="other-country"),
    ],
)
def test_item_row_meta_line_is_flag_country_city_then_time(shared_items_page, item_name, meta):
    """A row reads flag and country, then its city if it has one, then the time."""
    row = shared_items_page.locator(ROW, has_text=item_name)

    expect(row.locator("small").first).to_have_text(re.compile(meta))


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


def test_items_before_trip_start_share_one_group_with_its_own_total(before_trip_page):
    """Items before the start share one "Before the trip" group showing `before_trip_totals`."""
    expect(before_trip_page.locator(".day-sep")).to_have_count(1)
    expect(before_trip_page.locator(".day-sep small").first).to_have_text("Before the trip")
    expect(before_trip_page.locator(".day-sep .num span")).to_have_text(["2,000 ISK"])
    expect(before_trip_page.locator(ROW)).to_have_count(2)


# --- wallets and transfers -------------------------------------------------


def test_feed_merges_items_and_transfers_by_occurred_at(shared_items_page):
    """Transfers sit between items in the merged feed, sorted by occurred_at like items are.

    Fixture order (WALLETS.md §5): 42, T2, 41, 40, T1, 39, T3, 38.
    """
    rows = shared_items_page.locator(ROW)
    kinds = [
        "transfer" if "transfer-row" in (cls or "") else "item"
        for cls in rows.evaluate_all("els => els.map(e => e.className)")
    ]
    assert kinds == ["item", "transfer", "item", "item", "transfer", "item", "transfer", "item"]


@pytest.mark.parametrize(
    ("has_text", "shown"),
    [
        pytest.param("20,000 ISK", ["Card", "Cash", "20,000 ISK"], id="between-wallets"),
        pytest.param("20 EUR", ["20 EUR", "150 DKK"], id="exchange-both-sides"),
    ],
)
def test_transfer_row_shows_its_wallets_and_amounts(shared_items_page, has_text, shown):
    """A transfer row names both wallets and the moved amount; an exchange shows both sides."""
    row = shared_items_page.locator(f"{ROW}.transfer-row", has_text=has_text)

    for text in shown:
        expect(row).to_contain_text(text)


def test_filter_matches_a_transfer_by_wallet_name(items_page):
    """Filtering by a wallet's name shows only the transfers naming it, no items."""
    items_page.get_by_placeholder("filter by name or label").fill("cash")

    rows = items_page.locator(ROW)
    expect(rows).to_have_class([re.compile("transfer-row"), re.compile("transfer-row")])


def test_item_row_shows_wallet_name_when_not_the_payers_default(shared_items_page):
    """Dinner is paid from Petr's Cash, not his default Card, so the row names the wallet."""
    expect(shared_items_page.locator(ROW, has_text="Dinner at Messinn")).to_contain_text("Cash")


def test_item_row_hides_wallet_name_when_it_is_the_payers_default(shared_items_page):
    """Fuel is paid from Bob's default Card, so no wallet name clutters the row."""
    row = shared_items_page.locator(ROW, has_text="Fuel")

    expect(row.locator("small").first).not_to_contain_text("Card")
