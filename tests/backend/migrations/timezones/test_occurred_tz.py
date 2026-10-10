"""Migration `7c2e9a41b5d8`, which adds `occurred_tz` to items and transfers.

Rows are inserted at the revision before it, with their trips already set to the
zones users chose between the releases. The migration runs, and every row has to
carry its own trip's zone and the instant it had.
"""

from datetime import UTC, datetime

import pytest
import sqlalchemy as sa
from sqlalchemy import inspect
from sqlalchemy.exc import IntegrityError

from alembic import command

SOURCE_REVISION = "d431f6f93289"
TARGET_REVISION = "7c2e9a41b5d8"

# Either side of the Prague clock change on 25 Oct 2026, and around midnight UTC.
INSTANTS = [
    datetime(2026, 10, 24, 23, 30, tzinfo=UTC),
    datetime(2026, 10, 25, 0, 30, tzinfo=UTC),
    datetime(2026, 10, 25, 1, 30, tzinfo=UTC),
    datetime(2026, 10, 25, 23, 59, tzinfo=UTC),
]
TRIP_ZONES = {1: "Asia/Tokyo", 2: "Europe/Prague"}


@pytest.fixture(scope="module")
def migration_target() -> tuple[str, str]:
    """Migrate from the revision before `occurred_tz` to the one that adds it."""
    return SOURCE_REVISION, TARGET_REVISION


@pytest.fixture(scope="module")
def create_old_data(migrate_to_start, insert_trip):
    """Insert two trips in different zones, each with items and transfers, before the migration."""
    insert_trip(1, INSTANTS, timezone=TRIP_ZONES[1])
    insert_trip(2, INSTANTS[:2], timezone=TRIP_ZONES[2])


def test_upgrade_copies_each_trips_zone_onto_its_rows(connection, table, table_name):
    """Every row of every trip ends up in the zone its own trip had."""
    rows = connection.execute(sa.select(*table(table_name).c["trip_id", "occurred_tz"])).all()

    assert len(rows) == 6
    assert {(row.trip_id, row.occurred_tz) for row in rows} == set(TRIP_ZONES.items())


def test_upgrade_keeps_every_instant(instants, old_instants, table_name):
    """No instant moves, on either side of the clock change."""
    assert instants(table_name) == old_instants[table_name]


def test_occurred_tz_is_required(connection, table, table_name):
    """A row inserted without a zone is refused by the database."""
    rows = table(table_name)
    values = connection.execute(sa.select(rows).limit(1)).mappings().one()

    with pytest.raises(IntegrityError), connection.begin_nested():
        connection.execute(sa.insert(rows).values({**values, "id": 999, "occurred_tz": None}))


def test_downgrade_drops_the_zone_and_keeps_every_instant(
    alembic_config, connection, instants, old_instants, table_name
):
    """Downgrading removes `occurred_tz` from the table and leaves its instants alone."""
    command.downgrade(alembic_config, SOURCE_REVISION)
    try:
        columns = [column["name"] for column in inspect(connection).get_columns(table_name)]
        assert "occurred_tz" not in columns
        assert instants(table_name) == old_instants[table_name]
    finally:
        command.upgrade(alembic_config, TARGET_REVISION)
