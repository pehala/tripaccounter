"""Tests for components/LabelInput.js: chip commit keys and suggestions.

Space or comma commits a chip; Enter is left
alone and submits the form like any other field; Backspace on empty removes the
last; a suggestion commits the same way; the suggestion list is client-side, no
network on typing.
"""


def open_new_item_modal(page, trip_url):
    """Navigate to the trip and open the new-item modal, returning its label input."""
    page.goto(trip_url)
    page.get_by_role("button", name="Expense").click()
    page.locator(".modal.show").wait_for()
    return page.locator(".tag-input input")


def test_space_commits_a_chip(page, mockserver, trip_url):
    """Typing a word then pressing Space turns it into a lowercased chip and clears the input."""
    label_input = open_new_item_modal(page, trip_url)

    label_input.fill("Beach")
    label_input.press("Space")

    chips = page.locator(".tag-input .badge")
    assert chips.count() == 1
    assert chips.inner_text() == "beach"
    assert label_input.input_value() == ""


def test_comma_commits_a_chip(page, mockserver, trip_url):
    """A comma commits the typed label the same way a space does."""
    label_input = open_new_item_modal(page, trip_url)

    label_input.fill("street-food,")
    label_input.press(",")

    chips = page.locator(".tag-input .badge")
    assert chips.count() == 1
    assert chips.inner_text() == "street-food"
    assert label_input.input_value() == ""


def test_enter_submits_the_form_like_any_other_field(page, mockserver, trip_url, stub):
    """Enter is not a commit key for the label input — it submits the form."""
    posted = stub(
        "**/api/v1/trips/*/items",
        lambda request: (201, {"item": {"id": 9999}}) if request.method == "POST" else None,
    )
    page.goto(trip_url)
    page.get_by_role("button", name="Expense").click()
    page.locator(".modal.show").wait_for()
    page.locator('input[name="name"]').fill("Snacks")
    page.locator('input[name="amount"]').fill("500")
    label_input = page.locator(".tag-input input")
    label_input.fill("snacks")
    label_input.press("Space")

    label_input.press("Enter")

    assert len(posted) == 1


def test_backspace_on_empty_removes_last_chip(page, mockserver, trip_url):
    """Backspace with nothing typed drops the most recently added chip."""
    label_input = open_new_item_modal(page, trip_url)
    label_input.fill("first")
    label_input.press("Space")
    label_input.fill("second")
    label_input.press("Space")
    assert page.locator(".tag-input .badge").count() == 2

    label_input.press("Backspace")

    chips = page.locator(".tag-input .badge")
    assert chips.count() == 1
    assert chips.inner_text() == "first"


def test_picking_a_suggestion_commits_it(page, mockserver, trip_url):
    """Choosing a suggested label (typed to match, committed on blur) adds the chip."""
    label_input = open_new_item_modal(page, trip_url)
    options = page.locator("#trip-labels option").evaluate_all("els => els.map(e => e.value)")
    assert "food" in options

    label_input.fill("food")
    page.locator('input[name="name"]').click()

    assert page.locator(".tag-input .badge").inner_text() == "food"


def test_no_network_request_while_typing(page, mockserver, trip_url, stub):
    """The suggestion list comes from the already-loaded store; typing fires no request."""
    label_input = open_new_item_modal(page, trip_url)
    calls = stub("**/api/v1/trips/*/labels", lambda request: (200, {"labels": []}))

    label_input.press_sequentially("gro")

    assert calls == []
