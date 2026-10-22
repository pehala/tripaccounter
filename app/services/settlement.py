"""A trip's stored settlement - the agreed target currency and rates - and the lock it holds.

While a trip is settled, every field that enters a balance is frozen: `assert_unchanged`
guards the item fields one by one, `assert_unsettled` the writes frozen as a whole.
The rates are stored and validated here and never applied; the browser converts.
"""

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
    """Check a settlement against the trip's currencies; return its field errors.

    The target must be a trip currency, and every other trip currency needs exactly
    one rate. The balances are never read: the roster alone decides.
    """
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
    """Store the agreement, replacing whatever an earlier settle left.

    Only called once `validate` returned no errors.
    """
    by_currency = dict(rates)
    for currency in trip.currencies:
        rate = by_currency.get(currency.id)
        currency.settlement_rate_scaled = scale_rate(rate) if rate is not None else None
    trip.settlement_currency_id = target_currency_id
    trip.settled_at = settled_at
    session.flush()


def unlock(session: Session, trip: Trip) -> None:
    """Clear the target, `settled_at` and every rate together; a no-op on an unsettled trip."""
    for currency in trip.currencies:
        currency.settlement_rate_scaled = None
    trip.settlement_currency_id = None
    trip.settled_at = None
    session.flush()


def assert_settled(trip: Trip) -> None:
    """Raise `TripNotSettledError` when there is no settlement to unlock."""
    if trip.settled_at is None:
        raise TripNotSettledError()


def assert_unsettled(trip: Trip) -> None:
    """Reject a write frozen as a whole while the trip is settled.

    Item create and delete, every transfer write, currency create and delete. Raises
    the 409 under `fields.id`, the object-level slot.
    """
    if trip.settled_at is not None:
        raise ConflictError({"id": TripSettledError()})


def assert_unchanged(stored: dict[str, Any], sent: dict[str, Any]) -> None:
    """Reject a write that changes a locked field; the caller calls it on a settled trip only.

    `stored` and `sent` map each locked field to its comparable value; a field the
    write omits is absent from `sent`, and resending the stored value is accepted.
    Raises one 409 naming every changed field.
    """
    changed = {field: TripSettledError() for field, value in sent.items() if value != stored[field]}
    if changed:
        raise ConflictError(changed)
