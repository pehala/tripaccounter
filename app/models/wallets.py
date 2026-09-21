"""Wallets and the transfers that move money between them."""

from datetime import datetime

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Column,
    DateTime,
    Index,
    UniqueConstraint,
    func,
)
from sqlmodel import Field, Relationship, SQLModel

from app.models.constraints import trip_scoped_fk
from app.models.roster import Person, TripCurrency
from app.models.trip import Trip


class Wallet(SQLModel, table=True):
    """A pot of money a person spends from: tracked shows a balance, untracked is unlimited."""

    __tablename__ = "wallet"
    __table_args__ = (
        UniqueConstraint("person_id", "name", name="uq_wallet_person_name"),
        # Lets LineItem.wallet_id and WalletTransfer's wallet columns carry a
        # composite FK against (id, trip_id).
        UniqueConstraint("id", "trip_id", name="uq_wallet_id_trip"),
        trip_scoped_fk("person_id", "person", "fk_wallet_person_trip"),
    )

    id: int | None = Field(default=None, primary_key=True)
    trip_id: int = Field(foreign_key="trip.id", index=True)
    person_id: int = Field(index=True)
    name: str = Field(max_length=60)
    tracked: bool = False
    is_default: bool = False
    created_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), server_default=func.now())
    )

    trip: Trip = Relationship(sa_relationship_kwargs={"overlaps": "person,wallets"})
    person: Person = Relationship(
        back_populates="wallets", sa_relationship_kwargs={"overlaps": "trip"}
    )


class WalletTransfer(SQLModel, table=True):
    """Money moved between two wallets: a plain transfer, or an exchange when currencies differ."""

    __tablename__ = "wallet_transfer"
    __table_args__ = (
        trip_scoped_fk("from_currency_id", "trip_currency", "fk_transfer_from_currency_trip"),
        trip_scoped_fk("to_currency_id", "trip_currency", "fk_transfer_to_currency_trip"),
        trip_scoped_fk("from_wallet_id", "wallet", "fk_transfer_from_wallet_trip"),
        trip_scoped_fk("to_wallet_id", "wallet", "fk_transfer_to_wallet_trip"),
        CheckConstraint(
            "from_wallet_id <> to_wallet_id OR from_currency_id <> to_currency_id",
            name="ck_transfer_not_same",
        ),
        Index("ix_wallet_transfer_trip_occurred", "trip_id", "occurred_at"),
    )

    id: int | None = Field(default=None, primary_key=True)
    trip_id: int = Field(foreign_key="trip.id")
    occurred_at: datetime = Field(sa_column=Column(DateTime(timezone=True)))
    from_wallet_id: int = Field(index=True)
    from_currency_id: int
    from_amount_minor: int = Field(sa_column=Column(BigInteger))
    to_wallet_id: int = Field(index=True)
    to_currency_id: int
    to_amount_minor: int = Field(sa_column=Column(BigInteger))
    note: str | None = None
    created_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), server_default=func.now())
    )
    updated_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    )

    # As with LineItem: all five relationships below share the trip_id
    # column, and from/to each carry a second relationship into the same
    # target table, so both `foreign_keys` (to pick the right FK) and
    # `overlaps` (to silence the shared-column warning) are required.
    trip: Trip = Relationship(back_populates="transfers")
    from_currency: TripCurrency = Relationship(
        sa_relationship_kwargs={
            "foreign_keys": "[WalletTransfer.from_currency_id, WalletTransfer.trip_id]",
            "overlaps": "to_currency,from_wallet,to_wallet,transfers,trip",
        }
    )
    to_currency: TripCurrency = Relationship(
        sa_relationship_kwargs={
            "foreign_keys": "[WalletTransfer.to_currency_id, WalletTransfer.trip_id]",
            "overlaps": "from_currency,from_wallet,to_wallet,transfers,trip",
        }
    )
    from_wallet: Wallet = Relationship(
        sa_relationship_kwargs={
            "foreign_keys": "[WalletTransfer.from_wallet_id, WalletTransfer.trip_id]",
            "overlaps": "from_currency,to_currency,to_wallet,transfers,trip",
        }
    )
    to_wallet: Wallet = Relationship(
        sa_relationship_kwargs={
            "foreign_keys": "[WalletTransfer.to_wallet_id, WalletTransfer.trip_id]",
            "overlaps": "from_currency,to_currency,from_wallet,transfers,trip",
        }
    )
