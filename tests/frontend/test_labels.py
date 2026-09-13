"""Tests for components/LabelInput.js: chip commit keys and suggestions.

Space or comma commits a chip; Enter is left
alone and submits the form like any other field; Backspace on empty removes the
last; a suggestion commits the same way; the suggestion list is client-side, no
network on typing.
"""

import pytest
from playwright.sync_api import expect


@pytest.fixture
def label_input(new_item_modal):
    """Return the label input of the open new-expense modal."""
    return new_item_modal.locator(".tag-input input")


@pytest.fixture
def chips(new_item_modal):
    """Return the locator of the committed label chips in the open new-expense modal."""
    return new_item_modal.locator(".tag-input .badge")


@pytest.mark.parametrize(
    ("typed", "key", "chip"),
    [
        pytest.param("Beach", "Space", "beach", id="space"),
        pytest.param("street-food", ",", "street-food", id="comma"),
    ],
)
def test_commit_key_turns_the_typed_word_into_a_chip(label_input, chips, typed, key, chip):
    """Pressing a commit key after a word adds it as a lowercased chip and clears the input."""
    label_input.fill(typed)

    label_input.press(key)

    expect(chips).to_have_count(1)
    expect(chips).to_have_text(chip)
    expect(label_input).to_have_value("")


def test_enter_submits_the_form_like_any_other_field(new_item_modal, label_input, count_requests):
    """Enter is not a commit key for the label input — it submits the form, posting once."""
    new_item_modal.locator('input[name="name"]').fill("Snacks")
    new_item_modal.locator('input[name="amount"]').fill("500")
    label_input.fill("snacks")
    label_input.press("Space")
    posted = count_requests("*/items", method="POST")

    label_input.press("Enter")

    new_item_modal.wait_for(state="hidden")
    assert len(posted) == 1


def test_backspace_on_empty_removes_last_chip(label_input, chips):
    """Backspace with nothing typed drops the most recently added chip and keeps the earlier one."""
    label_input.fill("first")
    label_input.press("Space")
    label_input.fill("second")
    label_input.press("Space")

    label_input.press("Backspace")

    expect(chips).to_have_count(1)
    expect(chips).to_have_text("first")


def test_picking_a_suggestion_commits_it(new_item_modal, label_input, chips):
    """Typing a label offered by the trip's suggestion list commits it as a chip on blur."""
    label_input.fill("food")

    new_item_modal.locator('input[name="name"]').click()

    expect(chips).to_have_text("food")


def test_no_network_request_while_typing(label_input, count_requests):
    """The suggestion list comes from the already-loaded store; typing fires no API request."""
    requests = count_requests("*/api/v1/*")

    label_input.press_sequentially("gro")

    assert requests == []
