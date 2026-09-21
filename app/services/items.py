"""Line item writes: ref validation, the wallet/coordinate/split-mode rules, and share rows."""

from decimal import Decimal

from sqlalchemy.orm import Session

from app.models.items import ItemShare, LineItem
from app.models.roster import Person, TripCountry, TripCurrency, active_roster_ids
from app.models.trip import Trip
from app.models.wallets import Wallet
from app.schemas.requests import ItemWrite
from app.services import geo, roster, splits
from app.services.errors.base import FieldError
from app.services.errors.fields import (
    InactiveError,
    InvalidAmountError,
    RequiredError,
    TooLongError,
    WalletOwnerMismatchError,
)
from app.services.money import AMOUNT_SCALE, to_hundredths
from app.services.scope import in_trip, ref_error


def validate_name(name: str | None, *, required: bool) -> FieldError | None:
    """Return the error a write's `name` earns, or None when it is acceptable."""
    if name is None:
        return RequiredError() if required else None
    if len(name.strip()) < 1:
        return RequiredError()
    if len(name) > 200:
        return TooLongError(max=200)
    return None


def validate_write(
    session: Session, trip: Trip, body: ItemWrite, *, creating: bool
) -> dict[str, FieldError]:
    """Validate a write's name, amount and references; return its field errors."""
    fields: dict[str, FieldError] = {}

    name_error = validate_name(body.name, required=creating)
    if name_error:
        fields["name"] = name_error
    if creating and body.amount is None:
        fields["amount"] = InvalidAmountError()

    for field, model, required in (
        ("currency_id", TripCurrency, creating),
        ("payer_id", Person, creating),
        ("country_id", TripCountry, creating),
        ("wallet_id", Wallet, False),
    ):
        error = ref_error(session, model, getattr(body, field), trip.id, required=required)
        if error:
            fields[field] = error

    payer = in_trip(session, Person, body.payer_id, trip.id)
    if payer is not None and not payer.active:
        fields["payer_id"] = InactiveError()

    return fields


def resolve_wallet_id(session: Session, wallet_id: int | None, payer_id: int) -> int:
    """Resolve the wallet an item write settles on: the one given, or the payer's default.

    Raises `wallet_owner_mismatch` if the given wallet belongs to someone else.
    Only called once `validate_write` has already confirmed `wallet_id` (if any)
    exists in this trip and `payer_id` names an active person in it.
    """
    if wallet_id is None:
        return roster.default_wallet(session, payer_id).id
    wallet = session.get(Wallet, wallet_id)
    if wallet.person_id != payer_id:
        raise WalletOwnerMismatchError()
    return wallet.id


def rewrite_wallet(session: Session, item: LineItem, body: ItemWrite) -> None:
    """Re-resolve an item's wallet when a write changes the wallet or the payer.

    Raises `FieldError`.
    """
    if body.wallet_id is None and body.payer_id is None:
        return
    payer_id = body.payer_id if body.payer_id is not None else item.payer_id
    item.wallet_id = resolve_wallet_id(session, body.wallet_id, payer_id)


def resolve_coordinates(
    map_url: str | None, lat: str | None, lon: str | None
) -> tuple[str | None, str | None] | None:
    """Return the coordinates a write settles on: the pair given, else the pair `map_url` carries.

    None when the write supplies neither.
    """
    if lat is not None or lon is not None:
        return lat, lon
    if map_url:
        return geo.parse(map_url)
    return None


def apply_write(item: LineItem, body: ItemWrite) -> None:
    """Write the fields a body supplies onto an item, leaving the omitted ones as they are."""
    if body.name is not None:
        item.name = body.name
    if body.note is not None:
        item.note = body.note
    if body.city is not None:
        item.city = body.city
    if body.currency_id is not None:
        item.currency_id = body.currency_id
    if body.payer_id is not None:
        item.payer_id = body.payer_id
    if body.country_id is not None:
        item.country_id = body.country_id
    if body.occurred_at is not None:
        item.occurred_at = body.occurred_at
    if body.amount is not None:
        item.amount_minor = to_hundredths(body.amount)

    # DB storage and geo.parse both want a plain string, not pydantic's HttpUrl.
    map_url = str(body.map_url) if body.map_url is not None else None
    if map_url is not None:
        item.map_url = map_url
    coordinates = resolve_coordinates(map_url, body.lat, body.lon)
    if coordinates:
        item.lat, item.lon = coordinates


def split_mode(body: ItemWrite, item: LineItem | None) -> str:
    """Return the split mode a write settles on: the one given, else the item's, else `equal`."""
    if body.split_mode is not None:
        return body.split_mode
    return item.split_mode if item is not None else "equal"


def default_shares(item: LineItem, mode: str) -> list[dict]:
    """Re-express an item's saved shares as write rows in `mode`, for a write that omits them."""
    rows = []
    for share in item.shares:
        row: dict = {"person_id": share.person_id}
        if mode == "shares":
            row["weight"] = splits.format_weight(share.weight_scaled)
        elif mode == "exact":
            row["amount"] = splits.format_amount(share.owed_minor or 0)
        rows.append(row)
    return rows


def build_shares(
    trip: Trip, mode: str, shares_in: list[dict] | None, amount: Decimal, currency_code: str
) -> list[dict]:
    """Validate a write's shares against the trip roster and return the rows to persist.

    An omitted `shares` splits over everyone active. Raises `FieldError`.
    """
    if shares_in is None:
        shares_in = [{"person_id": pid} for pid in active_roster_ids(trip.people)]
    return splits.build_shares(mode, shares_in, [p.id for p in trip.people], amount, currency_code)


def persist_shares(session: Session, item: LineItem, rows: list[dict]) -> None:
    """Replace an item's share rows with `rows`."""
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


def rewrite_shares(session: Session, trip: Trip, item: LineItem, body: ItemWrite) -> None:
    """Rebuild an item's shares when a write changes the shares, the mode or the amount.

    Reads the amount off `item`, so it runs after `apply_write`. Raises `FieldError`.
    """
    if body.shares is None and body.split_mode is None and body.amount is None:
        return
    mode = split_mode(body, item)
    currency = session.get(TripCurrency, item.currency_id)
    rows = build_shares(
        trip,
        mode,
        body.shares if body.shares is not None else default_shares(item, mode),
        Decimal(item.amount_minor) / AMOUNT_SCALE,
        currency.code,
    )
    persist_shares(session, item, rows)
    item.split_mode = mode
