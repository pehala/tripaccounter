"""Tests for the CSV sheet importer.

`fixtures/sheet.csv` is the worked example of the format: an invented trip whose 24
rows carry no real data and cover every case the importer distinguishes. The
tests here import that file rather than inventing sheets inline, so the committed
example and the behaviour it documents cannot drift apart. Variants are built by
overriding one cell of it, which keeps one source of truth for what a row looks like.

The importer is a migration script, not an endpoint, so its two halves are tested the
two ways the skill allows. Resolving a row into an item body is pure arithmetic over
combinatorial inputs — split modes, date shapes, decimal grammars — and is called
directly, like `test_money.py`. Writing those rows goes through the `session` fixture
and is read back over `client`, which is the only place the result is observable.
"""

import csv
import sys
from decimal import Decimal
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest
from alembic.config import Config
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from alembic import command
from app.models.trip import Trip
from tools.import_sheet import (
    Layout,
    apply,
    build_plan,
    canonical_amount,
    create_trip,
    infer_split,
    parse_decimal,
    parse_occurred_at,
)
from tools.import_sheet import __main__ as cli

ALEMBIC_SCRIPT_LOCATION = Path(__file__).resolve().parent.parent.parent / "alembic"
SAMPLE = Path(__file__).parent / "fixtures" / "sheet.csv"
PRAGUE = ZoneInfo("Europe/Prague")
PEOPLE = ["Ann", "Bob"]

with SAMPLE.open(encoding="utf-8", newline="") as handle:
    SAMPLE_ROWS = list(csv.reader(handle))
HEADER = SAMPLE_ROWS[0]
BASE_ROW = SAMPLE_ROWS[3]  # ITEM3 — an equal two-way EUR row paid by Ann


def sheet(tmp_path, rows, header=None):
    """Write a CSV with the example header and the given data rows, and return its path."""
    target = tmp_path / "sheet.csv"
    with target.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(header or HEADER)
        writer.writerows(rows)
    return target


@pytest.fixture()
def row():
    """Return a builder for one sheet row, overriding cells of the example by index."""

    def build(**overrides):
        cells = list(BASE_ROW)
        for index, value in overrides.items():
            cells[int(index)] = value
        return cells

    return build


# --- reading cells ---------------------------------------------------------


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        pytest.param("1 240,00", Decimal("1240.00"), id="nbsp-grouped"),
        pytest.param("10,7", Decimal("10.7"), id="one-decimal"),
        pytest.param("697,00", Decimal("697.00"), id="plain"),
        pytest.param("", None, id="blank-cell"),
        pytest.param("?", None, id="not-a-number"),
    ],
)
def test_parse_decimal(raw, expected):
    """A sheet number with NBSP grouping and a comma decimal becomes an exact Decimal."""
    assert parse_decimal(raw) == expected


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        pytest.param(Decimal("10.7"), "10.70", id="pads-to-two-places"),
        pytest.param(Decimal(1162), "1162.00", id="whole"),
    ],
)
def test_canonical_amount_matches_the_amount_grammar(value, expected):
    """A Decimal renders as the two-decimal string app.services.parsing accepts."""
    assert canonical_amount(value) == expected


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        pytest.param("9.9.2026 19:45:00", "2026-09-09T17:45:00+00:00", id="date-time-seconds"),
        pytest.param("7.9.2026", "2026-09-07T10:00:00+00:00", id="date-only-takes-midday"),
        pytest.param("8.9 10:15", "2026-09-08T08:15:00+00:00", id="year-less"),
        pytest.param("8.9. 10:15", "2026-09-08T08:15:00+00:00", id="year-less-trailing-dot"),
    ],
)
def test_parse_occurred_at_local_wall_clock_to_utc(raw, expected):
    """Each date shape resolves to the UTC instant its Prague wall clock names."""
    assert parse_occurred_at(raw, PRAGUE, 2026).isoformat() == expected


def test_parse_occurred_at_honours_the_zone():
    """The same wall clock in a different zone is a different instant."""
    assert parse_occurred_at("8.9 10:15", ZoneInfo("UTC"), 2026).isoformat() == (
        "2026-09-08T10:15:00+00:00"
    )


@pytest.mark.parametrize(
    "raw", [pytest.param("", id="empty"), pytest.param("last tuesday", id="prose")]
)
def test_parse_occurred_at_unparsable_is_none(raw):
    """A cell the importer cannot read yields None, so the row becomes a reported problem."""
    assert parse_occurred_at(raw, PRAGUE, 2026) is None


# --- split inference -------------------------------------------------------


def test_infer_split_equal_over_everyone_who_owes():
    """Identical non-zero shares that sum to the amount are an equal split."""
    owed = [("Ann", Decimal("620.00")), ("Bob", Decimal("620.00"))]

    assert infer_split(Decimal("1240.00"), owed) == (
        "equal",
        [{"person_id": "Ann"}, {"person_id": "Bob"}],
        None,
    )


def test_infer_split_equal_leaves_out_whoever_owes_nothing():
    """A zero share means that person is not in the split at all, not that they owe 0."""
    owed = [("Ann", Decimal("0.00")), ("Bob", Decimal("13.00"))]

    assert infer_split(Decimal("13.00"), owed) == ("equal", [{"person_id": "Bob"}], None)


def test_infer_split_equal_absorbs_a_sheet_that_rounded_each_share_up():
    """3.34 + 3.34 for 6.67 is an equal split the sheet rounded, not an exact one that fails."""
    owed = [("Ann", Decimal("3.34")), ("Bob", Decimal("3.34"))]

    mode, shares, adjustment = infer_split(Decimal("6.67"), owed)

    assert (mode, adjustment) == ("equal", None)
    assert shares == [{"person_id": "Ann"}, {"person_id": "Bob"}]


def test_infer_split_exact_when_shares_differ_and_sum():
    """Unequal shares that sum to the amount are written as an exact split."""
    owed = [("Ann", Decimal("10.00")), ("Bob", Decimal("20.00"))]

    assert infer_split(Decimal("30.00"), owed) == (
        "exact",
        [
            {"person_id": "Ann", "amount": "10.00"},
            {"person_id": "Bob", "amount": "20.00"},
        ],
        None,
    )


def test_infer_split_nudges_the_largest_share_by_one_minor_unit():
    """An unequal split one cent over the amount loses the cent off its largest share."""
    owed = [("Ann", Decimal("1.48")), ("Bob", Decimal("3.48"))]

    mode, shares, adjustment = infer_split(Decimal("4.95"), owed)

    assert mode == "exact"
    assert shares == [
        {"person_id": "Ann", "amount": "1.48"},
        {"person_id": "Bob", "amount": "3.47"},
    ]
    assert adjustment == "Bob 3.48 -> 3.47"


@pytest.mark.parametrize(
    ("amount", "owed"),
    [
        pytest.param(
            Decimal("1.00"),
            [("Ann", Decimal("1.00")), ("Bob", Decimal("1.00"))],
            id="both-owe-the-whole-amount",
        ),
        pytest.param(
            Decimal("7.70"),
            [("Ann", Decimal("7.70")), ("Bob", Decimal("3.85"))],
            id="shares-overshoot",
        ),
        pytest.param(
            Decimal("5.00"),
            [("Ann", Decimal("0.00")), ("Bob", Decimal("0.00"))],
            id="nobody-owes-anything",
        ),
    ],
)
def test_infer_split_reports_amounts_that_fit_no_mode(amount, owed):
    """Shares that are neither equal nor summing yield no mode, so the row is reported."""
    mode, shares, reason = infer_split(amount, owed)

    assert (mode, shares) == (None, None)
    assert reason


# --- layout ----------------------------------------------------------------


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


def test_build_plan_rejects_a_people_list_that_overruns_the_row(tmp_path, row):
    """Naming more people than the sheet has columns for is refused before anything is read."""
    too_many = ["Ann", "Bob", "Cal", "Dee", "Eve", "Fay"]

    with pytest.raises(SystemExit, match="note column"):
        build_plan(sheet(tmp_path, [row()]), too_many, PRAGUE)


def test_build_plan_catches_owed_columns_that_land_on_the_summary_block(tmp_path, row):
    """A roster too long but still inside the row reads cells from the summary block."""
    plan = build_plan(sheet(tmp_path, [row()]), ["Ann", "Bob", "Cal", "Dee"], PRAGUE)

    assert [(problem.code, problem.detail) for problem in plan.problems] == [
        ("bad_share", "Dee: 'Ann'")
    ]


def test_build_plan_reads_columns_by_index_not_by_header(tmp_path, row):
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

    plan = build_plan(sheet(tmp_path, [row()], header=czech), PEOPLE, PRAGUE)

    assert plan.problems == []
    assert plan.items[0].name == "ITEM3"
    assert plan.items[0].amount == "1240.00"


def test_build_plan_reports_a_payer_who_is_not_in_the_roster(tmp_path, row):
    """A payer cell naming someone outside --people is a problem, not a new person."""
    plan = build_plan(sheet(tmp_path, [row(**{"3": "Cal"})]), PEOPLE, PRAGUE)

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
def test_build_plan_reports_unusable_cells(tmp_path, row, column, value, code):
    """Each unusable cell becomes a named problem rather than a partial import."""
    plan = build_plan(sheet(tmp_path, [row(**{column: value})]), PEOPLE, PRAGUE)

    assert code in {problem.code for problem in plan.problems}


def test_build_plan_skips_rows_with_no_name(tmp_path, row):
    """The blank rows a spreadsheet leaves below the data are dropped, not reported."""
    blank = [""] * len(HEADER)

    plan = build_plan(sheet(tmp_path, [row(), blank, blank]), PEOPLE, PRAGUE)

    assert (len(plan.items), plan.problems) == (1, [])


# --- the example sheet, end to end -----------------------------------------


@pytest.fixture()
def plan():
    """Resolve the committed example sheet, which is expected to be free of problems."""
    resolved = build_plan(SAMPLE, PEOPLE, PRAGUE)
    assert resolved.problems == []
    return resolved


def test_example_sheet_derives_the_roster_currencies_and_countries(plan):
    """Currencies rank by how often they appear; countries are the distinct codes."""
    assert plan.people == ("Ann", "Bob")
    assert plan.currencies == ["EUR", "CZK"]
    assert plan.countries == ["BE", "CZ", "DE", "LU"]


def test_example_sheet_resolves_every_row(plan):
    """All 24 rows resolve, the trailing blanks are dropped, and the summary block is not read."""
    assert [item.name for item in plan.items] == [f"ITEM{number}" for number in range(1, 25)]


@pytest.mark.parametrize(
    ("name", "occurred_at"),
    [
        pytest.param("ITEM3", "2026-09-06T10:00:00+00:00", id="date-only"),
        pytest.param("ITEM4", "2026-09-06T16:25:00+00:00", id="year-taken-from-the-sheet"),
        pytest.param("ITEM5", "2026-09-06T16:35:00+00:00", id="year-less-trailing-dot"),
        pytest.param("ITEM6", "2026-09-07T06:55:00+00:00", id="full-timestamp"),
    ],
)
def test_example_sheet_resolves_each_date_shape(plan, name, occurred_at):
    """A date-only cell lands at midday local, and a year-less one takes the sheet's year."""
    item = next(item for item in plan.items if item.name == name)

    assert item.occurred_at.isoformat() == occurred_at


def test_example_sheet_adjusts_only_the_row_that_needs_it(plan):
    """Two rows' shares miss their total by a cent; the rest are taken as written."""
    assert [(item.name, item.adjustment) for item in plan.items if item.adjustment] == [
        ("ITEM13", "Bob 3.48 -> 3.47"),
        ("ITEM22", "Bob 5.02 -> 5.01"),
    ]


@pytest.fixture()
def imported(session, plan):
    """Import the committed example sheet into a fresh trip and return the trip."""
    trip = create_trip(session, "Trip name", "2026-09-06", "2026-09-09")
    apply(session, plan, trip)
    return trip


def test_apply_creates_the_roster_it_referred_to(client, imported):
    """The people, currencies and countries the sheet named exist on the trip afterwards."""
    trip = client.get(f"/api/v1/trips/{imported.slug}").json()["trip"]

    assert [person["name"] for person in trip["people"]] == ["Ann", "Bob"]
    currencies = [(c["code"], c["is_primary"]) for c in trip["currencies"]]
    assert currencies == [("EUR", True), ("CZK", False)]
    countries = [(c["code"], c["is_default"], c["item_count"]) for c in trip["countries"]]
    assert countries == [("BE", True, 8), ("CZ", False, 2), ("DE", False, 8), ("LU", False, 6)]


def test_apply_sets_every_items_wallet_to_the_payers_default_card(client, imported):
    """The sheet knows nothing about wallets: every row lands on the payer's default `Card`."""
    trip = client.get(f"/api/v1/trips/{imported.slug}").json()["trip"]
    default_wallet_of = {w["person_id"]: w["id"] for w in trip["wallets"] if w["is_default"]}
    assert {w["name"] for w in trip["wallets"]} == {"Card"}

    items = client.get(f"/api/v1/trips/{imported.slug}/items").json()["items"]
    assert all(item["wallet_id"] == default_wallet_of[item["payer_id"]] for item in items)


def test_apply_carries_labels_and_notes_onto_the_items(client, imported):
    """Each row's category becomes its one label, and a note cell becomes the item's note."""
    items = client.get(f"/api/v1/trips/{imported.slug}/items").json()["items"]

    assert {item["labels"][0] for item in items} == {"alpha", "beta", "gamma", "delta"}
    assert {item["name"]: item["note"] for item in items if item["note"]} == {
        "ITEM5": "NOTE1",
        "ITEM9": "NOTE2",
        "ITEM13": "NOTE3",
        "ITEM20": "NOTE4",
    }


@pytest.mark.parametrize(
    ("name", "mode", "owed"),
    [
        pytest.param("ITEM3", "equal", [620, 620], id="equal-two-way"),
        pytest.param("ITEM6", "equal", [3.335, 3.335], id="equal-not-rounded-per-item"),
        pytest.param("ITEM12", "exact", [12, 20], id="exact-as-written"),
        pytest.param("ITEM13", "exact", [1.48, 3.47], id="exact-after-the-nudge"),
        pytest.param("ITEM8", "equal", [16.99, None], id="solo-leaves-bob-out"),
        pytest.param("ITEM9", "equal", [None, 7], id="solo-leaves-ann-out"),
    ],
)
def test_apply_resolves_each_split_shape(client, imported, name, mode, owed):
    """Every split the example covers comes back resolved in roster order."""
    items = client.get(f"/api/v1/trips/{imported.slug}/items").json()["items"]
    item = next(item for item in items if item["name"] == name)

    assert item["split"]["mode"] == mode
    assert [share["owed"] for share in item["split"]["shares"]] == owed


def test_apply_balances_settle_per_currency(client, imported):
    """Balances come back per currency, netting to zero within each."""
    balances = client.get(f"/api/v1/trips/{imported.slug}/balances").json()["balances"]

    nets = {
        block["currency_code"]: {person["person_id"]: person["net"] for person in block["people"]}
        for block in balances
    }
    assert sorted(nets["EUR"].values()) == [-741.14, 741.14]
    assert sorted(nets["CZK"].values()) == [-175, 175]


# --- the command line ------------------------------------------------------


@pytest.fixture()
def run_cli(monkeypatch):
    """Run `main()` against a private database, and return a factory to inspect it with.

    `main()` owns its own session and decides between commit and rollback, so it
    cannot use the `session` fixture's rolled-back transaction: the branch under test
    is exactly the one that ends the transaction. This gives it a throwaway engine
    with the real schema, and leaves both endings observable.
    """
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    alembic_config = Config()
    alembic_config.set_main_option("script_location", str(ALEMBIC_SCRIPT_LOCATION))
    with engine.connect() as connection:
        alembic_config.attributes["connection"] = connection
        command.upgrade(alembic_config, "head")
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    monkeypatch.setattr(cli, "SessionLocal", factory)

    def run(*argv):
        monkeypatch.setattr(sys, "argv", ["import_sheet", *argv])
        return cli.main(), factory

    return run


def test_main_dry_run_leaves_the_database_empty(run_cli):
    """--dry-run rolls the transaction back, so no trip survives the run."""
    code, factory = run_cli(str(SAMPLE), "Trip name", "--people", *PEOPLE, "--dry-run")

    assert code == 0
    with factory() as session:
        assert session.execute(select(Trip)).scalars().all() == []


def test_main_commits_the_trip_and_its_items(run_cli):
    """A plain run imports: the trip, its roster and its items are there afterwards."""
    code, factory = run_cli(str(SAMPLE), "Trip name", "--people", *PEOPLE)

    assert code == 0
    with factory() as session:
        trip = session.execute(select(Trip)).scalars().one()
        assert trip.slug == "trip-name"
        assert len(trip.items) == 24
        assert [person.name for person in trip.people] == ["Ann", "Bob"]


def test_main_reports_problems_and_writes_nothing(tmp_path, row, run_cli):
    """A sheet with an unusable row exits 2 before the write path, leaving no trip."""
    path = sheet(tmp_path, [row(), row(**{"1": ""})])

    code, factory = run_cli(str(path), "Trip name", "--people", *PEOPLE)

    assert code == 2
    with factory() as session:
        assert session.execute(select(Trip)).scalars().all() == []
