"""Tests for XSS-shaped user data (item names, labels, people, country names).

Hostile.json — an item named
`<script>alert(1)</script>` and a label with markup render as text.
"""

from playwright.sync_api import expect


def test_hostile_item_name_renders_as_text(page, make_mockserver):
    """A `<script>` in an item's name shows up literally, and never executes."""
    fired = []
    page.on("dialog", lambda dialog: (fired.append(dialog), dialog.dismiss()))
    base_url, fixture = make_mockserver("hostile.json")

    page.goto(f"{base_url}/t/{fixture['trip']['trip']['slug']}")

    expect(page.get_by_text("<script>alert(1)</script>")).to_be_visible()
    assert page.locator("script", has_text="alert(1)").count() == 0
    assert fired == []


def test_hostile_label_renders_as_text(page, make_mockserver):
    """A label carrying markup shows up literally as the badge's text."""
    fired = []
    page.on("dialog", lambda dialog: (fired.append(dialog), dialog.dismiss()))
    base_url, fixture = make_mockserver("hostile.json")

    page.goto(f"{base_url}/t/{fixture['trip']['trip']['slug']}")

    expect(page.locator(".badge", has_text="<img src=x onerror=alert(2)>")).to_be_visible()
    assert fired == []


def test_hostile_person_name_renders_as_text(page, make_mockserver):
    """A person's name carrying markup renders as text in the item row's payer line."""
    base_url, fixture = make_mockserver("hostile.json")
    page.goto(f"{base_url}/t/{fixture['trip']['trip']['slug']}")

    expect(page.get_by_text("<img src=x onerror=alert(1)> paid")).to_be_visible()


def test_hostile_country_name_renders_as_text(page, make_mockserver):
    """A country's name carrying markup renders as text in the item row."""
    base_url, fixture = make_mockserver("hostile.json")
    page.goto(f"{base_url}/t/{fixture['trip']['trip']['slug']}")

    expect(page.get_by_text("<script>alert('country')</script>")).to_be_visible()
