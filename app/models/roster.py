"""People, currencies and countries: the per-trip roster tables."""

from datetime import datetime

from sqlalchemy import Column, DateTime, UniqueConstraint, func
from sqlmodel import Field, Relationship, SQLModel

from app.models.trip import Trip


def active_roster_ids(people: list["Person"]) -> list[int]:
    """Return the ids of active people, ordered by sort_order."""
    return [p.id for p in sorted(people, key=lambda p: p.sort_order) if p.active]


class Person(SQLModel, table=True):
    """A member of a trip's roster, with a default split weight and display color."""

    __tablename__ = "person"
    __table_args__ = (
        UniqueConstraint("trip_id", "name", name="uq_person_trip_name"),
        # Lets LineItem.payer_id carry a composite FK against (id, trip_id),
        # so a payer from another trip is rejected by the DB, not just the router.
        UniqueConstraint("id", "trip_id", name="uq_person_id_trip"),
    )

    id: int | None = Field(default=None, primary_key=True)
    trip_id: int = Field(foreign_key="trip.id")
    name: str = Field(max_length=100)
    color: str = Field(max_length=7)
    default_weight_scaled: int = 10000
    sort_order: int = 0
    active: bool = True
    created_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), server_default=func.now())
    )

    trip: Trip = Relationship(back_populates="people")
    wallets: list["Wallet"] = Relationship(  # noqa: F821
        back_populates="person",
        sa_relationship_kwargs={"cascade": "all, delete-orphan", "order_by": "Wallet.sort_order"},
    )


class TripCurrency(SQLModel, table=True):
    """A currency enabled for a trip, with its display symbol and primary flag."""

    __tablename__ = "trip_currency"
    __table_args__ = (
        UniqueConstraint("trip_id", "code", name="uq_currency_trip_code"),
        # Lets LineItem.currency_id carry a composite FK against (id, trip_id).
        UniqueConstraint("id", "trip_id", name="uq_currency_id_trip"),
    )

    id: int | None = Field(default=None, primary_key=True)
    trip_id: int = Field(foreign_key="trip.id")
    code: str = Field(max_length=3)
    symbol: str | None = Field(default=None, max_length=10)
    is_primary: bool = False
    sort_order: int = 0

    trip: Trip = Relationship(back_populates="currencies")


class TripCountry(SQLModel, table=True):
    """A country visited on a trip, with an optional ISO code and default flag."""

    __tablename__ = "trip_country"
    __table_args__ = (
        UniqueConstraint("trip_id", "name", name="uq_country_trip_name"),
        # Lets LineItem.country_id carry a composite FK against (id, trip_id).
        UniqueConstraint("id", "trip_id", name="uq_country_id_trip"),
    )

    id: int | None = Field(default=None, primary_key=True)
    trip_id: int = Field(foreign_key="trip.id")
    name: str = Field(max_length=100)
    code: str | None = Field(default=None, max_length=2)
    is_default: bool = False
    sort_order: int = 0
    created_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), server_default=func.now())
    )

    trip: Trip = Relationship(back_populates="countries")
