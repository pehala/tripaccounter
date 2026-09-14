"""Tests for XSS-shaped user data (item names, labels, people, country names).

Hostile.json — an item named
`<script>alert(1)</script>` and a label with markup render as text.
"""

import pytest
from playwright.sync_api import expect


@pytest.fixture
def fixture_name():
    """Serve hostile.json: markup in every user-supplied string."""
    return "hostile.json"


@pytest.fixture
def dialogs(page):
    """Return the list of dialogs the page opens, each dismissed as it appears."""
    fired = []
    page.on("dialog", lambda dialog: (fired.append(dialog), dialog.dismiss()))
    return fired


@pytest.fixture
def hostile_page(dialogs, open_trip):
    """Return the hostile trip's Items tab, loaded with the dialog trap already armed."""
    return open_trip()


@pytest.mark.parametrize(
    "hostile_text",
    [
        pytest.param("<script>alert(1)</script>", id="item-name"),
        pytest.param("<img src=x onerror=alert(2)>", id="label"),
        pytest.param("<img src=x onerror=alert(1)> paid", id="person-name"),
        pytest.param("<script>alert('country')</script>", id="country-name"),
    ],
)
def test_hostile_text_renders_literally_and_never_executes(hostile_page, dialogs, hostile_text):
    """Markup in user data shows up as the row's literal text, opens no dialog, adds no script."""
    expect(hostile_page.get_by_text(hostile_text)).to_be_visible()
    assert hostile_page.locator("script", has_text="alert").count() == 0
    assert dialogs == []


def test_hostile_wallet_name_renders_literally_in_wallets_and_setup(dialogs, open_trip):
    """A wallet named `<i>x</i>` shows as literal text on the Wallets tab and in Setup."""
    wallets_page = open_trip("wallets")
    expect(wallets_page.get_by_text("<i>x</i>")).to_be_visible()
    assert wallets_page.locator("i", has_text="x").count() == 0

    setup_page = open_trip("setup")
    expect(setup_page.get_by_text("<i>x</i>")).to_be_visible()
    assert dialogs == []


def test_hostile_transfer_note_renders_literally_in_the_feed(dialogs, open_trip):
    """A transfer note with markup shows as literal text in the feed, never as a script tag."""
    page = open_trip()

    expect(page.get_by_text("alert('note')", exact=False)).to_be_visible()
    assert page.locator("script", has_text="alert").count() == 0
    assert dialogs == []
