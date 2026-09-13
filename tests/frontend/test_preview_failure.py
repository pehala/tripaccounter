"""Tests for the preview-split failure path (rule 2's failure half).

Preview-split stubbed to 500 — the
preview greys out, the last good numbers stay on screen, no NaN, no guessed split,
the form is still submittable.
"""

import pytest
from playwright.sync_api import expect

HAPPY_PREVIEW = {
    "split": {
        "mode": "equal",
        "shares": [
            {"person_id": 1, "weight": "1", "owed": 2500},
            {"person_id": 2, "weight": "1", "owed": 2500},
            {"person_id": 3, "weight": "1", "owed": 2500},
            {"person_id": 4, "weight": "1", "owed": 2500},
        ],
    }
}

INTERNAL_ERROR = {"error": {"code": "internal_error", "params": {}}}


@pytest.fixture
def failing_preview(page, stub, new_item_modal, split_expanded):
    """Return the page after a good preview of 10000 over four people, then a preview answered 500.

    preview-split answers the happy body until "2,500 each" is on screen, then every
    later call gets a 500; unchecking person 3 is the call that fails.
    """
    state = {"fail": False}

    def responder(request):
        if state["fail"]:
            return 500, INTERNAL_ERROR
        return 200, HAPPY_PREVIEW

    stub("**/api/v1/trips/*/items/preview-split", responder)
    amount = new_item_modal.locator('input[name="amount"]')
    amount.fill("10000")
    amount.blur()
    expect(page.locator(".num", has_text="2,500 each")).to_be_visible()
    state["fail"] = True
    with page.expect_response(lambda response: "preview-split" in response.url):
        split_expanded.locator("li:has(#split-3) input[type=checkbox]").uncheck()
    return page


def test_failed_preview_greys_out_the_list_and_keeps_the_last_numbers(failing_preview):
    """A failing preview-split greys out the split list while the last good numbers stay visible."""
    expect(failing_preview.locator("#split-body ul")).to_have_class(
        "list-group list-group-flush opacity-50"
    )
    expect(failing_preview.locator(".num", has_text="2,500 each")).to_be_visible()


def test_failed_preview_shows_no_nan_and_no_error_alert(failing_preview):
    """A failing preview-split renders no NaN and keeps the hint alert, with no error alert."""
    expect(failing_preview.locator("#split-body")).not_to_contain_text("NaN")
    expect(failing_preview.locator(".alert-primary")).to_be_visible()
    expect(failing_preview.locator(".alert-danger")).to_have_count(0)


def test_failed_preview_leaves_the_form_submittable(failing_preview, count_requests):
    """After a failing preview-split, Save still posts the item once and closes the modal."""
    failing_preview.locator('input[name="name"]').fill("Groceries")
    posted = count_requests("*/items", method="POST")

    failing_preview.get_by_role("button", name="Save", exact=True).click()

    failing_preview.locator(".modal.show").wait_for(state="hidden")
    assert len(posted) == 1
