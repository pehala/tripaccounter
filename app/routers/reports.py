"""Report routes: balances and statistics."""

from fastapi import APIRouter

from app.deps import SessionDep, TripDep
from app.schemas.envelopes import BalancesEnvelope
from app.schemas.error_shapes import error_responses
from app.schemas.responses import StatsOut
from app.services.balances import compute_balances
from app.services.stats import compute_stats

router = APIRouter(tags=["reports"])


@router.get(
    "/trips/{slug}/balances", response_model=BalancesEnvelope, responses=error_responses(404)
)
def get_balances(trip: TripDep, session: SessionDep):
    """Get who owes whom for a trip."""
    return {"balances": compute_balances(session, trip.id)}


@router.get("/trips/{slug}/stats", response_model=StatsOut, responses=error_responses(404))
def get_stats(trip: TripDep, session: SessionDep):
    """Get spending statistics for a trip."""
    return compute_stats(session, trip)
