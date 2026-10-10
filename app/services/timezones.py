"""Time zones and wall times: the checks that turn a bad value into a field error."""

from datetime import datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from app.models.occurred import NonexistentTimeError, Occurred
from app.models.trip import Trip
from app.services.errors.base import FieldError
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


def write_zone(name: str | None, row: Occurred | None, trip: Trip) -> ZoneInfo:
    """Return the zone a write's wall time is read in.

    The body's `occurred_tz`, else the row's on an update, else the trip's on a create.
    `name` has already passed `timezone_error`.
    """
    if name is not None:
        return ZoneInfo(name)
    return row.zone if row is not None else trip.zone


def time_errors(
    wall_time: datetime | None, name: str | None, row: Occurred | None, trip: Trip
) -> dict[str, FieldError]:
    """Return the field errors of a write's `occurred_at` and `occurred_tz`.

    The wall time is checked in the zone the write settles on (`write_zone`); an
    unknown zone leaves nothing to check it in.
    """
    if zone_error := timezone_error(name):
        return {"occurred_tz": zone_error}
    if wall_time is None:
        return {}
    try:
        Occurred.resolve(wall_time, write_zone(name, row, trip))
    except NonexistentTimeError:
        return {"occurred_at": InvalidDatetimeError()}
    return {}
