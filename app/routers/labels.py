"""Label routes: create, update, delete."""

from app.models.labels import Label
from app.routers.crud import TripChildRoutes
from app.schemas.envelopes import LabelEnvelope, LabelListEnvelope
from app.schemas.requests import LabelCreate, LabelUpdate
from app.schemas.responses import LabelOut
from app.services import labels as labels_service


class LabelRoutes(TripChildRoutes):
    """A trip's labels, ordered by how much they are used."""

    model = Label
    resource = "label"
    collection = "labels"
    out = LabelOut
    create_body = LabelCreate
    update_body = LabelUpdate
    envelope = LabelEnvelope
    list_envelope = LabelListEnvelope
    delete_statuses = (404,)
    list_doc = "List a trip's labels, most used first."
    create_doc = "Create a new label on a trip."
    update_doc = "Rename a label."
    delete_doc = "Delete a label from a trip."

    @classmethod
    def rows(cls, trip, session):
        """Return the trip's labels, most used first."""
        return sorted(trip.labels, key=lambda label: (-label.use_count, label.name))

    @classmethod
    def create(cls, session, trip, body):
        """Create a new label on a trip."""
        return labels_service.create_label(session, trip.id, body.name)

    @classmethod
    def update(cls, session, label, body):
        """Rename a label."""
        return labels_service.update_label(session, label, body.name)


router = LabelRoutes.router()
