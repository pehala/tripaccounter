"""Tests for rule 5: unknown fields are ignored, never break a view.

A fixture carrying an extra key on
the trip, an item and a balance renders identically — rule 5, the guarantee that
lets the backend ship first.
"""

import copy

from playwright.sync_api import expect


def with_unknown_fields(fixture_data):
    """Build a deep copy of the fixture with an unrecognized key added to trip, item and balance."""
    data = copy.deepcopy(fixture_data)
    data["trip"]["trip"]["unknown_trip_field"] = "surprise"
    data["items"]["items"][0]["unknown_item_field"] = {"nested": True}
    data["balances"]["balances"][0]["unknown_balance_field"] = 12345
    return data


def test_page_errors_never_fire_with_unknown_fields(page, make_mockserver, fixture_data):
    """No unhandled JS exception fires anywhere while browsing a fixture with extra keys."""
    errors = []
    page.on("pageerror", lambda exc: errors.append(exc))  # noqa: PLW0108 (bound method breaks Playwright's wrapper)
    data = with_unknown_fields(fixture_data)
    base_url, fixture = make_mockserver(data=data)

    page.goto(f"{base_url}/t/{fixture['trip']['trip']['slug']}")
    page.get_by_role("link", name="Balances").click()
    expect(page.get_by_text("Settle up").first).to_be_visible()
    page.get_by_role("link", name="Statistics").click()
    expect(page.get_by_text("By label").first).to_be_visible()
    page.get_by_role("link", name="Setup").click()
    expect(page.get_by_text("People", exact=True)).to_be_visible()

    assert errors == []


def test_trip_header_renders_identically_with_an_unknown_field(page, make_mockserver, fixture_data):
    """The header shows the trip's real fields; the unknown one is neither shown nor breaks it."""
    data = with_unknown_fields(fixture_data)
    base_url, fixture = make_mockserver(data=data)

    page.goto(f"{base_url}/t/{fixture['trip']['trip']['slug']}")

    expect(page.get_by_role("heading", name=fixture["trip"]["trip"]["name"])).to_be_visible()
    assert "surprise" not in page.locator("header").inner_text()


def test_item_row_renders_identically_with_an_unknown_field(page, make_mockserver, fixture_data):
    """The item row shows its real fields; the unknown one is neither shown nor breaks it."""
    data = with_unknown_fields(fixture_data)
    base_url, fixture = make_mockserver(data=data)
    item = data["items"]["items"][0]

    page.goto(f"{base_url}/t/{fixture['trip']['trip']['slug']}")

    row = page.locator("a.list-group-item-action", has_text=item["name"])
    expect(row).to_be_visible()
    assert "unknown_item_field" not in row.inner_text()


def test_balance_card_renders_identically_with_an_unknown_field(
    page, make_mockserver, fixture_data
):
    """The balance card shows its real fields; the unknown one is neither shown nor breaks it."""
    data = with_unknown_fields(fixture_data)
    base_url, fixture = make_mockserver(data=data)

    page.goto(f"{base_url}/t/{fixture['trip']['trip']['slug']}#balances")

    expect(page.get_by_text("Settle up").first).to_be_visible()
    assert "12345" not in page.locator("main").inner_text()
