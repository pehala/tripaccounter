"""The per-field error codes of the API.md §4 catalog."""

from typing import Any

from app.services.errors.base import ConflictFieldError, FieldError

# ---- presence & size ---------------------------------------------------------


class RequiredError(FieldError):
    """A required field was omitted."""

    code = "required"


class TooLongError(FieldError):
    """A string field exceeded its max length."""

    code = "too_long"
    param_names = ("max",)

    def __init__(self, max: int) -> None:
        super().__init__({"max": max})


class EmptyError(FieldError):
    """A required list/array was empty or malformed."""

    code = "empty"


# ---- number grammar ----------------------------------------------------------


class InvalidAmountError(FieldError):
    """Not the canonical amount grammar, or out of the allowed range."""

    code = "invalid_amount"


class NotPositiveError(FieldError):
    """Not the canonical weight grammar, or not greater than zero."""

    code = "not_positive"


class TooPreciseError(FieldError):
    """More fraction digits than the field allows."""

    code = "too_precise"
    param_names = ("max",)

    def __init__(self, max: int) -> None:
        super().__init__({"max": max})


# ---- value grammar -----------------------------------------------------------


class InvalidDatetimeError(FieldError):
    """Not a parseable ISO datetime."""

    code = "invalid_datetime"


class InvalidUrlError(FieldError):
    """Not a genuine absolute http(s) URL."""

    code = "invalid_url"


class InvalidCoordinatesError(FieldError):
    """Not the canonical coordinate grammar, or out of range."""

    code = "invalid_coordinates"


class InvalidCodeError(FieldError):
    """Not a 3-letter currency code."""

    code = "invalid_code"


class LabelWhitespaceError(FieldError):
    """A label token isn't a string, or contains whitespace."""

    code = "label_whitespace"
    param_names = ("value",)

    def __init__(self, value: Any) -> None:
        super().__init__({"value": value})


class UnknownDimensionError(FieldError):
    """A `group_by` name isn't in the statistics dimension registry, or repeats within one chain."""

    code = "unknown_dimension"
    param_names = ("dimension",)

    def __init__(self, dimension: str) -> None:
        super().__init__({"dimension": dimension})


# ---- trip references ---------------------------------------------------------


class NotInTripError(FieldError):
    """A referenced id doesn't belong to this trip."""

    code = "not_in_trip"


class InactiveError(FieldError):
    """The referenced person is not active."""

    code = "inactive"


# ---- shares ------------------------------------------------------------------


class DuplicatePersonError(FieldError):
    """The same person appears twice in `shares`."""

    code = "duplicate_person"


class SumMismatchError(FieldError):
    """`shares` (exact mode) don't sum to the item amount."""

    code = "sum_mismatch"
    param_names = ("diff", "currency_code")

    def __init__(self, diff: int, currency_code: str) -> None:
        super().__init__({"diff": diff, "currency_code": currency_code})


# ---- wallets & transfers -----------------------------------------------------


class WalletOwnerMismatchError(FieldError):
    """The wallet named on an item isn't owned by that item's payer."""

    code = "wallet_owner_mismatch"


class SameWalletError(FieldError):
    """A transfer's two sides name the same wallet in the same currency."""

    code = "same_wallet"


class CrossOwnerExchangeError(FieldError):
    """A transfer between two different people's wallets also changes currency."""

    code = "cross_owner_exchange"


# ---- conflicts (409) ---------------------------------------------------------


class DuplicateError(ConflictFieldError):
    """Another row in this trip already has this name/code."""

    code = "duplicate"
    param_names = ("name",)

    def __init__(self, name: str) -> None:
        super().__init__({"name": name})


class InUseError(ConflictFieldError):
    """The row is still referenced by items/shares and can't be deleted."""

    code = "in_use"
    param_names = ("count", "name")

    def __init__(self, count: int, name: str) -> None:
        super().__init__({"count": count, "name": name})


class IsDefaultError(ConflictFieldError):
    """The wallet is a person's default and can't be deleted while it holds that role."""

    code = "is_default"
