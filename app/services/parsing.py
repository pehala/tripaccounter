"""Canonical decimal/coordinate grammar and business rules, in one place.

Used two ways: `schemas/fields.py` wraps these in pydantic `BeforeValidator`s,
catching the `FieldError` and re-raising it as the `PydanticCustomError` pydantic
wants, and `splits.py` calls them plainly and lets the `FieldError` travel (for
`shares` rows - a raw `list[dict]` whose shape depends on the sibling `split_mode`
field, which pydantic cannot validate structurally). Both paths parse the same
grammar and raise the same catalog codes; only the rendering at the pydantic
boundary differs.
"""

import re
from decimal import Decimal

from app.services.errors.fields import (
    InvalidAmountError,
    InvalidCoordinatesError,
    InvalidRateError,
    NotPositiveError,
    TooPreciseError,
)

AMOUNT_RE = re.compile(r"^-?[0-9]+(\.[0-9]{1,2})?$")
WEIGHT_RE = re.compile(r"^[0-9]+(\.[0-9]+)?$")
COORD_RE = re.compile(r"^-?[0-9]+(\.[0-9]{1,6})?$")
# ≤ 9 integer digits keeps a rate ×10⁹ inside a bigint.
RATE_RE = re.compile(r"^[0-9]{1,9}(\.[0-9]{1,9})?$")


def parse_amount(raw: object, *, allow_zero: bool = False) -> Decimal:
    """Parse the canonical amount grammar: ≤ 12 integer digits, ≤ 2 fraction digits, > 0.

    Or ≥ 0 when `allow_zero` - an `exact` share may legitimately be zero.
    """
    if not isinstance(raw, str) or not AMOUNT_RE.match(raw):
        raise InvalidAmountError()
    value = Decimal(raw)
    if value < 0 or (value == 0 and not allow_zero):
        raise InvalidAmountError()
    if len(raw.lstrip("-").split(".")[0]) > 12:
        raise InvalidAmountError()
    return value


def parse_weight(raw: object) -> Decimal:
    """> 0, ≤ 4 fraction digits."""
    if not isinstance(raw, str) or not WEIGHT_RE.match(raw):
        raise NotPositiveError()
    value = Decimal(raw)
    if value <= 0:
        raise NotPositiveError()
    if value.as_tuple().exponent < -4:
        raise TooPreciseError(max=4)
    return value


def parse_coordinate(raw: object, *, low: Decimal, high: Decimal) -> Decimal:
    """Parse the canonical coordinate grammar, within the given [low, high] range."""
    if not isinstance(raw, str) or not COORD_RE.match(raw):
        raise InvalidCoordinatesError()
    value = Decimal(raw)
    if not (low <= value <= high):
        raise InvalidCoordinatesError()
    return value


def parse_rate(raw: object, currency_id: int | None) -> Decimal:
    """Parse the canonical rate grammar: ≤ 9 integer digits, ≤ 9 fraction digits, > 0.

    `currency_id` names the currency the rate is for, carried in the error.
    """
    if not isinstance(raw, str) or not RATE_RE.match(raw):
        raise InvalidRateError(currency_id=currency_id)
    value = Decimal(raw)
    if value <= 0:
        raise InvalidRateError(currency_id=currency_id)
    return value
