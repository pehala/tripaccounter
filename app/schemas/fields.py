"""Parse and validate raw request values into the canonical types the models carry.

These helpers back the `Annotated` field aliases below: pydantic runs them as
`BeforeValidator`/`AfterValidator`s, and a `FieldError` from
`app/services/parsing.py` becomes the `PydanticCustomError` the error envelope
renders (design/API.md §4).
"""

import re
from datetime import UTC, datetime
from decimal import Decimal
from typing import Annotated

from pydantic import (
    AfterValidator,
    BaseModel,
    BeforeValidator,
    ConfigDict,
    HttpUrl,
)
from pydantic_core import PydanticCustomError

from app.services import parsing
from app.services.errors.base import FieldError
from app.services.errors.fields import InvalidCoordinatesError, TooLongError


def iso_z(dt: datetime) -> str:
    """Render a datetime as a `Z`-suffixed second-precision ISO 8601 string."""
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def as_pydantic_error(err: FieldError) -> PydanticCustomError:
    """Carry a catalog error's code and params into a PydanticCustomError."""
    return PydanticCustomError(err.code, err.code, err.params)


def label_whitespace_error(value: object) -> PydanticCustomError:
    """Build the `label_whitespace` error for a label that holds whitespace."""
    return PydanticCustomError("label_whitespace", "label_whitespace", {"value": value})


def too_long_error() -> PydanticCustomError:
    """Build the `too_long` error for a label past the 40-character limit."""
    return as_pydantic_error(TooLongError(max=40))


def invalid_coordinates_error() -> PydanticCustomError:
    """Build the `invalid_coordinates` error for a half-supplied lat/lon pair."""
    return as_pydantic_error(InvalidCoordinatesError())


def parse_amount(v: object) -> Decimal:
    """Validate a money amount, raising the pydantic form of a parse failure."""
    try:
        return parsing.parse_amount(v)
    except FieldError as err:
        raise as_pydantic_error(err) from err


def parse_weight(v: object) -> Decimal:
    """Validate a split weight, raising the pydantic form of a parse failure."""
    try:
        return parsing.parse_weight(v)
    except FieldError as err:
        raise as_pydantic_error(err) from err


def parse_lat(v: object) -> str | None:
    """Validate a latitude string, returning it unchanged."""
    if v is None:
        return None
    try:
        parsing.parse_coordinate(v, low=Decimal(-90), high=Decimal(90))
    except FieldError as err:
        raise as_pydantic_error(err) from err
    return v


def parse_lon(v: object) -> str | None:
    """Validate a longitude string, returning it unchanged."""
    if v is None:
        return None
    try:
        parsing.parse_coordinate(v, low=Decimal(-180), high=Decimal(180))
    except FieldError as err:
        raise as_pydantic_error(err) from err
    return v


def normalize_to_utc(dt: datetime | None) -> datetime | None:
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


def parse_label(v: object) -> str:
    """Validate a label token: a stripped, whitespace-free string of 1-40 characters."""
    if not isinstance(v, str):
        raise label_whitespace_error(v)
    stripped = v.strip()
    if len(stripped) < 1 or len(stripped) > 40:
        raise too_long_error()
    if re.search(r"\s", stripped):
        raise label_whitespace_error(v)
    return stripped


Amount = Annotated[Decimal, BeforeValidator(parse_amount)]
Weight = Annotated[Decimal, BeforeValidator(parse_weight)]
LatStr = Annotated[str | None, BeforeValidator(parse_lat)]
LonStr = Annotated[str | None, BeforeValidator(parse_lon)]
OccurredAt = Annotated[datetime | None, AfterValidator(normalize_to_utc)]
LabelToken = Annotated[str, BeforeValidator(parse_label)]
# HttpUrl normalizes (trailing slash, host case, ...); map_url isn't required
# to survive a round trip byte-for-byte, only to be a genuine absolute
# http(s) URL (API.md §4 `invalid_url`).
MapUrl = HttpUrl | None


class Strict(BaseModel):
    """Base model that rejects unknown fields."""

    model_config = ConfigDict(extra="forbid")
