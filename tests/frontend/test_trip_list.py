"""Tests for views/TripList.js and views/TripNew.js.

One card per trip from GET /trips, empty
state when there are none; TripNew posts the people/currencies/countries block
plus the ticked starter labels in one request and routes to the slug the stub
returns; the starter set is the same six words in en and cs (labels are data, not
UI text) and unticking one drops it from the body.
"""

import pytest
from playwright.sync_api import expect

STARTER_LABELS = ["food", "lodging", "transport", "fun", "groceries", "drinks"]
MINTED_TRIP = {"trip": {"id": 999, "slug": "new-trip-slug"}}
EXPECTED_BODY = {
    "name": "Norway 2027",
    "people": [{"name": "Petr"}],
    "currencies": [{"code": "NOK", "is_primary": True}],
    "countries": [{"name": "Norway"}],
    "labels": ["food", "lodging", "transport", "fun", "groceries"],
}


@pytest.fixture
def no_trips(stub):
    """Answer GET /trips with an empty list."""
    stub(
        "**/api/v1/trips",
        lambda request: (200, {"trips": []}) if request.method == "GET" else None,
    )


@pytest.fixture
def new_trip_form(page, mockserver):
    """Return the page on the new-trip form."""
    page.goto(f"{mockserver}/trips/new")
    return page


@pytest.fixture
def czech_new_trip_form(new_trip_form):
    """Return the new-trip form with the UI switched to Czech in place."""
    new_trip_form.evaluate("async () => (await import('/js/i18n/index.js')).setLocale('cs')")
    expect(new_trip_form.locator("html")).to_have_attribute("lang", "cs")
    return new_trip_form


@pytest.fixture
def posted_trips(stub):
    """Answer POST /trips with a minted slug; return the recorded request bodies."""
    return stub(
        "**/api/v1/trips",
        lambda request: (201, MINTED_TRIP) if request.method == "POST" else None,
    )


@pytest.fixture
def submitted_form(posted_trips, new_trip_form):
    """Fill one person, primary currency and country, untick drinks, submit; return the form."""
    new_trip_form.get_by_placeholder("Trip name", exact=True).fill("Norway 2027")
    new_trip_form.get_by_placeholder("Name", exact=True).first.fill("Petr")
    new_trip_form.get_by_placeholder("ISK", exact=True).fill("nok")
    new_trip_form.locator("#new-trip-currency-primary-0").check()
    new_trip_form.get_by_placeholder("Name", exact=True).nth(1).fill("Norway")
    new_trip_form.locator("#starter-label-drinks").uncheck()
    with new_trip_form.expect_response(
        lambda response: response.request.method == "POST" and response.url.endswith("/trips")
    ):
        new_trip_form.get_by_role("button", name="Create trip").click()
    return new_trip_form


# --- trip list --------------------------------------------------------------------


def test_one_card_per_trip_from_the_trip_list(page, mockserver):
    """GET /trips renders one list-group-item per trip, name and people count shown."""
    page.goto(f"{mockserver}/")

    cards = page.locator(".list-group-item-action")
    expect(cards).to_have_count(1)
    expect(cards.first).to_contain_text("Iceland 2026")
    expect(cards.first).to_contain_text("4 people")


def test_trip_card_shows_its_date_range(page, mockserver):
    """A trip's start_date/end_date render as a same-month range on its card."""
    page.goto(f"{mockserver}/")

    expect(page.locator(".list-group-item-action").first).to_contain_text("12–21 Sep")


def test_empty_trip_list_shows_the_empty_state(no_trips, page, mockserver):
    """A GET /trips with no trips renders the empty-state text, not a blank list."""
    page.goto(f"{mockserver}/")

    expect(page.get_by_text("No trips yet.")).to_be_visible()
    expect(page.locator(".list-group-item-action")).to_have_count(0)


# --- new trip ---------------------------------------------------------------------


def test_starter_labels_are_the_same_english_words_regardless_of_locale(czech_new_trip_form):
    """Starter label checkboxes show exactly the six literal English words with the UI in Czech."""
    labels = czech_new_trip_form.locator("label[for^='starter-label-']")

    assert labels.all_inner_texts() == STARTER_LABELS


def test_submit_posts_people_currencies_countries_and_ticked_labels(submitted_form, posted_trips):
    """Submitting posts one body with only the filled-in rows and the ticked starter labels."""
    assert posted_trips == [EXPECTED_BODY]


def test_submit_routes_to_the_slug_the_server_minted(submitted_form, mockserver):
    """After a 201, the app routes to the trip page of the slug in the response."""
    expect(submitted_form).to_have_url(f"{mockserver}/t/new-trip-slug")
