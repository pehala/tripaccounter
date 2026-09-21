"""Person roster routes: list, create, update, delete."""

from sqlalchemy.orm import Session

from app.models.roster import Person
from app.models.trip import Trip
from app.routers.crud import Route, TripChildRoutes, route
from app.schemas.envelopes import PersonEnvelope, PersonListEnvelope
from app.schemas.requests import PersonCreate, PersonUpdate
from app.schemas.responses import PersonOut
from app.services import roster


class PersonRoutes(TripChildRoutes):
    """The people on a trip's roster."""

    model = Person
    resource = "person"
    collection = "people"
    envelope = PersonEnvelope
    list_envelope = PersonListEnvelope

    def serialize(self, person: Person, session: Session) -> PersonOut:
        """Return the person with the initial and weight the wire form derives."""
        return PersonOut.from_person(person)

    @route(Route.LIST)
    def rows(self, session: Session, trip: Trip) -> list[Person]:
        """List people on a trip, in sort order."""
        return trip.people

    @route(Route.CREATE)
    def create(self, session: Session, trip: Trip, body: PersonCreate) -> Person:
        """Add a new person to a trip's roster."""
        return roster.create_person(session, trip, body.name, body.default_weight, body.color)

    @route(Route.UPDATE)
    def update(self, session: Session, person: Person, body: PersonUpdate) -> Person:
        """Update a person's fields."""
        return roster.update_person(
            session, person, body.name, body.default_weight, body.active, body.sort_order
        )

    @route(Route.DELETE)
    def delete_row(self, session: Session, person: Person) -> None:
        """Delete a person from the roster."""
        roster.delete_person(session, person)


router = PersonRoutes().router()
