"""Tests for components/SplitEditor.js: mode switch, preview timing, rendered numbers.

Switching to Exact and entering a
mismatched sum shows the stubbed 422's sum_mismatch rendered through the catalog
as "Off by N ISK." on the shares field; preview-split fires on change, not per
keystroke; the rendered shares are exactly the stub's numbers, recomputed by
nothing (rule 2).
"""

from playwright.sync_api import expect


def open_new_item_modal_with_split_expanded(page, trip_url):
    """Open the new-item modal and expand the split section, without touching amount."""
    page.goto(trip_url)
    page.get_by_role("button", name="Expense").click()
    page.locator(".modal.show").wait_for()
    page.locator('[data-bs-target="#split-body"]').click()
    page.locator("#split-body.show").wait_for()
    return page.locator('input[name="amount"]')


def exact_input_for(page, person_id):
    """Return that person's per-share numeric input in the expanded split list."""
    return page.locator("li", has=page.locator(f"#split-{person_id}")).locator("input.num")


def test_exact_mode_mismatch_renders_sum_mismatch_from_the_catalog(
    page, mockserver, trip_url, stub
):
    """A stubbed 422 sum_mismatch on `shares` renders as the catalog's sentence, diff formatted."""
    stub(
        "**/api/v1/trips/*/items/preview-split",
        lambda request: (
            422,
            {
                "error": {
                    "code": "validation_error",
                    "params": {},
                    "fields": {
                        "shares": {
                            "code": "sum_mismatch",
                            "params": {"diff": 1, "currency_code": "ISK"},
                        }
                    },
                }
            },
        ),
    )
    amount = open_new_item_modal_with_split_expanded(page, trip_url)
    amount.fill("100")

    page.get_by_role("button", name="Exact", exact=True).click()

    expect(page.locator(".alert-danger")).to_have_text("Off by 1 ISK.")


def test_preview_fires_on_change_not_on_every_keystroke(page, mockserver, trip_url, stub):
    """Typing in a per-person exact amount fires preview-split on blur, once, not per key."""
    calls = stub(
        "**/api/v1/trips/*/items/preview-split",
        lambda request: (200, {"split": {"mode": "exact", "shares": []}}),
    )
    amount = open_new_item_modal_with_split_expanded(page, trip_url)
    amount.fill("100")
    with page.expect_response(lambda r: "preview-split" in r.url):
        amount.blur()
    assert len(calls) == 1  # the amount field commits its own change first

    with page.expect_response(lambda r: "preview-split" in r.url):
        page.get_by_role("button", name="Exact", exact=True).click()
    assert len(calls) == 2  # the mode switch itself previews once

    person1 = exact_input_for(page, 1)
    person1.press_sequentially("60")
    page.wait_for_timeout(200)  # give a stray request a chance to show up
    assert len(calls) == 2  # keystrokes alone never call firePreview

    with page.expect_response(lambda r: "preview-split" in r.url):
        person1.blur()
    assert len(calls) == 3  # committed once, on change


def test_rendered_shares_are_exactly_the_stubs_numbers(page, mockserver, trip_url, stub):
    """The split list shows the server's numbers verbatim — nothing here recomputes a share."""
    stub(
        "**/api/v1/trips/*/items/preview-split",
        lambda request: (
            200,
            {
                "split": {
                    "mode": "equal",
                    "shares": [
                        {"person_id": 1, "weight": "1", "owed": 12345},
                        {"person_id": 2, "weight": "1", "owed": 1},
                        {"person_id": 3, "weight": None, "owed": None},
                        {"person_id": 4, "weight": "1", "owed": 99999},
                    ],
                }
            },
        ),
    )
    amount = open_new_item_modal_with_split_expanded(page, trip_url)

    amount.fill("100200")
    amount.blur()

    rows = page.locator("#split-body li")
    expect(rows.nth(0).locator(".num")).to_have_text("12,345")
    expect(rows.nth(1).locator(".num")).to_have_text("1")
    expect(rows.nth(2).locator(".num")).to_have_text("—")
    expect(rows.nth(3).locator(".num")).to_have_text("99,999")
