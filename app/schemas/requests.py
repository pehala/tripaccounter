"""Request bodies: what a client may send, and how each field is validated.

Unknown fields are rejected (`Strict`), except `PreviewSplitRequest`, which
takes an item write body and reads only the fields a split needs.
"""

from typing import Literal

from pydantic import BaseModel, ConfigDict, model_validator

from app.schemas.fields import (
    Amount,
    LabelToken,
    LatStr,
    LonStr,
    MapUrl,
    OccurredAt,
    Strict,
    Weight,
    invalid_coordinates_error,
)


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
    def lat_lon_paired(self):
        """Require lat and lon to be supplied together."""
        if (self.lat is None) != (self.lon is None):
            raise invalid_coordinates_error()
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
