"""The Trip table: the root every other row hangs off."""

from datetime import datetime

from sqlalchemy import Column, DateTime, UniqueConstraint, func
from sqlmodel import Field, Relationship, SQLModel


class Trip(SQLModel, table=True):
    """A trip: its slug, dates, and the roster, currencies, countries, labels and items under it."""

    __tablename__ = "trip"
    __table_args__ = (UniqueConstraint("slug", name="uq_trip_slug"),)

    id: int | None = Field(default=None, primary_key=True)
    slug: str = Field(index=True, max_length=60)
    name: str = Field(max_length=200)
    start_date: str | None = Field(default=None, max_length=10)
    end_date: str | None = Field(default=None, max_length=10)
    note: str | None = None
    archived: bool = False
    created_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), server_default=func.now())
    )
    updated_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    )

    people: list["Person"] = Relationship(  # noqa: F821
        back_populates="trip",
        sa_relationship_kwargs={"cascade": "all, delete-orphan", "order_by": "Person.sort_order"},
    )
    currencies: list["TripCurrency"] = Relationship(  # noqa: F821
        back_populates="trip",
        sa_relationship_kwargs={
            "cascade": "all, delete-orphan",
            "order_by": "TripCurrency.sort_order",
        },
    )
    countries: list["TripCountry"] = Relationship(  # noqa: F821
        back_populates="trip",
        sa_relationship_kwargs={
            "cascade": "all, delete-orphan",
            "order_by": "TripCountry.sort_order",
        },
    )
    labels: list["Label"] = Relationship(  # noqa: F821
        back_populates="trip", sa_relationship_kwargs={"cascade": "all, delete-orphan"}
    )
    items: list["LineItem"] = Relationship(  # noqa: F821
        back_populates="trip", sa_relationship_kwargs={"cascade": "all, delete-orphan"}
    )
    transfers: list["WalletTransfer"] = Relationship(  # noqa: F821
        back_populates="trip", sa_relationship_kwargs={"cascade": "all, delete-orphan"}
    )
