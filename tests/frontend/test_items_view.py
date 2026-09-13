"""Tests for views/Items.js, components/DayGroup.js and components/ItemRow.js.

One row per fixture item, in order; one
owed chip per person in roster order; `owed: null` renders a dash while `owed: 0`
renders a zero; the split phrase matches the mode; labels as badges; country
flag shown; `empty.json` shows the empty state and the FAB; no per-day subtotal
element exists.
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


def test_owed_chips_in_roster_order_with_dash_for_null(page, mockserver, trip_url, fixture_data):
    """Each row shows one owed chip per person, in roster order; a null share is a dash."""
    page.goto(trip_url)
    trip = fixture_data["trip"]["trip"]
    blue_lagoon = next(
        i for i in fixture_data["items"]["items"] if i["name"] == "Blue Lagoon tickets"
    )

    row = page.locator("a.list-group-item-action", has_text="Blue Lagoon tickets")
    chips = row.locator(".owed span")
    expect(chips).to_have_count(len(trip["people"]))

    for i, person in enumerate(trip["people"]):
        share = next(
            (s for s in blue_lagoon["split"]["shares"] if s["person_id"] == person["id"]), None
        )
        if share is None or share["owed"] is None:
            expect(chips.nth(i)).to_contain_text("—")
        else:
            expect(chips.nth(i)).to_be_visible()


def test_owed_zero_renders_as_a_zero_not_a_dash(page, mockserver, trip_url, stub, fixture_data):
    """A share present with owed: 0 renders a literal 0, distinct from owed: null's dash."""
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
        lambda request: (200, {"items": [zeroed_item]}) if request.method == "GET" else None,
    )

    page.goto(trip_url)
    row = page.locator("a.list-group-item-action", has_text="Split with a zero share")
    chips = row.locator(".owed span")
    expect(chips.first).to_contain_text("0")
    expect(chips.first).not_to_contain_text("—")
    expect(chips.nth(1)).to_contain_text("—")


def test_split_phrase_matches_the_mode(page, mockserver, trip_url):
    """Each row's split phrase reflects its own mode and weights, not a generic label."""
    page.goto(trip_url)

    expect(page.locator("a.list-group-item-action", has_text="Dinner at Messinn")).to_contain_text(
        "equally, 4 ways"
    )
    expect(
        page.locator("a.list-group-item-action", has_text="Blue Lagoon tickets")
    ).to_contain_text("equally, 3 of 4")
    expect(page.locator("a.list-group-item-action", has_text="Guesthouse Vík")).to_contain_text(
        "shares 1·1·1·0.5"
    )


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


def test_no_per_day_subtotal_element_exists(page, mockserver, trip_url):
    """A day separator carries only its date label — no computed per-day total."""
    page.goto(trip_url)

    day_seps = page.locator(".day-sep")
    expect(day_seps).to_have_count(3)  # three distinct days in the fixture
    for i in range(3):
        text = day_seps.nth(i).inner_text()
        assert "ISK" not in text
        assert "EUR" not in text
        assert "DKK" not in text
