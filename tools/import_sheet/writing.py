"""Write a resolved plan onto a new trip, inside the caller's transaction.

This is `routers/items.create_item` with the HTTP removed: the same `ItemWrite`
validation, the same `build_shares`, the same label bookkeeping. Nothing is
committed here, so the caller decides between a dry run and an import.
"""

from app.models.items import ItemShare, LineItem
from app.models.trip import Trip
from app.schemas.requests import ItemWrite
from app.services import labels as label_service
from app.services import roster, slugs, splits
from app.services.money import to_hundredths


def create_trip(session, name, start_date, end_date):
    """Create an empty trip with a unique slug derived from its name."""
    trip = Trip(
        slug=slugs.unique_slug(session, name), name=name, start_date=start_date, end_date=end_date
    )
    session.add(trip)
    session.flush()
    return trip


def create_roster(session, trip, plan):
    """Create the trip's people, currencies and countries, keyed by the names the plan uses.

    A country is created with its ISO code as its name; the flag comes from the code
    and the name is editable in Setup.
    """
    people = {name: roster.create_person(session, trip, name, None, None) for name in plan.people}
    currencies = {
        code: roster.create_currency(session, trip, code, None, index == 0)
        for index, code in enumerate(plan.currencies)
    }
    countries = {
        code: roster.create_country(session, trip, code, code, None) for code in plan.countries
    }
    return people, currencies, countries


def apply(session, plan, trip):
    """Write every planned item onto the freshly created trip, roster and all."""
    people, currencies, countries = create_roster(session, trip, plan)
    person_ids = [person.id for person in people.values()]

    for planned in plan.items:
        currency = currencies[planned.currency_code]
        payer = people[planned.payer]
        wallet = roster.default_wallet(session, payer.id)
        body = ItemWrite(
            name=planned.name,
            note=planned.note,
            city=planned.city,
            amount=planned.amount,
            occurred_at=planned.occurred_at,
            labels=list(planned.item_labels),
            split_mode=planned.split_mode,
            shares=[
                {**share, "person_id": people[share["person_id"]].id} for share in planned.shares
            ],
        )
        rows = splits.build_shares(
            body.split_mode, body.shares, person_ids, body.amount, currency.code
        )
        item = LineItem(
            trip_id=trip.id,
            name=body.name,
            note=body.note,
            city=body.city,
            occurred_at=body.occurred_at,
            currency_id=currency.id,
            amount_minor=to_hundredths(body.amount),
            payer_id=payer.id,
            wallet_id=wallet.id,
            country_id=countries[planned.country_code].id,
            split_mode=body.split_mode,
        )
        session.add(item)
        session.flush()
        for share in rows:
            session.add(
                ItemShare(
                    item_id=item.id,
                    person_id=share["person_id"],
                    weight_scaled=share["weight_scaled"],
                    owed_minor=share["owed_minor"],
                    split_mode_exact=share["exact"],
                )
            )
        label_service.set_item_labels(session, item, body.labels or [])
    session.flush()
    session.expire(trip)
    return trip
