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


def test_stay_card_renders_server_total_and_per_night_verbatim_on_one_line(stay_card):
    """The total and the per-night figure are formatted as sent, never recomputed, on one line."""
    cost = stay_card.locator(".stay-cost")

    expect(cost).to_have_count(1)
    expect(cost.locator(".stay-amount")).to_have_text("96,000 ISK")
    expect(cost.locator(".stay-per-night")).to_have_text("48,000 ISK per night")
    expect(stay_card.locator(".card-body")).not_to_contain_text("1 expense")


def test_same_day_stay_shows_no_per_night_figure(fixture_data, open_trip):
    """A 0-night stay's `per_night: null` renders no figure at all."""
    stay = fixture_data["stays"]["stays"][0]
    stay.update(check_out=stay["check_in"], nights=0)
    stay["totals"][0]["per_night"] = None

    page = open_trip("stays")

    expect(page.locator(".stay-card")).to_have_count(1)
    expect(page.locator(".stay-amount")).to_have_text(["96,000 ISK"])
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


def test_stay_date_pickers_are_limited_to_the_trip_dates(stays_page):
    """Both pickers stop at the trip's first and last day; check-out also starts at check-in."""
    stays_page.locator(".stays-content .btn-primary").click()
    modal = stays_page.locator(".modal.show")
    # Bootstrap focuses the dialog once shown; a fill before that has its focus stolen mid-way.
    expect(modal).to_be_focused()
    check_in = modal.locator("#stay-check-in")
    check_out = modal.locator("#stay-check-out")

    expect(check_in).to_have_attribute("min", "2026-09-12")
    expect(check_in).to_have_attribute("max", "2026-09-21")
    expect(check_out).to_have_attribute("min", "2026-09-12")
    expect(check_out).to_have_attribute("max", "2026-09-21")

    check_in.fill("2026-09-14")

    expect(check_out).to_have_attribute("min", "2026-09-14")


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


def test_stays_tab_costs_two_calls(items_page, count_requests, open_tab):
    """Opening the tab after Items fetches the stays and the exchange rates the Total offers."""
    calls = count_requests("*/api/v1/*")

    open_tab("Accommodation")
    expect(items_page.locator(".stay-card")).to_have_count(1)

    assert len(calls) == 2


@pytest.fixture
def settlement() -> dict | None:
    """Return the trip's `settlement`: open unless a test parametrizes one in."""
    return None


@pytest.fixture
def total_section(fixture_data, open_trip, settlement):
    """Return the opened Total section of a stay costing 48 000 ISK and 100 EUR per night.

    Tests read the card through `total_section.page`: asking for `stay_card` too would
    load the page a second time and close the section again.
    """
    fixture_data["stays"]["stays"][0]["totals"].append(
        {"currency_code": "EUR", "currency_id": 2, "amount": 200, "per_night": 100}
    )
    fixture_data["trip"]["trip"]["settlement"] = settlement
    page = open_trip("stays")
    section = page.locator("#stays-total")
    section.get_by_role("button", name="Total").click()
    expect(section.locator("#rates-target")).to_be_visible()
    return section


def test_stay_total_asks_for_every_rate_before_showing_a_figure(total_section):
    """Until each currency has a rate the card shows only its own currencies' figures."""
    expect(total_section).to_contain_text("Add a rate for every currency to see the total.")
    expect(total_section.page.locator(".stay-card .stay-cost")).to_have_count(2)
    expect(total_section.page.locator(".stay-card .stay-cost-total")).to_have_count(0)


def test_stay_total_sums_the_per_night_figures_at_the_typed_rates(total_section):
    """With every rate typed the card adds one total and per-night line in the target currency."""
    for code, rate in {"EUR": "150", "DKK": "20"}.items():
        row = total_section.locator(".row").filter(
            has=total_section.page.locator(".badge", has_text=code)
        )
        row.locator("input").fill(rate)
        row.locator("input").blur()

    converted = total_section.page.locator(".stay-card .stay-cost-total")
    expect(converted.locator(".stay-amount")).to_have_text("126,000 ISK")
    expect(converted.locator(".stay-per-night")).to_have_text("63,000 ISK per night")


@pytest.mark.parametrize(
    "settlement",
    [
        {
            "target_currency_id": 1,
            "settled_at": "2026-09-22T18:00:00Z",
            "rates": [{"currency_id": 2, "rate": 150}, {"currency_id": 3, "rate": 20}],
        }
    ],
)
def test_settled_stay_total_reads_the_stored_rates_read_only(total_section):
    """A settled trip's stay Total converts at the agreed rates, with nothing typed or typeable."""
    for code in ("EUR", "DKK"):
        row = total_section.locator(".row").filter(
            has=total_section.page.locator(".badge", has_text=code)
        )
        expect(row.locator("input")).to_have_attribute("readonly", "")

    converted = total_section.page.locator(".stay-card .stay-cost-total")
    expect(converted.locator(".stay-amount")).to_have_text("126,000 ISK")
