"""Trip currency routes: create, update, delete."""

from app.models.roster import TripCurrency
from app.routers.crud import TripChildRoutes
from app.schemas.envelopes import CurrencyEnvelope, CurrencyListEnvelope
from app.schemas.requests import CurrencyCreate, CurrencyUpdate
from app.schemas.responses import CurrencyOut
from app.services import roster


class CurrencyRoutes(TripChildRoutes):
    """The currencies enabled for a trip."""

    model = TripCurrency
    resource = "currency"
    collection = "currencies"
    out = CurrencyOut
    create_body = CurrencyCreate
    update_body = CurrencyUpdate
    envelope = CurrencyEnvelope
    list_envelope = CurrencyListEnvelope
    conflict_field = "code"
    list_doc = "List a trip's currencies, in sort order."
    create_doc = "Add a new currency to a trip."
    update_doc = "Update a trip currency's fields."
    delete_doc = "Delete a currency from a trip."

    @classmethod
    def create(cls, session, trip, body):
        """Add a new currency to a trip."""
        return roster.create_currency(session, trip, body.code, body.symbol, body.is_primary)

    @classmethod
    def update(cls, session, currency, body):
        """Update a trip currency's fields."""
        return roster.update_currency(
            session, currency, body.symbol, body.is_primary, body.sort_order
        )

    @classmethod
    def delete_row(cls, session, currency):
        """Delete a currency, raising if any item or transfer still uses it."""
        roster.delete_currency(session, currency)


router = CurrencyRoutes.router()
