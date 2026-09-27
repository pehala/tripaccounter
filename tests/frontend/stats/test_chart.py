"""Tests for the statistics chart view (components/StatsChart.js + Stats.js's chartSpec).

The chart is a second rendering of the rows the list already has: switching to it
costs no request, it survives a reload, and two rules shape it for any chain: the
first dimension is the axis — columns over the trip's days, horizontal bars for the
rest — and every later one splits each bar into a series per combination, stacked
unless one of them is a label.
Its config is read back from Chart.js itself, since a canvas has no DOM to inspect.
"""

import pytest
from playwright.sync_api import expect

from tests.frontend.stats.conftest import ISK_ID, chart_config, chart_view, set_chain, show


def test_chart_replaces_the_list_without_a_request(stats_page, count_requests):
    """The chart draws the rows already in the store, so switching to it fetches nothing."""
    stats = count_requests("*/stats")

    chart_view(stats_page)

    expect(stats_page.locator(f"#breakdown-{ISK_ID} canvas")).to_be_visible()
    expect(stats_page.locator(f"#breakdown-{ISK_ID} > ul")).to_have_count(0)
    assert stats == []


@pytest.mark.parametrize(
    "end_date",
    [pytest.param("2026-09-21", id="dated-trip"), pytest.param(None, id="open-ended-trip")],
)
def test_day_columns_run_from_the_trip_start_to_the_last_spend(
    stub, fixture_data, open_trip, end_date
):
    """A day with no spend is an empty column; days after ISK's last expense, 14 Sep, are not."""
    trip = {**fixture_data["trip"]["trip"], "end_date": end_date}
    stub("**/api/v1/trips/iceland-2026", lambda request: (200, {"trip": trip}), method="GET")
    page = open_trip("stats")
    chart_view(page)

    config = chart_config(page, ISK_ID)

    assert config["labels"] == ["12 Sep", "13 Sep", "14 Sep"]


@pytest.mark.parametrize(
    ("dimension", "index_axis"),
    [
        pytest.param("Day", "x", id="day-columns"),
        pytest.param("Label", "y", id="label-bars"),
        pytest.param("Person", "y", id="person-bars"),
        pytest.param("Country", "y", id="country-bars"),
    ],
)
def test_only_a_day_axis_runs_across(stats_page, dimension, index_axis):
    """Day draws columns over time; every other first dimension is a horizontal bar per row."""
    set_chain(stats_page, dimension)
    chart_view(stats_page)

    config = chart_config(stats_page, ISK_ID)

    assert (config["type"], config["indexAxis"]) == ("bar", index_axis)


def test_a_second_dimension_stacks_each_column(stats_page):
    """Day then Person stacks each day's column with one series per person."""
    set_chain(stats_page, "Day", "Person")
    chart_view(stats_page)

    config = chart_config(stats_page, ISK_ID)

    assert config["stacked"] is True
    assert sorted(config["series"]) == ["Ann", "Bob", "Eva", "Petr"]


def test_a_label_second_level_draws_side_by_side_bars(stats_page):
    """Country then Label splits each country into one unstacked bar per label."""
    set_chain(stats_page, "Country", "Label")
    chart_view(stats_page)

    config = chart_config(stats_page, ISK_ID)

    assert (config["type"], config["stacked"]) == ("bar", False)
    assert config["series"] == ["lodging", "food", "restaurant", "fuel", "transport"]


def test_a_third_level_joins_the_second_in_each_series(stats_page):
    """Country, Payer, Label draws one side-by-side series per payer and label pair."""
    set_chain(stats_page, "Country", "Payer", "Label")
    chart_view(stats_page)

    config = chart_config(stats_page, ISK_ID)

    assert config["stacked"] is False
    assert config["series"] == [
        "Eva · lodging",
        "Petr · food",
        "Petr · restaurant",
        "Bob · fuel",
        "Bob · transport",
    ]


def test_the_before_trip_bucket_opens_the_day_axis(before_trip_stats_page):
    """Days before the start fold into one "Before the trip" column ahead of every trip day."""
    chart_view(before_trip_stats_page)

    config = chart_config(before_trip_stats_page, ISK_ID)

    assert config["labels"] == ["Before the trip", "12 Sep", "13 Sep"]


def test_the_total_draws_no_chart_until_every_rate_is_set(stats_page):
    """The Total's all-or-nothing gate holds for the chart as it does for the list."""
    chart_view(stats_page)
    show(stats_page, "Total")

    expect(stats_page.locator("#cur-total")).to_be_visible()
    expect(stats_page.locator("#cur-total canvas")).to_have_count(0)


def test_a_chart_that_cannot_load_says_so(stats_page):
    """Chart.js failing to load leaves a message where the chart would be, not a blank box."""
    stats_page.route("**/chart.js@*/**", lambda route: route.abort())

    chart_view(stats_page)

    expect(stats_page.locator(f"#breakdown-{ISK_ID}")).to_contain_text("The chart could not load.")
    expect(stats_page.locator(f"#breakdown-{ISK_ID} canvas")).to_have_count(0)
