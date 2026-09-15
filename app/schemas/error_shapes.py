"""The error envelope every 4xx/5xx carries.

A stable `code` the client switches on and the `params` its own catalog renders
into a sentence, per field where the failure has one. The codes themselves live
in `app/services/errors/`; what each one means is design/API.md §4.
"""

from typing import Any

from pydantic import BaseModel


class FieldErrorOut(BaseModel):
    """One field's `{code, params}` failure."""

    code: str
    params: dict[str, Any] = {}


class ErrorBodyOut(BaseModel):
    """The body of an error: a top-level code, its params, and optional per-field detail."""

    code: str
    params: dict[str, Any] = {}
    fields: dict[str, FieldErrorOut] | None = None


class ErrorEnvelope(BaseModel):
    """`{ "error": { "code": ..., "params": {...}, "fields": {...}? } }`."""

    error: ErrorBodyOut


def error_responses(*statuses: int) -> dict[int | str, dict[str, Any]]:
    """Declare the error envelope for each status a route can answer with.

    Listed per route, so the generated schema carries that route's own set.
    `500` applies to every route and is appended here, keeping each call site to
    the statuses its handler raises.
    """
    return {status: {"model": ErrorEnvelope} for status in (*statuses, 500)}
