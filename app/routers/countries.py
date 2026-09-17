"""Trip country routes: create, update, delete."""

from app.models.roster import TripCountry
from app.routers.crud import TripChildRoutes
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
    out = CountryOut
    create_body = CountryCreate
    update_body = CountryUpdate
    envelope = CountryEnvelope
    list_envelope = CountryListEnvelope
    list_doc = "List a trip's countries with their item counts."
    create_doc = "Add a new country to a trip."
    update_doc = "Update a trip country's fields."
    delete_doc = "Delete a country from a trip."

    @classmethod
    def serialize(cls, country, session):
        """Return the country with the number of items recorded in it."""
        counts = country_item_counts(session, country.trip_id)
        return CountryOut.from_country(country, counts.get(country.id, 0))

    @classmethod
    def create(cls, session, trip, body):
        """Add a new country to a trip."""
        return roster.create_country(session, trip, body.name, body.code, body.is_default)

    @classmethod
    def update(cls, session, country, body):
        """Update a trip country's fields."""
        return roster.update_country(
            session, country, body.name, body.code, body.is_default, body.sort_order
        )

    @classmethod
    def delete_row(cls, session, country):
        """Delete a country, raising if any item still uses it."""
        roster.delete_country(session, country)


router = CountryRoutes.router()
