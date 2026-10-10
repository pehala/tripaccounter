"""Time zones and wall times: the checks that turn a bad value into a field error."""

from datetime import datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from app.models.occurred import NonexistentTimeError, Occurred
from app.services.errors.fields import InvalidDatetimeError, InvalidTimezoneError

DEFAULT_TIMEZONE = "UTC"


def timezone_error(name: str | None) -> InvalidTimezoneError | None:
    """Return `invalid_timezone` when `name` is not a zone `zoneinfo` loads, else None."""
    if name is None:
        return None
    try:
        ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError, OSError):
        return InvalidTimezoneError()
    return None


def occurred_error(wall_time: datetime | None, zone: ZoneInfo) -> InvalidDatetimeError | None:
    """Return `invalid_datetime` when `wall_time` falls in a gap of `zone`, else None."""
    if wall_time is None:
        return None
    try:
        Occurred.resolve(wall_time, zone)
    except NonexistentTimeError:
        return InvalidDatetimeError()
    return None
