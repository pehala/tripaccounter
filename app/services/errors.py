"""The API.md §4 error code catalog. No message text lives here or anywhere in app/."""

from typing import Any, ClassVar

# Fields typed with a pydantic-native constraint (HttpUrl, datetime, ...) fail
# with pydantic's own error `type` string, not one of our codes. This maps
# those native types onto the catalog code API.md documents for that field -
# the other fields raise our codes directly, via PydanticCustomError.
NATIVE_ERROR_CODES: dict[str, str] = {
    "url_parsing": "invalid_url",
    "url_scheme": "invalid_url",
    "url_type": "invalid_url",
    "datetime_parsing": "invalid_datetime",
    "datetime_type": "invalid_datetime",
    "datetime_from_date_parsing": "invalid_datetime",
}


class FieldError(Exception):
    """One `{code, params}` entry attached to a request field.

    A subclass sets `code` as a ClassVar and is registered by it, so
    `FieldError.by_code` can rebuild one from a bare code string - the one
    legitimate use is bridging pydantic's own error-type strings (main.py)
    and ParseError's codes (splits.py) back into our catalog. Everywhere
    else, raise the subclass directly.
    """

    code: ClassVar[str]
    param_names: ClassVar[tuple[str, ...]] = ()
    params: dict[str, Any]

    _by_code: ClassVar[dict[str, type["FieldError"]]] = {}

    def __init_subclass__(cls, **kwargs: Any) -> None:
        """Register the subclass in `_by_code` under its `code`, if it declares one."""
        super().__init_subclass__(**kwargs)
        if "code" in cls.__dict__:
            existing = FieldError._by_code.get(cls.code)
            assert existing is None, f"duplicate FieldError code {cls.code!r}: {existing} vs {cls}"
            FieldError._by_code[cls.code] = cls

    def __init__(self, params: dict[str, Any] | None = None) -> None:
        self.params = params or {}
        super().__init__(self.code)

    def to_wire(self) -> dict[str, Any]:
        """Return the `{code, params}` wire representation of this error."""
        return {"code": self.code, "params": self.params}

    @classmethod
    def by_code(cls, code: str, params: dict[str, Any] | None = None) -> "FieldError":
        """Rebuild the right subclass from a bare code string.

        Only for bridging a third-party string-keyed error (pydantic, ParseError).
        """
        return cls._by_code[code](**(params or {}))


class ConflictFieldError(FieldError):
    """Mark the codes meaning 'this name/reference is already taken or still referenced'.

    `wrap_field_error` checks `isinstance` against this instead of a
    stringly-typed set.
    """


class RequiredError(FieldError):
    """A required field was omitted."""

    code = "required"


class TooLongError(FieldError):
    """A string field exceeded its max length."""

    code = "too_long"
    param_names = ("max",)

    def __init__(self, max: int) -> None:
        super().__init__({"max": max})


class InvalidAmountError(FieldError):
    """Not the canonical amount grammar, or out of the allowed range."""

    code = "invalid_amount"


class NotInTripError(FieldError):
    """A referenced id doesn't belong to this trip."""

    code = "not_in_trip"


class InactiveError(FieldError):
    """The referenced person is not active."""

    code = "inactive"


class InvalidDatetimeError(FieldError):
    """Not a parseable ISO datetime."""

    code = "invalid_datetime"


class LabelWhitespaceError(FieldError):
    """A label token isn't a string, or contains whitespace."""

    code = "label_whitespace"
    param_names = ("value",)

    def __init__(self, value: Any) -> None:
        super().__init__({"value": value})


class EmptyError(FieldError):
    """A required list/array was empty or malformed."""

    code = "empty"


class DuplicatePersonError(FieldError):
    """The same person appears twice in `shares`."""

    code = "duplicate_person"


class SumMismatchError(FieldError):
    """`shares` (exact mode) don't sum to the item amount."""

    code = "sum_mismatch"
    param_names = ("diff", "currency_code")

    def __init__(self, diff: int, currency_code: str) -> None:
        super().__init__({"diff": diff, "currency_code": currency_code})


class NotPositiveError(FieldError):
    """Not the canonical weight grammar, or not greater than zero."""

    code = "not_positive"


class TooPreciseError(FieldError):
    """More fraction digits than the field allows."""

    code = "too_precise"
    param_names = ("max",)

    def __init__(self, max: int) -> None:
        super().__init__({"max": max})


class InvalidUrlError(FieldError):
    """Not a genuine absolute http(s) URL."""

    code = "invalid_url"


class InvalidCoordinatesError(FieldError):
    """Not the canonical coordinate grammar, or out of range."""

    code = "invalid_coordinates"


class DuplicateError(ConflictFieldError):
    """Another row in this trip already has this name/code."""

    code = "duplicate"
    param_names = ("name",)

    def __init__(self, name: str) -> None:
        super().__init__({"name": name})


class InvalidCodeError(FieldError):
    """Not a 3-letter currency code."""

    code = "invalid_code"


class InUseError(ConflictFieldError):
    """The row is still referenced by items/shares and can't be deleted."""

    code = "in_use"
    param_names = ("count", "name")

    def __init__(self, count: int, name: str) -> None:
        super().__init__({"count": count, "name": name})


class WalletOwnerMismatchError(FieldError):
    """The wallet named on an item isn't owned by that item's payer."""

    code = "wallet_owner_mismatch"


class SameWalletError(FieldError):
    """A transfer's two sides name the same wallet in the same currency."""

    code = "same_wallet"


class CrossOwnerExchangeError(FieldError):
    """A transfer between two different people's wallets also changes currency."""

    code = "cross_owner_exchange"


class IsDefaultError(ConflictFieldError):
    """The wallet is a person's default and can't be deleted while it holds that role."""

    code = "is_default"


class ApiError(Exception):
    """The whole `{error: {code, params, fields?}}` envelope, with its HTTP status.

    A subclass sets `status_code` and `code` as ClassVars and is registered
    by `code`, mirroring `FieldError` so `TOP_LEVEL_PARAMS` derives the same
    mechanical way.
    """

    status_code: ClassVar[int]
    code: ClassVar[str]
    param_names: ClassVar[tuple[str, ...]] = ()
    params: dict[str, Any]
    fields: dict[str, FieldError]

    _by_code: ClassVar[dict[str, type["ApiError"]]] = {}

    def __init_subclass__(cls, **kwargs: Any) -> None:
        """Register the subclass in `_by_code` under its `code`, if it declares one."""
        super().__init_subclass__(**kwargs)
        if "code" in cls.__dict__:
            ApiError._by_code[cls.code] = cls

    def __init__(
        self,
        params: dict[str, Any] | None = None,
        fields: dict[str, FieldError] | None = None,
    ) -> None:
        self.params = params or {}
        self.fields = fields or {}
        super().__init__(self.code)

    def to_wire(self) -> dict[str, Any]:
        """Return the `{error: {code, params, fields?}}` wire envelope."""
        body: dict[str, Any] = {"code": self.code, "params": self.params}
        if self.fields:
            body["fields"] = {name: err.to_wire() for name, err in self.fields.items()}
        return {"error": body}


class BadRequestError(ApiError):
    """Malformed JSON, or an unexpected top-level field."""

    status_code = 400
    code = "bad_request"


class NotFoundError(ApiError):
    """No row matches the id/slug in the path."""

    status_code = 404
    code = "not_found"
    param_names = ("resource",)

    def __init__(self, resource: str) -> None:
        super().__init__({"resource": resource})


class ConflictError(ApiError):
    """A field's value conflicts with an existing or still-referenced row."""

    status_code = 409
    code = "conflict"

    def __init__(self, fields: dict[str, FieldError]) -> None:
        super().__init__(fields=fields)


class ValidationError(ApiError):
    """One or more fields failed validation."""

    status_code = 422
    code = "validation_error"

    def __init__(self, fields: dict[str, FieldError]) -> None:
        super().__init__(fields=fields)


class InternalError(ApiError):
    """An unhandled server error; `ref` is the log correlation id."""

    status_code = 500
    code = "internal_error"
    param_names = ("ref",)

    def __init__(self, ref: str) -> None:
        super().__init__({"ref": ref})


def wrap_field_error(field: str, err: FieldError) -> ApiError:
    """Address a `FieldError` from a service call to its request field, with the right HTTP status.

    409 for a naming/reference conflict, 422 for everything else.
    """
    if isinstance(err, ConflictFieldError):
        return ConflictError({field: err})
    return ValidationError({field: err})


def run_field(field: str, fn, *args, **kwargs):
    """Call a service function, translating a `FieldError` it raises.

    Turns it into the right `ApiError` addressed to `field`.
    """
    try:
        return fn(*args, **kwargs)
    except FieldError as err:
        raise wrap_field_error(field, err) from err


# Derived from the subclasses above, not hand-written - one source of truth
# per code. `app/main.py` uses these to filter pydantic's `ctx` dict down to
# each code's declared params; tests/backend/test_errors.py asserts every
# code seen on the wire is a key here.
FIELD_ERROR_PARAMS: dict[str, tuple[str, ...]] = {
    code: cls.param_names for code, cls in FieldError._by_code.items()
}

TOP_LEVEL_PARAMS: dict[str, tuple[str, ...]] = {
    code: cls.param_names for code, cls in ApiError._by_code.items()
}
