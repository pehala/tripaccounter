"""Response envelopes: the named-key object each route returns.

One per response (design/API.md §1), declared per route so the generated schema
matches what the handler returns.
"""

from pydantic import BaseModel

from app.schemas.responses import (
    BalanceBlockOut,
    CountryOut,
    CurrencyOut,
    ItemOut,
    LabelOut,
    Number,
    PersonOut,
    TransferOut,
    TripOut,
    TripSummaryOut,
    WalletOut,
    WalletReportOut,
)


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
