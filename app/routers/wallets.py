"""Wallet routes: CRUD, and the per-currency balances report on the same collection."""

from app.models.roster import Person
from app.models.wallets import Wallet
from app.routers.crud import TripChildRoutes
from app.schemas.envelopes import WalletEnvelope, WalletListEnvelope
from app.schemas.requests import WalletCreate, WalletUpdate
from app.schemas.responses import WalletOut
from app.services import roster
from app.services.errors.api import ValidationError
from app.services.errors.fields import NotInTripError
from app.services.scope import in_trip
from app.services.wallets import wallet_balances


class WalletRoutes(TripChildRoutes):
    """A trip's wallets; the collection answers with balances, a single wallet without."""

    model = Wallet
    resource = "wallet"
    collection = "wallets"
    out = WalletOut
    create_body = WalletCreate
    update_body = WalletUpdate
    envelope = WalletEnvelope
    list_envelope = WalletListEnvelope
    list_doc = "Get every wallet on the trip with its per-currency balances."
    create_doc = "Add a new wallet, owned by one of the trip's people."
    update_doc = "Update a wallet's fields."
    delete_doc = "Delete a wallet from a trip."

    @classmethod
    def rows(cls, trip, session):
        """Return every wallet already in its report form, balances included."""
        return wallet_balances(session, trip.id)

    @classmethod
    def serialize(cls, report, session):
        """Return the report row as built; `wallet_balances` is already the wire form."""
        return report

    @classmethod
    def create(cls, session, trip, body):
        """Add a new wallet, owned by one of the trip's people."""
        person = in_trip(session, Person, body.person_id, trip.id)
        if person is None:
            raise ValidationError({"person_id": NotInTripError()})
        return roster.create_wallet(session, trip, person, body.name, body.tracked)

    @classmethod
    def update(cls, session, wallet, body):
        """Update a wallet's fields."""
        return roster.update_wallet(
            session, wallet, body.name, body.tracked, body.is_default, body.sort_order
        )

    @classmethod
    def delete_row(cls, session, wallet):
        """Delete a wallet, raising if it is a default or still referenced."""
        roster.delete_wallet(session, wallet)


router = WalletRoutes.router()
