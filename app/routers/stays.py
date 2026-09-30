"""Stay routes: list, create, update, delete."""

from sqlalchemy.orm import Session

from app.models.stays import Stay
from app.models.trip import Trip
from app.routers.crud import Route, TripChildRoutes, route
from app.schemas.envelopes import StayEnvelope, StayListEnvelope
from app.schemas.requests import StayCreate, StayUpdate
from app.schemas.responses import StayReportOut
from app.services import stays


class StayRoutes(TripChildRoutes):
    """A trip's stays, each carrying its items' per-currency totals and nightly averages."""

    model = Stay
    resource = "stay"
    collection = "stays"
    envelope = StayEnvelope
    list_envelope = StayListEnvelope

    def serialize(self, stay: Stay, session: Session) -> StayReportOut:
        """Return the stay with what its items add up to."""
        return stays.stay_reports(session, stay.trip_id, [stay])[0]

    def serialize_list(self, rows: list[Stay], session: Session, trip: Trip) -> list[StayReportOut]:
        """Read every stay's totals in one grouped query."""
        return stays.stay_reports(session, trip.id, rows)

    @route(Route.LIST)
    def rows(self, session: Session, trip: Trip) -> list[Stay]:
        """List a trip's stays by check-in, with their totals."""
        return trip.stays

    @route(Route.CREATE)
    def create(self, session: Session, trip: Trip, body: StayCreate) -> Stay:
        """Add a new stay to a trip."""
        return stays.create_stay(session, trip, body)

    @route(Route.UPDATE)
    def update(self, session: Session, stay: Stay, body: StayUpdate) -> Stay:
        """Update a stay's fields; an optional field sent as `null` clears it."""
        return stays.update_stay(session, stay, body)

    @route(Route.DELETE, statuses=(404,))
    def delete_row(self, session: Session, stay: Stay) -> None:
        """Delete a stay; its items stay, no longer grouped under it."""
        stays.delete_stay(session, stay)


router = StayRoutes().router()
