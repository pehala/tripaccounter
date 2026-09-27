"""Compute each person's exchange rates per currency pair, first in first out.

Every exchange into a target currency is a lot, queued by `occurred_at` then id,
whatever currency funded it. What the person spent uses up the oldest lots first,
then whatever they exchanged back out of the target into any currency, and what is
still held in their tracked wallets is the newest. `rate` is
what the spent units cost, `leftover_rate` what the held ones cost, both in the
funding currency per one target unit, floored at `RATE_SCALE`.

Three queries - the trip's exchanges, `queries.wallet_flows` and the trip's
currencies - then the queue in Python, on integers and exact fractions.
"""

from collections import defaultdict
from dataclasses import dataclass
from fractions import Fraction

from sqlalchemy import select
from sqlalchemy.orm import Session, aliased

from app.models.roster import Person
from app.models.wallets import Wallet, WalletTransfer
from app.schemas.responses import ExchangeRateOut
from app.services import queries
from app.services.money import AMOUNT_SCALE, RATE_SCALE, to_wire


@dataclass
class Pair:
    """One person's exchanges between two currencies, and what they are worth."""

    person_id: int
    person_order: tuple
    direction: tuple
    spent_units: int = 0
    spent_cost: Fraction = Fraction(0)
    held_units: int = 0
    held_cost: Fraction = Fraction(0)


def exchanges_select(trip_id: int):
    """Select the trip's exchanges with their owner and both currency ids, oldest first."""
    from_wallet = aliased(Wallet, name="from_wallet")
    return (
        select(
            from_wallet.person_id,
            Person.sort_order,
            Person.name,
            WalletTransfer.from_currency_id,
            WalletTransfer.to_currency_id,
            WalletTransfer.from_amount_minor,
            WalletTransfer.to_amount_minor,
        )
        .join(from_wallet, from_wallet.id == WalletTransfer.from_wallet_id)
        .join(Person, Person.id == from_wallet.person_id)
        .where(
            WalletTransfer.trip_id == trip_id,
            WalletTransfer.from_currency_id != WalletTransfer.to_currency_id,
        )
        .order_by(WalletTransfer.occurred_at, WalletTransfer.id)
    )


def held_by_person(session: Session, trip_id: int) -> dict:
    """Return `{(person_id, currency_id): minor}`: positive balances of tracked wallets."""
    held = defaultdict(int)
    for flow in session.execute(queries.wallet_flows(trip_id)):
        balance = flow.received - flow.sent - flow.spent
        if flow.tracked and balance > 0:
            held[(flow.person_id, flow.currency_id)] += balance
    return held


def collect_pairs(rows) -> tuple[list[Pair], list]:
    """Group exchange rows into one `Pair` per person and unordered currency pair.

    A pair's first exchange sets its direction: what it paid in funds, what it got is
    the target.

    Also return the exchanges as `(pair, paid_in, paid, got)`, in row order.
    """
    pairs = {}
    exchanges = []
    for person_id, sort_order, name, paid_in, bought, paid, got in rows:
        key = (person_id, frozenset((paid_in, bought)))
        pair = pairs.setdefault(key, Pair(person_id, (sort_order, name), (paid_in, bought)))
        exchanges.append((pair, paid_in, paid, got))
    return list(pairs.values()), exchanges


def price_queues(exchanges: list, held: dict) -> None:
    """Split each person's target currency into spent, changed back and held, oldest first."""
    queues = defaultdict(list)
    sold = defaultdict(int)
    for pair, paid_in, paid, got in exchanges:
        sold[(pair.person_id, paid_in)] += paid
        if pair.direction[0] == paid_in:
            queues[(pair.person_id, pair.direction[1])].append((pair, paid, got))

    for key, lots in queues.items():
        bought = sum(got for _, _, got in lots)
        kept = min(held.get(key, 0), bought - sold[key])
        spent = bought - sold[key] - kept
        held_from = bought - kept
        start = 0
        for pair, paid, got in lots:
            end = start + got
            spent_units = max(min(end, spent) - start, 0)
            held_units = max(end - max(start, held_from), 0)
            pair.spent_units += spent_units
            pair.spent_cost += Fraction(paid * spent_units, got)
            pair.held_units += held_units
            pair.held_cost += Fraction(paid * held_units, got)
            start = end


def per_unit(cost: Fraction, units: int):
    """Return a cost over its units as a wire rate floored at `RATE_SCALE`, or None."""
    if units == 0:
        return None
    return to_wire(cost * RATE_SCALE // units, RATE_SCALE)


def exchange_rates(session: Session, trip_id: int) -> list[ExchangeRateOut]:
    """Return one row per person and currency pair the person exchanged between.

    Rows come in roster order, then funding and target currency in trip order.
    """
    pairs, exchanges = collect_pairs(session.execute(exchanges_select(trip_id)))
    price_queues(exchanges, held_by_person(session, trip_id))
    currencies = session.execute(queries.currencies_for_trip(trip_id)).scalars().all()
    by_id = {currency.id: currency for currency in currencies}
    position = {currency.id: index for index, currency in enumerate(currencies)}

    rows = []
    for pair in pairs:
        from_id, to_id = pair.direction
        rows.append(
            (
                (pair.person_order, position[from_id], position[to_id]),
                ExchangeRateOut(
                    person_id=pair.person_id,
                    from_currency_code=by_id[from_id].code,
                    to_currency_code=by_id[to_id].code,
                    rate=per_unit(pair.spent_cost, pair.spent_units),
                    leftover=to_wire(pair.held_units, AMOUNT_SCALE),
                    leftover_rate=per_unit(pair.held_cost, pair.held_units),
                ),
            )
        )
    return [row for _, row in sorted(rows, key=lambda entry: entry[0])]
