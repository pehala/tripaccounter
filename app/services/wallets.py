"""Compute each tracked wallet's per-currency balance: received, sent, spent.

One `GROUP BY (wallet_id, currency_id)` over the trip's transfers and items,
`queries.wallet_flows` - the client never sums a column.
"""

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models.roster import Person
from app.schemas.responses import WalletBalanceOut, WalletReportOut
from app.services import queries
from app.services.money import AMOUNT_SCALE, to_wire


def wallet_balances(session: Session, trip_id: int) -> list[WalletReportOut]:
    """Return every wallet on the trip, tracked ones carrying a balance row per currency."""
    # selectinload: one extra query for every person's wallets, not one per person.
    people = (
        session.execute(
            select(Person)
            .where(Person.trip_id == trip_id)
            .order_by(Person.sort_order, Person.name)
            .options(selectinload(Person.wallets))
        )
        .scalars()
        .all()
    )
    currencies = session.execute(queries.currencies_for_trip(trip_id)).scalars().all()

    flows = {
        (row.wallet_id, row.currency_id): row
        for row in session.execute(queries.wallet_flows(trip_id))
    }

    reports = []
    for person in people:
        for wallet in person.wallets:
            balances = []
            if wallet.tracked:
                # Walking `currencies` puts the rows in the trip's currency order.
                for currency in currencies:
                    flow = flows.get((wallet.id, currency.id))
                    if flow is None:
                        continue
                    balances.append(
                        WalletBalanceOut(
                            currency_code=currency.code,
                            currency_id=currency.id,
                            received=to_wire(flow.received, AMOUNT_SCALE),
                            sent=to_wire(flow.sent, AMOUNT_SCALE),
                            spent=to_wire(flow.spent, AMOUNT_SCALE),
                            balance=to_wire(flow.received - flow.sent - flow.spent, AMOUNT_SCALE),
                        )
                    )
            reports.append(
                WalletReportOut(
                    id=wallet.id,
                    person_id=wallet.person_id,
                    name=wallet.name,
                    tracked=wallet.tracked,
                    is_default=wallet.is_default,
                    balances=balances,
                )
            )
    return reports
