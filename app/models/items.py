"""Line items and the per-person shares that split them."""

from datetime import datetime

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Column,
    DateTime,
    ForeignKeyConstraint,
    UniqueConstraint,
    func,
)
from sqlmodel import Field, Relationship, SQLModel

from app.models.labels import ItemLabel, Label
from app.models.roster import Person, TripCountry, TripCurrency
from app.models.trip import Trip
from app.models.wallets import Wallet


class LineItem(SQLModel, table=True):
    """A single trip expense: who paid, in what currency, where, and its split shares."""

    __tablename__ = "line_item"
    __table_args__ = (
        # Cross-trip refs (a currency/payer/country from another trip) are
        # rejected at the DB, not just by the router's _validate_refs.
        ForeignKeyConstraint(
            ["currency_id", "trip_id"],
            ["trip_currency.id", "trip_currency.trip_id"],
            name="fk_item_currency_trip",
        ),
        ForeignKeyConstraint(
            ["payer_id", "trip_id"],
            ["person.id", "person.trip_id"],
            name="fk_item_payer_trip",
        ),
        ForeignKeyConstraint(
            ["country_id", "trip_id"],
            ["trip_country.id", "trip_country.trip_id"],
            name="fk_item_country_trip",
        ),
        ForeignKeyConstraint(
            ["wallet_id", "trip_id"],
            ["wallet.id", "wallet.trip_id"],
            name="fk_item_wallet_trip",
        ),
    )

    id: int | None = Field(default=None, primary_key=True)
    trip_id: int = Field(foreign_key="trip.id", index=True)
    # Always tz-aware (schemas/fields.py normalizes a naive input to UTC
    # before it ever reaches here) - timezone=True keeps that explicit in the
    # column type itself, and is honored for real on Postgres.
    occurred_at: datetime = Field(sa_column=Column(DateTime(timezone=True), index=True))
    name: str = Field(max_length=200)
    note: str | None = None
    currency_id: int = Field(index=True)
    amount_minor: int = Field(sa_column=Column(BigInteger))
    payer_id: int = Field(index=True)
    country_id: int = Field(index=True)
    wallet_id: int = Field(index=True)
    map_url: str | None = None
    lat: str | None = Field(default=None, max_length=20)
    lon: str | None = Field(default=None, max_length=20)
    split_mode: str = Field(max_length=10)
    created_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), server_default=func.now())
    )
    updated_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    )

    # Each composite FK above shares the trip_id column with the others and
    # with the plain trip_id -> trip.id FK; none of these relationships ever
    # writes trip_id (it's set directly on the row), so the overlap is safe.
    trip: Trip = Relationship(back_populates="items")
    payer: Person = Relationship(
        sa_relationship_kwargs={"overlaps": "country,currency,items,trip,wallet"}
    )
    currency: TripCurrency = Relationship(
        sa_relationship_kwargs={"overlaps": "country,items,payer,trip,wallet"}
    )
    country: TripCountry = Relationship(
        sa_relationship_kwargs={"overlaps": "currency,items,payer,trip,wallet"}
    )
    wallet: Wallet = Relationship(
        sa_relationship_kwargs={"overlaps": "country,currency,items,payer,trip"}
    )
    shares: list["ItemShare"] = Relationship(
        back_populates="item", sa_relationship_kwargs={"cascade": "all, delete-orphan"}
    )
    label_rows: list[Label] = Relationship(link_model=ItemLabel)


class ItemShare(SQLModel, table=True):
    """One person's weight or exact amount owed on a line item."""

    __tablename__ = "item_share"
    __table_args__ = (
        UniqueConstraint("item_id", "person_id", name="uq_share_item_person"),
        CheckConstraint(
            "(split_mode_exact = false AND owed_minor IS NULL) "
            "OR (split_mode_exact = true AND owed_minor IS NOT NULL)",
            name="ck_share_exact_owed",
        ),
    )

    id: int | None = Field(default=None, primary_key=True)
    item_id: int = Field(foreign_key="line_item.id", index=True)
    person_id: int = Field(foreign_key="person.id", index=True)
    weight_scaled: int
    owed_minor: int | None = Field(default=None, sa_column=Column(BigInteger, nullable=True))
    split_mode_exact: bool = False

    item: LineItem = Relationship(back_populates="shares")
    person: Person = Relationship()
