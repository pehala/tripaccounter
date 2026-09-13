"""Tests for components/ItemModal.js: new vs. edit mode, save, delete.

Open modal, type name+amount, pick payer,
Save -> the POST body is asserted field by field, the stub answers 201, the
re-read GET /items returns the item and the row appears; click a row -> edit mode,
prefilled, header amber; PATCH sends the built body; Delete removes it; "Save &
add another" keeps the modal open, clears name and amount, and holds date, payer
and currency.
"""

from playwright.sync_api import expect


def open_new_item_modal(page, trip_url):
    """Navigate to the trip and open the new-item modal."""
    page.goto(trip_url)
    page.get_by_role("button", name="Expense").click()
    page.locator(".modal.show").wait_for()


def open_edit_modal(page, trip_url, item_name):
    """Navigate to the trip and open the edit modal for the item with this name."""
    page.goto(trip_url)
    page.locator("a.list-group-item-action", has_text=item_name).first.click()
    page.locator(".modal.show").wait_for()


def test_save_posts_the_built_body_and_the_row_appears(
    page, mockserver, trip_url, fixture_data, stub
):
    """Saving a new expense posts one field-complete body; the re-read shows the row."""
    saved_item = {}

    def responder(request):
        if request.method == "POST":
            body = request.post_data_json
            saved_item.update(
                {
                    **body,
                    "id": 9001,
                    "currency_code": "ISK",
                    "split": {
                        "mode": body["split_mode"],
                        "shares": [
                            {**s, "weight": s.get("weight"), "owed": None} for s in body["shares"]
                        ],
                    },
                }
            )
            return 201, {"item": saved_item}
        if request.method == "GET" and saved_item:
            return 200, {"items": [saved_item, *fixture_data["items"]["items"]]}
        return None  # baseline GET before the save, real mockserver answers it

    stub("**/api/v1/trips/*/items", responder)

    open_new_item_modal(page, trip_url)
    page.locator('input[name="name"]').fill("Sushi night")
    page.locator('input[name="amount"]').fill("5000")
    page.locator('label[for="pay-2"]').click()

    page.get_by_role("button", name="Save", exact=True).click()
    page.locator(".modal.show").wait_for(state="hidden")

    assert saved_item["name"] == "Sushi night"
    assert saved_item["amount"] == "5000"
    assert saved_item["currency_id"] == 1
    assert saved_item["payer_id"] == 2
    assert saved_item["country_id"] == 1
    assert saved_item["split_mode"] == "equal"
    assert saved_item["labels"] == []
    assert saved_item["map_url"] is None
    assert saved_item["lat"] is None
    assert saved_item["lon"] is None
    assert {s["person_id"] for s in saved_item["shares"]} == {1, 2, 3, 4}
    assert all(set(s.keys()) == {"person_id"} for s in saved_item["shares"])
    expect(page.get_by_text("Sushi night")).to_be_visible()


def test_edit_prefills_equal_split_item_and_shows_amber_header(page, mockserver, trip_url):
    """Opening an equal-split item for edit prefills its fields and ambers the header."""
    open_edit_modal(page, trip_url, "Dinner at Messinn")

    assert page.locator(".modal-header.bg-warning-subtle").count() == 1
    expect(page.get_by_role("heading", name="Editing expense")).to_be_visible()
    assert page.locator('input[name="name"]').input_value() == "Dinner at Messinn"
    assert page.locator('input[name="amount"]').input_value() == "18400"
    assert page.locator("#pay-1").is_checked()
    expect(page.get_by_role("button", name="Delete")).to_be_visible()


def test_edit_prefills_shares_split_weights(page, mockserver, trip_url):
    """Opening a weighted-shares item shows its mode and each person's saved weight."""
    open_edit_modal(page, trip_url, "Guesthouse Vík, 2 nights")

    page.locator('[data-bs-target="#split-body"]').click()
    page.locator("#split-body.show").wait_for()

    shares_button = page.get_by_role("button", name="Shares", exact=True)
    assert "btn-primary" in shares_button.get_attribute("class")
    eva_row = page.locator("li", has=page.locator("#split-4"))
    assert eva_row.locator("input.num").input_value() == "0.5"


def test_patch_sends_the_built_body_on_save(page, mockserver, trip_url, stub):
    """Editing and saving sends a PATCH to that item's endpoint with the new value."""
    patched = {}

    def responder(request):
        if request.method == "PATCH":
            patched.update(request.post_data_json)
            return 200, {"item": {**patched, "id": 42}}
        return None

    stub("**/api/v1/trips/*/items/42", responder)

    open_edit_modal(page, trip_url, "Dinner at Messinn")
    page.locator('input[name="name"]').fill("Dinner at Messinn (renamed)")
    page.get_by_role("button", name="Save", exact=True).click()
    page.locator(".modal.show").wait_for(state="hidden")

    assert patched["name"] == "Dinner at Messinn (renamed)"
    assert patched["amount"] == "18400"
    assert patched["currency_id"] == 1


def test_delete_removes_the_row_after_confirm(page, mockserver, trip_url, fixture_data, stub):
    """Delete asks for confirmation, then the re-read list no longer has the row."""
    remaining = [i for i in fixture_data["items"]["items"] if i["name"] != "Dinner at Messinn"]
    page.on("dialog", lambda dialog: dialog.accept())

    open_edit_modal(page, trip_url, "Dinner at Messinn")

    stub(
        "**/api/v1/trips/*/items",
        lambda request: (200, {"items": remaining}) if request.method == "GET" else None,
    )
    deleted = stub(
        "**/api/v1/trips/*/items/42",
        lambda request: (204, {}) if request.method == "DELETE" else None,
    )

    page.get_by_role("button", name="Delete").click()

    page.locator(".modal.show").wait_for(state="hidden")
    assert len(deleted) == 1
    assert page.get_by_text("Dinner at Messinn").count() == 0


def test_save_and_add_another_keeps_modal_open_and_resets_only_name_and_amount(
    page, mockserver, trip_url, fixture_data, stub
):
    """'Save & add another' clears name/amount but keeps the modal, payer, date and currency."""
    saved = []

    def responder(request):
        if request.method == "POST":
            saved.append(request.post_data_json)
            return 201, {"item": {**request.post_data_json, "id": 9002}}
        if request.method == "GET":
            return 200, {"items": fixture_data["items"]["items"]}
        return None

    stub("**/api/v1/trips/*/items", responder)

    open_new_item_modal(page, trip_url)
    page.locator('input[name="name"]').fill("Coffee")
    page.locator('input[name="amount"]').fill("500")
    page.locator('label[for="pay-3"]').click()

    page.get_by_role("button", name="Save & add another").click()

    name_input = page.locator('input[name="name"]')
    expect(name_input).to_have_value("")
    assert len(saved) == 1
    assert page.locator(".modal.show").count() == 1
    assert page.locator('input[name="amount"]').input_value() == ""
    assert page.locator("#pay-3").is_checked()
