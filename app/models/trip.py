"""The Trip table: the root every other row hangs off."""

from datetime import datetime
from typing import TYPE_CHECKING
from zoneinfo import ZoneInfo

from sqlalchemy import (
    CheckConstraint,
    Column,
    DateTime,
    ForeignKeyConstraint,
    UniqueConstraint,
    func,
)
from sqlmodel import Field, Relationship, SQLModel

if TYPE_CHECKING:
    from app.models.items import LineItem
    from app.models.labels import Label
    from app.models.roster import Person, TripCountry, TripCurrency
    from app.models.stays import Stay
    from app.models.wallets import WalletTransfer


class Trip(SQLModel, table=True):
    """A trip: its slug, dates, and the roster, currencies, countries, labels, stays and items."""

    __tablename__ = "trip"
    __table_args__ = (
        UniqueConstraint("slug", name="uq_trip_slug"),
        # `use_alter`: trip_currency already references trip.
        ForeignKeyConstraint(
            ["settlement_currency_id", "id"],
            ["trip_currency.id", "trip_currency.trip_id"],
            name="fk_trip_settlement_currency",
            use_alter=True,
        ),
        CheckConstraint(
            "(settled_at IS NULL) = (settlement_currency_id IS NULL)",
            name="ck_trip_settlement_complete",
        ),
    )

    # Explicit, because `id` is also in the settlement foreign key.
    id: int | None = Field(default=None, primary_key=True, sa_column_kwargs={"autoincrement": True})
    slug: str = Field(index=True, max_length=60)
    name: str = Field(max_length=200)
    start_date: str | None = Field(default=None, max_length=10)
    end_date: str | None = Field(default=None, max_length=10)
    timezone: str = Field(default="UTC", max_length=64, sa_column_kwargs={"server_default": "UTC"})
    note: str | None = None
    archived: bool = False
    settled_at: datetime | None = Field(
        default=None, sa_column=Column(DateTime(timezone=True), nullable=True)
    )
    settlement_currency_id: int | None = None
    created_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), server_default=func.now())
    )
    updated_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    )

    @property
    def zone(self) -> ZoneInfo:
        """The trip's time zone: it cuts the days and is the zone every row reads in."""
        return ZoneInfo(self.timezone)

    people: list["Person"] = Relationship(
        back_populates="trip",
        sa_relationship_kwargs={
            "cascade": "all, delete-orphan",
            "order_by": "[Person.sort_order, Person.name]",
        },
    )
    currencies: list["TripCurrency"] = Relationship(
        back_populates="trip",
        sa_relationship_kwargs={
            "cascade": "all, delete-orphan",
            "foreign_keys": "[TripCurrency.trip_id]",
            "order_by": "[TripCurrency.is_primary.desc(), TripCurrency.code]",
        },
    )
    countries: list["TripCountry"] = Relationship(
        back_populates="trip",
        sa_relationship_kwargs={
            "cascade": "all, delete-orphan",
            "order_by": "[TripCountry.is_default.desc(), TripCountry.name]",
        },
    )
    labels: list["Label"] = Relationship(
        back_populates="trip",
        sa_relationship_kwargs={
            "cascade": "all, delete-orphan",
            "order_by": "Label.name",
        },
    )
    stays: list["Stay"] = Relationship(
        back_populates="trip",
        sa_relationship_kwargs={
            "cascade": "all, delete-orphan",
            "order_by": "[Stay.check_in, Stay.name, Stay.id]",
        },
    )
    items: list["LineItem"] = Relationship(
        back_populates="trip", sa_relationship_kwargs={"cascade": "all, delete-orphan"}
    )
    transfers: list["WalletTransfer"] = Relationship(
        back_populates="trip", sa_relationship_kwargs={"cascade": "all, delete-orphan"}
    )
