"""Helpers and fixtures the statistics tab's suites share.

The picker and section locators, the fixture's groupings as the API answers them,
the chart's config read back from Chart.js, and one page fixture for the case
`trip.json` cannot express — spending dated before the trip starts — served as a
per-test stub rather than by editing the fixture every other suite reads.
"""

import pytest

CHART_DRAWN = """async (canvas) => {
    const { Chart } = await import('chart.js');
    return Boolean(Chart.getChart(canvas));
}"""

CHART_CONFIG = """async (canvas) => {
    const { Chart } = await import('chart.js');
    const { config } = Chart.getChart(canvas);
    return {
        type: config.type,
        indexAxis: config.options.indexAxis ?? null,
        stacked: config.options.scales?.x?.stacked ?? false,
        labels: config.data.labels,
        series: config.data.datasets.map((dataset) => dataset.label ?? null),
    };
}"""


def rows_of(page, currency_id):
    """Return the top-level breakdown rows of one currency's section."""
    return page.locator(f"#breakdown-{currency_id} > ul > li")


def picker(page):
    """Return the breakdown picker card."""
    return page.locator(".card", has_text="Breakdown")


def pick(page, dimension):
    """Append a dimension to the breakdown chain."""
    picker(page).locator("#stats-dimension").select_option(label=dimension)


def drop(page, dimension):
    """Remove a dimension from the breakdown chain."""
    picker(page).get_by_role("button", name=dimension).click()


def show(page, label):
    """Switch the page to one currency's section, or to the Total."""
    picker(page).locator("#stats-currency").select_option(label=label)


def set_chain(page, *dimensions):
    """Replace the whole chain, so the request asks for exactly these dimensions."""
    for chip in picker(page).locator("#stats-chain button").all_inner_texts():
        drop(page, chip.strip())
    for dimension in dimensions:
        pick(page, dimension)


def group_for(fixture_data, *dimensions):
    """Return the fixture's grouping for a dimension chain, as the API answers it."""
    chain = ["currency", *dimensions]
    return next(g for g in fixture_data["stats"]["groups"] if g["by"] == chain)


def chart_view(page):
    """Switch the page's sections from the list to the chart."""
    picker(page).get_by_role("button", name="Chart").click()


def chart_config(page, section_id):
    """Return what Chart.js was handed for one section's chart, once it has drawn."""
    canvas = page.locator(f"#breakdown-{section_id} canvas")
    page.wait_for_function(CHART_DRAWN, arg=canvas.element_handle())
    return canvas.evaluate(CHART_CONFIG)


@pytest.fixture
def isk_id(fixture_data):
    """Return the fixture trip's primary currency id."""
    return next(c["id"] for c in fixture_data["trip"]["trip"]["currencies"] if c["is_primary"])


@pytest.fixture
def before_trip_stats_page(stub, fixture_data, open_trip):
    """Return the Statistics tab served a `day` grouping with two ISK days before 2026-09-12."""
    total = group_for(fixture_data)["rows"][0]
    currency_id = total["keys"]["currency_id"]
    stats = {
        "groups": [
            {"by": ["currency"], "rows": [total]},
            {
                "by": ["currency", "day"],
                "rows": [
                    {
                        "keys": {"currency_id": currency_id, "date": date},
                        "amount": amount,
                        "item_count": 1,
                    }
                    for date, amount in [
                        ("2026-09-09", 10000),
                        ("2026-09-10", 10000),
                        ("2026-09-13", 102300),
                    ]
                ],
            },
        ],
        "day_count": 10,
    }
    stub("**/api/v1/trips/*/stats*", lambda request: (200, stats))
    return open_trip("stats")
