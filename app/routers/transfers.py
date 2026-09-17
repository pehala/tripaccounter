"""Wallet transfer routes: create, list, update, delete."""

from fastapi import APIRouter, Response

from app.clock import ClockDep
from app.deps import SessionDep, TripDep
from app.models.wallets import WalletTransfer
from app.schemas.envelopes import TransferEnvelope, TransferListEnvelope
from app.schemas.error_shapes import error_responses
from app.schemas.requests import TransferWrite
from app.schemas.responses import TRANSFER_LOAD_OPTIONS, TransferOut
from app.services import queries
from app.services import transfers as transfer_service
from app.services.errors.api import ValidationError
from app.services.scope import require_in_trip

router = APIRouter(tags=["transfers"])


@router.get(
    "/trips/{slug}/transfers", response_model=TransferListEnvelope, responses=error_responses(404)
)
def list_transfers(trip: TripDep, session: SessionDep):
    """List a trip's wallet transfers, newest first."""
    rows = session.execute(queries.transfers_for_trip(trip.id)).scalars().all()
    return {"transfers": [TransferOut.from_transfer(row) for row in rows]}


@router.post(
    "/trips/{slug}/transfers",
    status_code=201,
    response_model=TransferEnvelope,
    responses=error_responses(400, 404, 422),
)
def create_transfer(body: TransferWrite, trip: TripDep, session: SessionDep, clock: ClockDep):
    """Create a new transfer between two wallets."""
    resolved = transfer_service.resolve_write(body, None)
    fields = transfer_service.validate(session, trip, resolved, creating=True)
    if fields:
        raise ValidationError(fields)

    transfer = WalletTransfer(trip_id=trip.id)
    transfer_service.apply_write(transfer, resolved, body.occurred_at or clock, body.note)
    session.add(transfer)
    session.flush()
    session.refresh(transfer)
    return {"transfer": TransferOut.from_transfer(transfer)}


@router.get(
    "/trips/{slug}/transfers/{transfer_id}",
    response_model=TransferEnvelope,
    responses=error_responses(404),
)
def get_transfer(transfer_id: int, trip: TripDep, session: SessionDep):
    """Get a single transfer by id."""
    transfer = require_in_trip(
        session, WalletTransfer, transfer_id, trip.id, "transfer", options=TRANSFER_LOAD_OPTIONS
    )
    return {"transfer": TransferOut.from_transfer(transfer)}


@router.patch(
    "/trips/{slug}/transfers/{transfer_id}",
    response_model=TransferEnvelope,
    responses=error_responses(400, 404, 422),
)
def update_transfer(transfer_id: int, body: TransferWrite, trip: TripDep, session: SessionDep):
    """Update a transfer's fields."""
    transfer = require_in_trip(
        session, WalletTransfer, transfer_id, trip.id, "transfer", options=TRANSFER_LOAD_OPTIONS
    )
    resolved = transfer_service.resolve_write(body, transfer)
    fields = transfer_service.validate(session, trip, resolved, creating=False)
    if fields:
        raise ValidationError(fields)

    transfer_service.apply_write(transfer, resolved, body.occurred_at, body.note)
    session.flush()
    session.refresh(transfer)
    return {"transfer": TransferOut.from_transfer(transfer)}


@router.delete(
    "/trips/{slug}/transfers/{transfer_id}", status_code=204, responses=error_responses(404)
)
def delete_transfer(transfer_id: int, trip: TripDep, session: SessionDep):
    """Delete a transfer from a trip."""
    transfer = require_in_trip(
        session, WalletTransfer, transfer_id, trip.id, "transfer", options=TRANSFER_LOAD_OPTIONS
    )
    session.delete(transfer)
    session.flush()
    return Response(status_code=204)
