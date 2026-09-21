"""Tests for views/Map.js.

An expense carrying lat/lon becomes a pin; one without simply is not on the map, and
the count line says how many of the trip's expenses made it. Expenses sharing a
coordinate share a pin, whose panel lists each of them with its own amount and opens
the edit modal — the panel never totals anything, because the frontend never sums
money (design/FRONTEND.md §4 rule 1).
"""

import pytest
from playwright.sync_api import expect

from tests.frontend.map.conftest import CONTROLS, FUEL_PIN, MESSINN_PIN, NEEDLE

# The canvas stops short of the viewport bottom by the page's own bottom padding plus
# the gap MapCanvas.js leaves; anything beyond that is height it failed to claim.
BOTTOM_GAP = 40

GEOMETRY = """() => {
  const canvas = document.querySelector('.map-canvas').getBoundingClientRect();
  const panel = document.querySelector('.card')?.getBoundingClientRect();
  return {
    height: Math.round(canvas.height),
    gap: Math.round(window.innerHeight - canvas.bottom),
    overflow: document.documentElement.scrollHeight - document.documentElement.clientHeight,
    canvas_top: Math.round(canvas.top),
    panel_bottom: panel ? Math.round(panel.bottom) : null,
  };
}"""


@pytest.fixture
def twin_map_page(serve_items, fixture_data, open_trip):
    """Return the Map tab served a second expense at Dinner at Messinn's exact coordinate."""
    items = fixture_data["items"]["items"]
    twin = {**items[0], "id": 99, "name": "Drinks at Messinn", "amount": 3200, "city": None}
    serve_items([*items, twin])

    return open_trip("map")


@pytest.fixture
def uncharted_map_page(serve_items, fixture_data, page, trip_url):
    """Return the Map tab served a trip whose every expense has null coordinates."""
    serve_items([{**item, "lat": None, "lon": None} for item in fixture_data["items"]["items"]])
    page.goto(f"{trip_url}/map")

    return page


def test_each_coordinate_on_the_trip_becomes_one_pin(shared_map_page):
    """Two of the fixture's five expenses carry lat/lon; the other three are not drawn."""
    expect(shared_map_page.locator("path.map-pin")).to_have_count(2)
    expect(shared_map_page.locator(MESSINN_PIN)).to_be_visible()
    expect(shared_map_page.locator(FUEL_PIN)).to_be_visible()


def test_count_line_states_how_many_expenses_reached_the_map(shared_map_page):
    """Coordinates are optional, so the tab says how many of the trip's expenses it placed."""
    expect(shared_map_page.get_by_text("2 expenses of 5 on the map")).to_be_visible()


def test_clicking_a_pin_lists_its_expense_and_marks_itself_selected(map_page):
    """A pin's panel names the place and shows that expense's own amount, and the pin marks up."""
    map_page.locator(MESSINN_PIN).click()

    panel = map_page.locator(".card")
    expect(panel.locator(".card-header")).to_contain_text("Reykjavík")
    expect(panel.locator(".list-group-item")).to_have_count(1)
    expect(panel.locator(".list-group-item")).to_contain_text("Dinner at Messinn")
    expect(panel.locator(".list-group-item")).to_contain_text("18,400 ISK")
    expect(map_page.locator(f"{MESSINN_PIN}.map-pin-on")).to_be_visible()


def test_expenses_at_one_coordinate_share_a_pin_that_lists_them_all(twin_map_page):
    """Two expenses at one place are one pin, whose panel lists both with their own amounts."""
    expect(twin_map_page.locator("path.map-pin")).to_have_count(2)

    twin_map_page.locator(MESSINN_PIN).click()

    rows = twin_map_page.locator(".card .list-group-item")
    expect(rows).to_have_count(2)
    expect(rows.nth(0)).to_contain_text("18,400 ISK")
    expect(rows.nth(1)).to_contain_text("3,200 ISK")


def test_panel_row_opens_that_expense_in_the_edit_modal(map_page):
    """A row in the panel is the same edit affordance the feed's row is."""
    map_page.locator(FUEL_PIN).click()
    map_page.locator(".card .list-group-item").click()

    modal = map_page.locator(".modal.show")
    modal.wait_for()
    expect(modal.locator('input[name="name"]')).to_have_value("Fuel — N1 Selfoss")


def test_canvas_fills_the_space_left_below_it(map_page):
    """The map ends where the viewport does, so opening the tab needs no scrolling."""
    geometry = map_page.evaluate(GEOMETRY)

    assert 0 <= geometry["gap"] <= BOTTOM_GAP
    assert geometry["overflow"] == 0


def test_selecting_a_pin_puts_its_expenses_above_the_map(map_page):
    """The panel opens above the canvas, and the canvas gives up the height it needs."""
    before = map_page.evaluate(GEOMETRY)

    map_page.locator(MESSINN_PIN).click()
    expect(map_page.locator(".card")).to_be_visible()
    after = map_page.evaluate(GEOMETRY)

    assert after["panel_bottom"] <= after["canvas_top"]
    assert after["height"] < before["height"]
    assert 0 <= after["gap"] <= BOTTOM_GAP
    assert after["overflow"] == 0


def test_canvas_follows_a_viewport_resize(map_page):
    """A shorter window is a shorter map, not a scrollbar — down to the canvas's floor."""
    tall = map_page.evaluate(GEOMETRY)

    map_page.set_viewport_size({"width": 1000, "height": 620})
    map_page.wait_for_function(
        "height => document.querySelector('.map-canvas').getBoundingClientRect().height < height",
        arg=tall["height"],
    )
    short = map_page.evaluate(GEOMETRY)

    assert 0 <= short["gap"] <= BOTTOM_GAP
    assert short["overflow"] == 0


@pytest.mark.parametrize(
    ("zoom_in", "id"),
    [
        pytest.param(lambda page: page.locator(MESSINN_PIN).click(), "click-the-selected-pin"),
        pytest.param(
            lambda page: page.get_by_role("button", name="Zoom to this place").click(),
            "panel-button",
        ),
    ],
)
def test_zooming_in_on_a_selected_pin_goes_to_street_level(map_page, zoom_in, id):
    """A pin is a place: once it is selected, either affordance goes the whole way in.

    A double-click cannot do this job — the first click opens the panel, which shifts
    the map down, so the second click lands on empty map. The tile requests are what
    say which zoom actually got loaded.
    """
    map_page.locator(MESSINN_PIN).click()
    expect(map_page.locator(".card")).to_be_visible()

    with map_page.expect_request(lambda request: "tile.openstreetmap.org/18/" in request.url):
        zoom_in(map_page)

    centres = map_page.evaluate("""() => {
      const canvas = document.querySelector('.map-canvas').getBoundingClientRect();
      const pin = document.querySelector('[data-pin]').getBoundingClientRect();
      return {
        x: Math.round(Math.abs((pin.left + pin.right) / 2 - (canvas.left + canvas.right) / 2)),
        y: Math.round(Math.abs((pin.top + pin.bottom) / 2 - (canvas.top + canvas.bottom) / 2)),
      };
    }""")
    assert centres["x"] <= 2
    assert centres["y"] <= 2


def test_folding_the_controls_away_gives_the_map_their_space(map_page):
    """Folding filters and selection away is how the map gets the rest of the page."""
    before = map_page.evaluate(GEOMETRY)

    map_page.get_by_role("button", name=CONTROLS).click()
    expect(map_page.get_by_placeholder(NEEDLE)).to_be_hidden()

    after = map_page.evaluate(GEOMETRY)
    assert after["height"] > before["height"]
    assert 0 <= after["gap"] <= BOTTOM_GAP
    expect(map_page.get_by_text("2 expenses of 5 on the map")).to_be_visible()


def test_picking_a_pin_unfolds_the_controls(map_page):
    """Its expenses live in the folded section, so picking a pin has to open it again."""
    map_page.get_by_role("button", name=CONTROLS).click()
    expect(map_page.get_by_placeholder(NEEDLE)).to_be_hidden()

    map_page.locator(MESSINN_PIN).click()

    expect(map_page.locator(".card .list-group-item")).to_contain_text("Dinner at Messinn")


def test_clicking_the_map_background_closes_the_panel(map_page):
    """The panel is a selection, not a mode: clicking off the pin drops it."""
    map_page.locator(MESSINN_PIN).click()
    expect(map_page.locator(".card")).to_be_visible()

    map_page.locator(".map-canvas").click(position={"x": 5, "y": 5})

    expect(map_page.locator(".card")).to_have_count(0)


def test_trip_with_no_coordinates_renders_the_empty_state_not_a_blank_map(uncharted_map_page):
    """With nothing to place, the tab says so instead of drawing an empty world map."""
    empty = uncharted_map_page.get_by_text("No expense on this trip has coordinates yet.")

    expect(empty).to_be_visible()
    expect(uncharted_map_page.locator(".map-canvas")).to_have_count(0)
