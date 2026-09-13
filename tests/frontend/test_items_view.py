"""Tests for views/Items.js, components/DayGroup.js and components/ItemRow.js.

One row per fixture item, in order; one owed chip per participating person, in
roster order, and a person with no share (`owed: null`) gets no chip at all;
labels as badges; country flag shown; `empty.json` shows the empty state and the
FAB; the day separator shows `items.day_totals`, one chip per currency.
"""

from playwright.sync_api import expect


def test_one_row_per_item_in_fixture_order(page, mockserver, trip_url, fixture_data):
    """Items render in the fixture's own order, one row each, across their day groups."""
    page.goto(trip_url)
    items = fixture_data["items"]["items"]

    rows = page.locator("a.list-group-item-action")
    expect(rows).to_have_count(len(items))
    for i, item in enumerate(items):
        expect(rows.nth(i)).to_contain_text(item["name"])


def test_owed_chips_skip_people_with_no_share(page, mockserver, trip_url, fixture_data):
    """A row shows one owed chip per participating person; no chip for a null share."""
    page.goto(trip_url)
    trip = fixture_data["trip"]["trip"]
    blue_lagoon = next(
        i for i in fixture_data["items"]["items"] if i["name"] == "Blue Lagoon tickets"
    )
    participants = [
        person
        for person in trip["people"]
        if next(s["owed"] for s in blue_lagoon["split"]["shares"] if s["person_id"] == person["id"])
        is not None
    ]

    row = page.locator("a.list-group-item-action", has_text="Blue Lagoon tickets")
    chips = row.locator(".owed span")
    expect(chips).to_have_count(len(participants))
    assert len(participants) < len(trip["people"])


def test_owed_zero_renders_as_a_zero_and_null_share_gets_no_chip(
    page, mockserver, trip_url, stub, fixture_data
):
    """A share with owed: 0 renders a chip with a literal 0; a null share renders no chip."""
    trip = fixture_data["trip"]["trip"]
    zeroed_item = {
        **fixture_data["items"]["items"][0],
        "id": 9999,
        "name": "Split with a zero share",
        "split": {
            "mode": "exact",
            "shares": [
                {"person_id": trip["people"][0]["id"], "weight": "1", "owed": 0},
                *({"person_id": p["id"], "weight": None, "owed": None} for p in trip["people"][1:]),
            ],
        },
    }
    stub(
        "**/api/v1/trips/*/items",
        lambda request: (
            (200, {"items": [zeroed_item], "day_totals": []}) if request.method == "GET" else None
        ),
    )

    page.goto(trip_url)
    row = page.locator("a.list-group-item-action", has_text="Split with a zero share")
    chips = row.locator(".owed span")
    expect(chips).to_have_count(1)
    expect(chips.first).to_contain_text("0")


def test_labels_render_as_badges(page, mockserver, trip_url):
    """An item's labels each render as their own badge element."""
    page.goto(trip_url)
    row = page.locator("a.list-group-item-action", has_text="Dinner at Messinn")

    badges = row.locator(".badge")
    expect(badges).to_have_count(2)
    expect(badges.nth(0)).to_have_text("food")
    expect(badges.nth(1)).to_have_text("restaurant")


def test_country_flag_shown(page, mockserver, trip_url):
    """A row shows its item's country flag, not just the name."""
    page.goto(trip_url)

    expect(page.locator("a.list-group-item-action", has_text="Dinner at Messinn")).to_contain_text(
        "🇮🇸 Iceland"
    )
    expect(page.locator("a.list-group-item-action", has_text="Layover lunch")).to_contain_text(
        "🇩🇰 Denmark"
    )


def test_empty_trip_shows_empty_state_and_fab(page, make_mockserver):
    """A trip with no items shows the empty-state text, and the FAB is still there."""
    base_url, fixture = make_mockserver("empty.json")
    page.goto(f"{base_url}/t/{fixture['trip']['trip']['slug']}")

    expect(page.get_by_text("No expenses yet.")).to_be_visible()
    expect(page.locator(".fab")).to_be_attached()
    assert page.locator("a.list-group-item-action").count() == 0


def test_day_separator_shows_day_totals_rounded_up_to_a_whole_unit(page, mockserver, trip_url):
    """The day separator renders `items.day_totals`, one chip per currency, rounded up."""
    page.goto(trip_url)

    day_seps = page.locator(".day-sep")
    expect(day_seps).to_have_count(3)  # three distinct days in the fixture
    expect(day_seps.nth(0)).to_contain_text("26,300 ISK")
    expect(day_seps.nth(0)).to_contain_text("41 EUR")  # fixture has 40.5, rounded up
    expect(day_seps.nth(1)).to_contain_text("96,000 ISK")
    expect(day_seps.nth(2)).to_contain_text("480 DKK")


def test_day_totals_hidden_while_filtering(page, mockserver, trip_url):
    """A day total covers the whole day, so it disappears once a filter hides part of it."""
    page.goto(trip_url)
    page.locator("input[placeholder]").fill("Dinner")

    expect(page.locator(".day-sep").first).not_to_contain_text("ISK")
