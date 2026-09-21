"""The list/create/update/delete routes every trip-scoped roster entity shares.

A subclass of `TripChildRoutes` names its model, path words and envelopes, then
declares one `@route`-decorated method per route it publishes. `router()` builds
the routes from what those decorators collected; a kind nobody declared is not
published.

The generated spec is written from the declarations, so each handler is given the
identity FastAPI reads it from: `__name__` for the operationId and summary,
`__doc__` for the description, and `__signature__` for the path parameter's name -
`{person_id}`, `{label_id}`, never a generic `{row_id}`. `endpoint` below is the
whole of that mechanism; nothing outside this file needs to know about it.
"""

from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum
from inspect import Parameter, Signature
from typing import Any, ClassVar, get_type_hints

from fastapi import APIRouter, Response
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlmodel import SQLModel

from app.deps import SessionDep, TripDep
from app.models.trip import Trip
from app.schemas.error_shapes import error_responses
from app.services.errors.api import field_errors
from app.services.scope import require_in_trip

ARG = Parameter.POSITIONAL_OR_KEYWORD
TRIP_ARG = Parameter("trip", ARG, annotation=TripDep)
SESSION_ARG = Parameter("session", ARG, annotation=SessionDep)


class Route(Enum):
    """The routes a roster entity can publish."""

    LIST = "list"
    CREATE = "create"
    UPDATE = "update"
    DELETE = "delete"


@dataclass(frozen=True)
class RouteSpec:
    """What one route needs beyond the method implementing it."""

    kind: Route
    doc: str
    body: type[BaseModel] | None = None
    field: str = "name"
    statuses: tuple[int, ...] = (404, 409)


def route(kind: Route, **spec):
    """Declare the decorated method as this entity's implementation of `kind`.

    The route's description is the method's docstring, and the request model of
    a create or update is the annotation on its `body` parameter, so both are
    written once, where the method uses them.
    """

    def apply(func):
        if not func.__doc__:
            raise TypeError(f"{func.__name__} has no docstring to describe its route")
        body = get_type_hints(func).get("body")
        if body is None and kind in (Route.CREATE, Route.UPDATE):
            raise TypeError(f"{func.__name__} declares no annotated body parameter")
        func.route_spec = RouteSpec(kind, doc=func.__doc__, body=body, **spec)
        return func

    return apply


def endpoint(func, name: str, doc: str, params: list[Parameter]):
    """Give a generic handler the identity the OpenAPI generator reads off it."""
    func.__name__ = name
    func.__doc__ = doc
    func.__signature__ = Signature(params)
    return func


class TripChildRoutes(ABC):
    """One roster entity's CRUD routes under `/trips/{slug}`."""

    model: ClassVar[type[SQLModel]]
    resource: ClassVar[str]
    collection: ClassVar[str]
    envelope: ClassVar[type[BaseModel]]
    list_envelope: ClassVar[type[BaseModel]]
    routes: ClassVar[dict[Route, tuple[Callable[..., Any], RouteSpec]]]

    def __init_subclass__(cls, **kwargs) -> None:
        """Collect the subclass's decorated methods, rejecting a kind declared twice."""
        super().__init_subclass__(**kwargs)
        cls.routes = {}
        for attr in vars(cls).values():
            spec = getattr(attr, "route_spec", None)
            if spec is None:
                continue
            if spec.kind in cls.routes:
                raise TypeError(f"{cls.__name__} declares {spec.kind.value} twice")
            cls.routes[spec.kind] = (attr, spec)

    @abstractmethod
    def serialize(self, row, session: Session) -> BaseModel:
        """Return one row's wire form.

        `row` is the entity's own model, which only the subclass knows.
        """

    def serialize_list(self, rows: list, session: Session, trip: Trip) -> list[BaseModel]:
        """Return the collection's wire forms, row by row.

        An entity whose row carries a trip-wide aggregate overrides this to read
        that aggregate once for the whole collection.
        """
        return [self.serialize(row, session) for row in rows]

    @property
    def collection_path(self) -> str:
        """The collection's URL - `/trips/{slug}/countries`."""
        return f"/trips/{{slug}}/{self.collection}"

    @property
    def row_path(self) -> str:
        """One row's URL - `/trips/{slug}/countries/{country_id}`."""
        return f"{self.collection_path}/{{{self.id_name}}}"

    @property
    def id_name(self) -> str:
        """The path parameter's name - `country_id`."""
        return f"{self.resource}_id"

    def add_list(self, router: APIRouter, rows: Callable[..., Any], spec: RouteSpec) -> None:
        """Register the collection's GET."""

        def list_rows(**kw):
            session, trip = kw["session"], kw["trip"]
            listed = rows(self, session, trip)
            return {self.collection: self.serialize_list(listed, session, trip)}

        router.get(
            self.collection_path,
            response_model=self.list_envelope,
            responses=error_responses(404),
        )(endpoint(list_rows, f"list_{self.collection}", spec.doc, [TRIP_ARG, SESSION_ARG]))

    def add_create(self, router: APIRouter, create: Callable[..., Any], spec: RouteSpec) -> None:
        """Register the collection's POST."""

        def create_row(**kw):
            session = kw["session"]
            with field_errors(spec.field):
                row = create(self, session, kw["trip"], kw["body"])
            return {self.resource: self.serialize(row, session)}

        router.post(
            self.collection_path,
            status_code=201,
            response_model=self.envelope,
            responses=error_responses(400, 404, 409, 422),
        )(
            endpoint(
                create_row,
                f"create_{self.resource}",
                spec.doc,
                [Parameter("body", ARG, annotation=spec.body), TRIP_ARG, SESSION_ARG],
            )
        )

    def add_update(self, router: APIRouter, update: Callable[..., Any], spec: RouteSpec) -> None:
        """Register one row's PATCH."""

        def update_row(**kw):
            session = kw["session"]
            row = require_in_trip(
                session, self.model, kw[self.id_name], kw["trip"].id, self.resource
            )
            with field_errors(spec.field):
                row = update(self, session, row, kw["body"])
            return {self.resource: self.serialize(row, session)}

        router.patch(
            self.row_path,
            response_model=self.envelope,
            responses=error_responses(400, 404, 409, 422),
        )(
            endpoint(
                update_row,
                f"update_{self.resource}",
                spec.doc,
                [
                    Parameter(self.id_name, ARG, annotation=int),
                    Parameter("body", ARG, annotation=spec.body),
                    TRIP_ARG,
                    SESSION_ARG,
                ],
            )
        )

    def add_delete(self, router: APIRouter, delete: Callable[..., Any], spec: RouteSpec) -> None:
        """Register one row's DELETE."""

        def delete_row(**kw):
            session = kw["session"]
            row = require_in_trip(
                session, self.model, kw[self.id_name], kw["trip"].id, self.resource
            )
            with field_errors("id"):
                delete(self, session, row)
            return Response(status_code=204)

        router.delete(self.row_path, status_code=204, responses=error_responses(*spec.statuses))(
            endpoint(
                delete_row,
                f"delete_{self.resource}",
                spec.doc,
                [Parameter(self.id_name, ARG, annotation=int), TRIP_ARG, SESSION_ARG],
            )
        )

    def router(self) -> APIRouter:
        """Build the APIRouter carrying the routes this entity declared."""
        router = APIRouter(tags=[self.collection])
        for kind, add in (
            (Route.LIST, self.add_list),
            (Route.CREATE, self.add_create),
            (Route.UPDATE, self.add_update),
            (Route.DELETE, self.add_delete),
        ):
            if declared := self.routes.get(kind):
                add(router, *declared)
        return router
