"""Tests for components/ItemModal.js's Transfer mode and components/TransferFields.js.

The Expense/Transfer switch only shows on a new entry and is frozen while
editing; picking Transfer swaps in TransferFields and posts to /transfers,
never preview-split; the to side mirrors the from side's amount until the
user edits it directly.
"""

from playwright.sync_api import expect


def test_transfer_switch_shows_on_a_new_entry(new_item_modal):
    """The Expense/Transfer switch is offered on a new entry."""
    expect(new_item_modal.get_by_role("button", name="Transfer")).to_be_visible()


def test_transfer_switch_is_absent_while_editing(open_edit_modal):
    """The kind switch never shows while editing an existing entry - the kind is frozen."""
    modal = open_edit_modal("Dinner at Messinn")

    expect(modal.get_by_role("button", name="Transfer")).to_have_count(0)


def test_transfer_mode_posts_the_built_body_and_never_calls_preview_split(
    new_item_modal, count_requests
):
    """Switching to Transfer and saving posts to /transfers, never touching preview-split."""
    new_item_modal.get_by_role("button", name="Transfer", exact=True).click()
    selects = new_item_modal.locator("form select")
    selects.nth(0).select_option("1")  # from wallet: Petr's Card
    new_item_modal.locator('input[inputmode="decimal"]').first.fill("20000")
    selects.nth(2).select_option("5")  # to wallet: Petr's Cash

    posted = count_requests("*/transfers", method="POST")
    preview = count_requests("*/preview-split")

    new_item_modal.get_by_role("button", name="Save", exact=True).click()

    new_item_modal.wait_for(state="hidden")
    assert len(posted) == 1
    assert preview == []
    body = posted[0].post_data_json
    assert body == {
        "from_wallet_id": 1,
        "from_amount": "20000",
        "from_currency_id": 1,
        "to_wallet_id": 5,
        "to_amount": "20000",
        "to_currency_id": 1,
        "occurred_at": body["occurred_at"],
        "note": None,
    }


def test_transfer_to_side_mirrors_the_from_side_until_edited(new_item_modal):
    """Typing the from amount and currency mirrors the to side, until the to side is touched."""
    new_item_modal.get_by_role("button", name="Transfer", exact=True).click()
    amount_inputs = new_item_modal.locator('input[inputmode="decimal"]')

    amount_inputs.first.fill("150")

    expect(amount_inputs.nth(1)).to_have_value("150")

    amount_inputs.nth(1).fill("99")
    amount_inputs.first.fill("200")

    expect(amount_inputs.nth(1)).to_have_value("99")
