"""Fixtures for migration tests: the real Alembic revisions, run against a scratch database.

A test module names the revisions it covers by overriding `migration_target`, and
inserts the rows it wants migrated by overriding `create_old_data`, which runs with
the schema as it was at the source revision. The migration itself runs once, after
that, so every test in the module sees the migrated database.
"""

import pytest
import sqlalchemy as sa
from alembic.config import Config

from alembic import command
from tests.backend.conftest import ALEMBIC_SCRIPT_LOCATION, empty_engine


@pytest.fixture(scope="module")
def migration_engine(worker_id):
    """Yield an engine on an empty scratch database, shared by the tests of one module."""
    with empty_engine(f"ta_test_{worker_id}_migrations") as engine:
        yield engine


@pytest.fixture(scope="module")
def connection(migration_engine):
    """Yield the one connection migrations and the tests of a module share."""
    with migration_engine.begin() as connection:
        yield connection


@pytest.fixture(scope="module")
def alembic_config(connection):
    """Return an Alembic config whose migrations run on `connection`."""
    config = Config()
    config.set_main_option("script_location", str(ALEMBIC_SCRIPT_LOCATION))
    config.attributes["connection"] = connection
    return config


@pytest.fixture(scope="module")
def migration_target() -> tuple[str, str]:
    """Return the (source, target) revisions a module tests; override per module."""
    return "base", "head"


@pytest.fixture(scope="module")
def migrate_to_start(alembic_config, migration_target):
    """Upgrade the empty database to the source revision."""
    command.upgrade(alembic_config, migration_target[0])


@pytest.fixture(scope="module")
def create_old_data(migrate_to_start):
    """Insert the rows to be migrated, at the source revision; override per module."""


@pytest.fixture(scope="module", autouse=True)
def migrate_to_end(create_old_data, alembic_config, migration_target):
    """Run the migration under test."""
    command.upgrade(alembic_config, migration_target[1])


@pytest.fixture(scope="module")
def table(connection):
    """Return `table(name)`, which reflects a table as the database has it right now."""

    def reflect(name):
        return sa.Table(name, sa.MetaData(), autoload_with=connection)

    return reflect
