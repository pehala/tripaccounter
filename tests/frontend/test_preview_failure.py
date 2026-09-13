"""Tests for the preview-split failure path (rule 2's failure half).

Preview-split stubbed to 500 — the
preview greys out, the last good numbers stay on screen, no NaN, no guessed split,
the form is still submittable.
"""

from playwright.sync_api import expect


def test_preview_failure_keeps_last_numbers_and_stays_submittable(page, mockserver, trip_url, stub):
    """A failing preview-split greys out the list but never blanks, guesses, or blocks Save."""
    state = {"fail": False}

    def responder(request):
        if state["fail"]:
            return 500, {"error": {"code": "internal_error", "params": {}}}
        return (
            200,
            {
                "split": {
                    "mode": "equal",
                    "shares": [
                        {"person_id": 1, "weight": "1", "owed": 2500},
                        {"person_id": 2, "weight": "1", "owed": 2500},
                        {"person_id": 3, "weight": "1", "owed": 2500},
                        {"person_id": 4, "weight": "1", "owed": 2500},
                    ],
                },
            },
        )

    posted = []

    def items_responder(request):
        if request.method == "POST":
            posted.append(request.post_data_json)
            return 201, {"item": {**request.post_data_json, "id": 9003}}
        return None

    stub("**/api/v1/trips/*/items/preview-split", responder)
    stub("**/api/v1/trips/*/items", items_responder)

    page.goto(trip_url)
    page.get_by_role("button", name="Expense").click()
    page.locator(".modal.show").wait_for()
    page.locator('[data-bs-target="#split-body"]').click()
    page.locator("#split-body.show").wait_for()

    amount = page.locator('input[name="amount"]')
    amount.fill("10000")
    amount.blur()
    each_amount = page.locator(".num", has_text="2,500 each")
    expect(each_amount).to_be_visible()

    state["fail"] = True
    page.locator("li", has=page.locator("#split-3")).locator("input[type=checkbox]").uncheck()

    expect(page.locator("#split-body ul")).to_have_class("list-group list-group-flush opacity-50")
    expect(each_amount).to_be_visible()
    assert "NaN" not in page.locator("#split-body").inner_text()
    expect(page.locator(".alert-primary")).to_be_visible()
    assert page.locator(".alert-danger").count() == 0

    save_button = page.get_by_role("button", name="Save", exact=True)
    assert save_button.is_enabled()
    page.locator('input[name="name"]').fill("Groceries")
    save_button.click()

    page.locator(".modal.show").wait_for(state="hidden")
    assert len(posted) == 1
