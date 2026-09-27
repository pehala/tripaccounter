"""Tests for views/Stats.js.

The page shows one currency at a time, picked from a dropdown, broken down by a
chain the user picks. The chain drives the request, the nesting and which caveats
show; the currency drives nothing but which rows are on screen — every grouping
carries every currency, so switching is a filter, never a fetch.
"""

import pytest
from playwright.sync_api import expect

from tests.frontend.stats.conftest import (
    DKK_ID,
    EUR_ID,
    ISK_ID,
    ISK_TOTAL,
    chart_view,
    drop,
    pick,
    reload,
    rows_of,
    set_chain,
    show,
)


@pytest.fixture
def unlabelled_stats_page(serve_stats, open_trip):
    """Return the Statistics tab served a single ISK grouping whose only label row is `null`."""
    serve_stats(
        [
            {"by": ["currency"], "rows": [ISK_TOTAL]},
            {
                "by": ["currency", "label"],
                "rows": [
                    {
                        "keys": {"currency_id": ISK_ID, "label": None},
                        "amount": ISK_TOTAL["amount"],
                        "item_count": 2,
                    }
                ],
            },
        ],
        day_count=1,
    )
    return open_trip("stats")


@pytest.fixture
def no_dkk_stats_page(serve_stats, fixture_data, open_trip):
    """Return the Statistics tab served the fixture's groupings with every DKK row taken out."""
    serve_stats(
        [
            {**group, "rows": [r for r in group["rows"] if r["keys"]["currency_id"] != DKK_ID]}
            for group in fixture_data["stats"]["groups"]
        ]
    )
    return open_trip("stats")


def test_the_default_breakdown_is_by_day(shared_stats_page):
    """With nothing picked, the page renders the day chain: ISK spent on 13 and 14 Sep."""
    rows = rows_of(shared_stats_page, ISK_ID)

    expect(rows).to_have_count(2)
    expect(rows.first).to_contain_text("13 Sep")


def test_picking_a_second_dimension_nests_it_under_the_first(stats_page):
    """Day then Person renders each day's people inside that day's own row, with their amount."""
    pick(stats_page, "Person")

    first_day = rows_of(stats_page, ISK_ID).first
    expect(first_day.locator("ul > li")).to_have_count(4)
    expect(first_day.locator("ul > li", has_text="Petr")).to_contain_text("27,428.57")


def test_a_nested_percentage_is_of_its_parent_row(stats_page):
    """A share reads against the row it sits in: 29% of its day, not 22% of the trip."""
    pick(stats_page, "Person")

    first_day = rows_of(stats_page, ISK_ID).first
    expect(first_day).to_contain_text("78%")
    expect(first_day.locator("ul > li", has_text="Petr")).to_contain_text("29%")


def test_dropping_a_dimension_removes_its_level(stats_page):
    """Removing Day leaves the chain it was leading, re-rendered without it."""
    pick(stats_page, "Person")
    drop(stats_page, "Day")

    expect(rows_of(stats_page, ISK_ID).first).to_contain_text("Petr")
    expect(rows_of(stats_page, ISK_ID).first.locator("ul > li")).to_have_count(0)


def test_page_settings_survive_a_reload(stats_page):
    """Chain, shown currency, chart view and date range all live in localStorage."""
    set_chain(stats_page, "Country")
    show(stats_page, "EUR")
    chart_view(stats_page)
    stats_page.locator("#stats-from").fill("2026-09-14")

    reload(stats_page)

    expect(stats_page.locator(".card", has_text="Breakdown")).to_contain_text("Country")
    expect(stats_page.locator(f"#cur-{EUR_ID}")).to_have_count(1)
    expect(stats_page.locator(f"#breakdown-{EUR_ID} canvas")).to_be_visible()
    expect(stats_page.locator("#stats-from")).to_have_value("2026-09-14")


def test_currency_is_not_offered_as_a_dimension(shared_stats_page):
    """Currency is forced on every grouping, so it is never something to pick."""
    options = shared_stats_page.locator(".card", has_text="Breakdown").locator("option")
    assert "Currency" not in options.all_inner_texts()


def test_country_flags_shown_in_country_rows(stats_page):
    """A country row shows the country's flag next to its name."""
    set_chain(stats_page, "Country")

    expect(rows_of(stats_page, ISK_ID).first).to_contain_text("🇮🇸 Iceland")


@pytest.mark.parametrize(
    ("dimension", "caveat"),
    [
        pytest.param(
            "Label",
            "An item can carry several labels, so these rows overlap and add up to more than"
            " the row they sit in.",
            id="label-overlap",
        ),
        pytest.param("Person", "what each owes, not what they paid", id="person-owed-not-paid"),
    ],
)
def test_a_dimension_caveat_shows_only_while_it_is_picked(stats_page, dimension, caveat):
    """The overlap note belongs to Label and API.md's owed-not-paid note to Person, not the page."""
    expect(stats_page.get_by_text(caveat).first).to_be_hidden()

    pick(stats_page, dimension)

    expect(stats_page.get_by_text(caveat).first).to_be_visible()


def test_null_label_row_renders_as_unlabelled(unlabelled_stats_page):
    """A label row with `"label": null` renders the catalog's *unlabelled*, not blank."""
    set_chain(unlabelled_stats_page, "Label")

    unlabelled = unlabelled_stats_page.get_by_text("unlabelled", exact=True)
    expect(unlabelled.first).to_be_visible()
    assert unlabelled_stats_page.locator(".badge", has_text="None").count() == 0


def test_only_the_picked_currency_is_on_screen(shared_stats_page):
    """One currency at a time: the others are a dropdown away, not further down the page."""
    expect(shared_stats_page.locator("[id^=cur-]")).to_have_count(1)
    expect(shared_stats_page.locator(f"#cur-{ISK_ID}")).to_have_count(1)


def test_switching_currency_costs_no_request(stats_page, count_requests):
    """The rows for every currency arrived in one answer, so a switch is a filter."""
    stats = count_requests("*/stats")

    show(stats_page, "EUR")

    expect(stats_page.locator(f"#cur-{EUR_ID}")).to_have_count(1)
    assert stats == []


def test_a_currency_with_no_rows_is_not_offered(no_dkk_stats_page):
    """Only the currencies the API returned rows for can be picked: DKK is gone from the list."""
    expect(no_dkk_stats_page.locator("#stats-currency option")).to_have_text(
        ["Total", "ISK", "EUR"]
    )


def test_days_before_the_trip_fold_into_one_leading_row(before_trip_stats_page):
    """Days before the start render as one "Before the trip" row, as in the item feed."""
    rows = rows_of(before_trip_stats_page, ISK_ID)

    expect(rows).to_have_count(2)
    expect(rows.first).to_contain_text("Before the trip")
    expect(rows.nth(1)).to_contain_text("13 Sep")
