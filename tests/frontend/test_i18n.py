"""Tests for i18n catalog completeness, the no-literal-UI-text rule, and locale switching."""

import re
from pathlib import Path

import pytest
from playwright.sync_api import expect

from tools import check_i18n

STATIC_JS = Path(__file__).parent.parent.parent / "static" / "js"
LITERAL_TEXT_RE = re.compile(r">(?!\$\{)[A-Za-z]")


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


@pytest.fixture
def browser_context_args(browser_context_args):
    """Force a real English browser locale so the pre-switch state is deterministic."""
    return {**browser_context_args, "locale": "en-US"}


@pytest.fixture
def page(context):
    """Return a page with no forced `lang` pin, bypassing conftest.py's `en`-pinning override."""
    return context.new_page()


def test_switching_locale_updates_header_tabs_modal_and_empty_state(make_mockserver, page):
    """Picking Čeština from the header menu re-renders the shell in place, no reload."""
    base_url, fixture = make_mockserver("empty.json")
    slug = fixture["trip"]["trip"]["slug"]
    page.goto(f"{base_url}/t/{slug}")

    expect(page.get_by_role("link", name="Items")).to_be_visible()
    expect(page.get_by_text("No expenses yet.")).to_be_visible()

    page.locator("button[data-bs-toggle=dropdown]").click()
    page.get_by_role("button", name="Čeština").click()

    assert page.locator("html").get_attribute("lang") == "cs"
    expect(page.get_by_role("link", name="Položky")).to_be_visible()
    expect(page.get_by_text("Zatím žádné výdaje.")).to_be_visible()

    page.get_by_role("button", name="Výdaj").click()
    page.locator(".modal.show").wait_for()
    expect(page.get_by_role("heading", name="Nový výdaj")).to_be_visible()


def test_locale_choice_persists_across_reload(make_mockserver, page):
    """setLocale() writes localStorage['lang']; a fresh load picks it back up."""
    base_url, fixture = make_mockserver("empty.json")
    slug = fixture["trip"]["trip"]["slug"]
    page.goto(f"{base_url}/t/{slug}")

    page.locator("button[data-bs-toggle=dropdown]").click()
    page.get_by_role("button", name="Čeština").click()
    expect(page.get_by_role("link", name="Položky")).to_be_visible()

    page.reload()

    assert page.locator("html").get_attribute("lang") == "cs"
    expect(page.get_by_role("link", name="Položky")).to_be_visible()


def test_sum_mismatch_renders_czech_sentence_with_czech_formatted_number(
    make_mockserver, page, stub
):
    """A stubbed 422 sum_mismatch renders through cs's catalog, diff formatted Czech-style."""
    base_url, fixture = make_mockserver("trip.json")
    slug = fixture["trip"]["trip"]["slug"]
    page.goto(f"{base_url}/t/{slug}")
    page.locator("button[data-bs-toggle=dropdown]").click()
    page.get_by_role("button", name="Čeština").click()

    stub(
        "**/api/v1/trips/*/items/preview-split",
        lambda request: (
            422,
            {
                "error": {
                    "code": "validation_error",
                    "params": {},
                    "fields": {
                        "shares": {
                            "code": "sum_mismatch",
                            "params": {"diff": 1234.5, "currency_code": "ISK"},
                        }
                    },
                }
            },
        ),
    )

    page.get_by_role("button", name="Výdaj").click()
    page.locator(".modal.show").wait_for()
    page.locator('input[name="amount"]').fill("100")
    page.locator('[data-bs-target="#split-body"]').click()
    page.locator("#split-body.show").wait_for()
    page.get_by_role("button", name="Přesně", exact=True).click()

    expect(page.locator(".alert-danger")).to_have_text("Chybí 1 234,5 ISK.")


def test_integer_plural_categories_for_1_3_5_in_czech(make_mockserver, page):
    """Czech needs three distinct forms for an integer count: one / few / other."""
    base_url, fixture = make_mockserver("trip.json")
    slug = fixture["trip"]["trip"]["slug"]
    page.goto(f"{base_url}/t/{slug}")

    forms = page.evaluate(
        """async () => {
            const { setLocale, t } = await import('/js/i18n/index.js');
            setLocale('cs');
            return [1, 3, 5].map((n) => t('setup.item_count', { n }));
        }"""
    )

    assert forms == ["1 položka", "3 položky", "5 položek"]
