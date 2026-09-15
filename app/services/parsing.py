"""Canonical decimal/coordinate grammar and business rules, in one place.

Used two ways: `schemas/fields.py` wraps these in pydantic `BeforeValidator`s (raising
`PydanticCustomError`, for fields pydantic validates directly), and
`splits.py` wraps them in plain calls (raising `FieldError`, for `shares` rows
- a raw `list[dict]` whose shape depends on the sibling `split_mode` field,
which pydantic cannot validate structurally). Both paths parse the same
grammar with the same rules; only the exception raised at the boundary
differs.
"""

import re
from decimal import Decimal, InvalidOperation
from typing import Any, ClassVar

AMOUNT_RE = re.compile(r"^-?[0-9]+(\.[0-9]{1,2})?$")
WEIGHT_RE = re.compile(r"^[0-9]+(\.[0-9]{1,4})?$")
COORD_RE = re.compile(r"^-?[0-9]+(\.[0-9]{1,6})?$")


class ParseError(Exception):
    """Base for the parsing grammar's own error codes.

    A subclass sets `code` as a ClassVar; a code with no params needs no
    `__init__` override.
    """

    code: ClassVar[str]
    params: dict[str, Any]

    def __init__(self, params: dict[str, Any] | None = None) -> None:
        self.params = params or {}
        super().__init__(self.code)


class InvalidAmountError(ParseError):
    """Not the canonical amount grammar, or out of the allowed range."""

    code = "invalid_amount"


class NotPositiveError(ParseError):
    """Not the canonical weight grammar, or not greater than zero."""

    code = "not_positive"


class TooPreciseError(ParseError):
    """More fraction digits than the field allows."""

    code = "too_precise"

    def __init__(self, max: int) -> None:
        super().__init__({"max": max})


class InvalidCoordinatesError(ParseError):
    """Not the canonical coordinate grammar, or out of range."""

    code = "invalid_coordinates"


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
    try:
        value = Decimal(raw)
    except InvalidOperation as exc:
        raise NotPositiveError() from exc
    if value <= 0:
        raise NotPositiveError()
    exponent = value.as_tuple().exponent
    if isinstance(exponent, int) and exponent < -4:
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
