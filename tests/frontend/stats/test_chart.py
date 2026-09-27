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

from tests.frontend.stats.conftest import (
    chart_config,
    chart_view,
    group_for,
    set_chain,
    show,
)


def test_chart_replaces_the_list_without_a_request(stats_page, count_requests, isk_id):
    """The chart draws the rows already in the store, so switching to it fetches nothing."""
    stats = count_requests("*/stats")

    chart_view(stats_page)

    expect(stats_page.locator(f"#breakdown-{isk_id} canvas")).to_be_visible()
    expect(stats_page.locator(f"#breakdown-{isk_id} > ul")).to_have_count(0)
    assert stats == []


def test_the_chart_view_survives_a_reload(stats_page, isk_id):
    """The view lives in localStorage, next to the chain and the shown currency."""
    chart_view(stats_page)
    stats_page.reload()
    stats_page.locator(".stats-content").wait_for()

    expect(stats_page.locator(f"#breakdown-{isk_id} canvas")).to_be_visible()


def test_day_columns_run_from_the_trip_start_to_the_last_spend(stats_page, isk_id):
    """A day with no spend is an empty column; days after the last expense are not drawn."""
    chart_view(stats_page)

    config = chart_config(stats_page, isk_id)

    assert (config["type"], config["indexAxis"]) == ("bar", "x")
    assert config["labels"] == ["12 Sep", "13 Sep", "14 Sep"]  # ISK last spent on 14 Sep


@pytest.mark.parametrize("dimension", ["Label", "Person", "Country"])
def test_any_first_dimension_but_day_draws_horizontal_bars(stats_page, isk_id, dimension):
    """Only a time axis runs across; every other first dimension is a bar per row."""
    set_chain(stats_page, dimension)
    chart_view(stats_page)

    config = chart_config(stats_page, isk_id)

    assert (config["type"], config["indexAxis"]) == ("bar", "y")


def test_a_second_dimension_stacks_each_column(stats_page, fixture_data, isk_id):
    """Day then Person stacks each day's column with one series per person."""
    people = {
        row["keys"]["person_id"]
        for row in group_for(fixture_data, "day", "person")["rows"]
        if row["keys"]["currency_id"] == isk_id
    }
    set_chain(stats_page, "Day", "Person")
    chart_view(stats_page)

    config = chart_config(stats_page, isk_id)

    assert config["stacked"] is True
    assert len(config["series"]) == len(people)
    assert "Petr" in config["series"]


def test_a_label_second_level_draws_side_by_side_bars(stats_page, isk_id):
    """Country then Label splits each country into one unstacked bar per label."""
    set_chain(stats_page, "Country", "Label")
    chart_view(stats_page)

    config = chart_config(stats_page, isk_id)

    assert (config["type"], config["stacked"]) == ("bar", False)
    assert config["series"] == ["lodging", "food", "restaurant", "fuel", "transport"]


def test_a_third_level_joins_the_second_in_each_series(stats_page, isk_id):
    """Country, Payer, Label draws one side-by-side series per payer and label pair."""
    set_chain(stats_page, "Country", "Payer", "Label")
    chart_view(stats_page)

    config = chart_config(stats_page, isk_id)

    assert config["stacked"] is False
    assert config["series"] == [
        "Eva · lodging",
        "Petr · food",
        "Petr · restaurant",
        "Bob · fuel",
        "Bob · transport",
    ]


def test_the_before_trip_bucket_opens_the_day_axis(before_trip_stats_page, isk_id):
    """Days before the start fold into one "Before the trip" column ahead of every trip day."""
    chart_view(before_trip_stats_page)

    config = chart_config(before_trip_stats_page, isk_id)

    assert config["labels"] == ["Before the trip", "12 Sep", "13 Sep"]


def test_the_total_draws_no_chart_until_every_rate_is_set(stats_page):
    """The Total's all-or-nothing gate holds for the chart as it does for the list."""
    chart_view(stats_page)
    show(stats_page, "Total")

    expect(stats_page.locator("#cur-total")).to_be_visible()
    expect(stats_page.locator("#cur-total canvas")).to_have_count(0)


def test_an_open_ended_trip_still_draws_its_empty_days(stub, fixture_data, open_trip, isk_id):
    """A trip with no end date fills the axis from its start to the last spend all the same."""
    trip = fixture_data["trip"]["trip"]
    stub(
        "**/api/v1/trips/iceland-2026", lambda request: (200, {"trip": {**trip, "end_date": None}})
    )
    page = open_trip("stats")
    chart_view(page)

    config = chart_config(page, isk_id)

    assert config["labels"] == ["12 Sep", "13 Sep", "14 Sep"]


def test_a_chart_that_cannot_load_says_so(stats_page, isk_id):
    """Chart.js failing to load leaves a message where the chart would be, not a blank box."""
    stats_page.route("**/chart.js@*/**", lambda route: route.abort())

    chart_view(stats_page)

    expect(stats_page.locator(f"#breakdown-{isk_id}")).to_contain_text("The chart could not load.")
    expect(stats_page.locator(f"#breakdown-{isk_id} canvas")).to_have_count(0)
