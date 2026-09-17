"""Label routes: create, update, delete."""

from fastapi import APIRouter, Response

from app.deps import SessionDep, TripDep
from app.models.labels import Label
from app.schemas.envelopes import LabelEnvelope, LabelListEnvelope
from app.schemas.error_shapes import error_responses
from app.schemas.requests import LabelCreate, LabelUpdate
from app.schemas.responses import LabelOut
from app.services import labels as labels_service
from app.services.errors.api import run_field
from app.services.scope import require_in_trip

router = APIRouter(tags=["labels"])


@router.get(
    "/trips/{slug}/labels", response_model=LabelListEnvelope, responses=error_responses(404)
)
def list_labels(trip: TripDep):
    """List a trip's labels, most used first."""
    ordered = sorted(trip.labels, key=lambda label: (-label.use_count, label.name))
    return {"labels": [LabelOut.model_validate(label) for label in ordered]}


@router.post(
    "/trips/{slug}/labels",
    status_code=201,
    response_model=LabelEnvelope,
    responses=error_responses(400, 404, 409, 422),
)
def create_label(body: LabelCreate, trip: TripDep, session: SessionDep):
    """Create a new label on a trip."""
    label = run_field("name", labels_service.create_label, session, trip.id, body.name)
    return {"label": LabelOut.model_validate(label)}


@router.patch(
    "/trips/{slug}/labels/{label_id}",
    response_model=LabelEnvelope,
    responses=error_responses(400, 404, 409, 422),
)
def update_label(label_id: int, body: LabelUpdate, trip: TripDep, session: SessionDep):
    """Rename a label."""
    label = require_in_trip(session, Label, label_id, trip.id, "label")
    label = run_field("name", labels_service.update_label, session, label, body.name)
    return {"label": LabelOut.model_validate(label)}


@router.delete("/trips/{slug}/labels/{label_id}", status_code=204, responses=error_responses(404))
def delete_label(label_id: int, trip: TripDep, session: SessionDep):
    """Delete a label from a trip."""
    label = require_in_trip(session, Label, label_id, trip.id, "label")
    session.delete(label)
    session.flush()
    return Response(status_code=204)
