"""Resolve a row by id under the trip that owns it.

Every id in a path or a write body is trip-scoped: the same integer names a
different row on a different trip, so a lookup that ignores the trip is a
cross-trip read. These two are the only ways `app/` resolves one - `in_trip`
where a miss is a field error the caller collects, `require_in_trip` where a
miss is the response.
"""

from sqlalchemy.orm import Session

from app.services.errors.api import NotFoundError
from app.services.errors.fields import NotInTripError, RequiredError


def in_trip(session: Session, model: type, row_id: int | None, trip_id: int):
    """Return the row of `model` with `row_id`, or None if missing or from another trip."""
    if row_id is None:
        return None
    row = session.get(model, row_id)
    if row is None or row.trip_id != trip_id:
        return None
    return row


def require_in_trip(  # noqa: PLR0913
    session: Session, model: type, row_id: int, trip_id: int, resource: str, *, options=()
):
    """Return the row of `model` with `row_id` under this trip, or raise not-found."""
    row = session.get(model, row_id, options=options or None)
    if row is None or row.trip_id != trip_id:
        raise NotFoundError(resource)
    return row


def ref_error(session: Session, model: type, row_id: int | None, trip_id: int, *, required: bool):
    """Return the field error a trip-scoped reference earns, or None when it is fine.

    Omitted is `required` only where the caller says so - a create demands the
    reference, a patch leaves an omitted one alone.
    """
    if row_id is None:
        return RequiredError() if required else None
    if in_trip(session, model, row_id, trip_id) is None:
        return NotInTripError()
    return None
