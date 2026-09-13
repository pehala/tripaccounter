"""Tests for views/Stats.js.

Per-currency view renders by_label,
by_country, by_person, by_day in the order given; the "label": null group renders
as unlabelled; country flags shown; the overlap caveat is on screen next to
by_label and by_person is labelled as owed, not paid — both are API.md
requirements, not copy.
"""

import copy

from playwright.sync_api import expect


def test_by_label_by_country_by_person_by_day_render_in_order_for_one_currency(
    page, mockserver, trip_url, fixture_data
):
    """A currency's four stat sections appear in the exact order the API returns them."""
    page.goto(f"{trip_url}#stats")
    isk = next(s for s in fixture_data["stats"]["stats"] if s["currency_code"] == "ISK")
    # "total ISK" is unique to ISK's own By label header — the combined view's
    # equivalent card shows the primary currency's symbol ("kr"), not its code.
    by_label_header = page.locator(".card-header", has_text="total ISK")
    expect(by_label_header).to_be_visible()

    headers = page.locator(".card-header").all_inner_texts()
    isk_index = next(i for i, h in enumerate(headers) if "total ISK" in h)
    assert "By label" in headers[isk_index]
    assert "By country" in headers[isk_index + 1]
    assert "Per person" in headers[isk_index + 2]
    assert "By day" in headers[isk_index + 3]
    assert isk["total"] > 0  # sanity: the fixture actually has data to render


def test_country_flags_shown_in_by_country_rows(page, mockserver, trip_url):
    """A by_country row shows the country's flag next to its name."""
    page.goto(f"{trip_url}#stats")

    expect(page.get_by_text("🇮🇸 Iceland").first).to_be_visible()
    expect(page.get_by_text("🇩🇰 Denmark").first).to_be_visible()


def test_overlap_caveat_is_inside_the_by_label_card(page, mockserver, trip_url):
    """The by_label overlap note lives in the same card as By label, not just somewhere."""
    page.goto(f"{trip_url}#stats")

    by_label_card = page.locator(".card").filter(
        has=page.locator(".card-header", has_text="total ISK")
    )
    expect(by_label_card).to_have_count(1)
    expect(by_label_card).to_contain_text(
        "An item can carry several labels, so these rows overlap and add up to more than the total."
    )


def test_by_person_is_labelled_as_owed_not_paid(page, mockserver, trip_url):
    """The Per person header carries API.md's required caveat: owed, not paid."""
    page.goto(f"{trip_url}#stats")

    expect(page.get_by_text("what each owes, not what they paid").first).to_be_visible()


def test_null_label_group_renders_as_unlabelled(page, mockserver, trip_url, stub, fixture_data):
    """A by_label row with `"label": null` renders the catalog's *unlabelled*, not blank.

    The stub returns only one stat currency, so both the combined view and the
    per-currency view show the same group — hence two matches, not one.
    """
    isk = copy.deepcopy(
        next(s for s in fixture_data["stats"]["stats"] if s["currency_code"] == "ISK")
    )
    isk["by_label"] = [{"label": None, "item_count": 2, "amount": isk["total"]}]
    stub(
        "**/api/v1/trips/*/stats",
        lambda request: (200, {"stats": [isk], "day_count": 1}),
    )

    page.goto(f"{trip_url}#stats")

    unlabelled = page.get_by_text("unlabelled", exact=True)
    expect(unlabelled.first).to_be_visible()
    assert unlabelled.count() == 2
    assert page.locator(".badge", has_text="None").count() == 0
