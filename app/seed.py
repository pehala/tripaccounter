"""Builds the demo trip `make seed` puts in the dev database.

Every id is assigned by the database. The specs below number their own rows, and one
list per entity translates a spec number into the id that row actually got, so the
demo lands next to whatever trips the database already holds.
"""

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

# (name, colour, default weight)
PEOPLE = (
    ("Petr", "#0d6efd", 10000),
    ("Ann", "#dc3545", 10000),
    ("Bob", "#198754", 10000),
    ("Eva", "#fd7e14", 5000),
)

# (owner's spec number, name, tracked, is_default)
WALLETS = (
    (1, "Card", False, True),
    (2, "Card", False, True),
    (3, "Card", False, True),
    (4, "Card", False, True),
    (1, "Cash", True, False),
    (2, "Envelope", True, False),
)

# (code, symbol, is_primary)
CURRENCIES = (("ISK", "kr", True), ("EUR", "€", False), ("DKK", "kr.", False))

# (name, ISO code, is_default)
COUNTRIES = (("Iceland", "IS", True), ("Denmark", "DK", False))

# (name, use_count)
LABELS = (
    ("food", 2),
    ("restaurant", 1),
    ("transport", 1),
    ("fuel", 1),
    ("fun", 1),
    ("spa", 1),
    ("lodging", 1),
    ("airport", 1),
    ("groceries", 0),
    ("drinks", 0),
)


@dataclass(frozen=True)
class SeedShare:
    """One person's stake in a seeded line item."""

    person_key: int
    weight_scaled: int
    owed_minor: int | None = None
    split_mode_exact: bool = False


@dataclass(frozen=True)
class SeedItem:
    """One seeded line item with the shares and labels that hang off it.

    Every expense carries a city and coordinates: the demo is what the map tab is shown with.
    """

    name: str
    occurred_at: datetime
    currency_key: int
    amount_minor: int
    payer_key: int
    wallet_key: int
    country_key: int
    labels: tuple[str, ...]
    shares: tuple[SeedShare, ...]
    city: str
    lat: str
    lon: str
    split_mode: str = "equal"
    map_url: str | None = None


@dataclass(frozen=True)
class SeedTransfer:
    """One seeded movement of money between two wallets."""

    occurred_at: datetime
    from_wallet_key: int
    from_currency_key: int
    from_amount_minor: int
    to_wallet_key: int
    to_currency_key: int
    to_amount_minor: int


@dataclass(frozen=True)
class SeedIds:
    """The row ids each entity's spec numbers resolved to, in spec order."""

    people: list[int]
    wallets: list[int]
    currencies: list[int]
    countries: list[int]


EVERYONE_EQUAL = (
    SeedShare(person_key=1, weight_scaled=10000),
    SeedShare(person_key=2, weight_scaled=10000),
    SeedShare(person_key=3, weight_scaled=10000),
    SeedShare(person_key=4, weight_scaled=10000),
)

ITEMS = (
    SeedItem(
        name="Dinner at Messinn",
        city="Reykjavík",
        occurred_at=datetime(2026, 9, 14, 19, 30, tzinfo=UTC),
        currency_key=1,
        amount_minor=1_840_000,
        payer_key=1,
        wallet_key=5,
        country_key=1,
        labels=("food", "restaurant"),
        shares=EVERYONE_EQUAL,
        map_url="https://maps.app.goo.gl/Kx9mNq2",
        lat="64.14930",
        lon="-21.94030",
    ),
    SeedItem(
        name="Fuel — N1 Selfoss",
        city="Selfoss",
        occurred_at=datetime(2026, 9, 14, 11, 5, tzinfo=UTC),
        currency_key=1,
        amount_minor=790_000,
        payer_key=3,
        wallet_key=3,
        country_key=1,
        labels=("fuel", "transport"),
        shares=EVERYONE_EQUAL,
        lat="63.93330",
        lon="-20.99000",
    ),
    SeedItem(
        name="Blue Lagoon tickets",
        city="Grindavík",
        occurred_at=datetime(2026, 9, 14, 9, 0, tzinfo=UTC),
        currency_key=2,
        amount_minor=4_000,
        payer_key=2,
        wallet_key=2,
        country_key=1,
        labels=("fun", "spa"),
        shares=(
            SeedShare(person_key=1, weight_scaled=10000),
            SeedShare(person_key=2, weight_scaled=10000),
            SeedShare(person_key=4, weight_scaled=10000),
        ),
        lat="63.88040",
        lon="-22.44950",
    ),
    SeedItem(
        name="Guesthouse Vík, 2 nights",
        city="Vík í Mýrdal",
        occurred_at=datetime(2026, 9, 13, 16, 0, tzinfo=UTC),
        currency_key=1,
        amount_minor=9_600_000,
        payer_key=4,
        wallet_key=4,
        country_key=1,
        labels=("lodging",),
        shares=(
            SeedShare(person_key=1, weight_scaled=10000),
            SeedShare(person_key=2, weight_scaled=10000),
            SeedShare(person_key=3, weight_scaled=10000),
            SeedShare(person_key=4, weight_scaled=5000),
        ),
        split_mode="shares",
        map_url="https://maps.app.goo.gl/Vik42",
        lat="63.41870",
        lon="-19.00600",
    ),
    SeedItem(
        name="Layover lunch — Kastrup",
        city="København",
        occurred_at=datetime(2026, 9, 12, 12, 40, tzinfo=UTC),
        currency_key=3,
        amount_minor=48_000,
        payer_key=2,
        wallet_key=6,
        country_key=2,
        labels=("airport", "food"),
        shares=EVERYONE_EQUAL,
        lat="55.61800",
        lon="12.65600",
    ),
)

TRANSFERS = (
    # Ann -> Bob, cross-owner, lands between the guesthouse and the Blue Lagoon.
    SeedTransfer(
        occurred_at=datetime(2026, 9, 13, 18, 0, tzinfo=UTC),
        from_wallet_key=2,
        from_currency_key=1,
        from_amount_minor=500_000,
        to_wallet_key=3,
        to_currency_key=1,
        to_amount_minor=500_000,
    ),
    # Petr funds Cash from Card, lands between the fuel stop and the dinner.
    SeedTransfer(
        occurred_at=datetime(2026, 9, 14, 12, 0, tzinfo=UTC),
        from_wallet_key=1,
        from_currency_key=1,
        from_amount_minor=2_000_000,
        to_wallet_key=5,
        to_currency_key=1,
        to_amount_minor=2_000_000,
    ),
    # Petr exchanges inside Cash, lands between the layover and the guesthouse.
    SeedTransfer(
        occurred_at=datetime(2026, 9, 13, 9, 0, tzinfo=UTC),
        from_wallet_key=5,
        from_currency_key=2,
        from_amount_minor=2_000,
        to_wallet_key=5,
        to_currency_key=3,
        to_amount_minor=15_000,
    ),
)


def resolve(ids: list[int], key: int) -> int:
    """Return the row id a spec number stands for."""
    return ids[key - 1]


def add_roster(session: Session, trip_id: int) -> SeedIds:
    """Insert the people, wallets, currencies and countries; return the ids they got."""
    people = [
        Person(trip_id=trip_id, name=name, color=color, default_weight_scaled=weight, sort_order=i)
        for i, (name, color, weight) in enumerate(PEOPLE)
    ]
    currencies = [
        TripCurrency(trip_id=trip_id, code=code, symbol=symbol, is_primary=is_primary)
        for code, symbol, is_primary in CURRENCIES
    ]
    countries = [
        TripCountry(trip_id=trip_id, name=name, code=code, is_default=is_default)
        for name, code, is_default in COUNTRIES
    ]
    session.add_all([*people, *currencies, *countries])
    session.flush()

    person_ids = [person.id for person in people]
    wallets = [
        Wallet(
            trip_id=trip_id,
            person_id=resolve(person_ids, owner_key),
            name=name,
            tracked=tracked,
            is_default=is_default,
        )
        for owner_key, name, tracked, is_default in WALLETS
    ]
    session.add_all(wallets)
    session.flush()

    return SeedIds(
        people=person_ids,
        wallets=[wallet.id for wallet in wallets],
        currencies=[currency.id for currency in currencies],
        countries=[country.id for country in countries],
    )


def add_item(
    session: Session, trip_id: int, ids: SeedIds, labels: dict[str, Label], spec: SeedItem
) -> LineItem:
    """Insert one seeded line item together with its shares and label links; return it."""
    item = LineItem(
        trip_id=trip_id,
        occurred_at=spec.occurred_at,
        name=spec.name,
        note=None,
        city=spec.city,
        currency_id=resolve(ids.currencies, spec.currency_key),
        amount_minor=spec.amount_minor,
        payer_id=resolve(ids.people, spec.payer_key),
        wallet_id=resolve(ids.wallets, spec.wallet_key),
        country_id=resolve(ids.countries, spec.country_key),
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
                person_id=resolve(ids.people, share.person_key),
                weight_scaled=share.weight_scaled,
                owed_minor=share.owed_minor,
                split_mode_exact=share.split_mode_exact,
            )
        )
    item.label_rows = [labels[name] for name in spec.labels]
    session.flush()
    return item


def add_transfer(
    session: Session, trip_id: int, ids: SeedIds, spec: SeedTransfer
) -> WalletTransfer:
    """Insert one seeded wallet transfer; return it."""
    transfer = WalletTransfer(
        trip_id=trip_id,
        occurred_at=spec.occurred_at,
        from_wallet_id=resolve(ids.wallets, spec.from_wallet_key),
        from_currency_id=resolve(ids.currencies, spec.from_currency_key),
        from_amount_minor=spec.from_amount_minor,
        to_wallet_id=resolve(ids.wallets, spec.to_wallet_key),
        to_currency_id=resolve(ids.currencies, spec.to_currency_key),
        to_amount_minor=spec.to_amount_minor,
        note=None,
    )
    session.add(transfer)
    return transfer


def seed_demo(session: Session) -> Trip:
    """Insert the demo trip, roster, currencies, countries, labels and items; return the trip."""
    trip = Trip(
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

    ids = add_roster(session, trip.id)

    labels = {
        name: Label(
            trip_id=trip.id, name=name, name_norm=name, color="#6c757d", use_count=use_count
        )
        for name, use_count in LABELS
    }
    session.add_all(labels.values())
    session.flush()

    for spec in ITEMS:
        add_item(session, trip.id, ids, labels, spec)
    for spec in TRANSFERS:
        add_transfer(session, trip.id, ids, spec)

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
