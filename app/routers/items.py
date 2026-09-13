"""Line item routes: create, update, delete, and preview splits."""

from decimal import Decimal

from fastapi import APIRouter, Response
from sqlalchemy import func, select

from app.clock import ClockDep
from app.deps import SessionDep, TripDep
from app.models import ItemShare, LineItem, Person, TripCountry, TripCurrency, active_roster_ids
from app.schemas import (
    ITEM_LOAD_OPTIONS,
    DayCurrencyTotalOut,
    DayTotalOut,
    ItemEnvelope,
    ItemListEnvelope,
    ItemOut,
    ItemWrite,
    PreviewSplitOut,
    PreviewSplitRequest,
    error_responses,
)
from app.services import geo, splits
from app.services.errors import (
    FieldError,
    InactiveError,
    InvalidAmountError,
    NotFoundError,
    NotInTripError,
    RequiredError,
    TooLongError,
    ValidationError,
)
from app.services.labels import release_item_labels, set_item_labels
from app.services.money import AMOUNT_SCALE, to_hundredths, to_wire

router = APIRouter(tags=["items"])


def _get_item(trip, item_id: int, session: SessionDep) -> LineItem:
    item = session.get(LineItem, item_id, options=ITEM_LOAD_OPTIONS)
    if item is None or item.trip_id != trip.id:
        raise NotFoundError("item")
    return item


def _validate_name(name: str | None, *, required: bool) -> FieldError | None:
    if name is None:
        return RequiredError() if required else None
    if len(name.strip()) < 1:
        return RequiredError()
    if len(name) > 200:
        return TooLongError(max=200)
    return None


def _validate_refs(  # noqa: PLR0913, PLR0912
    trip, currency_id, payer_id, country_id, session, *, creating: bool
) -> dict:
    fields: dict[str, FieldError] = {}

    if currency_id is None:
        if creating:
            fields["currency_id"] = RequiredError()
    else:
        currency = session.get(TripCurrency, currency_id)
        if currency is None or currency.trip_id != trip.id:
            fields["currency_id"] = NotInTripError()

    if payer_id is None:
        if creating:
            fields["payer_id"] = RequiredError()
    else:
        payer = session.get(Person, payer_id)
        if payer is None or payer.trip_id != trip.id:
            fields["payer_id"] = NotInTripError()
        elif not payer.active:
            fields["payer_id"] = InactiveError()

    if country_id is None:
        if creating:
            fields["country_id"] = RequiredError()
    else:
        country = session.get(TripCountry, country_id)
        if country is None or country.trip_id != trip.id:
            fields["country_id"] = NotInTripError()

    return fields


def _map_url_str(value) -> str | None:
    """Convert `ItemWrite.map_url`, a pydantic `HttpUrl | None`, to a plain string.

    DB storage and `geo.parse` both want a plain string.
    """
    return str(value) if value is not None else None


def _resolve_map_coordinates(map_url, lat, lon) -> tuple[str | None, str | None]:
    if lat is not None or lon is not None:
        return lat, lon
    if map_url:
        parsed = geo.parse(map_url)
        if parsed:
            return parsed
    return None, None


def _decimal_amount(amount_minor: int) -> Decimal:
    return Decimal(amount_minor) / AMOUNT_SCALE


def _default_shares_for_mode(item: LineItem, mode: str) -> list[dict]:
    rows = []
    for share in item.shares:
        row: dict = {"person_id": share.person_id}
        if mode == "shares":
            row["weight"] = splits.format_weight(share.weight_scaled)
        elif mode == "exact":
            row["amount"] = to_wire(share.owed_minor or 0, AMOUNT_SCALE)
        rows.append(row)
    return rows


def _persist_shares(session: SessionDep, item: LineItem, rows: list[dict]) -> None:
    for share in list(item.shares):
        session.delete(share)
    session.flush()
    for row in rows:
        session.add(
            ItemShare(
                item_id=item.id,
                person_id=row["person_id"],
                weight_scaled=row["weight_scaled"],
                owed_minor=row["owed_minor"],
                split_mode_exact=row["exact"],
            )
        )


@router.post(
    "/trips/{slug}/items/preview-split",
    response_model=PreviewSplitOut,
    responses=error_responses(400, 404, 422),
)
def preview_split(body: PreviewSplitRequest, trip: TripDep, session: SessionDep):
    """Preview how an amount would split without creating an item."""
    currency = session.get(TripCurrency, body.currency_id)
    if currency is None or currency.trip_id != trip.id:
        raise ValidationError({"currency_id": NotInTripError()})

    valid_person_ids = [p.id for p in trip.people]
    shares_in = body.shares
    if shares_in is None:
        shares_in = [{"person_id": pid} for pid in active_roster_ids(trip.people)]

    try:
        rows = splits.build_shares(
            body.split_mode, shares_in, valid_person_ids, body.amount, currency.code
        )
    except FieldError as err:
        raise ValidationError({"shares": err}) from err

    amount_minor = to_hundredths(body.amount)
    resolved = splits.resolve_shares_wire(active_roster_ids(trip.people), rows, amount_minor)
    return {
        "split": {"mode": body.split_mode, "shares": resolved},
        "total": to_wire(amount_minor, AMOUNT_SCALE),
    }


@router.get("/trips/{slug}/items", response_model=ItemListEnvelope, responses=error_responses(404))
def list_items(trip: TripDep, session: SessionDep):
    """List items for a trip."""
    items = (
        session.execute(
            select(LineItem)
            .where(LineItem.trip_id == trip.id)
            .options(*ITEM_LOAD_OPTIONS)
            .order_by(LineItem.occurred_at.desc(), LineItem.id.desc())
        )
        .scalars()
        .all()
    )
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

    return {
        "items": [ItemOut.from_item(item, roster_ids) for item in items],
        "day_totals": [DayTotalOut(date=day, totals=totals) for day, totals in day_totals.items()],
    }


@router.get(
    "/trips/{slug}/items/{item_id}", response_model=ItemEnvelope, responses=error_responses(404)
)
def get_item(item_id: int, trip: TripDep, session: SessionDep):
    """Get a single item by id."""
    item = _get_item(trip, item_id, session)
    return {"item": ItemOut.from_item(item, active_roster_ids(trip.people))}


@router.post(
    "/trips/{slug}/items",
    status_code=201,
    response_model=ItemEnvelope,
    responses=error_responses(400, 404, 422),
)
def create_item(body: ItemWrite, trip: TripDep, session: SessionDep, clock: ClockDep):
    """Create a new item on a trip."""
    fields: dict[str, FieldError] = {}
    name_error = _validate_name(body.name, required=True)
    if name_error:
        fields["name"] = name_error
    if body.amount is None:
        fields["amount"] = InvalidAmountError()
    fields.update(
        _validate_refs(
            trip, body.currency_id, body.payer_id, body.country_id, session, creating=True
        )
    )
    if fields:
        raise ValidationError(fields)

    currency = session.get(TripCurrency, body.currency_id)
    mode = body.split_mode or "equal"
    valid_person_ids = [p.id for p in trip.people]
    shares_in = body.shares
    if shares_in is None:
        shares_in = [{"person_id": pid} for pid in active_roster_ids(trip.people)]

    try:
        rows = splits.build_shares(mode, shares_in, valid_person_ids, body.amount, currency.code)
    except FieldError as err:
        raise ValidationError({"shares": err}) from err

    map_url = _map_url_str(body.map_url)
    lat, lon = _resolve_map_coordinates(map_url, body.lat, body.lon)

    item = LineItem(
        trip_id=trip.id,
        name=body.name,
        note=body.note,
        occurred_at=body.occurred_at or clock,
        currency_id=currency.id,
        amount_minor=to_hundredths(body.amount),
        payer_id=body.payer_id,
        country_id=body.country_id,
        map_url=map_url,
        lat=lat,
        lon=lon,
        split_mode=mode,
    )
    session.add(item)
    session.flush()

    for row in rows:
        session.add(
            ItemShare(
                item_id=item.id,
                person_id=row["person_id"],
                weight_scaled=row["weight_scaled"],
                owed_minor=row["owed_minor"],
                split_mode_exact=row["exact"],
            )
        )
    set_item_labels(session, item, body.labels or [])

    session.flush()
    session.refresh(item)
    return {"item": ItemOut.from_item(item, active_roster_ids(trip.people))}


@router.patch(
    "/trips/{slug}/items/{item_id}",
    response_model=ItemEnvelope,
    responses=error_responses(400, 404, 422),
)
def update_item(item_id: int, body: ItemWrite, trip: TripDep, session: SessionDep):  # noqa: PLR0912
    """Update an item's fields, and its shares if the split changed."""
    item = _get_item(trip, item_id, session)

    fields: dict[str, FieldError] = {}
    name_error = _validate_name(body.name, required=False)
    if name_error:
        fields["name"] = name_error
    fields.update(
        _validate_refs(
            trip, body.currency_id, body.payer_id, body.country_id, session, creating=False
        )
    )
    if fields:
        raise ValidationError(fields)

    if body.name is not None:
        item.name = body.name
    if body.note is not None:
        item.note = body.note
    if body.currency_id is not None:
        item.currency_id = body.currency_id
    if body.payer_id is not None:
        item.payer_id = body.payer_id
    if body.country_id is not None:
        item.country_id = body.country_id
    if body.occurred_at is not None:
        item.occurred_at = body.occurred_at
    map_url = _map_url_str(body.map_url)
    if map_url is not None:
        item.map_url = map_url

    if body.lat is not None or body.lon is not None:
        item.lat, item.lon = body.lat, body.lon
    elif map_url is not None:
        parsed = geo.parse(map_url)
        if parsed:
            item.lat, item.lon = parsed

    if body.amount is not None:
        item.amount_minor = to_hundredths(body.amount)

    new_mode = body.split_mode or item.split_mode
    if body.shares is not None or body.split_mode is not None or body.amount is not None:
        currency = session.get(TripCurrency, item.currency_id)
        valid_person_ids = [p.id for p in trip.people]
        current_amount = _decimal_amount(item.amount_minor)
        shares_in = (
            body.shares if body.shares is not None else _default_shares_for_mode(item, new_mode)
        )
        try:
            rows = splits.build_shares(
                new_mode, shares_in, valid_person_ids, current_amount, currency.code
            )
        except FieldError as err:
            raise ValidationError({"shares": err}) from err
        _persist_shares(session, item, rows)
        item.split_mode = new_mode

    if body.labels is not None:
        set_item_labels(session, item, body.labels)

    session.flush()
    session.refresh(item)
    return {"item": ItemOut.from_item(item, active_roster_ids(trip.people))}


@router.delete("/trips/{slug}/items/{item_id}", status_code=204, responses=error_responses(404))
def delete_item(item_id: int, trip: TripDep, session: SessionDep):
    """Delete an item from a trip."""
    item = _get_item(trip, item_id, session)
    release_item_labels(item)
    session.delete(item)
    session.flush()
    return Response(status_code=204)
