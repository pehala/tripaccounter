"""Tests for views/Stats.js.

Currency is the top-level organizing unit: each currency gets its own heading
and total, and its four stat sections (by_label, by_country, by_person,
by_day) render in that order, collapsed by default. The "label": null group
renders as unlabelled; country flags are shown; the overlap caveat is inside
by_label's own section; by_person is labelled as owed, not paid — all API.md
requirements, not copy.
"""

import pytest
from playwright.sync_api import expect

OVERLAP_CAVEAT = (
    "An item can carry several labels, so these rows overlap and add up to more than the total."
)


def expand(page, currency_id, group):
    """Open one stat section's collapse body, leaving an already-open one open."""
    body = page.locator(f"#sec-{currency_id}-{group}-body")
    if not body.is_visible():
        page.locator(f'[data-bs-target="#sec-{currency_id}-{group}-body"]').click()
    page.locator(f"#sec-{currency_id}-{group}-body.show").wait_for()


@pytest.fixture
def unlabelled_stats_page(stub, fixture_data, open_trip):
    """Return the Statistics tab served a single ISK stat whose only by_label row is `null`."""
    isk = next(s for s in fixture_data["stats"]["stats"] if s["currency_code"] == "ISK")
    isk["by_label"] = [{"label": None, "item_count": 2, "amount": isk["total"]}]
    stub("**/api/v1/trips/*/stats", lambda request: (200, {"stats": [isk], "day_count": 1}))

    return open_trip("stats")


def test_by_label_by_country_by_person_by_day_render_in_order_for_one_currency(
    shared_stats_page, fixture_data
):
    """A currency's four stat sections appear in the exact order the API returns them."""
    isk = next(s for s in fixture_data["stats"]["stats"] if s["currency_code"] == "ISK")
    assert isk["total"] > 0  # sanity: the fixture actually has data to render

    heading = shared_stats_page.locator("h2", has_text=f"total {isk['currency_code']}")
    expect(heading).to_be_visible()

    section = shared_stats_page.locator(f"#cur-{isk['currency_id']}")
    titles = section.locator('[data-bs-toggle="collapse"]').all_inner_texts()
    assert "By label" in titles[0]
    assert "By country" in titles[1]
    assert "Per person" in titles[2]
    assert "By day" in titles[3]


def test_country_flags_shown_in_by_country_rows(shared_stats_page, fixture_data):
    """A by_country row shows the country's flag next to its name."""
    isk = next(s for s in fixture_data["stats"]["stats"] if s["currency_code"] == "ISK")
    dkk = next(s for s in fixture_data["stats"]["stats"] if s["currency_code"] == "DKK")

    expand(shared_stats_page, isk["currency_id"], "by_country")
    expand(shared_stats_page, dkk["currency_id"], "by_country")

    expect(shared_stats_page.get_by_text("🇮🇸 Iceland").first).to_be_visible()
    expect(shared_stats_page.get_by_text("🇩🇰 Denmark").first).to_be_visible()


def test_overlap_caveat_is_inside_the_by_label_section(shared_stats_page, fixture_data):
    """The by_label overlap note lives in the same section as By label, not just somewhere."""
    isk = next(s for s in fixture_data["stats"]["stats"] if s["currency_code"] == "ISK")
    expand(shared_stats_page, isk["currency_id"], "by_label")

    by_label_section = shared_stats_page.locator(f"#sec-{isk['currency_id']}-by_label")
    expect(by_label_section).to_contain_text(OVERLAP_CAVEAT)


def test_by_person_is_labelled_as_owed_not_paid(shared_stats_page):
    """The Per person section carries API.md's required caveat: owed, not paid.

    The caveat is the section's collapsed summary, so it's visible without
    expanding anything.
    """
    expect(
        shared_stats_page.get_by_text("what each owes, not what they paid").first
    ).to_be_visible()


def test_null_label_group_renders_as_unlabelled(unlabelled_stats_page, fixture_data):
    """A by_label row with `"label": null` renders the catalog's *unlabelled*, not blank."""
    isk = next(s for s in fixture_data["stats"]["stats"] if s["currency_code"] == "ISK")
    expand(unlabelled_stats_page, isk["currency_id"], "by_label")

    unlabelled = unlabelled_stats_page.get_by_text("unlabelled", exact=True)
    expect(unlabelled.first).to_be_visible()
    assert unlabelled.count() == 1
    assert unlabelled_stats_page.locator(".badge", has_text="None").count() == 0


def test_stat_sections_are_collapsed_by_default(stats_page, fixture_data):
    """A stat section's body is not visible until its header is clicked."""
    isk = next(s for s in fixture_data["stats"]["stats"] if s["currency_code"] == "ISK")

    body = stats_page.locator(f"#sec-{isk['currency_id']}-by_label-body")
    expect(body).to_be_hidden()
    expand(stats_page, isk["currency_id"], "by_label")
    expect(body).to_be_visible()


def test_sidebar_link_jumps_to_currency_section(stats_page, fixture_data):
    """Clicking a currency's sidebar link is a real anchor: it scrolls in and updates the hash.

    The tab itself is the URL path, not the hash, so a deep link like this is
    shareable without disturbing which tab is showing.
    """
    eur = next(s for s in fixture_data["stats"]["stats"] if s["currency_code"] == "EUR")
    base_url = stats_page.url

    stats_page.locator(".side-nav a", has_text="EUR").click()

    expect(stats_page).to_have_url(f"{base_url}#cur-{eur['currency_id']}")
    expect(stats_page.locator(f"#cur-{eur['currency_id']}")).to_be_in_viewport()
