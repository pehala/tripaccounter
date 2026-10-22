"""A trip's stored settlement and the lock it puts on every field that enters a balance."""

from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy.orm import Session

from app.models.trip import Trip
from app.services.errors.api import ConflictError
from app.services.errors.base import FieldError
from app.services.errors.fields import (
    InvalidRateError,
    MissingRateError,
    NotInTripError,
    TripNotSettledError,
    TripSettledError,
)
from app.services.money import scale_rate


def validate(
    trip: Trip, target_currency_id: int, rates: list[tuple[int, Decimal]]
) -> dict[str, FieldError]:
    """Return the field errors of a settlement checked against the trip's currencies."""
    currency_ids = [currency.id for currency in trip.currencies]
    if target_currency_id not in currency_ids:
        return {"target_currency_id": NotInTripError()}

    seen: set[int] = set()
    for currency_id, _rate in rates:
        if currency_id == target_currency_id or currency_id not in currency_ids:
            return {"rates": InvalidRateError(currency_id=currency_id)}
        if currency_id in seen:
            return {"rates": InvalidRateError(currency_id=currency_id)}
        seen.add(currency_id)

    for currency_id in currency_ids:
        if currency_id != target_currency_id and currency_id not in seen:
            return {"rates": MissingRateError(currency_id=currency_id)}
    return {}


def settle(
    session: Session,
    trip: Trip,
    target_currency_id: int,
    rates: list[tuple[int, Decimal]],
    settled_at: datetime,
) -> None:
    """Store the agreement, replacing any earlier one."""
    by_currency = dict(rates)
    for currency in trip.currencies:
        rate = by_currency.get(currency.id)
        currency.settlement_rate_scaled = scale_rate(rate) if rate is not None else None
    trip.settlement_currency_id = target_currency_id
    trip.settled_at = settled_at
    session.flush()


def unlock(session: Session, trip: Trip) -> None:
    """Clear the target, `settled_at` and every rate."""
    for currency in trip.currencies:
        currency.settlement_rate_scaled = None
    trip.settlement_currency_id = None
    trip.settled_at = None
    session.flush()


def assert_settled(trip: Trip) -> None:
    """Raise `TripNotSettledError` on an unsettled trip."""
    if trip.settled_at is None:
        raise TripNotSettledError()


def assert_unsettled(trip: Trip) -> None:
    """Raise a 409 `trip_settled` under `fields.id` on a settled trip."""
    if trip.settled_at is not None:
        raise ConflictError({"id": TripSettledError()})


def assert_unchanged(stored: dict[str, Any], sent: dict[str, Any]) -> None:
    """Raise a 409 `trip_settled` under every field whose sent value differs from the stored one."""
    changed = {field: TripSettledError() for field, value in sent.items() if value != stored[field]}
    if changed:
        raise ConflictError(changed)
