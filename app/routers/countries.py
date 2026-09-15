"""Trip country routes: create, update, delete."""

from fastapi import APIRouter, Response

from app.deps import SessionDep, TripDep
from app.models.roster import TripCountry
from app.schemas import (
    CountryCreate,
    CountryEnvelope,
    CountryListEnvelope,
    CountryOut,
    CountryUpdate,
    error_responses,
)
from app.services import roster
from app.services.errors.api import NotFoundError, run_field
from app.services.roster import country_item_counts

router = APIRouter(tags=["countries"])


def _get_country(trip, country_id: int, session: SessionDep) -> TripCountry:
    country = session.get(TripCountry, country_id)
    if country is None or country.trip_id != trip.id:
        raise NotFoundError("country")
    return country


@router.get(
    "/trips/{slug}/countries", response_model=CountryListEnvelope, responses=error_responses(404)
)
def list_countries(trip: TripDep, session: SessionDep):
    """List a trip's countries with their item counts."""
    counts = country_item_counts(session, trip.id)
    return {
        "countries": [
            CountryOut.from_country(c, counts.get(c.id, 0))
            for c in sorted(trip.countries, key=lambda c: c.sort_order)
        ]
    }


@router.post(
    "/trips/{slug}/countries",
    status_code=201,
    response_model=CountryEnvelope,
    responses=error_responses(400, 404, 409, 422),
)
def create_country(body: CountryCreate, trip: TripDep, session: SessionDep):
    """Add a new country to a trip."""
    country = run_field(
        "name", roster.create_country, session, trip, body.name, body.code, body.is_default
    )
    return {"country": CountryOut.from_country(country, 0)}


@router.patch(
    "/trips/{slug}/countries/{country_id}",
    response_model=CountryEnvelope,
    responses=error_responses(400, 404, 409, 422),
)
def update_country(country_id: int, body: CountryUpdate, trip: TripDep, session: SessionDep):
    """Update a trip country's fields."""
    country = _get_country(trip, country_id, session)
    country = run_field(
        "name",
        roster.update_country,
        session,
        country,
        body.name,
        body.code,
        body.is_default,
        body.sort_order,
    )
    counts = country_item_counts(session, trip.id)
    return {"country": CountryOut.from_country(country, counts.get(country.id, 0))}


@router.delete(
    "/trips/{slug}/countries/{country_id}", status_code=204, responses=error_responses(404, 409)
)
def delete_country(country_id: int, trip: TripDep, session: SessionDep):
    """Delete a country from a trip."""
    country = _get_country(trip, country_id, session)
    run_field("id", roster.delete_country, session, country)
    return Response(status_code=204)
