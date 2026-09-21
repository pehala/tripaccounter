"""Wallet routes: CRUD, and the per-currency balances report on the same collection."""

from sqlalchemy.orm import Session

from app.models.roster import Person
from app.models.trip import Trip
from app.models.wallets import Wallet
from app.routers.crud import Route, TripChildRoutes, route
from app.schemas.envelopes import WalletEnvelope, WalletListEnvelope
from app.schemas.requests import WalletCreate, WalletUpdate
from app.schemas.responses import WalletReportOut
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
    envelope = WalletEnvelope
    list_envelope = WalletListEnvelope

    def serialize(
        self, wallet: Wallet | WalletReportOut, session: Session
    ) -> WalletReportOut | Wallet:
        """Return the row as it stands: a report row from `rows`, a `Wallet` from a write.

        Both reach the wire through the route's response model.
        """
        return wallet

    @route(Route.LIST)
    def rows(self, session: Session, trip: Trip) -> list[WalletReportOut]:
        """Get every wallet on the trip with its per-currency balances."""
        return wallet_balances(session, trip.id)

    @route(Route.CREATE)
    def create(self, session: Session, trip: Trip, body: WalletCreate) -> Wallet:
        """Add a new wallet, owned by one of the trip's people."""
        person = in_trip(session, Person, body.person_id, trip.id)
        if person is None:
            raise ValidationError({"person_id": NotInTripError()})
        return roster.create_wallet(session, trip, person, body.name, body.tracked)

    @route(Route.UPDATE)
    def update(self, session: Session, wallet: Wallet, body: WalletUpdate) -> Wallet:
        """Update a wallet's fields."""
        return roster.update_wallet(session, wallet, body.name, body.tracked, body.is_default)

    @route(Route.DELETE)
    def delete_row(self, session: Session, wallet: Wallet) -> None:
        """Delete a wallet from a trip."""
        roster.delete_wallet(session, wallet)


router = WalletRoutes().router()
