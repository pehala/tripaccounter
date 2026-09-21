"""The top-level error envelopes and the helpers that address a `FieldError` to a field."""

from collections.abc import Iterator
from contextlib import contextmanager

from app.services.errors.base import ApiError, ConflictFieldError, FieldError


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


@contextmanager
def field_errors(field: str) -> Iterator[None]:
    """Translate a `FieldError` raised inside the block into an `ApiError` for `field`."""
    try:
        yield
    except FieldError as err:
        raise wrap_field_error(field, err) from err
