"""The base exception types and the pydantic-native error code map."""

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
