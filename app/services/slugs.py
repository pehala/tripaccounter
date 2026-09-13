"""Generate URL-safe, unique trip slugs from a trip name."""

import re
import secrets
import unicodedata

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Trip

_NON_ALNUM = re.compile(r"[^a-z0-9]+")


def base_slug(name: str) -> str:
    """Return an ASCII, lowercase, dash-separated slug derived from the name."""
    stripped = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode("ascii")
    slug = _NON_ALNUM.sub("-", stripped.lower()).strip("-")
    slug = slug[:60].strip("-")
    if not slug:
        slug = secrets.token_hex(4)
    return slug


def unique_slug(session: Session, name: str) -> str:
    """Return a slug for the name, appending a numeric suffix if it's already taken."""
    candidate = base_slug(name)
    slug = candidate
    suffix = 2
    while session.execute(select(Trip.id).where(Trip.slug == slug)).first() is not None:
        slug = f"{candidate}-{suffix}"
        suffix += 1
    return slug
