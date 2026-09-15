"""Shared FastAPI dependencies for database sessions and trip resolution."""

from typing import Annotated

from fastapi import Depends
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.db import get_session
from app.models.roster import Person
from app.models.trip import Trip
from app.services.errors import NotFoundError

SessionDep = Annotated[Session, Depends(get_session)]


def get_trip(slug: str, session: SessionDep) -> Trip:
    """Look up the trip by slug or raise a not-found error.

    Eager-loads people -> wallets: TripOut.from_trip walks every person's
    wallets to build the flat `wallets` list, and a per-person lazy load
    there would be an N+1 (one extra query per person) on every trip read.
    """
    trip = session.execute(
        select(Trip)
        .where(Trip.slug == slug)
        .options(selectinload(Trip.people).selectinload(Person.wallets))
    ).scalar_one_or_none()
    if trip is None:
        raise NotFoundError("trip")
    return trip


TripDep = Annotated[Trip, Depends(get_trip)]
