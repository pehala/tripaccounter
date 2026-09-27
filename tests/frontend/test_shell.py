"""Tests for components/Shell.js, the chrome every route shares.

The navbar brand carries the site mark beside the app name; the mark is
decorative, so the link still reads as the app name alone.
"""

from playwright.sync_api import expect

BRAND_MARK = ".navbar-brand img"


def test_brand_mark_renders_and_leaves_the_link_named_by_its_text(page, mockserver):
    """The mark decodes (no broken image) and is alt="", so the link reads as the app name alone."""
    page.goto(mockserver)

    expect(page.locator(BRAND_MARK)).to_be_visible()
    assert page.locator(BRAND_MARK).evaluate("img => img.naturalWidth") > 0
    expect(page.get_by_role("link", name="Trip Accounter", exact=True)).to_be_visible()
