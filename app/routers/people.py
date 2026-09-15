"""Person roster routes: create, update, delete."""

from fastapi import APIRouter, Response

from app.deps import SessionDep, TripDep
from app.models.roster import Person
from app.schemas import (
    PersonCreate,
    PersonEnvelope,
    PersonListEnvelope,
    PersonOut,
    PersonUpdate,
    error_responses,
)
from app.services import roster
from app.services.errors.api import NotFoundError, run_field

router = APIRouter(tags=["people"])


def _get_person(trip, person_id: int, session: SessionDep) -> Person:
    person = session.get(Person, person_id)
    if person is None or person.trip_id != trip.id:
        raise NotFoundError("person")
    return person


@router.get(
    "/trips/{slug}/people", response_model=PersonListEnvelope, responses=error_responses(404)
)
def list_people(trip: TripDep):
    """List people on a trip, in sort order."""
    return {
        "people": [
            PersonOut.from_person(p) for p in sorted(trip.people, key=lambda p: p.sort_order)
        ]
    }


@router.post(
    "/trips/{slug}/people",
    status_code=201,
    response_model=PersonEnvelope,
    responses=error_responses(400, 404, 409, 422),
)
def create_person(body: PersonCreate, trip: TripDep, session: SessionDep):
    """Add a new person to a trip's roster."""
    person = run_field(
        "name", roster.create_person, session, trip, body.name, body.default_weight, body.color
    )
    return {"person": PersonOut.from_person(person)}


@router.patch(
    "/trips/{slug}/people/{person_id}",
    response_model=PersonEnvelope,
    responses=error_responses(400, 404, 409, 422),
)
def update_person(person_id: int, body: PersonUpdate, trip: TripDep, session: SessionDep):
    """Update a person's fields."""
    person = _get_person(trip, person_id, session)
    person = run_field(
        "name",
        roster.update_person,
        session,
        person,
        body.name,
        body.default_weight,
        body.active,
        body.sort_order,
    )
    return {"person": PersonOut.from_person(person)}


@router.delete(
    "/trips/{slug}/people/{person_id}", status_code=204, responses=error_responses(404, 409)
)
def delete_person(person_id: int, trip: TripDep, session: SessionDep):
    """Delete a person from the roster."""
    person = _get_person(trip, person_id, session)
    run_field("id", roster.delete_person, session, person)
    return Response(status_code=204)
