"""Tests for the phone-width layout (400px).

400px viewport — no horizontal scroll
on any tab, the modal is full-screen, the FAB is visible.
"""

from playwright.sync_api import expect


def no_horizontal_scroll(page):
    """Check whether the document ever grew wider than the viewport itself."""
    return page.evaluate(
        "document.documentElement.scrollWidth <= document.documentElement.clientWidth"
    )


def test_no_horizontal_scroll_on_any_tab(page, mockserver, trip_url):
    """Items, Balances, Stats and Setup all fit within a 400px viewport."""
    page.set_viewport_size({"width": 400, "height": 800})
    page.goto(trip_url)
    expect(page.get_by_role("link", name="Statistics")).to_be_visible()

    for tab_name in ("Items", "Balances", "Statistics", "Setup"):
        page.get_by_role("link", name=tab_name).click()
        expect(page.locator(".nav-link.active")).to_have_text(tab_name)
        assert no_horizontal_scroll(page), f"{tab_name} tab overflows horizontally at 400px"


def test_fab_is_visible_at_phone_width(page, mockserver, trip_url):
    """The floating add button shows at 400px, where the header 'Expense' button hides."""
    page.set_viewport_size({"width": 400, "height": 800})
    page.goto(trip_url)

    expect(page.locator(".fab")).to_be_visible()
    expect(page.get_by_role("button", name="Expense")).to_be_hidden()


def test_modal_is_full_screen_at_phone_width(page, mockserver, trip_url):
    """The item modal picks up modal-fullscreen-sm-down, which fills the phone viewport."""
    page.set_viewport_size({"width": 400, "height": 800})
    page.goto(trip_url)

    page.locator(".fab").click()
    page.locator(".modal.show").wait_for()

    dialog = page.locator(".modal-dialog")
    assert "modal-fullscreen-sm-down" in dialog.get_attribute("class")
    box = dialog.bounding_box()
    assert box["width"] >= 399  # fills the 400px viewport, not a centered card
