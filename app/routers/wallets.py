"""Wallet routes: CRUD, and the per-currency balances report on the same collection."""

from fastapi import APIRouter, Response

from app.deps import SessionDep, TripDep
from app.models.roster import Person
from app.models.wallets import Wallet
from app.schemas.envelopes import WalletEnvelope, WalletListEnvelope
from app.schemas.error_shapes import error_responses
from app.schemas.requests import WalletCreate, WalletUpdate
from app.schemas.responses import WalletOut
from app.services import roster
from app.services.errors.api import ValidationError, run_field
from app.services.errors.fields import NotInTripError
from app.services.scope import in_trip, require_in_trip
from app.services.wallets import wallet_balances

router = APIRouter(tags=["wallets"])


@router.get(
    "/trips/{slug}/wallets", response_model=WalletListEnvelope, responses=error_responses(404)
)
def list_wallets(trip: TripDep, session: SessionDep):
    """Get every wallet on the trip with its per-currency balances."""
    return {"wallets": wallet_balances(session, trip.id)}


@router.post(
    "/trips/{slug}/wallets",
    status_code=201,
    response_model=WalletEnvelope,
    responses=error_responses(400, 404, 409, 422),
)
def create_wallet(body: WalletCreate, trip: TripDep, session: SessionDep):
    """Add a new wallet, owned by one of the trip's people."""
    person = in_trip(session, Person, body.person_id, trip.id)
    if person is None:
        raise ValidationError({"person_id": NotInTripError()})
    wallet = run_field("name", roster.create_wallet, session, trip, person, body.name, body.tracked)
    return {"wallet": WalletOut.model_validate(wallet)}


@router.patch(
    "/trips/{slug}/wallets/{wallet_id}",
    response_model=WalletEnvelope,
    responses=error_responses(400, 404, 409, 422),
)
def update_wallet(wallet_id: int, body: WalletUpdate, trip: TripDep, session: SessionDep):
    """Update a wallet's fields."""
    wallet = require_in_trip(session, Wallet, wallet_id, trip.id, "wallet")
    wallet = run_field(
        "name",
        roster.update_wallet,
        session,
        wallet,
        body.name,
        body.tracked,
        body.is_default,
        body.sort_order,
    )
    return {"wallet": WalletOut.model_validate(wallet)}


@router.delete(
    "/trips/{slug}/wallets/{wallet_id}", status_code=204, responses=error_responses(404, 409)
)
def delete_wallet(wallet_id: int, trip: TripDep, session: SessionDep):
    """Delete a wallet from a trip."""
    wallet = require_in_trip(session, Wallet, wallet_id, trip.id, "wallet")
    run_field("id", roster.delete_wallet, session, wallet)
    return Response(status_code=204)
