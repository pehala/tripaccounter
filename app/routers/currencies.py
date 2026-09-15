"""Trip currency routes: create, update, delete."""

from fastapi import APIRouter, Response

from app.deps import SessionDep, TripDep
from app.models.roster import TripCurrency
from app.schemas.envelopes import CurrencyEnvelope, CurrencyListEnvelope
from app.schemas.error_shapes import error_responses
from app.schemas.requests import CurrencyCreate, CurrencyUpdate
from app.schemas.responses import CurrencyOut
from app.services import roster
from app.services.errors.api import NotFoundError, run_field

router = APIRouter(tags=["currencies"])


def _get_currency(trip, currency_id: int, session: SessionDep) -> TripCurrency:
    currency = session.get(TripCurrency, currency_id)
    if currency is None or currency.trip_id != trip.id:
        raise NotFoundError("currency")
    return currency


@router.get(
    "/trips/{slug}/currencies", response_model=CurrencyListEnvelope, responses=error_responses(404)
)
def list_currencies(trip: TripDep):
    """List a trip's currencies, in sort order."""
    return {
        "currencies": [
            CurrencyOut.from_currency(c)
            for c in sorted(trip.currencies, key=lambda c: c.sort_order)
        ]
    }


@router.post(
    "/trips/{slug}/currencies",
    status_code=201,
    response_model=CurrencyEnvelope,
    responses=error_responses(400, 404, 409, 422),
)
def create_currency(body: CurrencyCreate, trip: TripDep, session: SessionDep):
    """Add a new currency to a trip."""
    currency = run_field(
        "code", roster.create_currency, session, trip, body.code, body.symbol, body.is_primary
    )
    return {"currency": CurrencyOut.from_currency(currency)}


@router.patch(
    "/trips/{slug}/currencies/{currency_id}",
    response_model=CurrencyEnvelope,
    responses=error_responses(400, 404, 409, 422),
)
def update_currency(currency_id: int, body: CurrencyUpdate, trip: TripDep, session: SessionDep):
    """Update a trip currency's fields."""
    currency = _get_currency(trip, currency_id, session)
    currency = run_field(
        "code",
        roster.update_currency,
        session,
        currency,
        body.symbol,
        body.is_primary,
        body.sort_order,
    )
    return {"currency": CurrencyOut.from_currency(currency)}


@router.delete(
    "/trips/{slug}/currencies/{currency_id}", status_code=204, responses=error_responses(404, 409)
)
def delete_currency(currency_id: int, trip: TripDep, session: SessionDep):
    """Delete a currency from a trip."""
    currency = _get_currency(trip, currency_id, session)
    run_field("id", roster.delete_currency, session, currency)
    return Response(status_code=204)
