"""Tests for app.js's router: tab subpaths, back/forward, unknown slug.

`/t/{slug}/balances` deep-links straight to that tab on a cold load; back and
forward switch tabs without refetching; an unknown slug renders the 404 view, not
an empty shell.
"""

from playwright.sync_api import expect


def test_cold_load_with_tab_path_lands_directly_on_that_tab(shared_balances_page):
    """A first paint at /balances renders the Balances tab active and never mounts the Items FAB."""
    expect(shared_balances_page.locator(".nav-link.active")).to_have_text("Balances")
    expect(shared_balances_page.locator(".balances-content").first).to_be_visible()
    assert shared_balances_page.locator(".fab").count() == 0


def test_active_tab_link_marks_itself_current(shared_balances_page):
    """The tab nav is links, not ARIA tabs, so the one we are on says aria-current=page."""
    expect(shared_balances_page.get_by_role("link", name="Balances")).to_have_attribute(
        "aria-current", "page"
    )
    expect(shared_balances_page.get_by_role("link", name="Items")).not_to_have_attribute(
        "aria-current", "page"
    )


def test_back_and_forward_switch_tabs_without_refetching_balances(
    items_page, open_tab, count_requests
):
    """Going back to Items and forward to Balances again reuses the one cached balances fetch."""
    balance_requests = count_requests("*/balances")

    open_tab("Balances")
    assert len(balance_requests) == 1

    items_page.go_back()
    expect(items_page.locator(".nav-link.active")).to_have_text("Items")
    expect(items_page.get_by_role("button", name="Expense")).to_be_visible()
    assert len(balance_requests) == 1

    items_page.go_forward()
    expect(items_page.locator(".nav-link.active")).to_have_text("Balances")
    expect(items_page.locator(".balances-content").first).to_be_visible()
    assert len(balance_requests) == 1


def test_unknown_slug_renders_the_notfound_view(page, mockserver):
    """A slug the mock has never heard of renders the 404 view, not a blank shell."""
    page.goto(f"{mockserver}/t/does-not-exist")

    expect(page.get_by_role("heading", name="Trip not found")).to_be_visible()
    expect(page.get_by_text("There's no trip at this link.")).to_be_visible()
    assert page.locator(".nav-tabs").count() == 0
