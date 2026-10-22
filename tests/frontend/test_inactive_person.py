"""Tests for how components/ItemModal.js offers a deactivated person.

Eva is deactivated in this module's fixture. She paid for "Guesthouse Vík" and holds
a 0.5 share of it: editing that item keeps her as payer and sharer, and the PATCH
resends both. A new expense offers her neither as payer nor in the split.
"""

import pytest
from playwright.sync_api import expect

from tests.frontend.conftest import expand_split


@pytest.fixture
def fixture_data(fixture_data):
    """Deactivate Eva (id 4), who paid for "Guesthouse Vík" and shares in it."""
    eva = next(person for person in fixture_data["trip"]["trip"]["people"] if person["id"] == 4)
    eva["active"] = False
    return fixture_data


def test_edit_keeps_inactive_payer_and_sharer_on_save(open_edit_modal, count_requests):
    """Saving an edit resends the inactive payer, her wallet and her 0.5 share untouched."""
    modal = open_edit_modal("Guesthouse Vík")
    split = expand_split(modal)
    expect(modal.locator("#pay-4")).to_be_checked()
    expect(split.locator("#split-4")).to_be_checked()
    modal.locator('input[name="name"]').fill("Guesthouse Vík, renamed")
    patched = count_requests("*/items/39", method="PATCH")

    modal.get_by_role("button", name="Save", exact=True).click()

    modal.wait_for(state="hidden")
    assert len(patched) == 1
    body = patched[0].post_data_json
    assert (body["payer_id"], body["wallet_id"], body["split_mode"], body["shares"]) == (
        4,
        4,
        "shares",
        [
            {"person_id": 1, "weight": "1"},
            {"person_id": 2, "weight": "1"},
            {"person_id": 3, "weight": "1"},
            {"person_id": 4, "weight": "0.5"},
        ],
    )


def test_new_expense_offers_no_inactive_person(new_item_modal, count_requests):
    """A new expense lists no payer chip or split row for Eva, and posts a split without her."""
    split = expand_split(new_item_modal)
    expect(new_item_modal.locator("#pay-4")).to_have_count(0)
    expect(split.locator("#split-4")).to_have_count(0)
    new_item_modal.locator('input[name="name"]').fill("Hot dogs")
    new_item_modal.locator('input[name="amount"]').fill("3000")
    posted = count_requests("*/items", method="POST")

    new_item_modal.get_by_role("button", name="Save", exact=True).click()

    new_item_modal.wait_for(state="hidden")
    assert len(posted) == 1
    assert posted[0].post_data_json["shares"] == [
        {"person_id": 1},
        {"person_id": 2},
        {"person_id": 3},
    ]
