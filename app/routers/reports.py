"""Report routes: balances and statistics."""

from typing import Annotated

from fastapi import APIRouter, Query

from app.deps import SessionDep, TripDep
from app.schemas.envelopes import BalancesEnvelope
from app.schemas.error_shapes import error_responses
from app.schemas.responses import StatsOut
from app.services.balances import compute_balances
from app.services.errors.api import field_errors
from app.services.stats import compute_stats, expand_groupings

router = APIRouter(tags=["reports"])


@router.get(
    "/trips/{slug}/balances", response_model=BalancesEnvelope, responses=error_responses(404)
)
def get_balances(trip: TripDep, session: SessionDep):
    """Get who owes whom for a trip."""
    return {"balances": compute_balances(session, trip.id)}


@router.get("/trips/{slug}/stats", response_model=StatsOut, responses=error_responses(404, 422))
def get_stats(
    trip: TripDep,
    session: SessionDep,
    group_by: Annotated[
        list[str],
        Query(
            default_factory=list,
            description="A comma-separated dimension chain; repeat for several breakdowns.",
        ),
    ],
):
    """Get spending statistics for a trip, grouped by the requested dimension chains."""
    with field_errors("group_by"):
        chains = expand_groupings(group_by)
    return compute_stats(session, trip, chains)
