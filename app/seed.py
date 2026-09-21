"""Builds the demo trip `make seed` puts in the dev database."""

import argparse
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.db import SessionLocal
from app.models.items import ItemShare, LineItem
from app.models.labels import Label
from app.models.roster import Person, TripCountry, TripCurrency
from app.models.trip import Trip
from app.models.wallets import Wallet, WalletTransfer


@dataclass(frozen=True)
class SeedShare:
    """One person's stake in a seeded line item."""

    person_id: int
    weight_scaled: int
    owed_minor: int | None = None
    split_mode_exact: bool = False


@dataclass(frozen=True)
class SeedItem:
    """One seeded line item with the shares and labels that hang off it."""

    id: int
    name: str
    occurred_at: datetime
    currency_id: int
    amount_minor: int
    payer_id: int
    wallet_id: int
    country_id: int
    labels: tuple[str, ...]
    shares: tuple[SeedShare, ...]
    split_mode: str = "equal"
    map_url: str | None = None
    lat: str | None = None
    lon: str | None = None


EVERYONE_EQUAL = (
    SeedShare(person_id=1, weight_scaled=10000),
    SeedShare(person_id=2, weight_scaled=10000),
    SeedShare(person_id=3, weight_scaled=10000),
    SeedShare(person_id=4, weight_scaled=10000),
)

ITEMS = (
    SeedItem(
        id=42,
        name="Dinner at Messinn",
        occurred_at=datetime(2026, 9, 14, 19, 30, tzinfo=UTC),
        currency_id=1,
        amount_minor=1_840_000,
        payer_id=1,
        wallet_id=5,
        country_id=1,
        labels=("food", "restaurant"),
        shares=EVERYONE_EQUAL,
        map_url="https://maps.app.goo.gl/Kx9mNq2",
        lat="64.14930",
        lon="-21.94030",
    ),
    SeedItem(
        id=41,
        name="Fuel — N1 Selfoss",
        occurred_at=datetime(2026, 9, 14, 11, 5, tzinfo=UTC),
        currency_id=1,
        amount_minor=790_000,
        payer_id=3,
        wallet_id=3,
        country_id=1,
        labels=("fuel", "transport"),
        shares=EVERYONE_EQUAL,
        lat="63.93330",
        lon="-20.99000",
    ),
    SeedItem(
        id=40,
        name="Blue Lagoon tickets",
        occurred_at=datetime(2026, 9, 14, 9, 0, tzinfo=UTC),
        currency_id=2,
        amount_minor=4_000,
        payer_id=2,
        wallet_id=2,
        country_id=1,
        labels=("fun", "spa"),
        shares=(
            SeedShare(person_id=1, weight_scaled=10000),
            SeedShare(person_id=2, weight_scaled=10000),
            SeedShare(person_id=4, weight_scaled=10000),
        ),
    ),
    SeedItem(
        id=39,
        name="Guesthouse Vík, 2 nights",
        occurred_at=datetime(2026, 9, 13, 16, 0, tzinfo=UTC),
        currency_id=1,
        amount_minor=9_600_000,
        payer_id=4,
        wallet_id=4,
        country_id=1,
        labels=("lodging",),
        shares=(
            SeedShare(person_id=1, weight_scaled=10000),
            SeedShare(person_id=2, weight_scaled=10000),
            SeedShare(person_id=3, weight_scaled=10000),
            SeedShare(person_id=4, weight_scaled=5000),
        ),
        split_mode="shares",
        map_url="https://maps.app.goo.gl/Vik42",
    ),
    SeedItem(
        id=38,
        name="Layover lunch — Kastrup",
        occurred_at=datetime(2026, 9, 12, 12, 40, tzinfo=UTC),
        currency_id=3,
        amount_minor=48_000,
        payer_id=2,
        wallet_id=6,
        country_id=2,
        labels=("airport", "food"),
        shares=EVERYONE_EQUAL,
    ),
)


def add_item(session: Session, labels: dict[str, Label], spec: SeedItem) -> LineItem:
    """Insert one seeded line item together with its shares and label links; return it."""
    item = LineItem(
        id=spec.id,
        trip_id=1,
        occurred_at=spec.occurred_at,
        name=spec.name,
        note=None,
        currency_id=spec.currency_id,
        amount_minor=spec.amount_minor,
        payer_id=spec.payer_id,
        wallet_id=spec.wallet_id,
        country_id=spec.country_id,
        map_url=spec.map_url,
        lat=spec.lat,
        lon=spec.lon,
        split_mode=spec.split_mode,
        created_at=spec.occurred_at,
        updated_at=spec.occurred_at,
    )
    session.add(item)
    session.flush()
    for share in spec.shares:
        session.add(
            ItemShare(
                item_id=item.id,
                person_id=share.person_id,
                weight_scaled=share.weight_scaled,
                owed_minor=share.owed_minor,
                split_mode_exact=share.split_mode_exact,
            )
        )
    item.label_rows = [labels[name] for name in spec.labels]
    session.flush()
    return item


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
    session.flush()

    wallets = [
        Wallet(id=1, trip_id=1, person_id=1, name="Card", tracked=False, is_default=True),
        Wallet(id=2, trip_id=1, person_id=2, name="Card", tracked=False, is_default=True),
        Wallet(id=3, trip_id=1, person_id=3, name="Card", tracked=False, is_default=True),
        Wallet(id=4, trip_id=1, person_id=4, name="Card", tracked=False, is_default=True),
        Wallet(id=5, trip_id=1, person_id=1, name="Cash", tracked=True, is_default=False),
        Wallet(id=6, trip_id=1, person_id=2, name="Envelope", tracked=True, is_default=False),
    ]
    session.add_all(wallets)
    session.flush()

    currencies = [
        TripCurrency(id=1, trip_id=1, code="ISK", symbol="kr", is_primary=True),
        TripCurrency(id=2, trip_id=1, code="EUR", symbol="€", is_primary=False),
        TripCurrency(id=3, trip_id=1, code="DKK", symbol="kr.", is_primary=False),
    ]
    session.add_all(currencies)

    countries = [
        TripCountry(id=1, trip_id=1, name="Iceland", code="IS", is_default=True),
        TripCountry(id=2, trip_id=1, name="Denmark", code="DK", is_default=False),
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

    for spec in ITEMS:
        add_item(session, labels, spec)

    transfers = [
        # T1: Ann -> Bob, cross-owner, lands between item39 and item40.
        WalletTransfer(
            id=1,
            trip_id=1,
            occurred_at=datetime(2026, 9, 13, 18, 0, tzinfo=UTC),
            from_wallet_id=2,
            from_currency_id=1,
            from_amount_minor=500_000,
            to_wallet_id=3,
            to_currency_id=1,
            to_amount_minor=500_000,
            note=None,
        ),
        # T2: Petr funds Cash from Card, lands between item41 and item42.
        WalletTransfer(
            id=2,
            trip_id=1,
            occurred_at=datetime(2026, 9, 14, 12, 0, tzinfo=UTC),
            from_wallet_id=1,
            from_currency_id=1,
            from_amount_minor=2_000_000,
            to_wallet_id=5,
            to_currency_id=1,
            to_amount_minor=2_000_000,
            note=None,
        ),
        # T3: Petr exchanges inside Cash, lands between item38 and item39.
        WalletTransfer(
            id=3,
            trip_id=1,
            occurred_at=datetime(2026, 9, 13, 9, 0, tzinfo=UTC),
            from_wallet_id=5,
            from_currency_id=2,
            from_amount_minor=2_000,
            to_wallet_id=5,
            to_currency_id=3,
            to_amount_minor=15_000,
            note=None,
        ),
    ]
    session.add_all(transfers)

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
