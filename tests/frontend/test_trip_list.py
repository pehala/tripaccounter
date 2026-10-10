"""Tests for views/TripList.js and views/TripNew.js.

One card per trip from GET /trips, empty
state when there are none; TripNew posts the people/currencies/countries block
in one request and routes to the slug the stub returns.
"""

import pytest
from playwright.sync_api import expect

MINTED_TRIP = {"trip": {"id": 999, "slug": "new-trip-slug"}}
EXPECTED_BODY = {
    "name": "Norway 2027",
    "timezone": "UTC",
    "people": [{"name": "Petr"}],
    "currencies": [{"code": "NOK", "is_primary": True}],
    "countries": [{"name": "Norway"}],
}


@pytest.fixture
def no_trips(stub):
    """Answer GET /trips with an empty list."""
    stub("**/api/v1/trips", lambda request: (200, {"trips": []}), method="GET")


@pytest.fixture
def new_trip_form(page, mockserver):
    """Return the page on the new-trip form."""
    page.goto(f"{mockserver}/trips/new")
    return page


@pytest.fixture
def posted_trips(stub):
    """Answer POST /trips with a minted slug; return the recorded request bodies."""
    return stub("**/api/v1/trips", lambda request: (201, MINTED_TRIP), method="POST")


@pytest.fixture
def submitted_form(posted_trips, new_trip_form):
    """Fill one person, primary currency and country, submit; return the form."""
    new_trip_form.get_by_placeholder("Trip name", exact=True).fill("Norway 2027")
    new_trip_form.get_by_placeholder("Name", exact=True).first.fill("Petr")
    new_trip_form.get_by_placeholder("ISK", exact=True).fill("nok")
    new_trip_form.locator("#new-trip-currency-primary-0").check()
    new_trip_form.get_by_placeholder("Name", exact=True).nth(1).fill("Norway")
    with new_trip_form.expect_response(
        lambda response: response.request.method == "POST" and response.url.endswith("/trips")
    ):
        new_trip_form.get_by_role("button", name="Create trip").click()
    return new_trip_form


# --- trip list --------------------------------------------------------------------


def test_one_card_per_trip_from_the_trip_list(page, mockserver):
    """GET /trips renders one list-group-item per trip: name, date range and people count."""
    page.goto(f"{mockserver}/")

    cards = page.locator(".list-group-item-action")
    expect(cards).to_have_count(1)
    expect(cards.first).to_contain_text("Iceland 2026")
    expect(cards.first).to_contain_text("12–21 Sep")
    expect(cards.first).to_contain_text("4 people")


def test_empty_trip_list_shows_the_empty_state(no_trips, page, mockserver):
    """A GET /trips with no trips renders the empty-state text, not a blank list."""
    page.goto(f"{mockserver}/")

    expect(page.get_by_text("No trips yet.")).to_be_visible()
    expect(page.locator(".list-group-item-action")).to_have_count(0)


# --- new trip ---------------------------------------------------------------------


def test_submit_posts_people_currencies_and_countries(submitted_form, posted_trips):
    """Submitting posts one body with only the filled-in rows."""
    assert posted_trips == [EXPECTED_BODY]


def test_submit_routes_to_the_slug_the_server_minted(submitted_form, mockserver):
    """After a 201, the app routes to the trip page of the slug in the response."""
    expect(submitted_form).to_have_url(f"{mockserver}/t/new-trip-slug")
