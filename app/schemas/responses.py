"""Wire shapes: what each response carries, built from model instances.

Every `*Out` is constructed by a `from_*` classmethod that converts minor-unit
integers to plain JSON numbers via `money.to_wire` (design/BACKEND.md).
"""

from typing import Literal

from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import joinedload, selectinload

from app.models.items import LineItem
from app.models.roster import Person, TripCountry
from app.models.trip import Trip
from app.models.wallets import WalletTransfer
from app.schemas.fields import iso_z
from app.services.countries import flag_from_code
from app.services.money import AMOUNT_SCALE, to_wire
from app.services.splits import format_weight, resolve_shares_wire, rows_from_shares

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

    model_config = ConfigDict(from_attributes=True)

    id: int
    person_id: int
    name: str
    tracked: bool
    is_default: bool


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

    model_config = ConfigDict(from_attributes=True)

    id: int
    code: str
    symbol: str | None
    is_primary: bool


class CountryOut(BaseModel):
    """Wire representation of a trip country."""

    id: int
    name: str
    code: str | None
    flag: str | None
    is_default: bool
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
            item_count=item_count,
        )


class LabelOut(BaseModel):
    """Wire representation of a label."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    color: str
    use_count: int


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
        return cls(
            id=trip.id,
            slug=trip.slug,
            name=trip.name,
            start_date=trip.start_date,
            end_date=trip.end_date,
            note=trip.note,
            archived=trip.archived,
            people=[PersonOut.from_person(p) for p in trip.people],
            currencies=[CurrencyOut.model_validate(c) for c in trip.currencies],
            countries=[
                CountryOut.from_country(c, country_item_counts.get(c.id, 0)) for c in trip.countries
            ],
            wallets=[WalletOut.model_validate(w) for p in trip.people for w in p.wallets],
            created_at=iso_z(trip.created_at),
            updated_at=iso_z(trip.updated_at),
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
            created_at=iso_z(trip.created_at),
            updated_at=iso_z(trip.updated_at),
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
    city: str | None
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
        rows = rows_from_shares(item.shares)
        resolved = resolve_shares_wire(roster_ids_sorted, rows, item.amount_minor)
        return cls(
            id=item.id,
            name=item.name,
            note=item.note,
            city=item.city,
            occurred_at=iso_z(item.occurred_at),
            currency_code=item.currency.code,
            currency_id=item.currency_id,
            amount=to_wire(item.amount_minor, AMOUNT_SCALE),
            payer_id=item.payer_id,
            country_id=item.country_id,
            wallet_id=item.wallet_id,
            labels=[label.name_norm for label in item.label_rows],
            map_url=item.map_url,
            lat=item.lat,
            lon=item.lon,
            split=SplitOut(mode=item.split_mode, shares=[ShareOut(**row) for row in resolved]),
            created_at=iso_z(item.created_at),
            updated_at=iso_z(item.updated_at),
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
            occurred_at=iso_z(transfer.occurred_at),
            from_wallet_id=transfer.from_wallet_id,
            from_amount=to_wire(transfer.from_amount_minor, AMOUNT_SCALE),
            from_currency_id=transfer.from_currency_id,
            from_currency_code=transfer.from_currency.code,
            to_wallet_id=transfer.to_wallet_id,
            to_amount=to_wire(transfer.to_amount_minor, AMOUNT_SCALE),
            to_currency_id=transfer.to_currency_id,
            to_currency_code=transfer.to_currency.code,
            note=transfer.note,
            created_at=iso_z(transfer.created_at),
            updated_at=iso_z(transfer.updated_at),
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
