"""Alembic environment: point migrations at the app's configured database."""

from logging.config import fileConfig
from pathlib import Path

from sqlalchemy import DefaultClause, engine_from_config, pool
from sqlmodel import SQLModel
from sqlmodel.sql.sqltypes import AutoString

from alembic import context
from app.config import Settings

# Importing every model module registers all tables on SQLModel.metadata.
from app.models import items, labels, roster, trip, wallets  # noqa: F401

config = context.config
# config_file_name defaults to "alembic.ini" whether or not that file exists -
# config actually lives in pyproject.toml's [tool.alembic]. Only load it for
# logging setup when an .ini is actually there.
if config.config_file_name is not None and Path(config.config_file_name).exists():
    fileConfig(config.config_file_name)

config.set_main_option("sqlalchemy.url", Settings().database_url)
target_metadata = SQLModel.metadata

NOW_TEXTS = {"CURRENT_TIMESTAMP", "NOW"}


def render_item(type_: str, obj: object, autogen_context) -> str | bool:
    """Render two autogenerate outputs back to portable, import-free SQLAlchemy.

    Left to itself, `--autogenerate` renders a `server_default=func.now()`
    column as the *compiled* default text (`sa.text('CURRENT_TIMESTAMP')` on
    SQLite, something else on Postgres) and SQLModel's `AutoString` as
    `sqlmodel.sql.sqltypes.AutoString(...)`, which needs an `import sqlmodel`
    no migration otherwise has. Rendering the default back to `sa.func.now()`
    keeps it portable across dialects; rendering `AutoString` as the plain
    `sa.String` it wraps drops the dependency on SQLModel's own import path -
    a migration should outlive whichever ORM library wrote it.
    """
    if type_ == "type" and isinstance(obj, AutoString):
        return f"sa.String(length={obj.length})" if obj.length else "sa.String()"
    is_now_default = (
        type_ == "server_default"
        and isinstance(obj, DefaultClause)
        and str(obj.arg).strip("()").upper() in NOW_TEXTS
    )
    if is_now_default:
        return "sa.func.now()"
    return False


def run_migrations_offline() -> None:
    """Emit migration SQL against the configured URL without opening a connection."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url, target_metadata=target_metadata, literal_binds=True, render_item=render_item
    )
    with context.begin_transaction():
        context.run_migrations()


def _do_run_migrations(connection) -> None:
    context.configure(
        connection=connection, target_metadata=target_metadata, render_item=render_item
    )
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
