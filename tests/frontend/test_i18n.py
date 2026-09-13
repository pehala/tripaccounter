"""Tests for i18n catalog completeness, the no-literal-UI-text rule, and locale switching."""

import re
from pathlib import Path

import pytest
from playwright.sync_api import expect

from tools import check_i18n

STATIC_JS = Path(__file__).parent.parent.parent / "static" / "js"
LITERAL_TEXT_RE = re.compile(r">(?!\$\{)[A-Za-z]")

SUM_MISMATCH = {
    "error": {
        "code": "validation_error",
        "params": {},
        "fields": {
            "shares": {"code": "sum_mismatch", "params": {"diff": 1234.5, "currency_code": "ISK"}}
        },
    }
}


@pytest.fixture
def browser_context_args(browser_context_args):
    """Force a real English browser locale so the pre-switch state is deterministic."""
    return {**browser_context_args, "locale": "en-US"}


@pytest.fixture
def page(context):
    """Return a page with no forced `lang` pin, bypassing conftest.py's `en`-pinning override."""
    return context.new_page()


@pytest.fixture
def fixture_name():
    """Serve empty.json: two people, one currency, no items, so the empty state is on screen."""
    return "empty.json"


@pytest.fixture
def czech_page(open_trip):
    """Return the trip's Items tab, loaded in English, after picking Čeština in the header menu."""
    page = open_trip()
    page.locator("button[data-bs-toggle=dropdown]").click()
    page.get_by_role("button", name="Čeština").click()
    expect(page.locator("html")).to_have_attribute("lang", "cs")
    return page


@pytest.fixture
def czech_modal(czech_page):
    """Return the `.modal.show` locator of the new-expense modal, opened from the Czech UI."""
    czech_page.get_by_role("button", name="Výdaj").click()
    modal = czech_page.locator(".modal.show")
    modal.wait_for()
    return modal


# --- static checks ----------------------------------------------------------------


def test_check_i18n_tool_passes(capsys):
    """Run the authoritative tools.check_i18n static catalog check and expect it to pass clean."""
    assert check_i18n.main() == 0
    assert "failed" not in capsys.readouterr().out


def test_no_literal_ui_text_between_tags_in_templates():
    """Scan component and view source for literal UI text sitting directly in markup."""
    offenders = []
    for path in (*(STATIC_JS / "components").glob("*.js"), *(STATIC_JS / "views").glob("*.js")):
        for match in LITERAL_TEXT_RE.finditer(path.read_text()):
            offenders.append(f"{path.relative_to(STATIC_JS)}: ...{match.group(0)}...")
    assert offenders == []


# --- locale switching -------------------------------------------------------------


def test_switching_locale_rerenders_tabs_and_empty_state(czech_page):
    """Picking Čeština from the header menu re-renders the tab links and empty state in place."""
    expect(czech_page.get_by_role("link", name="Položky")).to_be_visible()
    expect(czech_page.get_by_text("Zatím žádné výdaje.")).to_be_visible()


def test_switching_locale_translates_the_new_expense_modal_heading(czech_modal):
    """A modal opened after the switch takes its heading from the Czech catalog."""
    expect(czech_modal.get_by_role("heading", name="Nový výdaj")).to_be_visible()


def test_locale_choice_persists_across_reload(czech_page):
    """setLocale() writes localStorage['lang']; a fresh load picks it back up."""
    czech_page.reload()

    expect(czech_page.locator("html")).to_have_attribute("lang", "cs")
    expect(czech_page.get_by_role("link", name="Položky")).to_be_visible()


def test_sum_mismatch_renders_czech_sentence_with_czech_formatted_number(
    czech_page, czech_modal, stub
):
    """A stubbed 422 sum_mismatch renders through cs's catalog, diff formatted Czech-style."""
    stub("**/api/v1/trips/*/items/preview-split", lambda request: (422, SUM_MISMATCH))
    czech_modal.locator('input[name="amount"]').fill("100")
    czech_modal.locator('[data-bs-target="#split-body"]').click()
    czech_modal.locator("#split-body.show").wait_for()

    czech_modal.get_by_role("button", name="Přesně", exact=True).click()

    expect(czech_page.locator(".alert-danger")).to_have_text("Chybí 1 234,5 ISK.")


@pytest.mark.parametrize(
    ("count", "expected"),
    [
        pytest.param(1, "1 položka", id="one"),
        pytest.param(3, "3 položky", id="few"),
        pytest.param(5, "5 položek", id="other"),
    ],
)
def test_integer_plural_categories_in_czech(js, count, expected):
    """Czech picks a distinct form for an integer count in each of one / few / other."""
    assert js("i18n/index.js", "t", "setup.item_count", {"n": count}, locale="cs") == expected
