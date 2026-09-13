"""Request-scoped clock dependency for occurred_at defaults."""

from datetime import UTC, datetime
from typing import Annotated

from fastapi import Depends


def current_time() -> datetime:
    """Return the default for occurred_at when a write omits it: UTC, tz-aware.

    Never the server's local time, so the default doesn't depend on how a
    given deployment is configured. Overridden in tests via dependency_overrides.
    """
    return datetime.now(UTC).replace(microsecond=0)


ClockDep = Annotated[datetime, Depends(current_time)]
