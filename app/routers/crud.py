"""The list/create/update/delete routes every trip-scoped roster entity shares.

A subclass of `TripChildRoutes` names its model, schemas and path words, supplies
the three service calls, and overrides a hook only where its behaviour differs.
`router()` builds the four routes from that.

The generated spec must stay byte-identical to the hand-written routers this
replaces, so each handler is given the identity FastAPI reads it from:
`__name__` for the operationId and summary, `__doc__` for the description, and
`__signature__` for the path parameter's name - `{person_id}`, `{label_id}`,
never a generic `{row_id}`. `endpoint` below is the whole of that mechanism;
nothing outside this file needs to know about it.
"""

from inspect import Parameter, Signature
from typing import ClassVar

from fastapi import APIRouter, Response
from pydantic import BaseModel
from sqlmodel import SQLModel

from app.deps import SessionDep, TripDep
from app.schemas.error_shapes import error_responses
from app.services.errors.api import field_errors
from app.services.scope import require_in_trip

ARG = Parameter.POSITIONAL_OR_KEYWORD


def endpoint(func, name: str, doc: str, params: list[Parameter]):
    """Give a generic handler the identity the OpenAPI generator reads off it."""
    func.__name__ = name
    func.__doc__ = doc
    func.__signature__ = Signature(params)
    return func


class TripChildRoutes:
    """One roster entity's four CRUD routes under `/trips/{slug}`."""

    model: ClassVar[type[SQLModel]]
    resource: ClassVar[str]
    collection: ClassVar[str]
    out: ClassVar[type[BaseModel]]
    create_body: ClassVar[type[BaseModel]]
    update_body: ClassVar[type[BaseModel]]
    envelope: ClassVar[type[BaseModel]]
    list_envelope: ClassVar[type[BaseModel]]
    list_doc: ClassVar[str]
    create_doc: ClassVar[str]
    update_doc: ClassVar[str]
    delete_doc: ClassVar[str]
    conflict_field: ClassVar[str] = "name"
    delete_statuses: ClassVar[tuple[int, ...]] = (404, 409)

    @classmethod
    def rows(cls, trip, session) -> list:
        """Return the trip's rows in wire order: the relationship, by sort_order."""
        return sorted(getattr(trip, cls.collection), key=lambda row: row.sort_order)

    @classmethod
    def serialize(cls, row, session):
        """Return one row's wire form.

        The default fits a schema declaring `from_attributes`, which is every
        schema whose fields are all plain copies of the model's. One carrying a
        derived or counted field overrides this with its own `from_*` builder.
        """
        return cls.out.model_validate(row)

    @classmethod
    def serialize_list(cls, rows: list, session, trip) -> list:
        """Return the collection's wire forms, row by row.

        An entity whose row carries a trip-wide aggregate overrides this to read
        that aggregate once for the whole collection.
        """
        return [cls.serialize(row, session) for row in rows]

    @classmethod
    def create(cls, session, trip, body):
        """Create one row from a validated request body."""
        raise NotImplementedError

    @classmethod
    def update(cls, session, row, body):
        """Apply a validated request body to one row."""
        raise NotImplementedError

    @classmethod
    def delete(cls, session, row) -> None:
        """Delete one row."""
        with field_errors("id"):
            cls.delete_row(session, row)

    @classmethod
    def delete_row(cls, session, row) -> None:
        """Remove the row, raising a field error when something still references it."""
        session.delete(row)
        session.flush()

    @classmethod
    def fetch(cls, session, trip, row_id: int):
        """Return the trip's row with this id, or raise not-found."""
        return require_in_trip(session, cls.model, row_id, trip.id, cls.resource)

    @classmethod
    def router(cls) -> APIRouter:
        """Build the APIRouter carrying this entity's four routes."""
        router = APIRouter(tags=[cls.collection])
        many = f"/trips/{{slug}}/{cls.collection}"
        one = f"{many}/{{{cls.resource}_id}}"
        id_name = f"{cls.resource}_id"

        id_arg = Parameter(id_name, ARG, annotation=int)
        trip_arg = Parameter("trip", ARG, annotation=TripDep)
        session_arg = Parameter("session", ARG, annotation=SessionDep)
        create_arg = Parameter("body", ARG, annotation=cls.create_body)
        update_arg = Parameter("body", ARG, annotation=cls.update_body)

        def list_rows(**kw):
            session, trip = kw["session"], kw["trip"]
            rows = cls.rows(trip, session)
            return {cls.collection: cls.serialize_list(rows, session, trip)}

        def create_row(**kw):
            session = kw["session"]
            with field_errors(cls.conflict_field):
                row = cls.create(session, kw["trip"], kw["body"])
            return {cls.resource: cls.serialize(row, session)}

        def update_row(**kw):
            session = kw["session"]
            row = cls.fetch(session, kw["trip"], kw[id_name])
            with field_errors(cls.conflict_field):
                row = cls.update(session, row, kw["body"])
            return {cls.resource: cls.serialize(row, session)}

        def delete_row(**kw):
            session = kw["session"]
            cls.delete(session, cls.fetch(session, kw["trip"], kw[id_name]))
            return Response(status_code=204)

        router.get(many, response_model=cls.list_envelope, responses=error_responses(404))(
            endpoint(list_rows, f"list_{cls.collection}", cls.list_doc, [trip_arg, session_arg])
        )
        router.post(
            many,
            status_code=201,
            response_model=cls.envelope,
            responses=error_responses(400, 404, 409, 422),
        )(
            endpoint(
                create_row,
                f"create_{cls.resource}",
                cls.create_doc,
                [create_arg, trip_arg, session_arg],
            )
        )
        router.patch(
            one, response_model=cls.envelope, responses=error_responses(400, 404, 409, 422)
        )(
            endpoint(
                update_row,
                f"update_{cls.resource}",
                cls.update_doc,
                [id_arg, update_arg, trip_arg, session_arg],
            )
        )
        router.delete(one, status_code=204, responses=error_responses(*cls.delete_statuses))(
            endpoint(
                delete_row,
                f"delete_{cls.resource}",
                cls.delete_doc,
                [id_arg, trip_arg, session_arg],
            )
        )
        return router
