"""Request bodies: what a client may send, and how each field is validated.

Unknown fields are rejected (`Strict`), except `PreviewSplitRequest`, which
takes an item write body and reads only the fields a split needs.
"""

from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, model_validator

from app.schemas.fields import (
    Amount,
    LabelToken,
    LatStr,
    LonStr,
    OccurredAt,
    Strict,
    UrlStr,
    Weight,
    invalid_coordinates_error,
)
from app.services import geo


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


class Located(Strict):
    """A maps link and/or coordinates; coordinates left out are read off the link."""

    map_url: UrlStr = None
    lat: LatStr = None
    lon: LonStr = None

    @model_validator(mode="after")
    def resolve_coordinates(self):
        """Require lat and lon together; fill them from `map_url` when neither was given."""
        if (self.lat is None) != (self.lon is None):
            raise invalid_coordinates_error()
        if self.map_url and self.lat is None and (coordinates := geo.parse(self.map_url)):
            self.lat, self.lon = coordinates
        return self


class StayCreate(Located):
    """Request body for creating a stay."""

    name: str
    check_in: date
    check_out: date
    url: UrlStr = None
    note: str | None = None
    country_id: int | None = None
    city: str | None = None


class StayUpdate(Located):
    """Request body for partially updating a stay; an optional field sent as `null` clears it."""

    name: str = None
    check_in: date = None
    check_out: date = None
    url: UrlStr = None
    note: str | None = None
    country_id: int | None = None
    city: str | None = None


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


class ItemWrite(Located):
    """Request body for creating or updating a line item."""

    name: str | None = None
    note: str | None = None
    city: str | None = None
    amount: Amount | None = None
    currency_id: int | None = None
    payer_id: int | None = None
    country_id: int | None = None
    wallet_id: int | None = None
    stay_id: int | None = None
    occurred_at: OccurredAt = None
    labels: list[LabelToken] | None = None
    split_mode: Literal["equal", "shares", "exact"] | None = None
    shares: list[dict] | None = None


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
