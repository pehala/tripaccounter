"""Stays: the places a trip slept, each grouping the items charged there."""

from datetime import date, datetime

from sqlalchemy import Column, Date, DateTime, UniqueConstraint, func
from sqlmodel import Field, Relationship, SQLModel

from app.models.constraints import trip_scoped_fk
from app.models.roster import TripCountry
from app.models.trip import Trip


class Stay(SQLModel, table=True):
    """A booked stay: its dates, booking link and location. Its cost is its items' sum."""

    __tablename__ = "stay"
    __table_args__ = (
        # Lets LineItem.stay_id carry a composite FK against (id, trip_id).
        UniqueConstraint("id", "trip_id", name="uq_stay_id_trip"),
        trip_scoped_fk("country_id", "trip_country", "fk_stay_country_trip"),
    )

    id: int | None = Field(default=None, primary_key=True)
    trip_id: int = Field(foreign_key="trip.id", index=True)
    name: str = Field(max_length=200)
    check_in: date = Field(sa_column=Column(Date, nullable=False))
    check_out: date = Field(sa_column=Column(Date, nullable=False))
    url: str | None = None
    note: str | None = None
    country_id: int | None = Field(default=None, index=True)
    city: str | None = None
    map_url: str | None = None
    lat: str | None = Field(default=None, max_length=20)
    lon: str | None = Field(default=None, max_length=20)
    created_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), server_default=func.now())
    )
    updated_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    )

    trip: Trip = Relationship(back_populates="stays")
    country: TripCountry | None = Relationship(sa_relationship_kwargs={"overlaps": "stays,trip"})
