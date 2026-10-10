"""Tests for views/Stays.js and components/StayModal.js, and the stay picker in the item form.

A card per stay: its dates and nights, where it is, the website link, and each
server per-night figure as the API sent it. The search box narrows the cards. The modal writes every
field, `null` for an emptied one. The item form's picker sends `stay_id` and fills
in the stay's country and city until the user sets them.
"""

import pytest
from playwright.sync_api import expect


@pytest.fixture
def stays_page(open_trip):
    """Return the page with the trip loaded on the Accommodation tab."""
    return open_trip("stays")


@pytest.fixture
def stay_card(stays_page):
    """Return the Guesthouse Vík card."""
    return stays_page.locator(".stay-card", has_text="Guesthouse Vík")


def test_stay_card_shows_dates_nights_place_and_link(stay_card):
    """The title carries the city; the card shows dates, nights, country and the website link."""
    expect(stay_card.locator(".card-header .stay-city")).to_have_text("Vík í Mýrdal")
    expect(stay_card).to_contain_text("13–15 Sep · 2 nights · 🇮🇸 Iceland")
    expect(stay_card.get_by_role("link", name="Website")).to_have_attribute(
        "href", "https://example.com/guesthouse-vik"
    )


def test_stay_card_renders_server_per_night_verbatim_without_a_total(stay_card):
    """The per-night figure is formatted as sent, never recomputed; no total or count shows."""
    expect(stay_card.locator(".card-body")).not_to_contain_text("96,000")
    expect(stay_card.locator(".stay-per-night")).to_have_text(["48,000 ISK per night"])
    expect(stay_card.locator(".card-body")).not_to_contain_text("1 expense")


def test_same_day_stay_shows_no_per_night_figure(fixture_data, open_trip):
    """A 0-night stay's `per_night: null` renders no figure at all."""
    stay = fixture_data["stays"]["stays"][0]
    stay.update(check_out=stay["check_in"], nights=0)
    stay["totals"][0]["per_night"] = None

    page = open_trip("stays")

    expect(page.locator(".stay-card")).to_have_count(1)
    expect(page.locator(".stay-per-night")).to_have_count(0)


def test_search_narrows_the_stays_by_city_and_reports_no_match(stays_page, stay_card):
    """Typing a city keeps the matching stay; a needle nothing matches shows the empty message."""
    search = stays_page.get_by_placeholder("filter by name, place or note")

    search.fill("mýrdal")
    expect(stay_card).to_be_visible()

    search.fill("nowhere")
    expect(stays_page.locator(".stay-card")).to_have_count(0)
    expect(stays_page.get_by_text("No accommodation matches.")).to_be_visible()


def test_editing_a_stay_patches_every_field_with_null_for_emptied_ones(
    stays_page, stay_card, count_requests
):
    """Emptying the booking link sends `url: null` alongside every other field."""
    stay_card.locator(".card-header").get_by_role("button", name="Edit").click()
    modal = stays_page.locator(".modal.show")
    # Bootstrap focuses the dialog once shown; a fill before that has its focus stolen mid-way.
    expect(modal).to_be_focused()
    modal.locator("#stay-url").fill("")
    patched = count_requests("*/stays/1", method="PATCH")

    modal.get_by_role("button", name="Save", exact=True).click()

    modal.wait_for(state="hidden")
    assert [request.post_data_json for request in patched] == [
        {
            "name": "Guesthouse Vík",
            "check_in": "2026-09-13",
            "check_out": "2026-09-15",
            "url": None,
            "country_id": 1,
            "city": "Vík í Mýrdal",
            "note": None,
            "map_url": None,
            "lat": "63.41870",
            "lon": "-19.00600",
        }
    ]


def test_picking_a_stay_keeps_a_city_the_user_typed(new_item_modal):
    """A city typed before the stay is picked survives the pick."""
    new_item_modal.locator('input[name="city"]').fill("Reykjavík")

    new_item_modal.locator("#item-stay").select_option("1")

    expect(new_item_modal.locator('input[name="city"]')).to_have_value("Reykjavík")


def test_detaching_an_item_from_its_stay_sends_null(open_edit_modal, count_requests):
    """Choosing None on an item grouped under a stay patches `stay_id: null`."""
    modal = open_edit_modal("Guesthouse Vík, 2 nights")
    expect(modal.locator("#item-stay")).to_have_value("1")
    modal.locator("#item-stay").select_option("")
    patched = count_requests("*/items/39", method="PATCH")

    modal.get_by_role("button", name="Save", exact=True).click()

    modal.wait_for(state="hidden")
    assert patched[0].post_data_json["stay_id"] is None


def test_item_row_names_its_stay(shared_items_page):
    """An item grouped under a stay shows the stay's name in its row."""
    row = shared_items_page.locator(".item-row", has_text="Guesthouse Vík, 2 nights")

    expect(row.locator(".item-stay")).to_have_text("Guesthouse Vík")
    expect(row.locator(".item-stay")).to_have_attribute("href", "/t/iceland-2026/stays#stay-1")


def test_stays_tab_costs_one_call(items_page, count_requests, open_tab):
    """Opening the tab after Items fetches only the stays report."""
    calls = count_requests("*/api/v1/*")

    open_tab("Accommodation")

    assert len(calls) == 1


def test_stay_card_lists_its_expenses_and_opens_one_for_editing(stays_page, stay_card):
    """The card lists the items grouped under it, and clicking one opens it in the edit form."""
    row = stay_card.locator(".item-row", has_text="Guesthouse Vík, 2 nights")
    expect(row).to_have_count(1)

    row.get_by_role("button", name="Edit").click()

    expect(stays_page.locator(".modal.show #item-stay")).to_have_value("1")
