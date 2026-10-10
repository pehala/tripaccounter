"""Database engine and session setup."""

from collections.abc import Generator
from datetime import UTC, datetime
from zoneinfo import ZoneInfo

from sqlalchemy import create_engine, event, make_url
from sqlalchemy.engine import URL, Engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import Settings


def tz_date(instant: str | None, zone: str) -> str | None:
    """Return the `YYYY-MM-DD` day a stored UTC instant falls on in `zone`.

    The SQLite twin of Postgres's `col AT TIME ZONE zone`: SQLite keeps the
    column as naive UTC text, which `fromisoformat` reads back.
    """
    if instant is None:
        return None
    utc = datetime.fromisoformat(instant).replace(tzinfo=UTC)
    return utc.astimezone(ZoneInfo(zone)).date().isoformat()


def make_engine(database_url: str | URL, **kwargs) -> Engine:
    """Build a SQLAlchemy engine, setting up each SQLite connection when applicable.

    SQLite connections get foreign keys and the `tz_date` function `day_of` calls.

    `kwargs` go to `create_engine` as they are.
    """
    is_sqlite = make_url(database_url).get_backend_name() == "sqlite"
    connect_args = {"check_same_thread": False} if is_sqlite else {}
    engine = create_engine(database_url, connect_args=connect_args, **kwargs)

    if is_sqlite:

        @event.listens_for(engine, "connect")
        def _configure_connection(dbapi_connection, _connection_record):
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()
            dbapi_connection.create_function("tz_date", 2, tz_date, deterministic=True)

    return engine


settings = Settings()
engine = make_engine(settings.database_url)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_session() -> Generator[Session]:
    """Yield a database session, committing on success and rolling back on error."""
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
