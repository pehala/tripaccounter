"""Tests for views/TripList.js and views/TripNew.js.

One card per trip from GET /trips, empty
state when there are none; TripNew posts the people/currencies/countries block
plus the ticked starter labels in one request and routes to the slug the stub
returns; the starter set is the same six words in en and cs (labels are data, not
UI text) and unticking one drops it from the body.
"""

from playwright.sync_api import expect

STARTER_LABELS = ["food", "lodging", "transport", "fun", "groceries", "drinks"]


def test_one_card_per_trip_from_the_trip_list(page, mockserver, fixture_data):
    """GET /trips renders one list-group-item per trip, name and people count shown."""
    page.goto(f"{mockserver}/")

    cards = page.locator(".list-group-item-action")
    expect(cards).to_have_count(1)
    trip = fixture_data["trip"]["trip"]
    expect(cards.first).to_contain_text(trip["name"])
    expect(cards.first).to_contain_text(f"{len(trip['people'])} people")


def test_empty_trip_list_shows_the_empty_state(page, mockserver, stub):
    """A GET /trips with no trips renders the empty-state text, not a blank list."""
    stub(
        "**/api/v1/trips",
        lambda request: (200, {"trips": []}) if request.method == "GET" else None,
    )

    page.goto(f"{mockserver}/")

    expect(page.get_by_text("No trips yet.")).to_be_visible()
    assert page.locator(".list-group-item-action").count() == 0


def test_starter_labels_are_the_same_english_words_regardless_of_locale(page, mockserver):
    """Starter label checkboxes show the literal English words even once the UI is in Czech."""
    page.goto(f"{mockserver}/trips/new")
    page.evaluate(
        """async () => {
            const { setLocale } = await import('/js/i18n/index.js');
            setLocale('cs');
        }"""
    )

    for word in STARTER_LABELS:
        expect(page.locator(f"label[for='starter-label-{word}']")).to_have_text(word)


def test_submit_posts_people_currencies_countries_and_ticked_labels_and_routes_to_the_slug(
    page, mockserver, stub
):
    """Submitting posts one body with only the filled-in rows and the ticked starter labels."""
    posted = stub(
        "**/api/v1/trips",
        lambda request: (
            (201, {"trip": {"id": 999, "slug": "new-trip-slug"}})
            if request.method == "POST"
            else None
        ),
    )

    page.goto(f"{mockserver}/trips/new")
    page.get_by_placeholder("Trip name", exact=True).fill("Norway 2027")
    page.get_by_placeholder("Name", exact=True).first.fill("Petr")
    page.get_by_placeholder("ISK", exact=True).fill("nok")
    page.locator("#new-trip-currency-primary-0").check()
    page.get_by_placeholder("Name", exact=True).nth(1).fill("Norway")
    page.locator("#starter-label-drinks").uncheck()

    page.get_by_role("button", name="Create trip").click()

    assert len(posted) == 1
    body = posted[0]
    assert body["name"] == "Norway 2027"
    assert body["people"] == [{"name": "Petr"}]
    assert body["currencies"] == [{"code": "NOK", "is_primary": True}]
    assert body["countries"] == [{"name": "Norway"}]
    assert set(body["labels"]) == set(STARTER_LABELS) - {"drinks"}
    assert len(body["labels"]) == 5

    expect(page).to_have_url(f"{mockserver}/t/new-trip-slug")
