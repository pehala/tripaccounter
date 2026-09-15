"""The committed example sheet, imported end to end and then through the command line.

Writing rows goes through the `session` fixture and is read back over `client`,
which is the only place the result is observable.
"""

import sys
from pathlib import Path

import pytest
from alembic.config import Config
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from alembic import command
from app.models.trip import Trip
from tests.backend.import_sheet.conftest import PEOPLE, PRAGUE, SAMPLE
from tools.import_sheet import __main__ as cli
from tools.import_sheet import apply, build_plan, create_trip

ALEMBIC_SCRIPT_LOCATION = Path(__file__).resolve().parent.parent.parent.parent / "alembic"


@pytest.fixture()
def plan():
    """Resolve the committed example sheet, which is expected to be free of problems."""
    resolved = build_plan(SAMPLE, PEOPLE, PRAGUE)
    assert resolved.problems == []
    return resolved


@pytest.fixture()
def imported(session, plan):
    """Import the committed example sheet into a fresh trip and return the trip."""
    trip = create_trip(session, "Trip name", "2026-09-06", "2026-09-09")
    apply(session, plan, trip)
    return trip


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


def test_main_reports_problems_and_writes_nothing(sheet, row, run_cli):
    """A sheet with an unusable row exits 2 before the write path, leaving no trip."""
    path = sheet([row(), row(**{"1": ""})])

    code, factory = run_cli(str(path), "Trip name", "--people", *PEOPLE)

    assert code == 2
    with factory() as session:
        assert session.execute(select(Trip)).scalars().all() == []
