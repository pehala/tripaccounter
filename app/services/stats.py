"""Group a trip's spend by any chain of dimensions.

One `GROUP BY` per chain, built from the registry below. `currency` leads every
chain, so a row is always one currency's money and nothing is ever converted.
A chain is answered together with its own prefixes, which is where a nested
breakdown's subtotals come from - see design/STATS.md §4.
"""

from dataclasses import dataclass
from datetime import date
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db_views import share_owed_view
from app.models.items import LineItem
from app.models.labels import ItemLabel, Label
from app.models.trip import Trip
from app.schemas.responses import StatsGroupOut, StatsOut, StatsRowOut
from app.services.errors.fields import UnknownDimensionError
from app.services.money import AMOUNT_SCALE, MICRO_SCALE, to_wire


@dataclass(frozen=True)
class Dimension:
    """One groupable column: the key it answers under, what it groups on, how it sorts."""

    key: str
    column: Any
    shares: bool = False
    ordinal: bool = False


# `label` is the only dimension needing a join of its own; `person` is the only
# one living on the share view rather than on the item.
DIMENSIONS: dict[str, Dimension] = {
    "currency": Dimension("currency_id", LineItem.currency_id),
    "label": Dimension("label", Label.name),
    "country": Dimension("country_id", LineItem.country_id),
    "city": Dimension("city", LineItem.city),
    "payer": Dimension("payer_id", LineItem.payer_id),
    "wallet": Dimension("wallet_id", LineItem.wallet_id),
    "day": Dimension("date", func.date(LineItem.occurred_at), ordinal=True),
    "person": Dimension("person_id", share_owed_view.c.person_id, shares=True),
}

CURRENCY = "currency"


def _day_count(trip: Trip) -> int | None:
    if not trip.start_date or not trip.end_date:
        return None
    return (date.fromisoformat(trip.end_date) - date.fromisoformat(trip.start_date)).days + 1


def expand_groupings(specs: list[str]) -> list[tuple[str, ...]]:
    """Turn the requested chains into the distinct chains to answer, shortest first.

    Each spec is a comma-separated chain. `currency` leads every chain, and a
    chain is expanded into its prefixes so each nesting level has a row of its
    own. `("currency",)` is therefore always answered: it is every chain's
    shortest prefix, and carries the per-currency trip total.
    """
    chains = {(CURRENCY,): None}
    for spec in specs:
        chain = [CURRENCY]
        for name in (part.strip() for part in spec.split(",")):
            if not name:
                continue
            if name not in DIMENSIONS or name in chain:
                raise UnknownDimensionError(name)
            chain.append(name)
            chains[tuple(chain)] = None
    # Stable: shallowest first, and within a depth the order they were asked in.
    return sorted(chains, key=len)


def _grouping(session: Session, trip_id: int, names: tuple[str, ...]) -> StatsGroupOut:
    """Run one chain's `GROUP BY` and return its rows."""
    dims = [DIMENSIONS[name] for name in names]
    columns = [dim.column for dim in dims]

    if any(dim.shares for dim in dims):
        # What a person owes is the share view's floored micro-units, never a
        # sum of typed amounts - design/ARCHITECTURE.md §Money.
        total = func.sum(share_owed_view.c.owed_micro)
        item_count = func.count(share_owed_view.c.item_id.distinct())
        source = share_owed_view.join(LineItem, LineItem.id == share_owed_view.c.item_id)
        scale = MICRO_SCALE
    else:
        total = func.sum(LineItem.amount_minor)
        item_count = func.count(LineItem.id.distinct())
        source = LineItem
        scale = AMOUNT_SCALE

    stmt = select(*columns, total, item_count).select_from(source)
    if "label" in names:
        # Outer, so items carrying no label group under `null`.
        stmt = stmt.outerjoin(ItemLabel, ItemLabel.item_id == LineItem.id).outerjoin(
            Label, Label.id == ItemLabel.label_id
        )
    ordinal = [dim.column for dim in dims if dim.ordinal]
    stmt = (
        stmt.where(LineItem.trip_id == trip_id)
        .group_by(*columns)
        .order_by(*ordinal, total.desc(), *columns)
    )

    rows = []
    for row in session.execute(stmt).all():
        *values, amount, count = row
        rows.append(
            StatsRowOut(
                keys={dim.key: value for dim, value in zip(dims, values, strict=True)},
                amount=to_wire(amount, scale),
                item_count=count,
            )
        )
    return StatsGroupOut(by=list(names), rows=rows)


def compute_stats(session: Session, trip: Trip, chains: list[tuple[str, ...]]) -> StatsOut:
    """Return one grouping per chain, each summed per currency."""
    return StatsOut(
        groups=[_grouping(session, trip.id, chain) for chain in chains],
        day_count=_day_count(trip),
    )
