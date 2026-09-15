"""Compute by_label / by_country / by_person / by_day breakdowns.

Plain GROUP BY aggregates, per currency, never across them.
"""

from datetime import date

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db_views import share_owed_view
from app.models.items import LineItem
from app.models.labels import ItemLabel, Label
from app.models.roster import TripCurrency
from app.models.trip import Trip
from app.schemas import (
    StatsBlockOut,
    StatsCountryOut,
    StatsDayOut,
    StatsLabelOut,
    StatsOut,
    StatsPersonOut,
)
from app.services.money import AMOUNT_SCALE, MICRO_SCALE, to_wire


def _day_count(trip: Trip) -> int | None:
    if not trip.start_date or not trip.end_date:
        return None
    return (date.fromisoformat(trip.end_date) - date.fromisoformat(trip.start_date)).days + 1


def compute_stats(session: Session, trip: Trip) -> StatsOut:
    """Return each currency's by-label, by-country, by-person and by-day spend breakdowns."""
    currencies = (
        session.execute(
            select(TripCurrency)
            .where(TripCurrency.trip_id == trip.id)
            .order_by(TripCurrency.sort_order)
        )
        .scalars()
        .all()
    )

    blocks = []
    for currency in currencies:
        total_minor = session.execute(
            select(func.coalesce(func.sum(LineItem.amount_minor), 0)).where(
                LineItem.trip_id == trip.id, LineItem.currency_id == currency.id
            )
        ).scalar_one()
        if not total_minor:
            continue

        labelled_rows = session.execute(
            select(Label.name, func.sum(LineItem.amount_minor), func.count(LineItem.id.distinct()))
            .select_from(LineItem)
            .join(ItemLabel, ItemLabel.item_id == LineItem.id)
            .join(Label, Label.id == ItemLabel.label_id)
            .where(LineItem.trip_id == trip.id, LineItem.currency_id == currency.id)
            .group_by(Label.name)
            .order_by(func.sum(LineItem.amount_minor).desc(), Label.name)
        ).all()
        by_label = [
            StatsLabelOut(label=name, amount=to_wire(amount, AMOUNT_SCALE), item_count=count)
            for name, amount, count in labelled_rows
        ]
        unlabelled_minor, unlabelled_count = session.execute(
            select(func.coalesce(func.sum(LineItem.amount_minor), 0), func.count(LineItem.id))
            .select_from(LineItem)
            .outerjoin(ItemLabel, ItemLabel.item_id == LineItem.id)
            .where(
                LineItem.trip_id == trip.id,
                LineItem.currency_id == currency.id,
                ItemLabel.item_id.is_(None),
            )
        ).one()
        if unlabelled_count:
            by_label.append(
                StatsLabelOut(
                    label=None,
                    amount=to_wire(unlabelled_minor, AMOUNT_SCALE),
                    item_count=unlabelled_count,
                )
            )

        by_country = [
            StatsCountryOut(
                country_id=country_id, amount=to_wire(amount, AMOUNT_SCALE), item_count=count
            )
            for country_id, amount, count in session.execute(
                select(
                    LineItem.country_id, func.sum(LineItem.amount_minor), func.count(LineItem.id)
                )
                .where(LineItem.trip_id == trip.id, LineItem.currency_id == currency.id)
                .group_by(LineItem.country_id)
                .order_by(func.sum(LineItem.amount_minor).desc(), LineItem.country_id)
            ).all()
        ]

        by_person = [
            StatsPersonOut(person_id=person_id, amount=to_wire(amount, MICRO_SCALE))
            for person_id, amount in session.execute(
                select(share_owed_view.c.person_id, func.sum(share_owed_view.c.owed_micro))
                .where(
                    share_owed_view.c.trip_id == trip.id,
                    share_owed_view.c.currency_id == currency.id,
                )
                .group_by(share_owed_view.c.person_id)
                .order_by(share_owed_view.c.person_id)
            ).all()
        ]

        by_day = [
            StatsDayOut(date=day, amount=to_wire(amount, AMOUNT_SCALE))
            for day, amount in session.execute(
                select(func.date(LineItem.occurred_at), func.sum(LineItem.amount_minor))
                .where(LineItem.trip_id == trip.id, LineItem.currency_id == currency.id)
                .group_by(func.date(LineItem.occurred_at))
                .order_by(func.date(LineItem.occurred_at))
            ).all()
        ]

        blocks.append(
            StatsBlockOut(
                currency_code=currency.code,
                currency_id=currency.id,
                total=to_wire(total_minor, AMOUNT_SCALE),
                by_label=by_label,
                by_country=by_country,
                by_person=by_person,
                by_day=by_day,
            )
        )

    return StatsOut(stats=blocks, day_count=_day_count(trip))
