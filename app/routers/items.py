"""Line item routes: create, update, delete, and preview splits."""

from fastapi import APIRouter, Response
from sqlalchemy import func, select

from app.clock import ClockDep
from app.deps import SessionDep, TripDep
from app.models.items import LineItem
from app.models.roster import TripCurrency, active_roster_ids
from app.schemas.envelopes import DayCurrencyTotalOut, DayTotalOut, ItemEnvelope, ItemListEnvelope
from app.schemas.error_shapes import error_responses
from app.schemas.requests import ItemWrite, PreviewSplitRequest
from app.schemas.responses import (
    ITEM_LOAD_OPTIONS,
    ItemOut,
    PreviewSplitOut,
    TransferOut,
)
from app.services import items as item_service
from app.services import queries, splits
from app.services.errors.api import ValidationError, field_errors
from app.services.errors.fields import NotInTripError
from app.services.labels import release_item_labels, set_item_labels
from app.services.money import AMOUNT_SCALE, to_hundredths, to_wire
from app.services.scope import in_trip, require_in_trip

router = APIRouter(tags=["items"])


@router.post(
    "/trips/{slug}/items/preview-split",
    response_model=PreviewSplitOut,
    responses=error_responses(400, 404, 422),
)
def preview_split(body: PreviewSplitRequest, trip: TripDep, session: SessionDep):
    """Preview how an amount would split without creating an item."""
    currency = in_trip(session, TripCurrency, body.currency_id, trip.id)
    if currency is None:
        raise ValidationError({"currency_id": NotInTripError()})

    with field_errors("shares"):
        rows = item_service.build_shares(
            trip, body.split_mode, body.shares, body.amount, currency.code
        )

    amount_minor = to_hundredths(body.amount)
    resolved = splits.resolve_shares_wire(active_roster_ids(trip.people), rows, amount_minor)
    return {
        "split": {"mode": body.split_mode, "shares": resolved},
        "total": to_wire(amount_minor, AMOUNT_SCALE),
    }


@router.get("/trips/{slug}/items", response_model=ItemListEnvelope, responses=error_responses(404))
def list_items(trip: TripDep, session: SessionDep):
    """List items for a trip."""
    items = session.execute(queries.items_for_trip(trip.id)).scalars().all()
    roster_ids = active_roster_ids(trip.people)

    day_rows = session.execute(
        select(
            func.date(LineItem.occurred_at),
            TripCurrency.code,
            TripCurrency.id,
            func.sum(LineItem.amount_minor),
        )
        .select_from(LineItem)
        .join(TripCurrency, TripCurrency.id == LineItem.currency_id)
        .where(LineItem.trip_id == trip.id)
        .group_by(func.date(LineItem.occurred_at), TripCurrency.id)
        .order_by(func.date(LineItem.occurred_at).desc(), TripCurrency.sort_order)
    ).all()
    day_totals: dict[str, list[DayCurrencyTotalOut]] = {}
    for day, code, currency_id, amount_minor in day_rows:
        day_totals.setdefault(day, []).append(
            DayCurrencyTotalOut(
                currency_code=code,
                currency_id=currency_id,
                amount=to_wire(amount_minor, AMOUNT_SCALE),
            )
        )

    transfer_rows = session.execute(queries.transfers_for_trip(trip.id)).scalars().all()

    return {
        "items": [ItemOut.from_item(item, roster_ids) for item in items],
        "day_totals": [DayTotalOut(date=day, totals=totals) for day, totals in day_totals.items()],
        "transfers": [TransferOut.from_transfer(row) for row in transfer_rows],
    }


@router.get(
    "/trips/{slug}/items/{item_id}", response_model=ItemEnvelope, responses=error_responses(404)
)
def get_item(item_id: int, trip: TripDep, session: SessionDep):
    """Get a single item by id."""
    item = require_in_trip(session, LineItem, item_id, trip.id, "item", options=ITEM_LOAD_OPTIONS)
    return {"item": ItemOut.from_item(item, active_roster_ids(trip.people))}


@router.post(
    "/trips/{slug}/items",
    status_code=201,
    response_model=ItemEnvelope,
    responses=error_responses(400, 404, 422),
)
def create_item(body: ItemWrite, trip: TripDep, session: SessionDep, clock: ClockDep):
    """Create a new item on a trip."""
    fields = item_service.validate_write(session, trip, body, creating=True)
    if fields:
        raise ValidationError(fields)

    with field_errors("wallet_id"):
        wallet_id = item_service.resolve_wallet_id(session, body.wallet_id, body.payer_id)
    mode = item_service.split_mode(body, None)
    currency = session.get(TripCurrency, body.currency_id)
    with field_errors("shares"):
        rows = item_service.build_shares(trip, mode, body.shares, body.amount, currency.code)

    item = LineItem(trip_id=trip.id, occurred_at=clock, wallet_id=wallet_id, split_mode=mode)
    item_service.apply_write(item, body)
    session.add(item)
    session.flush()

    item_service.persist_shares(session, item, rows)
    set_item_labels(session, item, body.labels or [])

    session.flush()
    session.refresh(item)
    return {"item": ItemOut.from_item(item, active_roster_ids(trip.people))}


@router.patch(
    "/trips/{slug}/items/{item_id}",
    response_model=ItemEnvelope,
    responses=error_responses(400, 404, 422),
)
def update_item(item_id: int, body: ItemWrite, trip: TripDep, session: SessionDep):
    """Update an item's fields, and its shares if the split changed."""
    item = require_in_trip(session, LineItem, item_id, trip.id, "item", options=ITEM_LOAD_OPTIONS)

    fields = item_service.validate_write(session, trip, body, creating=False)
    if fields:
        raise ValidationError(fields)

    with field_errors("wallet_id"):
        item_service.rewrite_wallet(session, item, body)
    item_service.apply_write(item, body)
    with field_errors("shares"):
        item_service.rewrite_shares(session, trip, item, body)

    if body.labels is not None:
        set_item_labels(session, item, body.labels)

    session.flush()
    session.refresh(item)
    return {"item": ItemOut.from_item(item, active_roster_ids(trip.people))}


@router.delete("/trips/{slug}/items/{item_id}", status_code=204, responses=error_responses(404))
def delete_item(item_id: int, trip: TripDep, session: SessionDep):
    """Delete an item from a trip."""
    item = require_in_trip(session, LineItem, item_id, trip.id, "item", options=ITEM_LOAD_OPTIONS)
    release_item_labels(item)
    session.delete(item)
    session.flush()
    return Response(status_code=204)
