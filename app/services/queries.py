"""The trip-scoped selects more than one caller needs, named once.

Each returns a `Select` the caller executes, so a router can add its own
options and a service can wrap it in an aggregate.
"""

from sqlalchemy import BigInteger, String, cast, func, literal, select, union_all

from app.db_views import share_owed_view
from app.models.items import LineItem
from app.models.roster import TripCurrency
from app.models.wallets import Wallet, WalletTransfer
from app.schemas.responses import ITEM_LOAD_OPTIONS, TRANSFER_LOAD_OPTIONS


def int_sum(column):
    """Sum `column` as a bigint; Postgres widens a bigint `SUM` to numeric otherwise."""
    return cast(func.sum(column), BigInteger)


def day_of(column):
    """Return `column`'s calendar day as a `YYYY-MM-DD` string, on every dialect."""
    return cast(func.date(column), String)


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
    return select(func.coalesce(int_sum(LineItem.amount_minor), 0)).where(
        LineItem.trip_id == trip_id, LineItem.currency_id == currency_id
    )


def owed_by_person(trip_id: int, currency_id: int):
    """Select `(person_id, owed_micro)` summed over a trip's shares in one currency."""
    return (
        select(share_owed_view.c.person_id, int_sum(share_owed_view.c.owed_micro))
        .where(
            share_owed_view.c.trip_id == trip_id,
            share_owed_view.c.currency_id == currency_id,
        )
        .group_by(share_owed_view.c.person_id)
        .order_by(share_owed_view.c.person_id)
    )


def wallet_flows(trip_id: int):
    """Select `(wallet_id, person_id, tracked, currency_id, received, sent, spent)`.

    One row per wallet and currency any transfer or item touched, summed in
    minor units: transfers in, transfers out and items each fill one column.
    Grouped on the wallet's primary key, so its other columns stay selectable.
    """
    zero = literal(0)

    def grouped(wallet_id, currency_id, amounts, where):
        """Sum one source's `(received, sent, spent)` per (wallet, currency) before the union."""
        received, sent, spent = amounts
        return (
            select(
                wallet_id.label("wallet_id"),
                currency_id.label("currency_id"),
                func.sum(received).label("received"),
                func.sum(sent).label("sent"),
                func.sum(spent).label("spent"),
            )
            .where(where)
            .group_by(wallet_id, currency_id)
        )

    movements = union_all(
        grouped(
            WalletTransfer.to_wallet_id,
            WalletTransfer.to_currency_id,
            (WalletTransfer.to_amount_minor, zero, zero),
            WalletTransfer.trip_id == trip_id,
        ),
        grouped(
            WalletTransfer.from_wallet_id,
            WalletTransfer.from_currency_id,
            (zero, WalletTransfer.from_amount_minor, zero),
            WalletTransfer.trip_id == trip_id,
        ),
        grouped(
            LineItem.wallet_id,
            LineItem.currency_id,
            (zero, zero, LineItem.amount_minor),
            LineItem.trip_id == trip_id,
        ),
    ).subquery("movements")
    return (
        select(
            Wallet.id.label("wallet_id"),
            Wallet.person_id,
            Wallet.tracked,
            movements.c.currency_id,
            int_sum(movements.c.received).label("received"),
            int_sum(movements.c.sent).label("sent"),
            int_sum(movements.c.spent).label("spent"),
        )
        .join(Wallet, Wallet.id == movements.c.wallet_id)
        .group_by(Wallet.id, movements.c.currency_id)
    )
