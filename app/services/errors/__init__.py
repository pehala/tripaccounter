"""The API.md §4 error code catalog. No message text lives here or anywhere in app/."""

# Imported for their side effect: each subclass registers itself on
# FieldError._by_code / ApiError._by_code at class-creation time.
from app.services.errors import api, fields  # noqa: F401
from app.services.errors.base import ApiError, FieldError

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
