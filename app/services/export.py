"""CSV (one row per share) and JSON (whole trip) export writers."""

import csv
import io

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import LineItem, Trip, WalletTransfer
from app.schemas import ITEM_LOAD_OPTIONS, TRANSFER_LOAD_OPTIONS, ItemOut, TransferOut, TripOut
from app.services import splits
from app.services.money import AMOUNT_SCALE, to_wire
from app.services.roster import country_item_counts

CSV_HEADER = [
    "item_id",
    "name",
    "occurred_at",
    "currency_code",
    "amount",
    "payer_id",
    "wallet_id",
    "country_id",
    "person_id",
    "weight",
    "owed",
]


def _items(session: Session, trip_id: int) -> list[LineItem]:
    return (
        session.execute(
            select(LineItem)
            .where(LineItem.trip_id == trip_id)
            .options(*ITEM_LOAD_OPTIONS)
            .order_by(LineItem.occurred_at, LineItem.id)
        )
        .scalars()
        .all()
    )


def export_csv(session: Session, trip: Trip) -> str:
    """Return the trip's items as CSV, one row per resolved share."""
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(CSV_HEADER)

    for item in _items(session, trip.id):
        rows = [
            {
                "person_id": share.person_id,
                "weight_scaled": share.weight_scaled,
                "owed_minor": share.owed_minor,
                "exact": share.split_mode_exact,
            }
            for share in item.shares
        ]
        person_ids = [row["person_id"] for row in rows]
        resolved = splits.resolve_shares_wire(person_ids, rows, item.amount_minor)
        for share in resolved:
            writer.writerow(
                [
                    item.id,
                    item.name,
                    item.occurred_at.isoformat(),
                    item.currency.code,
                    to_wire(item.amount_minor, AMOUNT_SCALE),
                    item.payer_id,
                    item.wallet_id,
                    item.country_id,
                    share["person_id"],
                    share["weight"],
                    share["owed"],
                ]
            )
    return buffer.getvalue()


def export_json(session: Session, trip: Trip) -> dict:
    """Return the whole trip, its roster-ordered items, as the wire JSON envelope."""
    items = (
        session.execute(
            select(LineItem)
            .where(LineItem.trip_id == trip.id)
            .options(*ITEM_LOAD_OPTIONS)
            .order_by(LineItem.occurred_at.desc(), LineItem.id.desc())
        )
        .scalars()
        .all()
    )
    roster_ids = [
        person.id for person in sorted(trip.people, key=lambda p: p.sort_order) if person.active
    ]
    transfers = (
        session.execute(
            select(WalletTransfer)
            .where(WalletTransfer.trip_id == trip.id)
            .options(*TRANSFER_LOAD_OPTIONS)
            .order_by(WalletTransfer.occurred_at.desc(), WalletTransfer.id.desc())
        )
        .scalars()
        .all()
    )
    return {
        "trip": TripOut.from_trip(trip, country_item_counts(session, trip.id)),
        "items": [ItemOut.from_item(item, roster_ids) for item in items],
        "transfers": [TransferOut.from_transfer(t) for t in transfers],
    }
