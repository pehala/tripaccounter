"""Tests for the API call budget in design/FRONTEND.md §5.

Intercept network — opening a trip makes exactly 3 API calls, opening the edit
modal makes 0, saving makes 2, the stats tab 1, the balances tab 1 — every row of
the table, asserted as equality, not a ceiling.
"""

from playwright.sync_api import expect


def count_api_calls(page):
    """Return a list that grows by one for every request to /api/v1/.

    Attach it right before the action under test.
    """
    calls = []
    page.on("request", lambda request: calls.append(request) if "/api/v1/" in request.url else None)
    return calls


def test_opening_a_trip_makes_exactly_three_calls(page, mockserver, slug):
    """store.load() fires trip + items + labels in parallel — three calls, no more."""
    calls = count_api_calls(page)
    page.goto(f"{mockserver}/t/{slug}")
    expect(page.get_by_role("button", name="Expense")).to_be_visible()
    assert len(calls) == 3


def test_opening_the_edit_modal_makes_no_calls(page, mockserver, trip_url):
    """The item is already in store.items — opening it for edit fetches nothing."""
    page.goto(trip_url)
    expect(page.get_by_role("button", name="Expense")).to_be_visible()
    calls = count_api_calls(page)

    page.locator("a.list-group-item-action").first.click()
    page.locator(".modal.show").wait_for()

    assert len(calls) == 0


def test_balances_tab_makes_exactly_one_call(page, mockserver, trip_url):
    """Opening Balances for the first time is one GET /balances."""
    page.goto(trip_url)
    expect(page.get_by_role("button", name="Expense")).to_be_visible()
    calls = count_api_calls(page)

    page.get_by_role("link", name="Balances").click()
    expect(page.get_by_text("Settle up").first).to_be_visible()

    assert len(calls) == 1


def test_stats_tab_makes_exactly_one_call(page, mockserver, trip_url):
    """Opening Stats for the first time is one GET /stats."""
    page.goto(trip_url)
    expect(page.get_by_role("button", name="Expense")).to_be_visible()
    calls = count_api_calls(page)

    page.get_by_role("link", name="Statistics").click()
    expect(page.get_by_text("By label").first).to_be_visible()

    assert len(calls) == 1


def test_revisiting_balances_and_stats_makes_no_further_calls(page, mockserver, trip_url):
    """Once loaded, store.balances/store.stats are cached — switching back refetches nothing."""
    page.goto(trip_url)
    expect(page.get_by_role("button", name="Expense")).to_be_visible()
    page.get_by_role("link", name="Balances").click()
    expect(page.get_by_text("Settle up").first).to_be_visible()
    page.get_by_role("link", name="Statistics").click()
    expect(page.get_by_text("By label").first).to_be_visible()
    page.get_by_role("link", name="Items").click()
    expect(page.get_by_role("button", name="Expense")).to_be_visible()

    calls = count_api_calls(page)
    page.get_by_role("link", name="Balances").click()
    expect(page.get_by_text("Settle up").first).to_be_visible()
    page.get_by_role("link", name="Statistics").click()
    expect(page.get_by_text("By label").first).to_be_visible()

    assert len(calls) == 0


def test_saving_an_item_makes_exactly_two_calls(page, mockserver, trip_url, stub, fixture_data):
    """A save with no new label is POST + the re-read GET /items — two calls, no labels reload."""
    saved = {}

    def responder(request):
        if request.method == "POST":
            saved.update(request.post_data_json)
            saved.update({"id": 12345, "split": {"mode": "equal", "shares": []}})
            return 201, {"item": saved}
        if request.method == "GET" and saved:
            return 200, {"items": [saved, *fixture_data["items"]["items"]]}
        return None

    stub("**/api/v1/trips/*/items", responder)
    page.goto(trip_url)
    expect(page.get_by_role("button", name="Expense")).to_be_visible()

    page.get_by_role("button", name="Expense").click()
    page.locator(".modal.show").wait_for()
    page.locator('input[name="name"]').fill("Snacks")
    page.locator('input[name="amount"]').fill("500")
    # The amount's own change-preview call (call budget's separate
    # "change amount/split" row) has to settle before counting "save" itself.
    with page.expect_response(lambda r: "preview-split" in r.url):
        page.locator('input[name="amount"]').blur()

    calls = count_api_calls(page)
    page.get_by_role("button", name="Save", exact=True).click()
    page.locator(".modal.show").wait_for(state="hidden")

    assert len(calls) == 2
