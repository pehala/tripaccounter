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
        """Return the label's wire form, counting its items."""
        count = labels_service.use_counts(session, [label.id])[label.id]
        return LabelOut(id=label.id, name=label.name, color=label.color, use_count=count)

    def serialize_list(
        self, rows: list[tuple[Label, int]], session: Session, trip: Trip
    ) -> list[LabelOut]:
        """Return the wire forms of the counted labels `rows` produced."""
        return [
            LabelOut(id=label.id, name=label.name, color=label.color, use_count=count)
            for label, count in rows
        ]

    @route(Route.LIST)
    def rows(self, session: Session, trip: Trip) -> list[tuple[Label, int]]:
        """List a trip's labels, most used first."""
        return labels_service.list_with_use_counts(session, trip.id)

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
