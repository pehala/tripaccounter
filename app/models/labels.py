"""Labels and the item-label link table."""

from datetime import datetime

from sqlalchemy import Column, DateTime, UniqueConstraint, func
from sqlmodel import Field, Relationship, SQLModel

from app.models.trip import Trip


class Label(SQLModel, table=True):
    """A trip-scoped tag applied to items, tracking how many items currently use it."""

    __tablename__ = "label"
    __table_args__ = (UniqueConstraint("trip_id", "name_norm", name="uq_label_trip_norm"),)

    id: int | None = Field(default=None, primary_key=True)
    trip_id: int = Field(foreign_key="trip.id")
    name: str = Field(max_length=40)
    name_norm: str = Field(max_length=40, index=True)
    color: str = Field(max_length=7)
    use_count: int = 0
    created_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), server_default=func.now())
    )

    trip: Trip = Relationship(back_populates="labels")


class ItemLabel(SQLModel, table=True):
    """The many-to-many link table between line items and labels."""

    __tablename__ = "item_label"

    item_id: int = Field(foreign_key="line_item.id", primary_key=True)
    label_id: int = Field(foreign_key="label.id", primary_key=True)
