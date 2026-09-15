"""Label normalization, lookup, and use-count bookkeeping."""

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.items import LineItem
from app.models.labels import Label
from app.services.errors import DuplicateError

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
        use_count=0,
    )
    session.add(label)
    session.flush()
    return label


def set_item_labels(session: Session, item: LineItem, tokens: list[str]) -> None:
    """Replace the item's labels with those for the given tokens, adjusting use counts."""
    wanted: list[Label] = []
    seen_norms: set[str] = set()
    for token in tokens:
        norm = normalize(token)
        if norm in seen_norms:
            continue
        seen_norms.add(norm)
        wanted.append(get_or_create(session, item.trip_id, token))

    current_ids = {label.id for label in item.label_rows}
    wanted_ids = {label.id for label in wanted}

    for label in item.label_rows:
        if label.id not in wanted_ids:
            label.use_count = max(0, label.use_count - 1)
    for label in wanted:
        if label.id not in current_ids:
            label.use_count += 1

    item.label_rows = wanted


def release_item_labels(item: LineItem) -> None:
    """Decrement the use count of each label attached to this item."""
    for label in item.label_rows:
        label.use_count = max(0, label.use_count - 1)


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
