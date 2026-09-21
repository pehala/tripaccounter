"""Tests for views/Stats.js.

The page shows one currency at a time, picked from a dropdown, broken down by a
chain the user picks. The chain drives the request, the nesting and which caveats
show; the currency drives nothing but which rows are on screen — every grouping
carries every currency, so switching is a filter, never a fetch.
"""

import pytest
from playwright.sync_api import expect

OVERLAP_CAVEAT = (
    "An item can carry several labels, so these rows overlap and add up to more than the row"
    " they sit in."
)


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
    for chip in picker(page).locator("button").all_inner_texts():
        drop(page, chip.strip())
    for dimension in dimensions:
        pick(page, dimension)


def group_for(fixture_data, *dimensions):
    """Return the fixture's grouping for a dimension chain, as the API answers it."""
    chain = ["currency", *dimensions]
    return next(g for g in fixture_data["stats"]["groups"] if g["by"] == chain)


@pytest.fixture
def isk_id(fixture_data):
    """Return the fixture trip's primary currency id."""
    return next(c["id"] for c in fixture_data["trip"]["trip"]["currencies"] if c["is_primary"])


@pytest.fixture
def unlabelled_stats_page(stub, fixture_data, open_trip):
    """Return the Statistics tab served a single ISK grouping whose only label row is `null`."""
    total = group_for(fixture_data)["rows"][0]
    stub(
        "**/api/v1/trips/*/stats*",
        lambda request: (
            200,
            {
                "groups": [
                    {"by": ["currency"], "rows": [total]},
                    {
                        "by": ["currency", "label"],
                        "rows": [
                            {
                                "keys": {
                                    "currency_id": total["keys"]["currency_id"],
                                    "label": None,
                                },
                                "amount": total["amount"],
                                "item_count": 2,
                            }
                        ],
                    },
                ],
                "day_count": 1,
            },
        ),
    )

    return open_trip("stats")


def test_the_default_breakdown_is_by_day(shared_stats_page, fixture_data, isk_id):
    """With nothing picked, the page renders the day chain the store asks for by default."""
    days = [
        row["keys"]["date"]
        for row in group_for(fixture_data, "day")["rows"]
        if row["keys"]["currency_id"] == isk_id
    ]
    assert days  # sanity: the fixture has ISK days to render

    expect(rows_of(shared_stats_page, isk_id)).to_have_count(len(days))
    expect(rows_of(shared_stats_page, isk_id).first).to_contain_text("13 Sep")


def test_picking_a_second_dimension_nests_it_under_the_first(stats_page, fixture_data, isk_id):
    """Day then Person renders each day's people inside that day's own row."""
    pick(stats_page, "Person")

    first_day = rows_of(stats_page, isk_id).first
    expect(first_day.locator("ul > li")).to_have_count(
        len(
            [
                row
                for row in group_for(fixture_data, "day", "person")["rows"]
                if row["keys"]["currency_id"] == isk_id and row["keys"]["date"] == "2026-09-13"
            ]
        )
    )
    expect(first_day).to_contain_text("Petr")


def test_a_nested_row_shows_the_amount_the_api_grouped(stats_page, fixture_data, isk_id):
    """A leaf renders its own grouping's amount — the page never sums anything itself."""
    pick(stats_page, "Person")

    owed = next(
        row
        for row in group_for(fixture_data, "day", "person")["rows"]
        if row["keys"]["currency_id"] == isk_id and row["keys"]["date"] == "2026-09-13"
    )
    person = next(
        p for p in fixture_data["trip"]["trip"]["people"] if p["id"] == owed["keys"]["person_id"]
    )

    leaf = rows_of(stats_page, isk_id).first.locator("ul > li", has_text=person["name"])
    expect(leaf).to_contain_text("27,428.57")


def test_a_nested_percentage_is_of_its_parent_row(stats_page, isk_id):
    """A share reads against the row it sits in: 29% of its day, not 22% of the trip."""
    pick(stats_page, "Person")

    first_day = rows_of(stats_page, isk_id).first
    expect(first_day).to_contain_text("78%")  # the day itself, against the ISK total
    expect(first_day.locator("ul > li", has_text="Petr")).to_contain_text("29%")


def test_dropping_a_dimension_removes_its_level(stats_page, isk_id):
    """Removing Day leaves the chain it was leading, re-rendered without it."""
    pick(stats_page, "Person")
    drop(stats_page, "Day")

    expect(rows_of(stats_page, isk_id).first).to_contain_text("Petr")
    expect(rows_of(stats_page, isk_id).first.locator("ul > li")).to_have_count(0)


def test_the_picked_chain_survives_a_reload(stats_page, isk_id):
    """The chain lives in localStorage, so the page comes back grouped the same way."""
    set_chain(stats_page, "Country")
    stats_page.reload()
    stats_page.locator(".stats-content").wait_for()

    expect(stats_page.locator(".card", has_text="Breakdown")).to_contain_text("Country")
    expect(rows_of(stats_page, isk_id).first).to_contain_text("Iceland")


def test_currency_is_not_offered_as_a_dimension(shared_stats_page):
    """Currency is forced on every grouping, so it is never something to pick."""
    options = shared_stats_page.locator(".card", has_text="Breakdown").locator("option")
    assert "Currency" not in options.all_inner_texts()


def test_country_flags_shown_in_country_rows(stats_page, isk_id):
    """A country row shows the country's flag next to its name."""
    set_chain(stats_page, "Country")

    expect(stats_page.get_by_text("🇮🇸 Iceland").first).to_be_visible()


def test_overlap_caveat_shows_only_while_label_is_picked(stats_page, isk_id):
    """The overlap note belongs to the label dimension, not to the page."""
    expect(stats_page.get_by_text(OVERLAP_CAVEAT).first).to_be_hidden()

    pick(stats_page, "Label")

    expect(stats_page.locator(f"#breakdown-{isk_id}")).to_contain_text(OVERLAP_CAVEAT)


def test_owed_not_paid_caveat_shows_only_while_person_is_picked(stats_page):
    """Per-person figures carry API.md's required caveat wherever they render."""
    expect(stats_page.get_by_text("what each owes, not what they paid").first).to_be_hidden()

    pick(stats_page, "Person")

    expect(stats_page.get_by_text("what each owes, not what they paid").first).to_be_visible()


def test_null_label_row_renders_as_unlabelled(unlabelled_stats_page, isk_id):
    """A label row with `"label": null` renders the catalog's *unlabelled*, not blank."""
    set_chain(unlabelled_stats_page, "Label")

    unlabelled = unlabelled_stats_page.get_by_text("unlabelled", exact=True)
    expect(unlabelled.first).to_be_visible()
    assert unlabelled_stats_page.locator(".badge", has_text="None").count() == 0


def test_only_the_picked_currency_is_on_screen(shared_stats_page, fixture_data, isk_id):
    """One currency at a time: the others are a dropdown away, not further down the page."""
    others = [c["id"] for c in fixture_data["trip"]["trip"]["currencies"] if c["id"] != isk_id]

    expect(shared_stats_page.locator(f"#cur-{isk_id}")).to_have_count(1)
    for currency_id in others:
        expect(shared_stats_page.locator(f"#cur-{currency_id}")).to_have_count(0)


def test_switching_currency_costs_no_request(stats_page, fixture_data):
    """The rows for every currency arrived in one answer, so a switch is a filter."""
    calls = []
    stats_page.on(
        "request", lambda request: calls.append(request.url) if "/stats" in request.url else None
    )

    show(stats_page, "EUR")

    eur = next(c for c in fixture_data["trip"]["trip"]["currencies"] if c["code"] == "EUR")
    expect(stats_page.locator(f"#cur-{eur['id']}")).to_have_count(1)
    assert calls == []


def test_a_currency_with_no_rows_is_not_offered(stats_page, fixture_data):
    """Only the currencies the API returned rows for can be picked."""
    spent = {row["keys"]["currency_id"] for row in group_for(fixture_data)["rows"]}
    offered = stats_page.locator("#stats-currency option").all_inner_texts()

    for currency in fixture_data["trip"]["trip"]["currencies"]:
        assert (currency["code"] in offered) is (currency["id"] in spent)


def test_the_picked_currency_survives_a_reload(stats_page, fixture_data):
    """The shown currency lives in localStorage, like the chain and the rates."""
    eur = next(c for c in fixture_data["trip"]["trip"]["currencies"] if c["code"] == "EUR")

    show(stats_page, "EUR")
    stats_page.reload()
    stats_page.locator(".stats-content").wait_for()

    expect(stats_page.locator(f"#cur-{eur['id']}")).to_have_count(1)
