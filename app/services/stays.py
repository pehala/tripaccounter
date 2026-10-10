"""Stay writes, and the per-currency totals and nightly averages of the items a stay groups."""

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.models.items import LineItem
from app.models.roster import TripCountry, TripCurrency
from app.models.stays import Stay
from app.models.trip import Trip
from app.schemas.requests import StayCreate, StayUpdate
from app.schemas.responses import StayOut, StayReportOut, StayTotalOut
from app.services import queries
from app.services.errors.api import ValidationError
from app.services.errors.base import FieldError
from app.services.errors.fields import InvalidDateRangeError
from app.services.items import validate_name
from app.services.money import AMOUNT_SCALE, MICRO_PER_MINOR, MICRO_SCALE, to_wire
from app.services.scope import ref_error


def validate(session: Session, stay: Stay) -> None:
    """Raise `ValidationError` for every field that leaves a written stay invalid."""
    fields: dict[str, FieldError] = {}
    name_error = validate_name(stay.name, required=True)
    if name_error:
        fields["name"] = name_error
    country_error = ref_error(session, TripCountry, stay.country_id, stay.trip_id, required=False)
    if country_error:
        fields["country_id"] = country_error
    if stay.check_out < stay.check_in:
        fields["check_out"] = InvalidDateRangeError()
    if fields:
        raise ValidationError(fields)


def create_stay(session: Session, trip: Trip, body: StayCreate) -> Stay:
    """Create a stay on the trip."""
    stay = Stay(trip_id=trip.id, **body.model_dump())
    validate(session, stay)
    session.add(stay)
    session.flush()
    return stay


def update_stay(session: Session, stay: Stay, body: StayUpdate) -> Stay:
    """Write the fields a body sends onto a stay; an optional one sent as `null` clears."""
    stay.sqlmodel_update(body.model_dump(exclude_unset=True))
    validate(session, stay)
    session.flush()
    return stay


def delete_stay(session: Session, stay: Stay) -> None:
    """Delete a stay, detaching its items first; the items themselves survive."""
    session.execute(update(LineItem).where(LineItem.stay_id == stay.id).values(stay_id=None))
    session.delete(stay)
    session.flush()


def stay_reports(session: Session, trip_id: int, stays: list[Stay]) -> list[StayReportOut]:
    """Return each stay with its item count and per-currency totals.

    A total's nightly average divides the whole sum, floored at micro-units;
    a 0-night stay has none.
    """
    rows = session.execute(
        select(
            LineItem.stay_id,
            TripCurrency.id,
            TripCurrency.code,
            queries.int_sum(LineItem.amount_minor),
            func.count(LineItem.id),
        )
        .join(TripCurrency, TripCurrency.id == LineItem.currency_id)
        .where(LineItem.trip_id == trip_id, LineItem.stay_id.in_([stay.id for stay in stays]))
        .group_by(LineItem.stay_id, TripCurrency.id)
        .order_by(TripCurrency.is_primary.desc(), TripCurrency.code)
    ).all()

    reports = {
        stay.id: StayReportOut(**StayOut.from_stay(stay).model_dump(), item_count=0, totals=[])
        for stay in stays
    }
    for stay_id, currency_id, code, amount_minor, count in rows:
        report = reports[stay_id]
        report.item_count += count
        per_night = amount_minor * MICRO_PER_MINOR // report.nights if report.nights else None
        report.totals.append(
            StayTotalOut(
                currency_code=code,
                currency_id=currency_id,
                amount=to_wire(amount_minor, AMOUNT_SCALE),
                per_night=to_wire(per_night, MICRO_SCALE) if per_night is not None else None,
            )
        )
    return list(reports.values())
