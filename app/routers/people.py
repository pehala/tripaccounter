"""Person roster routes: create, update, delete."""

from app.models.roster import Person
from app.routers.crud import TripChildRoutes
from app.schemas.envelopes import PersonEnvelope, PersonListEnvelope
from app.schemas.requests import PersonCreate, PersonUpdate
from app.schemas.responses import PersonOut
from app.services import roster


class PersonRoutes(TripChildRoutes):
    """The people on a trip's roster."""

    model = Person
    resource = "person"
    collection = "people"
    out = PersonOut
    create_body = PersonCreate
    update_body = PersonUpdate
    envelope = PersonEnvelope
    list_envelope = PersonListEnvelope
    list_doc = "List people on a trip, in sort order."
    create_doc = "Add a new person to a trip's roster."
    update_doc = "Update a person's fields."
    delete_doc = "Delete a person from the roster."

    @classmethod
    def serialize(cls, person, session):
        """Return the person with the initial and weight the wire form derives."""
        return PersonOut.from_person(person)

    @classmethod
    def create(cls, session, trip, body):
        """Add a new person to a trip's roster."""
        return roster.create_person(session, trip, body.name, body.default_weight, body.color)

    @classmethod
    def update(cls, session, person, body):
        """Update a person's fields."""
        return roster.update_person(
            session, person, body.name, body.default_weight, body.active, body.sort_order
        )

    @classmethod
    def delete_row(cls, session, person):
        """Delete a person, raising if they still pay or share any item."""
        roster.delete_person(session, person)


router = PersonRoutes.router()
