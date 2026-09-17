"""The composite foreign key every trip-scoped reference carries."""

from sqlalchemy import ForeignKeyConstraint


def trip_scoped_fk(column: str, target: str, name: str) -> ForeignKeyConstraint:
    """Point `(column, trip_id)` at `(target.id, target.trip_id)`.

    The DB, not the router, is what rejects a row naming another trip's person,
    currency, country or wallet.
    """
    return ForeignKeyConstraint(
        [column, "trip_id"], [f"{target}.id", f"{target}.trip_id"], name=name
    )
