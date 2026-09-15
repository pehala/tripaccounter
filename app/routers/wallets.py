"""Wallet routes: CRUD, and the per-currency balances report on the same collection."""

from fastapi import APIRouter, Response

from app.deps import SessionDep, TripDep
from app.models.roster import Person
from app.models.wallets import Wallet
from app.schemas import (
    WalletCreate,
    WalletEnvelope,
    WalletListEnvelope,
    WalletOut,
    WalletUpdate,
    error_responses,
)
from app.services import roster
from app.services.errors.api import NotFoundError, ValidationError, run_field
from app.services.errors.fields import NotInTripError
from app.services.wallets import wallet_balances

router = APIRouter(tags=["wallets"])


def _get_wallet(trip, wallet_id: int, session: SessionDep) -> Wallet:
    wallet = session.get(Wallet, wallet_id)
    if wallet is None or wallet.trip_id != trip.id:
        raise NotFoundError("wallet")
    return wallet


def _get_person(trip, person_id: int, session: SessionDep) -> Person | None:
    person = session.get(Person, person_id)
    if person is None or person.trip_id != trip.id:
        return None
    return person


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
    person = _get_person(trip, body.person_id, session)
    if person is None:
        raise ValidationError({"person_id": NotInTripError()})
    wallet = run_field("name", roster.create_wallet, session, trip, person, body.name, body.tracked)
    return {"wallet": WalletOut.from_wallet(wallet)}


@router.patch(
    "/trips/{slug}/wallets/{wallet_id}",
    response_model=WalletEnvelope,
    responses=error_responses(400, 404, 409, 422),
)
def update_wallet(wallet_id: int, body: WalletUpdate, trip: TripDep, session: SessionDep):
    """Update a wallet's fields."""
    wallet = _get_wallet(trip, wallet_id, session)
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
    return {"wallet": WalletOut.from_wallet(wallet)}


@router.delete(
    "/trips/{slug}/wallets/{wallet_id}", status_code=204, responses=error_responses(404, 409)
)
def delete_wallet(wallet_id: int, trip: TripDep, session: SessionDep):
    """Delete a wallet from a trip."""
    wallet = _get_wallet(trip, wallet_id, session)
    run_field("id", roster.delete_wallet, session, wallet)
    return Response(status_code=204)
