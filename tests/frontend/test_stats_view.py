"""Tests for views/Stats.js.

Per-currency view renders by_label, by_country, by_person, by_day in the order given;
the "label": null group renders as unlabelled; country flags shown; the overlap caveat
is on screen next to by_label and by_person is labelled as owed, not paid — both are
API.md requirements, not copy.
"""

import pytest
from playwright.sync_api import expect

OVERLAP_CAVEAT = (
    "An item can carry several labels, so these rows overlap and add up to more than the total."
)


@pytest.fixture
def unlabelled_stats_page(stub, fixture_data, open_trip):
    """Return the Statistics tab served a single ISK stat whose only by_label row is `null`."""
    isk = next(s for s in fixture_data["stats"]["stats"] if s["currency_code"] == "ISK")
    isk["by_label"] = [{"label": None, "item_count": 2, "amount": 122300}]
    stub("**/api/v1/trips/*/stats", lambda request: (200, {"stats": [isk], "day_count": 1}))

    return open_trip("stats")


def test_sections_render_in_api_order_for_one_currency(stats_page):
    """A currency's four stat sections appear in the exact order the API returns them.

    "total ISK" is unique to ISK's own By label header — the combined view's card shows
    the primary currency's symbol ("kr"), not its code.
    """
    expect(stats_page.locator(".card-header", has_text="total ISK")).to_be_visible()

    headers = stats_page.locator(".card-header").all_inner_texts()

    isk_index = next(i for i, header in enumerate(headers) if "total ISK" in header)
    assert "By label" in headers[isk_index]
    assert "By country" in headers[isk_index + 1]
    assert "Per person" in headers[isk_index + 2]
    assert "By day" in headers[isk_index + 3]


@pytest.mark.parametrize(
    "flag_and_name",
    [
        pytest.param("🇮🇸 Iceland", id="iceland"),
        pytest.param("🇩🇰 Denmark", id="denmark"),
    ],
)
def test_country_flag_shown_in_by_country_row(stats_page, flag_and_name):
    """A by_country row shows the country's flag next to its name."""
    expect(stats_page.get_by_text(flag_and_name).first).to_be_visible()


def test_overlap_caveat_is_inside_the_by_label_card(stats_page, card):
    """The by_label overlap note lives in the same card as By label, not just somewhere."""
    by_label_card = card("total ISK")

    expect(by_label_card).to_have_count(1)
    expect(by_label_card).to_contain_text(OVERLAP_CAVEAT)


def test_by_person_is_labelled_as_owed_not_paid(stats_page):
    """The Per person header carries API.md's required caveat: owed, not paid."""
    expect(stats_page.get_by_text("what each owes, not what they paid").first).to_be_visible()


def test_null_label_group_renders_as_unlabelled(unlabelled_stats_page):
    """A by_label row with `"label": null` renders the catalog's *unlabelled*, not blank.

    The stub returns only one stat currency, so both the combined view and the
    per-currency view show the same group — hence two matches, not one.
    """
    unlabelled = unlabelled_stats_page.get_by_text("unlabelled", exact=True)

    expect(unlabelled.first).to_be_visible()
    assert unlabelled.count() == 2
    assert unlabelled_stats_page.locator(".badge", has_text="None").count() == 0
