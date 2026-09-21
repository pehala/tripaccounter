"""Tests for the map tab's filters (components/MapFilters.js).

Three filters narrow the same set of pins: the feed's own needle over name and
labels, label chips that OR together, and a date range over occurred_at. They
compose, they are undone by Clear, and a filter that matches nothing says so rather
than leaving an empty map to be read as "no coordinates".
"""

import pytest
from playwright.sync_api import expect

from tests.frontend.map.conftest import FUEL_PIN, MESSINN_PIN, NEEDLE

PARKING_PIN = '[data-pin="63.99790,-22.56280"]'


@pytest.fixture
def dated_map_page(serve_items, fixture_data, open_trip):
    """Return the Map tab served a third placed expense, on an earlier day of the trip.

    trip.json's two placed expenses fall on one day, so a date range has nothing to
    tell apart until this one is added.
    """
    items = fixture_data["items"]["items"]
    earlier = {
        **items[0],
        "id": 99,
        "name": "Harbour parking",
        "occurred_at": "2026-09-12T08:15:00Z",
        "city": "Keflavík",
        "lat": "63.99790",
        "lon": "-22.56280",
        "labels": ["transport"],
    }
    serve_items([*items, earlier])

    return open_trip("map")


@pytest.mark.parametrize(
    ("needle", "expected"),
    [
        pytest.param("messinn", [MESSINN_PIN], id="name"),
        pytest.param("restaurant", [MESSINN_PIN], id="label"),
        pytest.param("n1", [FUEL_PIN], id="name-of-the-other"),
        pytest.param("reykjavik", [], id="matches-nothing"),
    ],
)
def test_needle_keeps_only_the_pins_whose_expense_matches(map_page, needle, expected):
    """The search box reaches an expense's name and its labels, and nothing else."""
    map_page.get_by_placeholder(NEEDLE).fill(needle)

    expect(map_page.locator("path.map-pin")).to_have_count(len(expected))
    for pin in expected:
        expect(map_page.locator(pin)).to_be_visible()


def test_filter_matching_nothing_says_so_instead_of_showing_a_bare_map(map_page):
    """An empty map after filtering must not read as a trip without coordinates."""
    map_page.get_by_placeholder(NEEDLE).fill("reykjavik")

    expect(map_page.get_by_text("No expense matches these filters.")).to_be_visible()
    expect(map_page.get_by_text("0 expenses of 5 on the map")).to_be_visible()


def test_label_chip_narrows_to_that_label_and_toggling_it_off_restores(map_page):
    """A chip is a toggle, not a one-way choice: pressing it twice leaves every pin drawn."""
    chip = map_page.get_by_role("button", name="restaurant", exact=True)

    chip.click()
    expect(map_page.locator("path.map-pin")).to_have_count(1)
    expect(map_page.locator(MESSINN_PIN)).to_be_visible()
    expect(chip).to_have_attribute("aria-pressed", "true")

    chip.click()
    expect(map_page.locator("path.map-pin")).to_have_count(2)


def test_two_label_chips_are_an_or(map_page):
    """Chips widen the selection: an expense carrying either label stays on the map."""
    map_page.get_by_role("button", name="restaurant", exact=True).click()
    map_page.get_by_role("button", name="fuel", exact=True).click()

    expect(map_page.locator("path.map-pin")).to_have_count(2)


@pytest.mark.parametrize(
    ("from_day", "to_day", "expected"),
    [
        pytest.param("2026-09-13", "", [MESSINN_PIN, FUEL_PIN], id="from-excludes-the-earlier-day"),
        pytest.param("", "2026-09-13", [PARKING_PIN], id="to-excludes-the-later-day"),
        pytest.param("2026-09-12", "2026-09-12", [PARKING_PIN], id="one-day-range"),
    ],
)
def test_date_range_keeps_the_expenses_that_fall_inside_it(
    dated_map_page, from_day, to_day, expected
):
    """Each bound is inclusive and either one may be left empty to mean unbounded."""
    dated_map_page.get_by_label("From").fill(from_day)
    dated_map_page.get_by_label("To").fill(to_day)

    expect(dated_map_page.locator("path.map-pin")).to_have_count(len(expected))
    for pin in expected:
        expect(dated_map_page.locator(pin)).to_be_visible()


def test_clear_undoes_every_filter_at_once(dated_map_page):
    """Clear appears once anything is filtering and puts every pin back in one click."""
    dated_map_page.get_by_placeholder(NEEDLE).fill("parking")
    dated_map_page.get_by_label("From").fill("2026-09-12")
    expect(dated_map_page.locator("path.map-pin")).to_have_count(1)

    dated_map_page.get_by_role("button", name="Clear filters").click()

    expect(dated_map_page.locator("path.map-pin")).to_have_count(3)
    expect(dated_map_page.get_by_placeholder(NEEDLE)).to_have_value("")
