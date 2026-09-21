"""Trip country routes: list, create, update, delete."""

from sqlalchemy.orm import Session

from app.models.roster import TripCountry
from app.models.trip import Trip
from app.routers.crud import Route, TripChildRoutes, route
from app.schemas.envelopes import CountryEnvelope, CountryListEnvelope
from app.schemas.requests import CountryCreate, CountryUpdate
from app.schemas.responses import CountryOut
from app.services import roster
from app.services.roster import country_item_counts


class CountryRoutes(TripChildRoutes):
    """The countries visited on a trip, each carrying its item count."""

    model = TripCountry
    resource = "country"
    collection = "countries"
    envelope = CountryEnvelope
    list_envelope = CountryListEnvelope

    def serialize(self, country: TripCountry, session: Session) -> CountryOut:
        """Return the country with the number of items recorded in it."""
        counts = country_item_counts(session, country.trip_id)
        return CountryOut.from_country(country, counts.get(country.id, 0))

    def serialize_list(
        self, countries: list[TripCountry], session: Session, trip: Trip
    ) -> list[CountryOut]:
        """Read the whole trip's item counts once, rather than one aggregate per country."""
        counts = country_item_counts(session, trip.id)
        return [
            CountryOut.from_country(country, counts.get(country.id, 0)) for country in countries
        ]

    @route(Route.LIST)
    def rows(self, session: Session, trip: Trip) -> list[TripCountry]:
        """List a trip's countries with their item counts."""
        return trip.countries

    @route(Route.CREATE)
    def create(self, session: Session, trip: Trip, body: CountryCreate) -> TripCountry:
        """Add a new country to a trip."""
        return roster.create_country(session, trip, body.name, body.code, body.is_default)

    @route(Route.UPDATE)
    def update(self, session: Session, country: TripCountry, body: CountryUpdate) -> TripCountry:
        """Update a trip country's fields."""
        return roster.update_country(
            session, country, body.name, body.code, body.is_default, body.sort_order
        )

    @route(Route.DELETE)
    def delete_row(self, session: Session, country: TripCountry) -> None:
        """Delete a country from a trip."""
        roster.delete_country(session, country)


router = CountryRoutes().router()
