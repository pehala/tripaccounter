"""Trip currency routes: list, create, update, delete."""

from sqlalchemy.orm import Session

from app.models.roster import TripCurrency
from app.models.trip import Trip
from app.routers.crud import Route, TripChildRoutes, route
from app.schemas.envelopes import CurrencyEnvelope, CurrencyListEnvelope
from app.schemas.requests import CurrencyCreate, CurrencyUpdate
from app.schemas.responses import CurrencyOut
from app.services import roster


class CurrencyRoutes(TripChildRoutes):
    """The currencies enabled for a trip."""

    model = TripCurrency
    resource = "currency"
    collection = "currencies"
    envelope = CurrencyEnvelope
    list_envelope = CurrencyListEnvelope

    def serialize(self, currency: TripCurrency, session: Session) -> CurrencyOut:
        """Return the currency's wire form."""
        return CurrencyOut.model_validate(currency)

    @route(Route.LIST)
    def rows(self, session: Session, trip: Trip) -> list[TripCurrency]:
        """List a trip's currencies, in sort order."""
        return trip.currencies

    @route(Route.CREATE, field="code")
    def create(self, session: Session, trip: Trip, body: CurrencyCreate) -> TripCurrency:
        """Add a new currency to a trip."""
        return roster.create_currency(session, trip, body.code, body.symbol, body.is_primary)

    @route(Route.UPDATE, field="code")
    def update(
        self, session: Session, currency: TripCurrency, body: CurrencyUpdate
    ) -> TripCurrency:
        """Update a trip currency's fields."""
        return roster.update_currency(
            session, currency, body.symbol, body.is_primary, body.sort_order
        )

    @route(Route.DELETE)
    def delete_row(self, session: Session, currency: TripCurrency) -> None:
        """Delete a currency from a trip."""
        roster.delete_currency(session, currency)


router = CurrencyRoutes().router()
