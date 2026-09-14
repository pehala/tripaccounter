"""Tests for components/Shell.js, the chrome every route shares.

The navbar brand carries the site mark beside the app name; the mark is
decorative, so the link still reads as the app name alone.
"""

from playwright.sync_api import expect

BRAND_MARK = ".navbar-brand img"


def test_brand_mark_renders(page, mockserver):
    """The brand mark decodes, so a wrong path or content type shows as a broken image."""
    page.goto(mockserver)

    expect(page.locator(BRAND_MARK)).to_be_visible()
    assert page.locator(BRAND_MARK).evaluate("img => img.naturalWidth") > 0


def test_brand_link_is_named_by_its_text_alone(page, mockserver):
    """The mark is alt="", so it adds nothing to the accessible name the brand text gives."""
    page.goto(mockserver)

    expect(page.get_by_role("link", name="Trip Accounter", exact=True)).to_be_visible()
