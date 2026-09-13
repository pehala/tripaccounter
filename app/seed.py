"""Builds the demo trip `make seed` puts in the dev database."""

import argparse
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.db import SessionLocal
from app.models import ItemShare, Label, LineItem, Person, Trip, TripCountry, TripCurrency


def seed_demo(session: Session) -> Trip:
    """Insert the demo trip, roster, currencies, countries, labels and items; return the trip."""
    trip = Trip(
        id=1,
        slug="iceland-2026",
        name="Iceland 2026",
        start_date="2026-09-12",
        end_date="2026-09-21",
        note=None,
        archived=False,
        created_at=datetime(2026, 9, 1, 8, 12, 0, tzinfo=UTC),
        updated_at=datetime(2026, 9, 12, 14, 2, 0, tzinfo=UTC),
    )
    session.add(trip)
    session.flush()

    people = [
        Person(
            id=1, trip_id=1, name="Petr", color="#0d6efd", default_weight_scaled=10000, sort_order=0
        ),
        Person(
            id=2, trip_id=1, name="Ann", color="#dc3545", default_weight_scaled=10000, sort_order=1
        ),
        Person(
            id=3, trip_id=1, name="Bob", color="#198754", default_weight_scaled=10000, sort_order=2
        ),
        Person(
            id=4, trip_id=1, name="Eva", color="#fd7e14", default_weight_scaled=5000, sort_order=3
        ),
    ]
    session.add_all(people)

    currencies = [
        TripCurrency(id=1, trip_id=1, code="ISK", symbol="kr", is_primary=True, sort_order=0),
        TripCurrency(id=2, trip_id=1, code="EUR", symbol="€", is_primary=False, sort_order=1),
        TripCurrency(id=3, trip_id=1, code="DKK", symbol="kr.", is_primary=False, sort_order=2),
    ]
    session.add_all(currencies)

    countries = [
        TripCountry(id=1, trip_id=1, name="Iceland", code="IS", is_default=True, sort_order=0),
        TripCountry(id=2, trip_id=1, name="Denmark", code="DK", is_default=False, sort_order=1),
    ]
    session.add_all(countries)

    label_names = [
        "food",
        "restaurant",
        "transport",
        "fuel",
        "fun",
        "spa",
        "lodging",
        "airport",
        "groceries",
        "drinks",
    ]
    use_counts = [2, 1, 1, 1, 1, 1, 1, 1, 0, 0]
    labels = {
        name: Label(
            id=i + 1, trip_id=1, name=name, name_norm=name, color="#6c757d", use_count=use_counts[i]
        )
        for i, name in enumerate(label_names)
    }
    session.add_all(labels.values())
    session.flush()

    def make_item(  # noqa: PLR0913, PLR0917
        item_id,
        name,
        occurred_at,
        currency_id,
        amount_minor,
        payer_id,
        country_id,
        label_names,
        map_url,
        lat,
        lon,
        split_mode,
        shares,
    ):
        item = LineItem(
            id=item_id,
            trip_id=1,
            occurred_at=occurred_at,
            name=name,
            note=None,
            currency_id=currency_id,
            amount_minor=amount_minor,
            payer_id=payer_id,
            country_id=country_id,
            map_url=map_url,
            lat=lat,
            lon=lon,
            split_mode=split_mode,
            created_at=occurred_at,
            updated_at=occurred_at,
        )
        session.add(item)
        session.flush()
        for person_id, weight_scaled, owed_minor, exact in shares:
            session.add(
                ItemShare(
                    item_id=item.id,
                    person_id=person_id,
                    weight_scaled=weight_scaled,
                    owed_minor=owed_minor,
                    split_mode_exact=exact,
                )
            )
        item.label_rows = [labels[n] for n in label_names]
        session.flush()
        return item

    make_item(
        42,
        "Dinner at Messinn",
        datetime(2026, 9, 14, 19, 30, tzinfo=UTC),
        1,
        1_840_000,
        1,
        1,
        ["food", "restaurant"],
        "https://maps.app.goo.gl/Kx9mNq2",
        "64.14930",
        "-21.94030",
        "equal",
        [
            (1, 10000, None, False),
            (2, 10000, None, False),
            (3, 10000, None, False),
            (4, 10000, None, False),
        ],
    )
    make_item(
        41,
        "Fuel — N1 Selfoss",
        datetime(2026, 9, 14, 11, 5, tzinfo=UTC),
        1,
        790_000,
        3,
        1,
        ["fuel", "transport"],
        None,
        "63.93330",
        "-20.99000",
        "equal",
        [
            (1, 10000, None, False),
            (2, 10000, None, False),
            (3, 10000, None, False),
            (4, 10000, None, False),
        ],
    )
    make_item(
        40,
        "Blue Lagoon tickets",
        datetime(2026, 9, 14, 9, 0, tzinfo=UTC),
        2,
        4_000,
        2,
        1,
        ["fun", "spa"],
        None,
        None,
        None,
        "equal",
        [(1, 10000, None, False), (2, 10000, None, False), (4, 10000, None, False)],
    )
    make_item(
        39,
        "Guesthouse Vík, 2 nights",
        datetime(2026, 9, 13, 16, 0, tzinfo=UTC),
        1,
        9_600_000,
        4,
        1,
        ["lodging"],
        "https://maps.app.goo.gl/Vik42",
        None,
        None,
        "shares",
        [
            (1, 10000, None, False),
            (2, 10000, None, False),
            (3, 10000, None, False),
            (4, 5000, None, False),
        ],
    )
    make_item(
        38,
        "Layover lunch — Kastrup",
        datetime(2026, 9, 12, 12, 40, tzinfo=UTC),
        3,
        48_000,
        2,
        2,
        ["airport", "food"],
        None,
        None,
        None,
        "equal",
        [
            (1, 10000, None, False),
            (2, 10000, None, False),
            (3, 10000, None, False),
            (4, 10000, None, False),
        ],
    )

    session.flush()
    return trip


def main() -> None:
    """Run the seed script from the command line."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--demo", action="store_true")
    parser.parse_args()

    with SessionLocal() as session:
        seed_demo(session)
        session.commit()


if __name__ == "__main__":
    main()
