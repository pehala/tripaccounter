"""Tests for views/Setup.js: people/currencies/countries/labels CRUD, in-use delete.

People/currencies/countries/labels each add,
rename and delete; a stubbed in-use 409 with `{code: "in_use", params: {count: 4,
name: "Iceland"}}` renders "Iceland is used by 4 items." from the catalog; a
referenced person offers Deactivate (`PATCH {"active": false}`) instead of a
Delete that can only fail.
"""

import pytest
from playwright.sync_api import expect

from tests.frontend.conftest import load_fixture


@pytest.fixture
def setup_card(setup_page, card):
    """Return `card(header_text)` with the trip loaded on the Setup tab."""
    return card


@pytest.fixture
def refused_delete(stub):
    """Answer DELETE on any person with the 409 in_use envelope; return the recorded calls."""
    body = load_fixture("errors/409_in_use.json")
    return stub(
        "**/api/v1/trips/*/people/*",
        lambda request: (409, body) if request.method == "DELETE" else None,
    )


@pytest.fixture
def in_use_row(setup_card, refused_delete):
    """Return the first People row after its Delete was refused as in use."""
    row = setup_card("People").locator("li").first
    row.get_by_label("Delete").click()
    return row


@pytest.mark.parametrize(
    ("header", "row_selector", "fields", "shown"),
    [
        pytest.param("People", "li", [("Name", "Zoe")], "Zoe", id="people"),
        pytest.param(
            "Currencies", "li", [("ISK", "usd"), ("symbol (optional)", "$")], "USD", id="currencies"
        ),
        pytest.param("Countries", "li", [("Name", "Norway")], "Norway", id="countries"),
        pytest.param("Labels", ".badge", [("Label", "snacks")], "snacks", id="labels"),
    ],
)
def test_add(setup_card, header, row_selector, fields, shown):
    """Filling the add form and saving appends a row showing the value, currency code upcased."""
    section = setup_card(header)
    section.get_by_role("button", name="+ Add").click()
    for placeholder, value in fields:
        section.get_by_placeholder(placeholder, exact=True).fill(value)

    section.get_by_role("button", name="Save", exact=True).click()

    expect(section.locator(row_selector).last).to_contain_text(shown)


@pytest.mark.parametrize(
    ("header", "row_selector", "current", "renamed"),
    [
        pytest.param("People", "li", "Petr", "Petr Renamed", id="people"),
        pytest.param("Currencies", "li", "€", "euro", id="currencies"),
        pytest.param("Countries", "li", "Iceland", "Ísland", id="countries"),
        pytest.param("Labels", ".badge", "drinks", "beer", id="labels"),
    ],
)
def test_rename(setup_card, header, row_selector, current, renamed):
    """Clicking a row's text opens an inline input; saving shows the new text on that row."""
    section = setup_card(header)
    row = section.locator(row_selector).filter(has_text=current)
    row.get_by_text(current).click()
    section.locator("input").fill(renamed)

    section.get_by_role("button", name="Save", exact=True).click()

    expect(section.locator(row_selector).filter(has_text=renamed)).to_have_count(1)


@pytest.mark.parametrize(
    ("header", "row_selector", "row_text", "remove_label"),
    [
        pytest.param("People", "li", "Ann", "Delete", id="people"),
        pytest.param("Currencies", "li", "DKK", "Delete", id="currencies"),
        pytest.param("Countries", "li", "Denmark", "Delete", id="countries"),
        pytest.param("Labels", ".badge", "drinks", "Remove", id="labels"),
    ],
)
def test_delete(setup_card, header, row_selector, row_text, remove_label):
    """The row's remove button deletes it through the mock and the re-read no longer shows it."""
    section = setup_card(header)
    row = section.locator(row_selector).filter(has_text=row_text)

    row.get_by_label(remove_label).click()

    expect(section.get_by_text(row_text)).to_have_count(0)


def test_person_delete_in_use_renders_catalog_sentence_and_withdraws_delete(
    in_use_row, refused_delete
):
    """A 409 in_use on delete shows the catalog sentence on the row and removes its Delete."""
    expect(in_use_row.locator(".alert-warning")).to_have_text("Iceland is used by 4 items.")
    expect(in_use_row.get_by_label("Delete")).to_have_count(0)
    assert refused_delete == [None]


def test_deactivate_after_in_use_marks_row_inactive(in_use_row):
    """Deactivate on an in-use person goes through; the row shows inactive and offers Activate."""
    in_use_row.get_by_role("button", name="Deactivate").click()

    expect(in_use_row.get_by_text("inactive")).to_be_visible()
    expect(in_use_row.get_by_role("button", name="Activate")).to_be_visible()
