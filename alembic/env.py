"""Alembic environment: point migrations at the app's configured database."""

from logging.config import fileConfig
from pathlib import Path

from sqlalchemy import engine_from_config, pool
from sqlmodel import SQLModel

import app.models  # noqa: F401  registers all tables on SQLModel.metadata
from alembic import context
from app.config import Settings

config = context.config
# config_file_name defaults to "alembic.ini" whether or not that file exists -
# config actually lives in pyproject.toml's [tool.alembic]. Only load it for
# logging setup when an .ini is actually there.
if config.config_file_name is not None and Path(config.config_file_name).exists():
    fileConfig(config.config_file_name)

config.set_main_option("sqlalchemy.url", Settings().database_url)
target_metadata = SQLModel.metadata


def run_migrations_offline() -> None:
    """Emit migration SQL against the configured URL without opening a connection."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(url=url, target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


def _do_run_migrations(connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations against a live connection, reusing one from context.attributes if given."""
    # tests/backend/conftest.py passes an already-open Connection through
    # config.attributes so migrations run against the same in-memory engine
    # the test session uses, instead of opening a second one.
    connection = config.attributes.get("connection")
    if connection is not None:
        _do_run_migrations(connection)
        return

    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        _do_run_migrations(connection)


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
