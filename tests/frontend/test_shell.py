"""Tests for components/Shell.js, the chrome every route shares.

The navbar brand carries the site mark beside the app name; the mark is
decorative, so the link still reads as the app name alone. The settings menu ends
with the running build — its id and build date, from `GET /version` — which it simply
omits when that call cannot be answered.
"""

import pytest
from playwright.sync_api import expect

BRAND_MARK = ".navbar-brand img"
BUILD_VERSION = "[data-testid=build-version]"
VERSION_GLOB = "**/api/v1/version"
PHONE_VIEWPORT = {"width": 400, "height": 800}


def test_brand_mark_renders_and_leaves_the_link_named_by_its_text(page, mockserver):
    """The mark decodes (no broken image) and is alt="", so the link reads as the app name alone."""
    page.goto(mockserver)

    expect(page.locator(BRAND_MARK)).to_be_visible()
    assert page.locator(BRAND_MARK).evaluate("img => img.naturalWidth") > 0
    expect(page.get_by_role("link", name="Trip Accounter", exact=True)).to_be_visible()


def open_settings(page):
    """Open the settings menu and return the page."""
    page.get_by_role("button", name="Settings").click()
    return page


def test_settings_menu_shows_the_build_id_and_date(page, mockserver):
    """The menu names the build the fixture reports, its date formatted for the viewer."""
    page.goto(mockserver)
    open_settings(page)

    expect(page.locator(BUILD_VERSION)).to_have_text("a1b2c3d · 14 Sep")


def test_settings_menu_build_carries_the_full_build_time_in_its_tooltip(page, mockserver):
    """Hovering the build reveals the day and time it was built, not just the day."""
    page.goto(mockserver)
    open_settings(page)

    expect(page.locator(BUILD_VERSION)).to_have_attribute("title", "14 Sep, 12:00 PM")


def test_settings_menu_shows_a_dev_build_without_a_date(page, stub, mockserver):
    """A dev backend reports `dev` and no time: the menu shows just that, with no dangling dot."""
    stub(VERSION_GLOB, lambda request: (200, {"version": "dev", "built_at": None}))
    page.goto(mockserver)
    open_settings(page)

    expect(page.locator(BUILD_VERSION)).to_have_text("dev")


def test_settings_menu_build_is_reachable_at_phone_width(page, mockserver):
    """The bar has no room for the build at 400px, but the menu does: it is readable there."""
    page.set_viewport_size(PHONE_VIEWPORT)
    page.goto(mockserver)
    open_settings(page)

    expect(page.locator(BUILD_VERSION)).to_be_visible()


def test_navbar_itself_carries_no_build(page, mockserver):
    """Closed, the menu keeps the build out of the bar, which has no room for it at phone width."""
    page.goto(mockserver)

    expect(page.locator(BUILD_VERSION)).to_be_hidden()


@pytest.mark.parametrize(
    "answer",
    [
        pytest.param((404, {"error": {"code": "not_found", "params": {}}}), id="older-backend"),
        pytest.param((500, {"error": {"code": "internal_error", "params": {}}}), id="failing"),
        pytest.param((200, {"unrelated": True}), id="unrecognised-body"),
    ],
)
def test_settings_menu_omits_the_build_when_the_call_cannot_be_answered(
    page, stub, mockserver, answer
):
    """No version, no error, no empty line: the menu still offers language and theme."""
    errors = []
    page.on("pageerror", lambda exc: errors.append(exc))  # noqa: PLW0108 (bound method breaks Playwright's wrapper)
    stub(VERSION_GLOB, lambda request: answer)
    page.goto(mockserver)
    open_settings(page)

    expect(page.get_by_role("button", name="English")).to_be_visible()
    expect(page.locator(BUILD_VERSION)).to_have_count(0)
    assert errors == []
