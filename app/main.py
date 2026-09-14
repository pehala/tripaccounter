"""FastAPI app factory: routers, error handlers, and static file serving."""

import hashlib
import logging
import uuid

from fastapi import FastAPI, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware

from app.config import Settings
from app.routers import (
    countries,
    currencies,
    export,
    items,
    labels,
    people,
    reports,
    trips,
)
from app.services.errors import (
    FIELD_ERROR_PARAMS,
    NATIVE_ERROR_CODES,
    ApiError,
    BadRequestError,
    FieldError,
    InternalError,
    RequiredError,
    ValidationError,
)

logger = logging.getLogger("app")
settings = Settings()

ROUTERS = (
    trips.router,
    items.router,
    people.router,
    currencies.router,
    countries.router,
    labels.router,
    reports.router,
    export.router,
)


def _field_from_loc(loc: tuple) -> str:
    """Resolve the request field name a pydantic error location refers to."""
    if loc and loc[0] == "body" and len(loc) > 1:
        return str(loc[1])
    return str(loc[-1]) if loc else "body"


async def handle_api_error(request: Request, exc: ApiError) -> JSONResponse:
    """Render an `ApiError` as its wire envelope with the matching HTTP status."""
    return JSONResponse(status_code=exc.status_code, content=exc.to_wire())


async def handle_validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
    """Translate FastAPI's request validation errors into the error catalog."""
    fields: dict[str, FieldError] = {}
    for err in exc.errors():
        error_type = err["type"]
        if error_type in ("json_invalid", "extra_forbidden"):
            return JSONResponse(status_code=400, content=BadRequestError().to_wire())
        field = _field_from_loc(err["loc"])
        if error_type == "missing":
            fields[field] = RequiredError()
        elif error_type in FIELD_ERROR_PARAMS:
            ctx = err.get("ctx") or {}
            params = {name: ctx[name] for name in FIELD_ERROR_PARAMS[error_type] if name in ctx}
            fields[field] = FieldError.by_code(error_type, params)
        elif error_type in NATIVE_ERROR_CODES:
            fields[field] = FieldError.by_code(NATIVE_ERROR_CODES[error_type])
        else:
            return JSONResponse(status_code=400, content=BadRequestError().to_wire())
    return JSONResponse(status_code=422, content=ValidationError(fields).to_wire())


async def handle_unexpected(request: Request, exc: Exception) -> JSONResponse:
    """Log an unhandled error and return a 500 with a correlation reference."""
    ref = uuid.uuid4().hex
    logger.exception("unhandled error ref=%s", ref)
    return JSONResponse(status_code=500, content=InternalError(ref).to_wire())


class ETagMiddleware(BaseHTTPMiddleware):
    """Give every `/api/v1` GET response an ETag so a client can revalidate instead of refetching.

    A page load under `/t/{slug}/{tab}` is now an independent HTTP request, not a
    client-side route switch, so this is what keeps repeat loads of the same trip
    cheap: unchanged data comes back as a 304 with no body, and a write immediately
    changes the hash, so there is no stale-data window to reason about.
    """

    async def dispatch(self, request: Request, call_next):
        """Recompute the response as a conditional GET when its route matches."""
        response = await call_next(request)
        is_api_get = request.method == "GET" and request.url.path.startswith("/api/v1")
        if not is_api_get or response.status_code != 200:
            return response

        body = b"".join([chunk async for chunk in response.body_iterator])
        etag = f'"{hashlib.sha256(body).hexdigest()}"'
        headers = dict(response.headers)
        headers["etag"] = etag
        headers["cache-control"] = "no-cache"

        if request.headers.get("if-none-match") == etag:
            headers.pop("content-length", None)
            return Response(status_code=304, headers=headers)
        return Response(
            content=body,
            status_code=response.status_code,
            headers=headers,
            media_type=response.media_type,
        )


async def index_root() -> FileResponse:
    """Serve the frontend's index page at the site root."""
    return FileResponse(settings.static_dir / "index.html")


async def index_trip(slug: str, tab: str | None = None) -> FileResponse:
    """Serve the frontend's index page for a trip deep link, tab included."""
    return FileResponse(settings.static_dir / "index.html")


def strip_default_validation_error(schema: dict) -> dict:
    """Leave each operation's responses as its decorator declared them.

    FastAPI attaches an `HTTPValidationError` 422 to every route carrying a path
    parameter or a body. This API answers 422 with its own
    `{error: {code, params, fields}}` envelope, declared per route through
    `schemas.error_responses`, so the generated 422 is replaced by that envelope
    where a route can raise one and dropped where it cannot. Doing it here keeps
    every decorator stating exactly what its own handler returns.
    """
    for operations in schema.get("paths", {}).values():
        for operation in operations.values():
            responses = operation.get("responses", {})
            content = responses.get("422", {}).get("content", {}).get("application/json", {})
            if content.get("schema", {}).get("$ref", "").endswith("/HTTPValidationError"):
                del responses["422"]
    components = schema.get("components", {}).get("schemas", {})
    for name in ("HTTPValidationError", "ValidationError"):
        components.pop(name, None)
    return schema


def create_app() -> FastAPI:
    """Build the FastAPI app: routers, error handlers, and static file serving."""
    app = FastAPI(
        title="Trip Accounter API",
        version="0.1.0",
        description=(
            "Expense tracking for a shared trip: people, currencies, countries and "
            "labels belong to a trip; every line item records who paid and how the "
            "cost splits across the roster.\n\n"
            "JSON in, JSON out. Every response is a single object with its payload "
            "under a named key, never a bare array. Amounts are plain numbers in the "
            "currency's own units - typed values to 2 fraction digits, computed "
            "shares to 6 - and are taken on input as canonical decimal strings "
            '(`"18400.50"`). Nothing is ever converted between currencies: '
            "balances and statistics are per currency.\n\n"
            "Errors are `{code, params}` with no message text, so a client renders "
            "them through its own catalog in its own language."
        ),
    )

    for router in ROUTERS:
        app.include_router(router, prefix="/api/v1")

    app.add_middleware(ETagMiddleware)

    generate_openapi = app.openapi

    def openapi() -> dict:
        """Generate the schema once, then hand back the cleaned-up copy."""
        if app.openapi_schema is None:
            app.openapi_schema = strip_default_validation_error(generate_openapi())
        return app.openapi_schema

    app.openapi = openapi

    app.add_exception_handler(ApiError, handle_api_error)
    app.add_exception_handler(RequestValidationError, handle_validation_error)
    app.add_exception_handler(Exception, handle_unexpected)

    app.add_api_route("/", index_root, methods=["GET"], include_in_schema=False)
    app.add_api_route("/trips/new", index_root, methods=["GET"], include_in_schema=False)
    app.add_api_route("/t/{slug}", index_trip, methods=["GET"], include_in_schema=False)
    app.add_api_route("/t/{slug}/{tab}", index_trip, methods=["GET"], include_in_schema=False)

    if settings.static_dir.exists():
        app.mount("/", StaticFiles(directory=settings.static_dir), name="static")

    return app


app = create_app()
