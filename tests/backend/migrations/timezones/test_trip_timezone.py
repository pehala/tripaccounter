"""Migration `d431f6f93289`, which adds `trip.timezone`.

Trips inserted at the revision before it carry no zone; the migration gives each `UTC`,
which reproduces the feed as it read, and leaves every instant as it was.
"""

from datetime import UTC, datetime

import pytest
import sqlalchemy as sa

SOURCE_REVISION = "deac5897cc75"
TARGET_REVISION = "d431f6f93289"

INSTANTS = [
    datetime(2026, 10, 25, 0, 30, tzinfo=UTC),
    datetime(2026, 10, 25, 1, 30, tzinfo=UTC),
]


@pytest.fixture(scope="module")
def migration_target() -> tuple[str, str]:
    """Migrate from the revision before `trip.timezone` to the one that adds it."""
    return SOURCE_REVISION, TARGET_REVISION


@pytest.fixture(scope="module")
def create_old_data(migrate_to_start, insert_trip):
    """Insert two trips with items and transfers before the migration."""
    insert_trip(1, INSTANTS)
    insert_trip(2, INSTANTS)


def test_upgrade_gives_every_existing_trip_utc(connection, table):
    """Each trip that existed before the migration reads in UTC."""
    zones = connection.execute(sa.select(table("trip").c.timezone)).scalars().all()

    assert zones == ["UTC", "UTC"]


def test_upgrade_keeps_every_instant(instants, old_instants, table_name):
    """No instant moves when the trips gain a zone."""
    assert instants(table_name) == old_instants[table_name]
