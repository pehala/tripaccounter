"""Shared FastAPI dependencies for database sessions and trip resolution."""

from typing import Annotated

from fastapi import Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_session
from app.models import Trip
from app.services.errors import NotFoundError

SessionDep = Annotated[Session, Depends(get_session)]


def get_trip(slug: str, session: SessionDep) -> Trip:
    """Look up the trip by slug or raise a not-found error."""
    trip = session.execute(select(Trip).where(Trip.slug == slug)).scalar_one_or_none()
    if trip is None:
        raise NotFoundError("trip")
    return trip


TripDep = Annotated[Trip, Depends(get_trip)]
