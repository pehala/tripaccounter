"""Trip routes: create, list, update, delete."""

from fastapi import APIRouter, Response
from sqlalchemy import func, select

from app.deps import SessionDep, TripDep
from app.models.items import LineItem
from app.models.roster import Person
from app.models.trip import Trip
from app.schemas import (
    TripCreate,
    TripEnvelope,
    TripListEnvelope,
    TripOut,
    TripSummaryOut,
    TripUpdate,
    error_responses,
)
from app.services import roster
from app.services.errors.api import ValidationError, run_field
from app.services.errors.fields import EmptyError
from app.services.labels import get_or_create as get_or_create_label
from app.services.roster import country_item_counts
from app.services.slugs import unique_slug

router = APIRouter(tags=["trips"])


@router.get("/trips", response_model=TripListEnvelope, responses=error_responses())
def list_trips(session: SessionDep):
    """List all trips, most recently ended first; undated trips sort last, newest created first."""
    trips = (
        session.execute(
            select(Trip).order_by(
                Trip.end_date.is_(None), Trip.end_date.desc(), Trip.created_at.desc()
            )
        )
        .scalars()
        .all()
    )
    result = []
    for trip in trips:
        people_count = session.execute(
            select(func.count()).select_from(Person).where(Person.trip_id == trip.id)
        ).scalar_one()
        item_count = session.execute(
            select(func.count()).select_from(LineItem).where(LineItem.trip_id == trip.id)
        ).scalar_one()
        result.append(TripSummaryOut.from_trip(trip, people_count, item_count))
    return {"trips": result}


@router.post(
    "/trips",
    status_code=201,
    response_model=TripEnvelope,
    responses=error_responses(400, 409, 422),
)
def create_trip(body: TripCreate, session: SessionDep):
    """Create a new trip with its people, currencies, and countries."""
    fields = {}
    if len(body.people) == 0:
        fields["people"] = EmptyError()
    if len(body.currencies) == 0:
        fields["currencies"] = EmptyError()
    if len(body.countries) == 0:
        fields["countries"] = EmptyError()
    if fields:
        raise ValidationError(fields)

    trip = Trip(
        slug="", name=body.name, start_date=body.start_date, end_date=body.end_date, note=body.note
    )
    session.add(trip)
    session.flush()
    trip.slug = unique_slug(session, body.name)

    for person_in in body.people:
        run_field(
            "people",
            roster.create_person,
            session,
            trip,
            person_in.name,
            person_in.default_weight,
            person_in.color,
        )
    for currency_in in body.currencies:
        run_field(
            "currencies",
            roster.create_currency,
            session,
            trip,
            currency_in.code,
            currency_in.symbol,
            currency_in.is_primary,
        )
    for country_in in body.countries:
        run_field(
            "countries",
            roster.create_country,
            session,
            trip,
            country_in.name,
            country_in.code,
            country_in.is_default,
        )
    for token in body.labels or []:
        get_or_create_label(session, trip.id, token)

    session.flush()
    session.refresh(trip)
    return {"trip": TripOut.from_trip(trip, country_item_counts(session, trip.id))}


@router.get("/trips/{slug}", response_model=TripEnvelope, responses=error_responses(404))
def get_trip_route(trip: TripDep, session: SessionDep):
    """Get a single trip by slug."""
    return {"trip": TripOut.from_trip(trip, country_item_counts(session, trip.id))}


@router.patch(
    "/trips/{slug}", response_model=TripEnvelope, responses=error_responses(400, 404, 422)
)
def update_trip(body: TripUpdate, trip: TripDep, session: SessionDep):
    """Update a trip's fields."""
    if body.name is not None:
        trip.name = body.name
    if body.start_date is not None:
        trip.start_date = body.start_date
    if body.end_date is not None:
        trip.end_date = body.end_date
    if body.note is not None:
        trip.note = body.note
    if body.archived is not None:
        trip.archived = body.archived
    session.flush()
    session.refresh(trip)
    return {"trip": TripOut.from_trip(trip, country_item_counts(session, trip.id))}


@router.delete("/trips/{slug}", status_code=204, responses=error_responses(404))
def delete_trip(trip: TripDep, session: SessionDep):
    """Delete a trip."""
    session.delete(trip)
    session.flush()
    return Response(status_code=204)
