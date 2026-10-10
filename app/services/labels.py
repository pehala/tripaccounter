"""Label normalization, lookup, and per-label item counts."""

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.items import LineItem
from app.models.labels import ItemLabel, Label
from app.services.errors.fields import DuplicateError

PALETTE = [
    "#6c757d",
    "#0d6efd",
    "#dc3545",
    "#198754",
    "#fd7e14",
    "#6f42c1",
    "#20c997",
    "#d63384",
]


def normalize(name: str) -> str:
    """Return the label token folded to its comparison form: trimmed, casefolded, dash-stripped."""
    return name.strip().casefold().strip("-")


def get_or_create(session: Session, trip_id: int, token: str) -> Label:
    """Return the trip's existing label matching this token, creating one if none exists."""
    norm = normalize(token)
    existing = session.execute(
        select(Label).where(Label.trip_id == trip_id, Label.name_norm == norm)
    ).scalar_one_or_none()
    if existing is not None:
        return existing

    count = session.execute(
        select(func.count()).select_from(Label).where(Label.trip_id == trip_id)
    ).scalar_one()
    label = Label(
        trip_id=trip_id,
        name=token,
        name_norm=norm,
        color=PALETTE[count % len(PALETTE)],
    )
    session.add(label)
    session.flush()
    return label


def set_item_labels(session: Session, item: LineItem, tokens: list[str]) -> None:
    """Replace the item's labels with those for the given tokens; labels it leaves unused go."""
    wanted: list[Label] = []
    seen_norms: set[str] = set()
    for token in tokens:
        norm = normalize(token)
        if norm in seen_norms:
            continue
        seen_norms.add(norm)
        wanted.append(get_or_create(session, item.trip_id, token))

    previous = item.label_rows
    item.label_rows = wanted
    session.flush()
    prune_unused(session, [label for label in previous if label not in wanted])


def prune_unused(session: Session, labels: list[Label]) -> None:
    """Delete each of the given labels that no item carries any more."""
    counts = use_counts(session, [label.id for label in labels])
    for label in labels:
        if counts[label.id] == 0:
            session.delete(label)
    session.flush()


def use_counts(session: Session, label_ids: list[int]) -> dict[int, int]:
    """Return how many items carry each of the given labels; unused labels map to 0."""
    rows = session.execute(
        select(ItemLabel.label_id, func.count())
        .where(ItemLabel.label_id.in_(label_ids))
        .group_by(ItemLabel.label_id)
    ).all()
    counts = dict(rows)
    return {label_id: counts.get(label_id, 0) for label_id in label_ids}


def list_with_use_counts(session: Session, trip_id: int) -> list[tuple[Label, int]]:
    """Return the trip's labels with their item counts, most used first, in one query."""
    uses = func.count(ItemLabel.item_id)
    rows = session.execute(
        select(Label, uses)
        .outerjoin(ItemLabel, ItemLabel.label_id == Label.id)
        .where(Label.trip_id == trip_id)
        .group_by(Label.id)
        .order_by(uses.desc(), Label.name)
    ).all()
    return [(label, count) for label, count in rows]


def create_label(session: Session, trip_id: int, name: str) -> Label:
    """Create a new label for the trip, raising on a duplicate normalized name."""
    norm = normalize(name)
    exists = session.execute(
        select(Label.id).where(Label.trip_id == trip_id, Label.name_norm == norm)
    ).first()
    if exists:
        raise DuplicateError(name=name)
    return get_or_create(session, trip_id, name)


def update_label(session: Session, label: Label, name: str | None) -> Label:
    """Rename the label if a new name is given, raising on a duplicate normalized name."""
    if name is not None:
        norm = normalize(name)
        exists = session.execute(
            select(Label.id).where(
                Label.trip_id == label.trip_id, Label.name_norm == norm, Label.id != label.id
            )
        ).first()
        if exists:
            raise DuplicateError(name=name)
        label.name = name
        label.name_norm = norm
    session.flush()
    return label


def delete_label(session: Session, label: Label) -> None:
    """Delete the label from its trip; the database detaches it from every item."""
    session.delete(label)
    session.flush()
