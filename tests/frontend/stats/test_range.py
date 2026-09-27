"""Tests for the statistics date range (breakdown.js range + Stats.js's withinRange).

The tab's one request already carries every level grouped by day as well, so a
range is a filter: the page keeps the days inside it and sums each level over them,
and no date change costs a request. It narrows the list and the chart alike and
survives a reload.
"""

import pytest
from playwright.sync_api import expect

from tests.frontend.stats.conftest import (
    EUR_ID,
    ISK_ID,
    chart_config,
    chart_view,
    rows_of,
    set_chain,
    show,
)


def pick_range(page, start=None, end=None):
    """Type the From and To dates into the picker; None leaves that end untouched."""
    if start is not None:
        page.locator("#stats-from").fill(start)
    if end is not None:
        page.locator("#stats-to").fill(end)


@pytest.fixture
def person_stats_page(stats_page):
    """Return the Statistics tab broken down by person."""
    set_chain(stats_page, "Person")
    return stats_page


def test_a_range_keeps_only_its_days(stats_page):
    """A one-day range leaves that day's row alone, with the section total narrowed to it."""
    pick_range(stats_page, "2026-09-14", "2026-09-14")

    expect(rows_of(stats_page, ISK_ID)).to_have_count(1)
    expect(rows_of(stats_page, ISK_ID).first).to_contain_text("14 Sep")
    expect(stats_page.locator(f"#cur-{ISK_ID} h2")).to_contain_text("26,300 total")


def test_no_date_change_costs_a_request(stats_page, count_requests):
    """Setting, moving and resetting a range all filter the rows the tab already holds."""
    stats = count_requests("*/api/v1/trips/*/stats")

    pick_range(stats_page, "2026-09-13", "2026-09-13")
    expect(rows_of(stats_page, ISK_ID)).to_have_count(1)
    pick_range(stats_page, end="2026-09-14")
    stats_page.get_by_role("button", name="Reset").click()
    expect(stats_page.locator("#stats-from")).to_have_value("")

    assert stats == []


def test_the_tab_asks_for_each_level_grouped_by_day(page, count_requests, open_trip):
    """Picking Person asks for the currency and person levels, each with day appended."""
    page.add_init_script("localStorage.setItem('breakdown:iceland-2026', '[\"person\"]')")
    stats = count_requests("*/api/v1/trips/*/stats")

    open_trip("stats")

    assert stats[0].url.endswith("?group_by=day&group_by=person,day")


def test_a_level_without_day_is_summed_over_the_range(person_stats_page):
    """By person, each row is that person's days inside the range added together."""
    pick_range(person_stats_page, "2026-09-13", "2026-09-14")

    petr = rows_of(person_stats_page, ISK_ID).filter(has_text="Petr")
    expect(petr).to_contain_text("34,003.57")  # 27,428.571428 + 6,575


def test_a_person_with_no_spend_in_range_drops_out(person_stats_page):
    """EUR on 14 Sep has no row for Bob, so Bob is absent from the narrowed list."""
    show(person_stats_page, "EUR")
    pick_range(person_stats_page, "2026-09-14", "2026-09-14")

    expect(rows_of(person_stats_page, EUR_ID)).to_have_count(3)
    expect(rows_of(person_stats_page, EUR_ID).filter(has_text="Bob")).to_have_count(0)


def test_a_range_with_no_spend_says_so(stats_page):
    """A range the currency spent nothing in shows the empty note instead of rows."""
    pick_range(stats_page, "2026-09-18", "2026-09-19")

    expect(stats_page.locator(f"#cur-{ISK_ID}")).to_contain_text(
        "Nothing was spent in these dates."
    )
    expect(stats_page.locator(f"#breakdown-{ISK_ID}")).to_have_count(0)


def test_the_chart_axis_covers_only_the_range(stats_page):
    """A range ending before the last spend ends the axis there, not at the spend."""
    chart_view(stats_page)
    pick_range(stats_page, "2026-09-13", "2026-09-13")

    config = chart_config(stats_page, ISK_ID)

    assert config["labels"] == ["13 Sep"]


def test_clearing_the_range_brings_every_day_back(stats_page):
    """Reset drops the range, so the list renders both ISK days again."""
    pick_range(stats_page, "2026-09-14", "2026-09-14")

    stats_page.get_by_role("button", name="Reset").click()

    expect(rows_of(stats_page, ISK_ID)).to_have_count(2)
    expect(stats_page.locator("#stats-from")).to_have_value("")


def test_trip_start_sets_the_range_to_begin_with_the_trip(stats_page):
    """Trip start fills From with the trip's start date, then hides until From moves off it."""
    trip_start = stats_page.get_by_role("button", name="Trip start")

    trip_start.click()

    expect(stats_page.locator("#stats-from")).to_have_value("2026-09-12")
    expect(trip_start).to_have_count(0)
