"""Tests for views/Setup.js: people/currencies/countries/labels CRUD, in-use delete.

People/currencies/countries/labels each add,
rename and delete; a stubbed in-use 409 with `{code: "in_use", params: {count: 4,
name: "Iceland"}}` renders "Iceland is used by 4 items." from the catalog; a
referenced person offers Deactivate (`PATCH {"active": false}`) instead of a
Delete that can only fail.
"""

import json
from pathlib import Path

from playwright.sync_api import expect

ERRORS = Path(__file__).parent / "fixtures" / "errors"


def open_setup(page, trip_url):
    """Navigate to the trip's Setup tab."""
    page.goto(f"{trip_url}#setup")


def card(page, header_text):
    """Return the Setup section card whose header contains `header_text`."""
    return page.locator(".card").filter(has=page.locator(".card-header", has_text=header_text))


def test_people_add_rename_and_delete(page, mockserver, trip_url):
    """Adding, renaming and deleting a person round-trips through the real mock.

    A row is located by its position (`.last`), not by name text: once renaming
    starts the name is only an <input> value, invisible to a has_text filter.
    """
    open_setup(page, trip_url)
    people_card = card(page, "People")

    people_card.get_by_role("button", name="+ Add").click()
    people_card.get_by_placeholder("Name").fill("Zoe")
    people_card.get_by_role("button", name="Save", exact=True).click()
    row = people_card.locator("li").last
    expect(row).to_contain_text("Zoe")

    row.get_by_text("Zoe", exact=True).click()
    row.locator("input").fill("Zoe Renamed")
    row.get_by_role("button", name="Save", exact=True).click()
    expect(row).to_contain_text("Zoe Renamed")

    row.get_by_label("Delete").click()
    expect(people_card.get_by_text("Zoe Renamed")).to_have_count(0)


def test_currencies_add_rename_and_delete(page, mockserver, trip_url):
    """Adding, renaming (symbol) and deleting a currency round-trips through the real mock."""
    open_setup(page, trip_url)
    currencies_card = card(page, "Currencies")

    currencies_card.get_by_role("button", name="+ Add").click()
    currencies_card.get_by_placeholder("ISK", exact=True).fill("usd")
    currencies_card.get_by_placeholder("symbol (optional)").fill("$")
    currencies_card.get_by_role("button", name="Save", exact=True).click()
    row = currencies_card.locator("li").last
    expect(row).to_contain_text("USD")

    row.get_by_text("$", exact=True).click()
    row.locator("input").fill("US$")
    row.get_by_role("button", name="Save", exact=True).click()
    expect(row).to_contain_text("US$")

    row.get_by_label("Delete").click()
    expect(currencies_card.get_by_text("USD")).to_have_count(0)


def test_countries_add_rename_and_delete(page, mockserver, trip_url):
    """Adding, renaming and deleting a country round-trips through the real mock."""
    open_setup(page, trip_url)
    countries_card = card(page, "Countries")

    countries_card.get_by_role("button", name="+ Add").click()
    countries_card.get_by_placeholder("Name").fill("Norway")
    countries_card.get_by_role("button", name="Save", exact=True).click()
    row = countries_card.locator("li").last
    expect(row).to_contain_text("Norway")

    row.get_by_text("Norway", exact=True).click()
    row.locator("input").fill("Norway (renamed)")
    row.get_by_role("button", name="Save", exact=True).click()
    expect(row).to_contain_text("Norway (renamed)")

    row.get_by_label("Delete").click()
    expect(countries_card.get_by_text("Norway (renamed)")).to_have_count(0)


def test_labels_add_rename_and_delete(page, mockserver, trip_url):
    """Adding, renaming and deleting a label round-trips through the real mock."""
    open_setup(page, trip_url)
    labels_card = card(page, "Labels")

    labels_card.get_by_role("button", name="+ Add").click()
    labels_card.get_by_placeholder("Label").fill("snacks")
    labels_card.get_by_role("button", name="Save", exact=True).click()
    chip = labels_card.locator(".badge").last
    expect(chip).to_contain_text("snacks")

    chip.get_by_text("snacks", exact=True).click()
    labels_card.locator("input").fill("snacks (renamed)")
    labels_card.get_by_role("button", name="Save", exact=True).click()
    expect(labels_card.locator(".badge").last).to_contain_text("snacks (renamed)")

    labels_card.locator(".badge").last.get_by_label("Remove").click()
    expect(labels_card.get_by_text("snacks (renamed)")).to_have_count(0)


def test_person_delete_in_use_renders_catalog_sentence_and_offers_deactivate_instead(
    page, mockserver, trip_url, stub
):
    """A 409 in_use on delete shows the catalog sentence and swaps Delete for Deactivate only."""
    body = json.loads((ERRORS / "409_in_use.json").read_text())
    deactivated = stub(
        "**/api/v1/trips/*/people/*",
        lambda request: (409, body) if request.method == "DELETE" else None,
    )

    open_setup(page, trip_url)
    people_card = card(page, "People")
    row = people_card.locator("li").first
    row.get_by_label("Delete").click()

    expect(row.locator(".alert-warning")).to_have_text("Iceland is used by 4 items.")
    expect(row.get_by_label("Delete")).to_have_count(0)
    assert deactivated == [None]  # the DELETE attempt itself, recorded with no body

    deactivate = row.get_by_role("button", name="Deactivate")
    expect(deactivate).to_be_visible()
    deactivate.click()  # falls through to the real mock (PATCH {active: false})

    expect(row.get_by_text("inactive")).to_be_visible()
    expect(row.get_by_role("button", name="Activate")).to_be_visible()
