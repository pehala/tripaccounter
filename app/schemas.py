"""Define pydantic schemas for the Trip Accounter API request and response bodies.

These classes are the shape half of the contract: `/openapi.json` is generated
from them, `/docs` renders it, and the committed `openapi.json` at the repo root
is a snapshot of that generation (`make openapi`). The meaning half — what each
number stands for, how a split resolves, which rule yields which code — is
`design/API.md`.
"""

import re
from datetime import UTC, datetime
from decimal import Decimal
from typing import Annotated, Any, Literal

from pydantic import (
    AfterValidator,
    BaseModel,
    BeforeValidator,
    ConfigDict,
    HttpUrl,
    model_validator,
)
from pydantic_core import PydanticCustomError
from sqlalchemy.orm import joinedload, selectinload

from app.models.items import LineItem
from app.models.labels import Label
from app.models.roster import Person, TripCountry, TripCurrency
from app.models.trip import Trip
from app.models.wallets import Wallet, WalletTransfer
from app.services.countries import flag_from_code
from app.services.money import AMOUNT_SCALE, to_wire
from app.services.parsing import ParseError, parse_amount, parse_coordinate, parse_weight
from app.services.splits import format_weight, resolve_shares_wire


def _iso_z(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def _as_pydantic_error(err: ParseError) -> PydanticCustomError:
    return PydanticCustomError(err.code, err.code, err.params)


def _label_whitespace_error(value: object) -> PydanticCustomError:
    return PydanticCustomError("label_whitespace", "label_whitespace", {"value": value})


def _too_long_error() -> PydanticCustomError:
    return PydanticCustomError("too_long", "too_long", {"max": 40})


def _invalid_coordinates_error() -> PydanticCustomError:
    return PydanticCustomError("invalid_coordinates", "invalid_coordinates")


def _parse_amount(v: object) -> Decimal:
    try:
        return parse_amount(v)
    except ParseError as err:
        raise _as_pydantic_error(err) from err


def _parse_weight(v: object) -> Decimal:
    try:
        return parse_weight(v)
    except ParseError as err:
        raise _as_pydantic_error(err) from err


def _parse_lat(v: object) -> str | None:
    if v is None:
        return None
    try:
        parse_coordinate(v, low=Decimal(-90), high=Decimal(90))
    except ParseError as err:
        raise _as_pydantic_error(err) from err
    return v


def _parse_lon(v: object) -> str | None:
    if v is None:
        return None
    try:
        parse_coordinate(v, low=Decimal(-180), high=Decimal(180))
    except ParseError as err:
        raise _as_pydantic_error(err) from err
    return v


def _normalize_to_utc(dt: datetime | None) -> datetime | None:
    """occurred_at is always stored and returned tz-aware, in UTC (API.md §1 "Time").

    pydantic's own datetime parsing already produced a `datetime`
    from the ISO string, aware or not; a naive one is assumed to already be
    UTC (no ambient server timezone ever enters this), an aware one is
    converted. Either way the result carries an explicit `tzinfo`.
    """
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


def _parse_label(v: object) -> str:
    if not isinstance(v, str):
        raise _label_whitespace_error(v)
    stripped = v.strip()
    if len(stripped) < 1 or len(stripped) > 40:
        raise _too_long_error()
    if re.search(r"\s", stripped):
        raise _label_whitespace_error(v)
    return stripped


Amount = Annotated[Decimal, BeforeValidator(_parse_amount)]
Weight = Annotated[Decimal, BeforeValidator(_parse_weight)]
LatStr = Annotated[str | None, BeforeValidator(_parse_lat)]
LonStr = Annotated[str | None, BeforeValidator(_parse_lon)]
OccurredAt = Annotated[datetime | None, AfterValidator(_normalize_to_utc)]
LabelToken = Annotated[str, BeforeValidator(_parse_label)]
# HttpUrl normalizes (trailing slash, host case, ...); map_url isn't required
# to survive a round trip byte-for-byte, only to be a genuine absolute
# http(s) URL (API.md §4 `invalid_url`).
MapUrl = HttpUrl | None


class Strict(BaseModel):
    """Base model that rejects unknown fields."""

    model_config = ConfigDict(extra="forbid")


# ---- Trip roster writes -----------------------------------------------------


class PersonCreate(Strict):
    """Request body for creating a person on a trip."""

    name: str
    default_weight: Weight | None = None
    color: str | None = None


class PersonUpdate(Strict):
    """Request body for partially updating a person."""

    name: str | None = None
    default_weight: Weight | None = None
    active: bool | None = None
    sort_order: int | None = None


class CurrencyCreate(Strict):
    """Request body for creating a trip currency."""

    code: str
    symbol: str | None = None
    is_primary: bool | None = None


class CurrencyUpdate(Strict):
    """Request body for partially updating a trip currency."""

    symbol: str | None = None
    is_primary: bool | None = None
    sort_order: int | None = None


class CountryCreate(Strict):
    """Request body for creating a trip country."""

    name: str
    code: str | None = None
    is_default: bool | None = None


class CountryUpdate(Strict):
    """Request body for partially updating a trip country."""

    name: str | None = None
    code: str | None = None
    is_default: bool | None = None
    sort_order: int | None = None


class LabelCreate(Strict):
    """Request body for creating a label."""

    name: LabelToken


class LabelUpdate(Strict):
    """Request body for partially updating a label."""

    name: LabelToken | None = None


class WalletCreate(Strict):
    """Request body for creating a wallet."""

    person_id: int
    name: str
    tracked: bool | None = None


class WalletUpdate(Strict):
    """Request body for partially updating a wallet."""

    name: str | None = None
    tracked: bool | None = None
    is_default: bool | None = None
    sort_order: int | None = None


class TripCreate(Strict):
    """Request body for creating a trip with its roster, currencies, and countries."""

    name: str
    start_date: str | None = None
    end_date: str | None = None
    note: str | None = None
    people: list[PersonCreate]
    currencies: list[CurrencyCreate]
    countries: list[CountryCreate]
    labels: list[LabelToken] | None = None


class TripUpdate(Strict):
    """Request body for partially updating a trip."""

    name: str | None = None
    start_date: str | None = None
    end_date: str | None = None
    note: str | None = None
    archived: bool | None = None


# ---- Items -------------------------------------------------------------------
# `shares` rows are validated in app/services/splits.py, not here: their shape
# (person_id [+ weight | + amount]) depends on the sibling `split_mode` field,
# which pydantic cannot express structurally without a discriminated union
# keyed on a field of a different model - so ItemWrite carries `shares` as a
# raw list[dict] and splits.build_shares() does the real validation.


class ItemWrite(Strict):
    """Request body for creating or updating a line item."""

    name: str | None = None
    note: str | None = None
    amount: Amount | None = None
    currency_id: int | None = None
    payer_id: int | None = None
    country_id: int | None = None
    wallet_id: int | None = None
    occurred_at: OccurredAt = None
    labels: list[LabelToken] | None = None
    map_url: MapUrl = None
    lat: LatStr = None
    lon: LonStr = None
    split_mode: Literal["equal", "shares", "exact"] | None = None
    shares: list[dict] | None = None

    @model_validator(mode="after")
    def _lat_lon_paired(self):
        if (self.lat is None) != (self.lon is None):
            raise _invalid_coordinates_error()
        return self


# ---- Transfers -----------------------------------------------------------------
# One write shape for create and update, like ItemWrite: every field optional
# here, required-ness for a create and the plain/exchange mirroring rule for
# `to_amount`/`to_currency_id` both live in app/services/transfers.py, since
# the mirroring rule reads differently depending on whether a value is being
# created fresh or is defaulting from a row already on file.


class TransferWrite(Strict):
    """Request body for creating or updating a wallet transfer."""

    from_wallet_id: int | None = None
    from_amount: Amount | None = None
    from_currency_id: int | None = None
    to_wallet_id: int | None = None
    to_amount: Amount | None = None
    to_currency_id: int | None = None
    occurred_at: OccurredAt = None
    note: str | None = None


class PreviewSplitRequest(BaseModel):
    """Takes the same body an item write does; only these fields are read.

    (API.md §3) — extra fields (name, payer_id, ...) are ignored, not rejected.
    """

    model_config = ConfigDict(extra="ignore")

    amount: Amount
    currency_id: int
    split_mode: Literal["equal", "shares", "exact"] = "equal"
    shares: list[dict] | None = None


# ---- Wire (response) shapes ---------------------------------------------------

Number = float | int


class PersonOut(BaseModel):
    """Wire representation of a person on a trip."""

    id: int
    name: str
    initial: str
    color: str
    default_weight: str
    sort_order: int
    active: bool

    @classmethod
    def from_person(cls, person: Person) -> "PersonOut":
        """Build a PersonOut from a Person model instance."""
        return cls(
            id=person.id,
            name=person.name,
            initial=person.name[:1].upper(),
            color=person.color,
            default_weight=format_weight(person.default_weight_scaled),
            sort_order=person.sort_order,
            active=person.active,
        )


class WalletOut(BaseModel):
    """Wire representation of a wallet, roster form: no balances."""

    id: int
    person_id: int
    name: str
    tracked: bool
    is_default: bool
    sort_order: int

    @classmethod
    def from_wallet(cls, wallet: Wallet) -> "WalletOut":
        """Build a WalletOut from a Wallet model instance."""
        return cls(
            id=wallet.id,
            person_id=wallet.person_id,
            name=wallet.name,
            tracked=wallet.tracked,
            is_default=wallet.is_default,
            sort_order=wallet.sort_order,
        )


class WalletBalanceOut(BaseModel):
    """Wire representation of one wallet's activity in one currency."""

    currency_code: str
    currency_id: int
    received: Number
    sent: Number
    spent: Number
    balance: Number


class WalletReportOut(WalletOut):
    """A wallet plus its per-currency balances - `[]` for an untracked wallet."""

    balances: list[WalletBalanceOut]


class CurrencyOut(BaseModel):
    """Wire representation of a trip currency."""

    id: int
    code: str
    symbol: str | None
    is_primary: bool
    sort_order: int

    @classmethod
    def from_currency(cls, currency: TripCurrency) -> "CurrencyOut":
        """Build a CurrencyOut from a TripCurrency model instance."""
        return cls(
            id=currency.id,
            code=currency.code,
            symbol=currency.symbol,
            is_primary=currency.is_primary,
            sort_order=currency.sort_order,
        )


class CountryOut(BaseModel):
    """Wire representation of a trip country."""

    id: int
    name: str
    code: str | None
    flag: str | None
    is_default: bool
    sort_order: int
    item_count: int

    @classmethod
    def from_country(cls, country: TripCountry, item_count: int) -> "CountryOut":
        """Build a CountryOut from a TripCountry model instance and its item count."""
        return cls(
            id=country.id,
            name=country.name,
            code=country.code,
            flag=flag_from_code(country.code),
            is_default=country.is_default,
            sort_order=country.sort_order,
            item_count=item_count,
        )


class LabelOut(BaseModel):
    """Wire representation of a label."""

    id: int
    name: str
    color: str
    use_count: int

    @classmethod
    def from_label(cls, label: Label) -> "LabelOut":
        """Build a LabelOut from a Label model instance."""
        return cls(id=label.id, name=label.name, color=label.color, use_count=label.use_count)


class TripOut(BaseModel):
    """Wire representation of a full trip, including its roster."""

    id: int
    slug: str
    name: str
    start_date: str | None
    end_date: str | None
    note: str | None
    archived: bool
    people: list[PersonOut]
    currencies: list[CurrencyOut]
    countries: list[CountryOut]
    wallets: list[WalletOut]
    created_at: str
    updated_at: str

    @classmethod
    def from_trip(cls, trip: Trip, country_item_counts: dict[int, int]) -> "TripOut":
        """Build a TripOut from a Trip model instance and its country item counts."""
        people = sorted(trip.people, key=lambda p: p.sort_order)
        return cls(
            id=trip.id,
            slug=trip.slug,
            name=trip.name,
            start_date=trip.start_date,
            end_date=trip.end_date,
            note=trip.note,
            archived=trip.archived,
            people=[PersonOut.from_person(p) for p in people],
            currencies=[CurrencyOut.from_currency(c) for c in trip.currencies],
            countries=[
                CountryOut.from_country(c, country_item_counts.get(c.id, 0)) for c in trip.countries
            ],
            wallets=[
                WalletOut.from_wallet(w)
                for p in people
                for w in sorted(p.wallets, key=lambda w: w.sort_order)
            ],
            created_at=_iso_z(trip.created_at),
            updated_at=_iso_z(trip.updated_at),
        )


class TripSummaryOut(BaseModel):
    """Wire representation of a trip summary for list views."""

    id: int
    slug: str
    name: str
    start_date: str | None
    end_date: str | None
    note: str | None
    archived: bool
    people_count: int
    item_count: int
    created_at: str
    updated_at: str

    @classmethod
    def from_trip(cls, trip: Trip, people_count: int, item_count: int) -> "TripSummaryOut":
        """Build a TripSummaryOut from a Trip model instance and its counts."""
        return cls(
            id=trip.id,
            slug=trip.slug,
            name=trip.name,
            start_date=trip.start_date,
            end_date=trip.end_date,
            note=trip.note,
            archived=trip.archived,
            people_count=people_count,
            item_count=item_count,
            created_at=_iso_z(trip.created_at),
            updated_at=_iso_z(trip.updated_at),
        )


class ShareOut(BaseModel):
    """Wire representation of one person's share of a split."""

    person_id: int
    weight: str | None
    owed: Number | None


class SplitOut(BaseModel):
    """Wire representation of an item's split across its shares."""

    mode: Literal["equal", "shares", "exact"]
    shares: list[ShareOut]


# `from_item` walks `shares`, `currency` and `label_rows` on every item it is handed,
# so a bare `select(LineItem)` pays three extra queries per row. Every query whose rows
# reach `from_item` carries these; `currency` is many-to-one, so it joins without
# multiplying rows and the callers need no `.unique()`.
ITEM_LOAD_OPTIONS = (
    selectinload(LineItem.shares),
    joinedload(LineItem.currency),
    selectinload(LineItem.label_rows),
)

# `from_transfer` reads both currencies' codes; both are many-to-one, so
# joining them doesn't multiply rows.
TRANSFER_LOAD_OPTIONS = (
    joinedload(WalletTransfer.from_currency),
    joinedload(WalletTransfer.to_currency),
)


class ItemOut(BaseModel):
    """Wire representation of a line item."""

    id: int
    name: str
    note: str | None
    occurred_at: str
    currency_code: str
    currency_id: int
    amount: Number
    payer_id: int
    country_id: int
    wallet_id: int
    labels: list[str]
    map_url: str | None
    lat: str | None
    lon: str | None
    split: SplitOut
    created_at: str
    updated_at: str

    @classmethod
    def from_item(cls, item: LineItem, roster_ids_sorted: list[int]) -> "ItemOut":
        """Build an ItemOut from a LineItem model instance and the trip roster."""
        rows = [
            {
                "person_id": share.person_id,
                "weight_scaled": share.weight_scaled,
                "owed_minor": share.owed_minor,
                "exact": share.split_mode_exact,
            }
            for share in item.shares
        ]
        resolved = resolve_shares_wire(roster_ids_sorted, rows, item.amount_minor)
        return cls(
            id=item.id,
            name=item.name,
            note=item.note,
            occurred_at=_iso_z(item.occurred_at),
            currency_code=item.currency.code,
            currency_id=item.currency_id,
            amount=to_wire(item.amount_minor, AMOUNT_SCALE),
            payer_id=item.payer_id,
            country_id=item.country_id,
            wallet_id=item.wallet_id,
            labels=sorted(label.name_norm for label in item.label_rows),
            map_url=item.map_url,
            lat=item.lat,
            lon=item.lon,
            split=SplitOut(mode=item.split_mode, shares=[ShareOut(**row) for row in resolved]),
            created_at=_iso_z(item.created_at),
            updated_at=_iso_z(item.updated_at),
        )


class TransferOut(BaseModel):
    """Wire representation of a wallet transfer: both typed sides, no rate."""

    id: int
    occurred_at: str
    from_wallet_id: int
    from_amount: Number
    from_currency_id: int
    from_currency_code: str
    to_wallet_id: int
    to_amount: Number
    to_currency_id: int
    to_currency_code: str
    note: str | None
    created_at: str
    updated_at: str

    @classmethod
    def from_transfer(cls, transfer: WalletTransfer) -> "TransferOut":
        """Build a TransferOut from a WalletTransfer model instance."""
        return cls(
            id=transfer.id,
            occurred_at=_iso_z(transfer.occurred_at),
            from_wallet_id=transfer.from_wallet_id,
            from_amount=to_wire(transfer.from_amount_minor, AMOUNT_SCALE),
            from_currency_id=transfer.from_currency_id,
            from_currency_code=transfer.from_currency.code,
            to_wallet_id=transfer.to_wallet_id,
            to_amount=to_wire(transfer.to_amount_minor, AMOUNT_SCALE),
            to_currency_id=transfer.to_currency_id,
            to_currency_code=transfer.to_currency.code,
            note=transfer.note,
            created_at=_iso_z(transfer.created_at),
            updated_at=_iso_z(transfer.updated_at),
        )


class BalancePersonOut(BaseModel):
    """Wire representation of one person's balance in a currency."""

    person_id: int
    paid: Number
    owed: Number
    sent: Number
    received: Number
    net: Number


class SuggestionOut(BaseModel):
    """Wire representation of a suggested settle-up payment."""

    from_person_id: int
    to_person_id: int
    amount: Number


class BalanceBlockOut(BaseModel):
    """Wire representation of balances and suggestions for one currency."""

    currency_code: str
    currency_id: int
    total_spent: Number
    people: list[BalancePersonOut]
    suggestions: list[SuggestionOut]


class StatsLabelOut(BaseModel):
    """Wire representation of spending totals for one label."""

    label: str | None
    amount: Number
    item_count: int


class StatsCountryOut(BaseModel):
    """Wire representation of spending totals for one country."""

    country_id: int
    amount: Number
    item_count: int


class StatsPersonOut(BaseModel):
    """Wire representation of spending totals for one person."""

    person_id: int
    amount: Number


class StatsDayOut(BaseModel):
    """Wire representation of spending totals for one day."""

    date: str
    amount: Number


class StatsBlockOut(BaseModel):
    """Wire representation of statistics for one currency."""

    currency_code: str
    currency_id: int
    total: Number
    by_label: list[StatsLabelOut]
    by_country: list[StatsCountryOut]
    by_person: list[StatsPersonOut]
    by_day: list[StatsDayOut]


class StatsOut(BaseModel):
    """Wire representation of trip statistics across all currencies."""

    stats: list[StatsBlockOut]
    day_count: int | None


class PreviewSplitOut(BaseModel):
    """Wire representation of a split computed from a request body, without saving."""

    split: SplitOut
    total: Number


# ---- Response envelopes -------------------------------------------------------
# One named-key object per response (design/API.md §1), declared per route so
# the generated schema matches what the handler returns.


class TripEnvelope(BaseModel):
    """`{ "trip": Trip }`."""

    trip: TripOut


class TripListEnvelope(BaseModel):
    """`{ "trips": [TripSummary] }`."""

    trips: list[TripSummaryOut]


class ItemEnvelope(BaseModel):
    """`{ "item": Item }`."""

    item: ItemOut


class DayCurrencyTotalOut(BaseModel):
    """Wire representation of one currency's total for one day."""

    currency_code: str
    currency_id: int
    amount: Number


class DayTotalOut(BaseModel):
    """Wire representation of a day's per-currency totals."""

    date: str
    totals: list[DayCurrencyTotalOut]


class ItemListEnvelope(BaseModel):
    """`{ "items": [Item], "day_totals": [DayTotal], "transfers": [Transfer] }`."""

    items: list[ItemOut]
    day_totals: list[DayTotalOut]
    transfers: list[TransferOut]


class PersonEnvelope(BaseModel):
    """`{ "person": Person }`."""

    person: PersonOut


class PersonListEnvelope(BaseModel):
    """`{ "people": [Person] }`."""

    people: list[PersonOut]


class CurrencyEnvelope(BaseModel):
    """`{ "currency": Currency }`."""

    currency: CurrencyOut


class CurrencyListEnvelope(BaseModel):
    """`{ "currencies": [Currency] }`."""

    currencies: list[CurrencyOut]


class CountryEnvelope(BaseModel):
    """`{ "country": Country }`."""

    country: CountryOut


class CountryListEnvelope(BaseModel):
    """`{ "countries": [Country] }`."""

    countries: list[CountryOut]


class LabelEnvelope(BaseModel):
    """`{ "label": Label }`."""

    label: LabelOut


class LabelListEnvelope(BaseModel):
    """`{ "labels": [Label] }`."""

    labels: list[LabelOut]


class BalancesEnvelope(BaseModel):
    """`{ "balances": [BalanceBlock] }`, one block per currency with any activity."""

    balances: list[BalanceBlockOut]


class WalletEnvelope(BaseModel):
    """`{ "wallet": Wallet }`."""

    wallet: WalletOut


class WalletListEnvelope(BaseModel):
    """`{ "wallets": [WalletReport] }`, the balances report - `GET /trips/{slug}/wallets`."""

    wallets: list[WalletReportOut]


class TransferEnvelope(BaseModel):
    """`{ "transfer": Transfer }`."""

    transfer: TransferOut


class TransferListEnvelope(BaseModel):
    """`{ "transfers": [Transfer] }`."""

    transfers: list[TransferOut]


# ---- Errors -------------------------------------------------------------------
# The envelope every 4xx/5xx carries: a stable `code` the client switches on and
# the `params` its own catalog renders into a sentence, per field where the
# failure has one. The codes themselves live in `app/services/errors/`; what
# each one means is design/API.md §4.


class FieldErrorOut(BaseModel):
    """One field's `{code, params}` failure."""

    code: str
    params: dict[str, Any] = {}


class ErrorBodyOut(BaseModel):
    """The body of an error: a top-level code, its params, and optional per-field detail."""

    code: str
    params: dict[str, Any] = {}
    fields: dict[str, FieldErrorOut] | None = None


class ErrorEnvelope(BaseModel):
    """`{ "error": { "code": ..., "params": {...}, "fields": {...}? } }`."""

    error: ErrorBodyOut


def error_responses(*statuses: int) -> dict[int | str, dict[str, Any]]:
    """Declare the error envelope for each status a route can answer with.

    Listed per route, so the generated schema carries that route's own set.
    `500` applies to every route and is appended here, keeping each call site to
    the statuses its handler raises.
    """
    return {status: {"model": ErrorEnvelope} for status in (*statuses, 500)}
