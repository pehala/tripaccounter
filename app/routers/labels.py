"""Label routes: create, update, delete."""

from fastapi import APIRouter, Response

from app.deps import SessionDep, TripDep
from app.models.labels import Label
from app.schemas.envelopes import LabelEnvelope, LabelListEnvelope
from app.schemas.error_shapes import error_responses
from app.schemas.requests import LabelCreate, LabelUpdate
from app.schemas.responses import LabelOut
from app.services import labels as labels_service
from app.services.errors.api import NotFoundError, run_field

router = APIRouter(tags=["labels"])


def _get_label(trip, label_id: int, session: SessionDep) -> Label:
    label = session.get(Label, label_id)
    if label is None or label.trip_id != trip.id:
        raise NotFoundError("label")
    return label


@router.get(
    "/trips/{slug}/labels", response_model=LabelListEnvelope, responses=error_responses(404)
)
def list_labels(trip: TripDep):
    """List a trip's labels, most used first."""
    ordered = sorted(trip.labels, key=lambda label: (-label.use_count, label.name))
    return {"labels": [LabelOut.from_label(label) for label in ordered]}


@router.post(
    "/trips/{slug}/labels",
    status_code=201,
    response_model=LabelEnvelope,
    responses=error_responses(400, 404, 409, 422),
)
def create_label(body: LabelCreate, trip: TripDep, session: SessionDep):
    """Create a new label on a trip."""
    label = run_field("name", labels_service.create_label, session, trip.id, body.name)
    return {"label": LabelOut.from_label(label)}


@router.patch(
    "/trips/{slug}/labels/{label_id}",
    response_model=LabelEnvelope,
    responses=error_responses(400, 404, 409, 422),
)
def update_label(label_id: int, body: LabelUpdate, trip: TripDep, session: SessionDep):
    """Rename a label."""
    label = _get_label(trip, label_id, session)
    label = run_field("name", labels_service.update_label, session, label, body.name)
    return {"label": LabelOut.from_label(label)}


@router.delete("/trips/{slug}/labels/{label_id}", status_code=204, responses=error_responses(404))
def delete_label(label_id: int, trip: TripDep, session: SessionDep):
    """Delete a label from a trip."""
    label = _get_label(trip, label_id, session)
    session.delete(label)
    session.flush()
    return Response(status_code=204)
