"""Compute per-currency balances and settle-up suggestions.

SQL GROUP BY aggregates over `share_owed`, `line_item.amount_minor` and
`wallet_transfer` — the client never sums a column. A transfer only enters a
person's `sent`/`received` (and so `net`) when it crosses owners: by the
`cross_owner_exchange` rule such a transfer is always single-currency, so it
adds equal and opposite hundredths and never needs a conversion to balance.
"""

from sqlalchemy import func, select
from sqlalchemy.orm import Session, aliased

from app.models.items import LineItem
from app.models.wallets import Wallet, WalletTransfer
from app.schemas.responses import BalanceBlockOut, BalancePersonOut, SuggestionOut
from app.services import queries, settle
from app.services.money import AMOUNT_SCALE, MICRO_PER_MINOR, MICRO_SCALE, to_wire


def _cross_owner_by_person(session: Session, trip_id: int, currency_id: int) -> tuple[dict, dict]:
    """Return `({person_id: sent_minor}, {person_id: received_minor})` for cross-owner transfers.

    Cross-owner transfers are single-currency (`cross_owner_exchange` forbids
    otherwise), so filtering each side by its own currency column picks up
    exactly the transfers that touch `currency_id` at all.
    """
    from_wallet = aliased(Wallet)
    to_wallet = aliased(Wallet)
    sent = dict(
        session.execute(
            select(from_wallet.person_id, func.sum(WalletTransfer.from_amount_minor))
            .join(from_wallet, WalletTransfer.from_wallet_id == from_wallet.id)
            .join(to_wallet, WalletTransfer.to_wallet_id == to_wallet.id)
            .where(
                WalletTransfer.trip_id == trip_id,
                WalletTransfer.from_currency_id == currency_id,
                from_wallet.person_id != to_wallet.person_id,
            )
            .group_by(from_wallet.person_id)
        ).all()
    )
    received = dict(
        session.execute(
            select(to_wallet.person_id, func.sum(WalletTransfer.to_amount_minor))
            .join(from_wallet, WalletTransfer.from_wallet_id == from_wallet.id)
            .join(to_wallet, WalletTransfer.to_wallet_id == to_wallet.id)
            .where(
                WalletTransfer.trip_id == trip_id,
                WalletTransfer.to_currency_id == currency_id,
                from_wallet.person_id != to_wallet.person_id,
            )
            .group_by(to_wallet.person_id)
        ).all()
    )
    return sent, received


def compute_balances(session: Session, trip_id: int) -> list[BalanceBlockOut]:
    """Return each currency's total spend, per-person balance fields, and settle-up suggestions."""
    currencies = session.execute(queries.currencies_for_trip(trip_id)).scalars().all()
    people = session.execute(queries.people_for_trip(trip_id)).scalars().all()
    sort_order = {person.id: person.sort_order for person in people}

    blocks = []
    for currency in currencies:
        total_spent_minor = session.execute(queries.spend_total(trip_id, currency.id)).scalar_one()
        sent_minor, received_minor = _cross_owner_by_person(session, trip_id, currency.id)
        if not total_spent_minor and not sent_minor and not received_minor:
            continue

        paid_minor = dict(
            session.execute(
                select(LineItem.payer_id, func.sum(LineItem.amount_minor))
                .where(LineItem.trip_id == trip_id, LineItem.currency_id == currency.id)
                .group_by(LineItem.payer_id)
            ).all()
        )
        owed_micro = dict(session.execute(queries.owed_by_person(trip_id, currency.id)).all())

        net_micro: dict[int, int] = {}
        person_blocks = []
        for person in people:
            paid = paid_minor.get(person.id, 0)
            owed = owed_micro.get(person.id, 0)
            sent = sent_minor.get(person.id, 0)
            received = received_minor.get(person.id, 0)
            net = paid * MICRO_PER_MINOR - owed + (sent - received) * MICRO_PER_MINOR
            net_micro[person.id] = net
            person_blocks.append(
                BalancePersonOut(
                    person_id=person.id,
                    paid=to_wire(paid, AMOUNT_SCALE),
                    owed=to_wire(owed, MICRO_SCALE),
                    sent=to_wire(sent, AMOUNT_SCALE),
                    received=to_wire(received, AMOUNT_SCALE),
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
