"""SQLModel table definitions for the trip, roster, and line-item schema."""

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


def active_roster_ids(people: list["Person"]) -> list[int]:
    """Return the ids of active people, ordered by sort_order."""
    return [p.id for p in sorted(people, key=lambda p: p.sort_order) if p.active]


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

    people: list["Person"] = Relationship(
        back_populates="trip",
        sa_relationship_kwargs={"cascade": "all, delete-orphan", "order_by": "Person.sort_order"},
    )
    currencies: list["TripCurrency"] = Relationship(
        back_populates="trip",
        sa_relationship_kwargs={
            "cascade": "all, delete-orphan",
            "order_by": "TripCurrency.sort_order",
        },
    )
    countries: list["TripCountry"] = Relationship(
        back_populates="trip",
        sa_relationship_kwargs={
            "cascade": "all, delete-orphan",
            "order_by": "TripCountry.sort_order",
        },
    )
    labels: list["Label"] = Relationship(
        back_populates="trip", sa_relationship_kwargs={"cascade": "all, delete-orphan"}
    )
    items: list["LineItem"] = Relationship(
        back_populates="trip", sa_relationship_kwargs={"cascade": "all, delete-orphan"}
    )


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
    )

    id: int | None = Field(default=None, primary_key=True)
    trip_id: int = Field(foreign_key="trip.id", index=True)
    # Always tz-aware (schemas.py normalizes a naive input to UTC before it
    # ever reaches here) - timezone=True keeps that explicit in the column
    # type itself, and is honored for real on Postgres.
    occurred_at: datetime = Field(sa_column=Column(DateTime(timezone=True), index=True))
    name: str = Field(max_length=200)
    note: str | None = None
    currency_id: int = Field(index=True)
    amount_minor: int = Field(sa_column=Column(BigInteger))
    payer_id: int = Field(index=True)
    country_id: int = Field(index=True)
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
    payer: Person = Relationship(sa_relationship_kwargs={"overlaps": "country,currency,items,trip"})
    currency: TripCurrency = Relationship(
        sa_relationship_kwargs={"overlaps": "country,items,payer,trip"}
    )
    country: TripCountry = Relationship(
        sa_relationship_kwargs={"overlaps": "currency,items,payer,trip"}
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
