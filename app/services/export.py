"""CSV and JSON export writers. Both are share-grained: one row per resolved share."""

import csv
import io

from sqlalchemy.orm import Session

from app.models.items import LineItem
from app.models.trip import Trip
from app.schemas.responses import ItemOut, TransferOut, TripOut
from app.services import queries
from app.services.roster import country_item_counts

# Every column but the trailing share triple comes straight off `ItemOut` — the same
# wire shape the live API uses — so a field added there can't go stale here without a
# deliberate header change (design/API.md "Export"). `currency_id` and a share's
# `person_id` are dropped in favor of the roster names a reader (human or another
# app; this isn't meant to rebuild the database) would otherwise have to look up.
CSV_HEADER = [
    "item_id",
    "name",
    "note",
    "city",
    "occurred_at",
    "currency_code",
    "amount",
    "payer_id",
    "wallet_id",
    "country_id",
    "labels",
    "map_url",
    "lat",
    "lon",
    "created_at",
    "updated_at",
    "person_name",
    "weight",
    "owed",
]

# The share triple is built per row; everything before it is read off `ItemOut` by
# name, so `CSV_HEADER` is the one place a column is named. A header entry with no
# matching `ItemOut` field fails the export tests rather than exporting a blank.
ITEM_COLUMNS = CSV_HEADER[:-3]


def _items(session: Session, trip_id: int) -> list[LineItem]:
    return session.execute(queries.items_for_trip(trip_id, newest_first=False)).scalars().all()


def _export_rows(session: Session, trip: Trip) -> list[dict]:
    """One flat dict per resolved share: the row shape CSV and JSON export share."""
    # Export resolves against the whole roster, inactive people included: a
    # deactivated person keeps the shares they already carry (`delete_person`
    # refuses while any exist) and the balances still charge them, so dropping
    # them here would export an item whose owed column no longer sums to its
    # amount.
    roster_ids = [person.id for person in trip.people]
    person_names = {person.id: person.name for person in trip.people}
    rows = []
    for item in _items(session, trip.id):
        payload = ItemOut.from_item(item, roster_ids).model_dump()
        payload["item_id"] = payload["id"]
        base = {column: payload[column] for column in ITEM_COLUMNS}
        # A roster-padded share (a null weight for someone this item doesn't touch)
        # is dropped: export is share-grained, not roster-grained.
        for share in payload["split"]["shares"]:
            if share["weight"] is None:
                continue
            rows.append(
                {
                    **base,
                    "person_name": person_names[share["person_id"]],
                    "weight": share["weight"],
                    "owed": share["owed"],
                }
            )
    return rows


def _csv_value(value: object) -> object:
    """CSV has no `null` or list type: an absent value is an empty field, a list joins with `;`."""
    if value is None:
        return ""
    if isinstance(value, list):
        return ";".join(value)
    return value


def export_csv(session: Session, trip: Trip) -> str:
    """Return the trip's items as CSV, one row per resolved share."""
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(CSV_HEADER)
    for row in _export_rows(session, trip):
        writer.writerow([_csv_value(row[column]) for column in CSV_HEADER])
    return buffer.getvalue()


def export_json(session: Session, trip: Trip) -> dict:
    """Return the whole trip as the wire JSON envelope, items share-grained like the CSV."""
    transfers = session.execute(queries.transfers_for_trip(trip.id)).scalars().all()
    return {
        "trip": TripOut.from_trip(trip, country_item_counts(session, trip.id)),
        "items": _export_rows(session, trip),
        "transfers": [TransferOut.from_transfer(t) for t in transfers],
    }
