"""Tests for components/SplitEditor.js: mode switch, preview timing, rendered numbers.

Switching to Exact and entering a
mismatched sum shows the stubbed 422's sum_mismatch rendered through the catalog
as "Off by N ISK." on the shares field; preview-split fires on change, not per
keystroke; the rendered shares are exactly the stub's numbers, recomputed by
nothing (rule 2).
"""

import pytest
from playwright.sync_api import expect

PREVIEW_URL = "**/api/v1/trips/*/items/preview-split"

SUM_MISMATCH = {
    "error": {
        "code": "validation_error",
        "params": {},
        "fields": {
            "shares": {"code": "sum_mismatch", "params": {"diff": 1, "currency_code": "ISK"}}
        },
    }
}

EXACT_PREVIEW = {"split": {"mode": "exact", "shares": []}}

EQUAL_PREVIEW = {
    "split": {
        "mode": "equal",
        "shares": [
            {"person_id": 1, "weight": "1", "owed": 12345},
            {"person_id": 2, "weight": "1", "owed": 1},
            {"person_id": 3, "weight": None, "owed": None},
            {"person_id": 4, "weight": "1", "owed": 99999},
        ],
    }
}


@pytest.fixture
def amount(new_item_modal):
    """Return the amount input of the open new-expense modal."""
    return new_item_modal.locator('input[name="amount"]')


@pytest.fixture
def exact_input_for(split_expanded):
    """Return `exact_input_for(person_id)`: that person's per-share input in the split list."""

    def find(person_id):
        return split_expanded.locator(f"li:has(#split-{person_id}) input.num")

    return find


def test_exact_mode_mismatch_renders_sum_mismatch_from_the_catalog(
    new_item_modal, split_expanded, amount, stub
):
    """A stubbed 422 sum_mismatch on `shares` renders as the catalog's sentence, diff formatted."""
    stub(PREVIEW_URL, lambda request: (422, SUM_MISMATCH))
    amount.fill("100")

    new_item_modal.get_by_role("button", name="Exact", exact=True).click()

    expect(new_item_modal.locator(".alert-danger")).to_have_text("Off by 1 ISK.")


def test_preview_fires_on_change_not_on_every_keystroke(
    new_item_modal, amount, exact_input_for, stub, count_requests
):
    """Committing the amount, the mode and one exact share previews three times, keystrokes none."""
    stub(PREVIEW_URL, lambda request: (200, EXACT_PREVIEW))
    page = new_item_modal.page
    amount.fill("100")
    previews = count_requests("*/items/preview-split")

    with page.expect_response(lambda response: "preview-split" in response.url):
        amount.blur()
    with page.expect_response(lambda response: "preview-split" in response.url):
        new_item_modal.get_by_role("button", name="Exact", exact=True).click()
    person1 = exact_input_for(1)
    person1.press_sequentially("60")
    with page.expect_response(lambda response: "preview-split" in response.url):
        person1.blur()

    assert len(previews) == 3


def test_rendered_shares_are_exactly_the_stubs_numbers(split_expanded, amount, stub):
    """The split list shows the server's numbers verbatim — nothing here recomputes a share."""
    stub(PREVIEW_URL, lambda request: (200, EQUAL_PREVIEW))
    amount.fill("100200")

    amount.blur()

    rows = split_expanded.locator("li")
    expect(rows.nth(0).locator(".num")).to_have_text("12,345")
    expect(rows.nth(1).locator(".num")).to_have_text("1")
    expect(rows.nth(2).locator(".num")).to_have_text("—")
    expect(rows.nth(3).locator(".num")).to_have_text("99,999")
