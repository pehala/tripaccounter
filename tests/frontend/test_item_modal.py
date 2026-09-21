"""Tests for components/ItemModal.js: new vs. edit mode, save, delete.

Open modal, type name+amount, pick payer,
Save -> the POST body is asserted whole, the mock answers 201, the
re-read GET /items returns the item and the row appears; click a row -> edit mode,
prefilled, header amber; PATCH sends the built body; Delete removes it; "Save &
add another" keeps the modal open, clears name and amount, and holds date, payer
and currency.
"""

import pytest
from playwright.sync_api import expect


def test_save_posts_the_built_body_and_the_row_appears(items_page, new_item_modal, count_requests):
    """Saving a new expense posts one field-complete body; the re-read shows the row."""
    new_item_modal.locator('input[name="name"]').fill("Sushi night")
    new_item_modal.locator('input[name="amount"]').fill("5000")
    new_item_modal.locator('label[for="pay-2"]').click()
    posted = count_requests("*/items", method="POST")

    new_item_modal.get_by_role("button", name="Save", exact=True).click()

    new_item_modal.wait_for(state="hidden")
    assert len(posted) == 1
    body = posted[0].post_data_json
    assert body == {
        "name": "Sushi night",
        "amount": "5000",
        "currency_id": 1,
        "payer_id": 2,
        "wallet_id": 2,
        "country_id": 1,
        "occurred_at": body["occurred_at"],
        "labels": [],
        "city": None,
        "map_url": None,
        "lat": None,
        "lon": None,
        "split_mode": "equal",
        "shares": [{"person_id": 1}, {"person_id": 2}, {"person_id": 3}, {"person_id": 4}],
    }
    expect(items_page.get_by_text("Sushi night")).to_be_visible()


def test_save_with_city_posts_it_trimmed_and_the_row_shows_it(
    items_page, new_item_modal, count_requests
):
    """A typed city is trimmed onto the POST body, and the new row names it."""
    new_item_modal.locator('input[name="name"]').fill("Street food")
    new_item_modal.locator('input[name="amount"]').fill("2000")
    new_item_modal.locator('input[name="city"]').fill("  Bangkok  ")
    posted = count_requests("*/items", method="POST")

    new_item_modal.get_by_role("button", name="Save", exact=True).click()

    new_item_modal.wait_for(state="hidden")
    assert posted[0].post_data_json["city"] == "Bangkok"
    expect(items_page.locator("a.list-group-item-action", has_text="Street food")).to_contain_text(
        "Bangkok"
    )


def test_edit_mode_shows_amber_header_and_delete(open_edit_modal):
    """Opening a row for edit ambers the header, titles it "Editing expense" and offers Delete."""
    modal = open_edit_modal("Dinner at Messinn")

    expect(modal.locator(".modal-header.bg-warning-subtle")).to_have_count(1)
    expect(modal.get_by_role("heading", name="Editing expense")).to_be_visible()
    expect(modal.get_by_role("button", name="Delete")).to_be_visible()


@pytest.mark.parametrize(
    ("item_name", "selector", "js_property", "expected"),
    [
        pytest.param(
            "Dinner at Messinn", 'input[name="name"]', "value", "Dinner at Messinn", id="equal-name"
        ),
        pytest.param(
            "Dinner at Messinn", 'input[name="amount"]', "value", "18400", id="equal-amount"
        ),
        pytest.param("Dinner at Messinn", "#pay-1", "checked", True, id="equal-radio"),
        pytest.param(
            "Dinner at Messinn", 'input[name="city"]', "value", "Reykjavík", id="equal-city"
        ),
        pytest.param(
            "Guesthouse Vík, 2 nights",
            'button:text-is("Shares")',
            "className",
            "btn btn-primary",
            id="shares-radio",
        ),
        pytest.param(
            "Guesthouse Vík, 2 nights",
            "li:has(#split-4) input.num",
            "value",
            "0.5",
            id="shares-weight",
        ),
    ],
)
def test_edit_prefills_the_saved_item(open_edit_modal, item_name, selector, js_property, expected):
    """Opening a row for edit fills each field, split mode and weight included, as saved."""
    modal = open_edit_modal(item_name)
    modal.locator('[data-bs-target="#split-body"]').click()
    modal.locator("#split-body.show").wait_for()

    expect(modal.locator(selector)).to_have_js_property(js_property, expected)


def test_patch_sends_the_built_body_on_save(open_edit_modal, count_requests):
    """Editing and saving sends one PATCH to that item's endpoint carrying the whole built body."""
    modal = open_edit_modal("Dinner at Messinn")
    modal.locator('input[name="name"]').fill("Dinner at Messinn (renamed)")
    patched = count_requests("*/items/42", method="PATCH")

    modal.get_by_role("button", name="Save", exact=True).click()

    modal.wait_for(state="hidden")
    assert len(patched) == 1
    body = patched[0].post_data_json
    assert body == {
        "name": "Dinner at Messinn (renamed)",
        "amount": "18400",
        "currency_id": 1,
        "payer_id": 1,
        "wallet_id": 5,
        "country_id": 1,
        "occurred_at": body["occurred_at"],
        "labels": ["food", "restaurant"],
        "city": "Reykjavík",
        "map_url": "https://maps.app.goo.gl/Kx9mNq2",
        "lat": "64.14930",
        "lon": "-21.94030",
        "split_mode": "equal",
        "shares": [{"person_id": 1}, {"person_id": 2}, {"person_id": 3}, {"person_id": 4}],
    }


def test_delete_removes_the_row_after_confirm(items_page, open_edit_modal, count_requests):
    """Delete asks for confirmation, sends one DELETE, and the re-read list drops the row."""
    items_page.on("dialog", lambda dialog: dialog.accept())
    modal = open_edit_modal("Dinner at Messinn")
    deleted = count_requests("*/items/42", method="DELETE")

    modal.get_by_role("button", name="Delete").click()

    modal.wait_for(state="hidden")
    assert len(deleted) == 1
    expect(items_page.get_by_text("Dinner at Messinn")).to_have_count(0)


def test_save_and_add_another_keeps_modal_open_and_resets_only_name_and_amount(
    new_item_modal, count_requests
):
    """'Save & add another' posts once, clears name and amount, keeps the modal and the payer."""
    new_item_modal.locator('input[name="name"]').fill("Coffee")
    new_item_modal.locator('input[name="amount"]').fill("500")
    new_item_modal.locator('label[for="pay-3"]').click()
    posted = count_requests("*/items", method="POST")

    new_item_modal.get_by_role("button", name="Save & add another").click()

    expect(new_item_modal.locator('input[name="name"]')).to_have_value("")
    assert len(posted) == 1
    expect(new_item_modal).to_have_count(1)
    expect(new_item_modal.locator('input[name="amount"]')).to_have_value("")
    expect(new_item_modal.locator("#pay-3")).to_be_checked()


# --- wallets ----------------------------------------------------------------


def test_new_expense_wallet_select_defaults_to_the_payers_default_wallet(new_item_modal):
    """A new expense preselects Petr's default wallet, Card, before anything is touched."""
    expect(new_item_modal.locator('select[name="wallet_id"]')).to_have_value("1")


def test_changing_payer_resets_the_wallet_select_to_the_new_payers_default(new_item_modal):
    """Picking a different payer chip re-defaults the wallet select to their own Card."""
    new_item_modal.locator('label[for="pay-2"]').click()

    expect(new_item_modal.locator('select[name="wallet_id"]')).to_have_value("2")


def test_edit_preselects_the_items_own_wallet(open_edit_modal):
    """Dinner was paid from Petr's Cash, not his default Card - the select shows Cash."""
    modal = open_edit_modal("Dinner at Messinn")

    expect(modal.locator('select[name="wallet_id"]')).to_have_value("5")
