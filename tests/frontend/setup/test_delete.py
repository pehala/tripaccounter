"""Tests for the delete buttons on views/Setup.js: confirmation and in-use refusals.

Every row's delete asks first; a dismissed prompt sends nothing. A stubbed in-use 409
with `{code: "in_use", params: {count: 4, name: "Iceland"}}` renders "Iceland is used
by 4 items." from the catalog; a referenced person offers Deactivate
(`PATCH {"active": false}`) instead of a Delete that can only fail.
"""

import pytest
from playwright.sync_api import expect

from tests.frontend.conftest import load_fixture


@pytest.fixture
def refused_delete(stub):
    """Answer DELETE on any person with the 409 in_use envelope; return the recorded calls."""
    body = load_fixture("errors/409_in_use.json")
    return stub("**/api/v1/trips/*/people/*", lambda request: (409, body), method="DELETE")


@pytest.fixture
def in_use_row(setup_card, refused_delete):
    """Return the first People row after its Delete was refused as in use."""
    row = setup_card("People").locator("li").first
    row.page.once("dialog", lambda dialog: dialog.accept())
    row.get_by_label("Delete").click()
    return row


@pytest.mark.parametrize(
    ("header", "row_selector", "row_text", "remove_label"),
    [
        pytest.param("People", "li", "Ann", "Delete", id="people"),
        pytest.param("Currencies", "li", "DKK", "Delete", id="currencies"),
        pytest.param("Countries", "li", "Denmark", "Delete", id="countries"),
        pytest.param("Labels", ".badge", "drinks", "Remove", id="labels"),
        pytest.param("Wallets", "li", "Cash", "Delete", id="wallets"),
    ],
)
def test_delete(setup_card, header, row_selector, row_text, remove_label):
    """The row's remove button deletes it through the mock and the re-read no longer shows it."""
    section = setup_card(header)
    row = section.locator(row_selector).filter(has_text=row_text)
    row.page.once("dialog", lambda dialog: dialog.accept())

    row.get_by_label(remove_label).click()

    expect(section.get_by_text(row_text)).to_have_count(0)


@pytest.mark.parametrize(
    ("header", "row_text", "remove_label"),
    [
        pytest.param("People", "Ann", "Delete", id="people"),
        pytest.param("Currencies", "DKK", "Delete", id="currencies"),
        pytest.param("Countries", "Denmark", "Delete", id="countries"),
        pytest.param("Labels", "drinks", "Remove", id="labels"),
        pytest.param("Wallets", "Cash", "Delete", id="wallets"),
    ],
)
def test_delete_dismissed_keeps_the_row_and_sends_nothing(
    setup_card, count_requests, header, row_text, remove_label
):
    """Dismissing the confirmation leaves the row in place and sends no DELETE."""
    section = setup_card(header)
    row = section.locator("li, .badge").filter(has_text=row_text)
    row.page.once("dialog", lambda dialog: dialog.dismiss())
    deleted = count_requests("**/api/v1/trips/*/*/*", method="DELETE")

    row.get_by_label(remove_label).click()

    expect(row).to_have_count(1)
    assert deleted == []


@pytest.mark.parametrize(
    ("header", "row_text", "remove_label", "message"),
    [
        pytest.param("People", "Ann", "Delete", 'Delete "Ann"?', id="person"),
        pytest.param("Wallets", "Cash", "Delete", 'Delete "Cash"?', id="wallet"),
        pytest.param(
            "Labels",
            "drinks",
            "Remove",
            'Delete label "drinks"? It would be deleted from 0 items.',
            id="label-states-its-item-count",
        ),
    ],
)
def test_delete_confirmation_names_what_is_deleted(
    setup_card, header, row_text, remove_label, message
):
    """The prompt quotes the row's name; a label's also says how many items lose it."""
    row = setup_card(header).locator("li, .badge").filter(has_text=row_text)
    prompts = []
    row.page.once("dialog", lambda dialog: (prompts.append(dialog.message), dialog.dismiss()))

    row.get_by_label(remove_label).click()

    assert prompts == [message]


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
