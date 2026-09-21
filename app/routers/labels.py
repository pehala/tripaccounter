"""Label routes: list, create, update, delete."""

from sqlalchemy.orm import Session

from app.models.labels import Label
from app.models.trip import Trip
from app.routers.crud import Route, TripChildRoutes, route
from app.schemas.envelopes import LabelEnvelope, LabelListEnvelope
from app.schemas.requests import LabelCreate, LabelUpdate
from app.schemas.responses import LabelOut
from app.services import labels as labels_service


class LabelRoutes(TripChildRoutes):
    """A trip's labels, ordered by how much they are used."""

    model = Label
    resource = "label"
    collection = "labels"
    envelope = LabelEnvelope
    list_envelope = LabelListEnvelope

    def serialize(self, label: Label, session: Session) -> LabelOut:
        """Return the label's wire form."""
        return LabelOut.model_validate(label)

    @route(Route.LIST)
    def rows(self, session: Session, trip: Trip) -> list[Label]:
        """List a trip's labels, most used first."""
        return trip.labels

    @route(Route.CREATE)
    def create(self, session: Session, trip: Trip, body: LabelCreate) -> Label:
        """Create a new label on a trip."""
        return labels_service.create_label(session, trip.id, body.name)

    @route(Route.UPDATE)
    def update(self, session: Session, label: Label, body: LabelUpdate) -> Label:
        """Rename a label."""
        return labels_service.update_label(session, label, body.name)

    @route(Route.DELETE, statuses=(404,))
    def delete_row(self, session: Session, label: Label) -> None:
        """Delete a label from a trip."""
        labels_service.delete_label(session, label)


router = LabelRoutes().router()
