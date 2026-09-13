"""Tests for the phone-width layout (400px).

400px viewport — no horizontal scroll on any tab, the modal is full-screen, the
FAB is visible.
"""

import re

import pytest
from playwright.sync_api import expect

from tests.frontend.conftest import TAB_PARAMS, TABS

PHONE_VIEWPORT = {"width": 400, "height": 800}
FITS_VIEWPORT_JS = "document.documentElement.scrollWidth <= document.documentElement.clientWidth"


@pytest.fixture
def phone_page(page):
    """Return the page with a 400x800 viewport, set before any navigation."""
    page.set_viewport_size(PHONE_VIEWPORT)
    return page


@pytest.fixture
def phone_items_page(phone_page, open_trip):
    """Return the trip loaded on the Items tab at phone width."""
    return open_trip()


@pytest.mark.parametrize("tab", TAB_PARAMS)
def test_no_horizontal_scroll_on_any_tab(phone_page, open_trip, tab):
    """Each tab fits within a 400px viewport on a cold load, with no horizontal overflow."""
    open_trip(TABS[tab][0])

    assert phone_page.evaluate(FITS_VIEWPORT_JS)


def test_fab_is_visible_at_phone_width(phone_items_page):
    """The floating add button shows at 400px, where the header 'Expense' button hides."""
    expect(phone_items_page.locator(".fab")).to_be_visible()
    expect(phone_items_page.get_by_role("button", name="Expense")).to_be_hidden()


def test_modal_is_full_screen_at_phone_width(phone_items_page):
    """The item modal picks up modal-fullscreen-sm-down and spans the whole 400px viewport."""
    phone_items_page.locator(".fab").click()
    phone_items_page.locator(".modal.show").wait_for()

    dialog = phone_items_page.locator(".modal-dialog")
    expect(dialog).to_have_class(re.compile(r"\bmodal-fullscreen-sm-down\b"))
    assert dialog.bounding_box()["width"] >= 399
