"""Compute each tracked wallet's per-currency balance: received, sent, spent.

Three `GROUP BY (wallet_id, currency_id)` queries over the trip - the client
never sums a column (same shape as `app/services/balances.py`).
"""

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.models.items import LineItem
from app.models.roster import Person
from app.models.wallets import WalletTransfer
from app.schemas.responses import WalletBalanceOut, WalletReportOut
from app.services import queries
from app.services.money import AMOUNT_SCALE, to_wire


def _group_sum(session: Session, wallet_col, currency_col, amount_col, trip_id: int) -> dict:
    """Return `{(wallet_id, currency_id): summed amount_minor}` for one side of every transfer."""
    rows = session.execute(
        select(wallet_col, currency_col, func.sum(amount_col))
        .select_from(WalletTransfer)
        .where(WalletTransfer.trip_id == trip_id)
        .group_by(wallet_col, currency_col)
    ).all()
    return {(wallet_id, currency_id): amount for wallet_id, currency_id, amount in rows}


def wallet_balances(session: Session, trip_id: int) -> list[WalletReportOut]:
    """Return every wallet on the trip, tracked ones carrying a balance row per currency."""
    # selectinload: one extra query for every person's wallets, not one per person.
    people = (
        session.execute(
            select(Person)
            .where(Person.trip_id == trip_id)
            .order_by(Person.sort_order)
            .options(selectinload(Person.wallets))
        )
        .scalars()
        .all()
    )
    currencies = session.execute(queries.currencies_for_trip(trip_id)).scalars().all()
    currency_order = {c.id: c.sort_order for c in currencies}
    currency_codes = {c.id: c.code for c in currencies}

    received = _group_sum(
        session,
        WalletTransfer.to_wallet_id,
        WalletTransfer.to_currency_id,
        WalletTransfer.to_amount_minor,
        trip_id,
    )
    sent = _group_sum(
        session,
        WalletTransfer.from_wallet_id,
        WalletTransfer.from_currency_id,
        WalletTransfer.from_amount_minor,
        trip_id,
    )
    spent_rows = session.execute(
        select(LineItem.wallet_id, LineItem.currency_id, func.sum(LineItem.amount_minor))
        .where(LineItem.trip_id == trip_id)
        .group_by(LineItem.wallet_id, LineItem.currency_id)
    ).all()
    spent = {(wallet_id, currency_id): amount for wallet_id, currency_id, amount in spent_rows}

    reports = []
    for person in people:
        for wallet in sorted(person.wallets, key=lambda w: w.sort_order):
            balances = []
            if wallet.tracked:
                currency_ids = sorted(
                    {
                        currency_id
                        for wallet_id, currency_id in (*received, *sent, *spent)
                        if wallet_id == wallet.id
                    },
                    key=lambda cid: currency_order.get(cid, 0),
                )
                for currency_id in currency_ids:
                    r = received.get((wallet.id, currency_id), 0)
                    s = sent.get((wallet.id, currency_id), 0)
                    sp = spent.get((wallet.id, currency_id), 0)
                    balances.append(
                        WalletBalanceOut(
                            currency_code=currency_codes[currency_id],
                            currency_id=currency_id,
                            received=to_wire(r, AMOUNT_SCALE),
                            sent=to_wire(s, AMOUNT_SCALE),
                            spent=to_wire(sp, AMOUNT_SCALE),
                            balance=to_wire(r - s - sp, AMOUNT_SCALE),
                        )
                    )
            reports.append(
                WalletReportOut(
                    id=wallet.id,
                    person_id=wallet.person_id,
                    name=wallet.name,
                    tracked=wallet.tracked,
                    is_default=wallet.is_default,
                    sort_order=wallet.sort_order,
                    balances=balances,
                )
            )
    return reports
