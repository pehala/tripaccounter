"""Trip export routes: CSV and JSON download."""

import json

from fastapi import Query, Response
from fastapi.encoders import jsonable_encoder
from fastapi.routing import APIRouter

from app.deps import SessionDep, TripDep
from app.schemas.error_shapes import error_responses
from app.services import export
from app.services.errors.api import BadRequestError

router = APIRouter(tags=["export"])


@router.get(
    "/trips/{slug}/export",
    # A file download: the body is whatever `format` asked for, carried with
    # `Content-Disposition: attachment`, so the schema declares the two media
    # types this route can answer with.
    responses={
        200: {"content": {"text/csv": {}, "application/json": {}}},
        **error_responses(400, 404),
    },
)
def export_trip(trip: TripDep, session: SessionDep, format: str = Query(...)):
    """Export a trip as a CSV or JSON file download."""
    if format == "csv":
        content = export.export_csv(session, trip)
        return Response(
            content=content,
            media_type="text/csv",
            headers={"Content-Disposition": f'attachment; filename="{trip.slug}.csv"'},
        )
    if format == "json":
        payload = jsonable_encoder(export.export_json(session, trip))
        return Response(
            content=json.dumps(payload),
            media_type="application/json",
            headers={"Content-Disposition": f'attachment; filename="{trip.slug}.json"'},
        )
    raise BadRequestError()
