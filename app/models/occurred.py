"""The `Occurred` mixin: when an item or a transfer happened, and how that reads on the wire."""

from datetime import UTC, datetime
from zoneinfo import ZoneInfo

from sqlalchemy import DateTime
from sqlmodel import Field, SQLModel

WALL_TIME_FORMAT = "%Y-%m-%dT%H:%M:%S"


class NonexistentTimeError(ValueError):
    """The wall time falls in a spring-forward gap of its zone: no instant has it."""


class Occurred(SQLModel):
    """`occurred_at`, the UTC instant, and the one place it converts to and from wall time.

    Shared by `LineItem` and `WalletTransfer`, so both follow one rule. The indexes
    stay declared on each model.
    """

    occurred_at: datetime = Field(
        sa_type=DateTime(timezone=True), sa_column_kwargs={"nullable": True}
    )

    @staticmethod
    def resolve(wall_time: datetime, zone: ZoneInfo) -> datetime:
        """Return the UTC instant a wall time names in `zone`.

        `fold=0` takes the earlier instant of an autumn repeat. A wall time the zone
        skips renders back as a different one, which raises `NonexistentTimeError`.
        """
        instant = wall_time.replace(tzinfo=zone, fold=0).astimezone(UTC)
        if instant.astimezone(zone).replace(tzinfo=None) != wall_time:
            raise NonexistentTimeError(wall_time.isoformat())
        return instant

    def wall_time_in(self, zone: ZoneInfo) -> datetime:
        """Return the stored instant as a naive wall time in `zone`.

        SQLite returns the column naive, so UTC is attached before converting.
        """
        instant = self.occurred_at
        if instant.tzinfo is None:
            instant = instant.replace(tzinfo=UTC)
        return instant.astimezone(zone).replace(tzinfo=None)

    def wire_times(self) -> dict[str, str]:
        """Return the four time fields of the wire form, in the trip's zone."""
        trip = self.trip
        wall = self.wall_time_in(trip.zone).strftime(WALL_TIME_FORMAT)
        return {
            "occurred_at": wall,
            "occurred_tz": trip.timezone,
            "trip_occurred_at": wall,
            "day": wall[:10],
        }
