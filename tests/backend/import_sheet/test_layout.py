"""Column layout and the problems `build_plan` reports before anything is written."""

import pytest

from tests.backend.import_sheet.conftest import HEADER, PEOPLE, PRAGUE
from tools.import_sheet import Layout, build_plan


@pytest.mark.parametrize(
    ("names", "owed", "note"),
    [
        pytest.param(["Ann", "Bob"], (9, 11), 13, id="two-people"),
        pytest.param(["Ann", "Bob", "Cal"], (9, 11, 13), 15, id="three-people"),
    ],
)
def test_layout_places_owed_columns_two_apart_with_the_note_after(names, owed, note):
    """Each person owns one owed column plus its helper, and the note column follows them."""
    layout = Layout.for_people(names)

    assert (layout.owed, layout.note) == (owed, note)


def test_build_plan_rejects_a_people_list_that_overruns_the_row(sheet, row):
    """Naming more people than the sheet has columns for is refused before anything is read."""
    too_many = ["Ann", "Bob", "Cal", "Dee", "Eve", "Fay"]

    with pytest.raises(SystemExit, match="note column"):
        build_plan(sheet([row()]), too_many, PRAGUE)


def test_build_plan_catches_owed_columns_that_land_on_the_summary_block(sheet, row):
    """A roster too long but still inside the row reads cells from the summary block."""
    plan = build_plan(sheet([row()]), ["Ann", "Bob", "Cal", "Dee"], PRAGUE)

    assert [(problem.code, problem.detail) for problem in plan.problems] == [
        ("bad_share", "Dee: 'Ann'")
    ]


def test_build_plan_reads_columns_by_index_not_by_header(sheet, row):
    """Headers in another language change nothing: only the indexes are read."""
    czech = [
        "Název",
        "Datum",
        "Kategorie",
        "Kdo platil",
        "Kolik",
        "Měna",
        "Stát",
        "Kurz CZK",
        "Kurz EUR",
        "Ann dluží",
        "",
        "Bob dluží",
        "",
        "Poznámky",
    ]

    plan = build_plan(sheet([row()], header=czech), PEOPLE, PRAGUE)

    assert plan.problems == []
    assert plan.items[0].name == "ITEM3"
    assert plan.items[0].amount == "1240.00"


def test_build_plan_reports_a_payer_who_is_not_in_the_roster(sheet, row):
    """A payer cell naming someone outside --people is a problem, not a new person."""
    plan = build_plan(sheet([row(**{"3": "Cal"})]), PEOPLE, PRAGUE)

    assert [(problem.code, problem.detail) for problem in plan.problems] == [
        ("unknown_payer", "'Cal' is not in --people ['Ann', 'Bob']")
    ]


@pytest.mark.parametrize(
    ("column", "value", "code"),
    [
        pytest.param("1", "", "bad_date", id="date-empty"),
        pytest.param("2", "two words", "label_whitespace", id="category-with-a-space"),
        pytest.param("4", "0,00", "bad_amount", id="amount-zero"),
        pytest.param("5", "EURO", "bad_currency", id="currency-not-three-letters"),
        pytest.param("6", "", "bad_country", id="country-blank"),
        pytest.param("11", "?", "bad_share", id="owed-cell-not-a-number"),
    ],
)
def test_build_plan_reports_unusable_cells(sheet, row, column, value, code):
    """Each unusable cell becomes a named problem rather than a partial import."""
    plan = build_plan(sheet([row(**{column: value})]), PEOPLE, PRAGUE)

    assert code in {problem.code for problem in plan.problems}


def test_build_plan_skips_rows_with_no_name(sheet, row):
    """The blank rows a spreadsheet leaves below the data are dropped, not reported."""
    blank = [""] * len(HEADER)

    plan = build_plan(sheet([row(), blank, blank]), PEOPLE, PRAGUE)

    assert (len(plan.items), plan.problems) == (1, [])
