"""Tests for app.js's router: hash tabs, back/forward, unknown slug.

`/t/{slug}#balances` deep-links straight to
that tab on a cold load; back and forward switch tabs without refetching; an
unknown slug renders the 404 view, not an empty shell.
"""

from playwright.sync_api import expect


def test_cold_load_with_hash_lands_directly_on_that_tab(page, mockserver, slug):
    """A first paint at #balances renders the Balances tab active, not Items."""
    page.goto(f"{mockserver}/t/{slug}#balances")

    expect(page.locator(".nav-link.active")).to_have_text("Balances")
    expect(page.get_by_text("Balance", exact=False).first).to_be_visible()
    assert page.locator(".fab").count() == 0  # the Items-tab FAB never rendered


def test_back_and_forward_switch_tabs_without_refetching_balances(page, mockserver, slug):
    """Going back to Items and forward to Balances again reuses the cached balances."""
    balance_requests = []
    page.on(
        "request",
        lambda request: (
            balance_requests.append(request) if request.url.endswith("/balances") else None
        ),
    )

    page.goto(f"{mockserver}/t/{slug}#items")
    expect(page.locator(".nav-link.active")).to_have_text("Items")

    page.get_by_role("link", name="Balances").click()
    expect(page.locator(".nav-link.active")).to_have_text("Balances")
    expect(page.get_by_text("Settle up").first).to_be_visible()  # balances finished loading
    assert len(balance_requests) == 1

    page.go_back()
    expect(page.locator(".nav-link.active")).to_have_text("Items")
    expect(page.get_by_role("button", name="Expense")).to_be_visible()
    assert len(balance_requests) == 1  # back to Items makes no balances call

    page.go_forward()
    expect(page.locator(".nav-link.active")).to_have_text("Balances")
    expect(page.get_by_text("Settle up").first).to_be_visible()
    assert len(balance_requests) == 1  # forward to the cached tab, no second fetch


def test_unknown_slug_renders_the_notfound_view(page, mockserver):
    """A slug the mock has never heard of renders the 404 view, not a blank shell."""
    page.goto(f"{mockserver}/t/does-not-exist")

    expect(page.get_by_role("heading", name="Trip not found")).to_be_visible()
    expect(page.get_by_text("There's no trip at this link.")).to_be_visible()
    assert page.locator(".nav-tabs").count() == 0
