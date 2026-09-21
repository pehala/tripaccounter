"""The trip-scoped selects more than one caller needs, named once.

Each returns a `Select` the caller executes, so a router can add its own
options and a service can wrap it in an aggregate.
"""

from sqlalchemy import func, select

from app.db_views import share_owed_view
from app.models.items import LineItem
from app.models.roster import TripCurrency
from app.models.wallets import WalletTransfer
from app.schemas.responses import ITEM_LOAD_OPTIONS, TRANSFER_LOAD_OPTIONS


def items_for_trip(trip_id: int, *, newest_first: bool = True):
    """Select a trip's line items, eager-loading what the wire form reads.

    `newest_first` is the feed order the API and the JSON export answer in;
    the CSV export asks for the opposite, reading as a chronological sheet.
    """
    order = (
        (LineItem.occurred_at.desc(), LineItem.id.desc())
        if newest_first
        else (LineItem.occurred_at, LineItem.id)
    )
    return (
        select(LineItem)
        .where(LineItem.trip_id == trip_id)
        .options(*ITEM_LOAD_OPTIONS)
        .order_by(*order)
    )


def transfers_for_trip(trip_id: int):
    """Select a trip's wallet transfers, newest first."""
    return (
        select(WalletTransfer)
        .where(WalletTransfer.trip_id == trip_id)
        .options(*TRANSFER_LOAD_OPTIONS)
        .order_by(WalletTransfer.occurred_at.desc(), WalletTransfer.id.desc())
    )


def currencies_for_trip(trip_id: int):
    """Select a trip's currencies in sort order."""
    return (
        select(TripCurrency)
        .where(TripCurrency.trip_id == trip_id)
        .order_by(TripCurrency.is_primary.desc(), TripCurrency.code)
    )


def spend_total(trip_id: int, currency_id: int):
    """Select the summed spend on a trip in one currency, 0 when there is none."""
    return select(func.coalesce(func.sum(LineItem.amount_minor), 0)).where(
        LineItem.trip_id == trip_id, LineItem.currency_id == currency_id
    )


def owed_by_person(trip_id: int, currency_id: int):
    """Select `(person_id, owed_micro)` summed over a trip's shares in one currency."""
    return (
        select(share_owed_view.c.person_id, func.sum(share_owed_view.c.owed_micro))
        .where(
            share_owed_view.c.trip_id == trip_id,
            share_owed_view.c.currency_id == currency_id,
        )
        .group_by(share_owed_view.c.person_id)
        .order_by(share_owed_view.c.person_id)
    )
