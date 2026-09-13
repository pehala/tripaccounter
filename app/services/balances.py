"""Compute per-currency balances and settle-up suggestions.

SQL GROUP BY aggregates over `share_owed` and `line_item.amount_minor` — the
client never sums a column.
"""

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db_views import share_owed_view
from app.models import LineItem, Person, TripCurrency
from app.schemas import BalanceBlockOut, BalancePersonOut, SuggestionOut
from app.services import settle
from app.services.money import AMOUNT_SCALE, MICRO_PER_MINOR, MICRO_SCALE, to_wire


def compute_balances(session: Session, trip_id: int) -> list[BalanceBlockOut]:
    """Return each currency's total spend, per-person paid/owed/net, and settle-up suggestions."""
    currencies = (
        session.execute(
            select(TripCurrency)
            .where(TripCurrency.trip_id == trip_id)
            .order_by(TripCurrency.sort_order)
        )
        .scalars()
        .all()
    )
    people = (
        session.execute(select(Person).where(Person.trip_id == trip_id).order_by(Person.sort_order))
        .scalars()
        .all()
    )
    sort_order = {person.id: person.sort_order for person in people}

    blocks = []
    for currency in currencies:
        total_spent_minor = session.execute(
            select(func.coalesce(func.sum(LineItem.amount_minor), 0)).where(
                LineItem.trip_id == trip_id, LineItem.currency_id == currency.id
            )
        ).scalar_one()
        if not total_spent_minor:
            continue

        paid_minor = dict(
            session.execute(
                select(LineItem.payer_id, func.sum(LineItem.amount_minor))
                .where(LineItem.trip_id == trip_id, LineItem.currency_id == currency.id)
                .group_by(LineItem.payer_id)
            ).all()
        )
        owed_micro = dict(
            session.execute(
                select(share_owed_view.c.person_id, func.sum(share_owed_view.c.owed_micro))
                .where(
                    share_owed_view.c.trip_id == trip_id,
                    share_owed_view.c.currency_id == currency.id,
                )
                .group_by(share_owed_view.c.person_id)
            ).all()
        )

        net_micro: dict[int, int] = {}
        person_blocks = []
        for person in people:
            paid = paid_minor.get(person.id, 0)
            owed = owed_micro.get(person.id, 0)
            net = paid * MICRO_PER_MINOR - owed
            net_micro[person.id] = net
            person_blocks.append(
                BalancePersonOut(
                    person_id=person.id,
                    paid=to_wire(paid, AMOUNT_SCALE),
                    owed=to_wire(owed, MICRO_SCALE),
                    net=to_wire(net, MICRO_SCALE),
                )
            )

        net_minor = settle.round_nets_to_minor(net_micro, sort_order)
        suggestions = [
            SuggestionOut(
                from_person_id=transfer["from_person_id"],
                to_person_id=transfer["to_person_id"],
                amount=to_wire(transfer["amount"], AMOUNT_SCALE),
            )
            for transfer in settle.suggest_transfers(net_minor, sort_order)
        ]

        blocks.append(
            BalanceBlockOut(
                currency_code=currency.code,
                currency_id=currency.id,
                total_spent=to_wire(total_spent_minor, AMOUNT_SCALE),
                people=person_blocks,
                suggestions=suggestions,
            )
        )
    return blocks
