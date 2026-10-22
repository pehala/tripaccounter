"""Builds the demo trips `make seed` puts in the dev database.

`iceland-2026` is the open trip every tab is shown with; `faroe-2025` is the same
group's earlier trip, settled, so the demo also shows a locked one.

Every id is assigned by the database. The specs below number their own rows, and one
list per entity translates a spec number into the id that row actually got, so the
demo lands next to whatever trips the database already holds.
"""

import argparse
from dataclasses import dataclass
from datetime import UTC, date, datetime

from sqlalchemy.orm import Session

from app.db import SessionLocal
from app.models.items import ItemShare, LineItem
from app.models.labels import Label
from app.models.roster import Person, TripCountry, TripCurrency
from app.models.stays import Stay
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
FAROE_CURRENCIES = (("DKK", "kr.", True), ("EUR", "€", False))

# (name, ISO code, is_default)
COUNTRIES = (("Iceland", "IS", True), ("Denmark", "DK", False))
FAROE_COUNTRIES = (("Faroe Islands", "FO", True),)

FAROE_LABELS = ("food", "lodging", "transport")
LABELS = (
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
    stay_key: int | None = None


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


@dataclass(frozen=True)
class SeedSettlement:
    """A settled trip's agreement: the target's spec number and each other currency's rate."""

    settled_at: datetime
    target_key: int
    # (currency spec number, rate ×10⁹)
    rates: tuple[tuple[int, int], ...]


@dataclass(frozen=True)
class SeedTrip:
    """One seeded trip: its own fields, roster specs, rows and, when settled, its agreement."""

    slug: str
    name: str
    start_date: str
    end_date: str
    timezone: str
    created_at: datetime
    updated_at: datetime
    currencies: tuple[tuple[str, str, bool], ...]
    countries: tuple[tuple[str, str, bool], ...]
    labels: tuple[str, ...]
    items: tuple["SeedItem", ...]
    transfers: tuple[SeedTransfer, ...]
    stays: tuple[tuple, ...] = ()
    settlement: SeedSettlement | None = None


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
        map_url="https://example.com/Kx9mNq2",
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
        stay_key=1,
        shares=(
            SeedShare(person_key=1, weight_scaled=10000),
            SeedShare(person_key=2, weight_scaled=10000),
            SeedShare(person_key=3, weight_scaled=10000),
            SeedShare(person_key=4, weight_scaled=5000),
        ),
        split_mode="shares",
        map_url="https://example.com/Vik42",
        lat="63.41870",
        lon="-19.00600",
    ),
    SeedItem(
        name="Hotel Borg, 3 nights",
        city="Reykjavík",
        occurred_at=datetime(2026, 9, 15, 15, 0, tzinfo=UTC),
        currency_key=1,
        amount_minor=21_000_000,
        payer_key=1,
        wallet_key=5,
        country_key=1,
        labels=("lodging",),
        stay_key=2,
        shares=EVERYONE_EQUAL,
        lat="64.14700",
        lon="-21.93900",
    ),
    SeedItem(
        name="Hotel Borg breakfast",
        city="Reykjavík",
        occurred_at=datetime(2026, 9, 16, 8, 30, tzinfo=UTC),
        currency_key=1,
        amount_minor=1_200_000,
        payer_key=3,
        wallet_key=3,
        country_key=1,
        labels=("food",),
        stay_key=2,
        shares=EVERYONE_EQUAL,
        lat="64.14700",
        lon="-21.93900",
    ),
    SeedItem(
        name="Airport Hotel Kastrup, 1 night",
        city="København",
        occurred_at=datetime(2026, 9, 12, 21, 0, tzinfo=UTC),
        currency_key=3,
        amount_minor=32_000,
        payer_key=2,
        wallet_key=6,
        country_key=2,
        labels=("lodging",),
        stay_key=3,
        shares=EVERYONE_EQUAL,
        lat="55.62900",
        lon="12.64800",
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
    SeedItem(
        name="Car rental, booked in advance",
        city="Keflavík",
        occurred_at=datetime(2026, 9, 5, 10, 15, tzinfo=UTC),
        currency_key=2,
        amount_minor=32_000,
        payer_key=1,
        wallet_key=1,
        country_key=1,
        labels=("transport",),
        shares=EVERYONE_EQUAL,
        lat="63.99990",
        lon="-22.62400",
    ),
    SeedItem(
        name="Whale watching, pre-booked",
        city="Húsavík",
        occurred_at=datetime(2026, 9, 8, 18, 45, tzinfo=UTC),
        currency_key=2,
        amount_minor=24_000,
        payer_key=3,
        wallet_key=3,
        country_key=1,
        labels=("fun",),
        shares=EVERYONE_EQUAL,
        lat="66.04490",
        lon="-17.33830",
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
    # Petr withdraws ISK into Cash on his EUR Card, lands between the fuel stop and the dinner.
    SeedTransfer(
        occurred_at=datetime(2026, 9, 14, 12, 0, tzinfo=UTC),
        from_wallet_key=1,
        from_currency_key=2,
        from_amount_minor=14_000,
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


# (name, check-in, check-out, booking link, country spec number, city, lat, lon)
STAYS = (
    (
        "Guesthouse Vík",
        date(2026, 9, 13),
        date(2026, 9, 15),
        "https://example.com/guesthouse-vik",
        1,
        "Vík í Mýrdal",
        "63.41870",
        "-19.00600",
    ),
    (
        "Hotel Borg",
        date(2026, 9, 15),
        date(2026, 9, 18),
        "https://example.com/hotel-borg",
        1,
        "Reykjavík",
        "64.14700",
        "-21.93900",
    ),
    (
        "Airport Hotel Kastrup",
        date(2026, 9, 12),
        date(2026, 9, 13),
        "https://example.com/kastrup-hotel",
        2,
        "København",
        "55.62900",
        "12.64800",
    ),
)

FAROE_ITEMS = (
    SeedItem(
        name="Guesthouse Tórshavn, 3 nights",
        city="Tórshavn",
        occurred_at=datetime(2025, 6, 6, 15, 0, tzinfo=UTC),
        currency_key=1,
        amount_minor=480_000,
        payer_key=2,
        wallet_key=2,
        country_key=1,
        labels=("lodging",),
        shares=EVERYONE_EQUAL,
        lat="62.01100",
        lon="-6.77160",
    ),
    SeedItem(
        name="Ferry to Mykines",
        city="Sørvágur",
        occurred_at=datetime(2025, 6, 7, 8, 30, tzinfo=UTC),
        currency_key=2,
        amount_minor=12_000,
        payer_key=1,
        wallet_key=1,
        country_key=1,
        labels=("transport",),
        shares=EVERYONE_EQUAL,
        lat="62.07120",
        lon="-7.31440",
    ),
    SeedItem(
        name="Fish soup at Barbara",
        city="Tórshavn",
        occurred_at=datetime(2025, 6, 8, 19, 0, tzinfo=UTC),
        currency_key=1,
        amount_minor=96_000,
        payer_key=3,
        wallet_key=3,
        country_key=1,
        labels=("food",),
        shares=EVERYONE_EQUAL,
        lat="62.01030",
        lon="-6.77300",
    ),
)

TRIPS = (
    SeedTrip(
        slug="iceland-2026",
        name="Iceland 2026",
        start_date="2026-09-12",
        end_date="2026-09-21",
        timezone="Atlantic/Reykjavik",
        created_at=datetime(2026, 9, 1, 8, 12, 0, tzinfo=UTC),
        updated_at=datetime(2026, 9, 12, 14, 2, 0, tzinfo=UTC),
        currencies=CURRENCIES,
        countries=COUNTRIES,
        labels=LABELS,
        items=ITEMS,
        transfers=TRANSFERS,
        stays=STAYS,
    ),
    SeedTrip(
        slug="faroe-2025",
        name="Faroe Islands 2025",
        start_date="2025-06-06",
        end_date="2025-06-09",
        timezone="Atlantic/Faroe",
        created_at=datetime(2025, 5, 20, 9, 0, 0, tzinfo=UTC),
        updated_at=datetime(2025, 6, 10, 18, 30, 0, tzinfo=UTC),
        currencies=FAROE_CURRENCIES,
        countries=FAROE_COUNTRIES,
        labels=FAROE_LABELS,
        items=FAROE_ITEMS,
        transfers=(),
        # Settled in EUR: 1 DKK = 0.134 EUR.
        settlement=SeedSettlement(
            settled_at=datetime(2025, 6, 10, 18, 30, 0, tzinfo=UTC),
            target_key=2,
            rates=((1, 134_000_000),),
        ),
    ),
)


def resolve(ids: list[int], key: int) -> int:
    """Return the row id a spec number stands for."""
    return ids[key - 1]


def add_roster(session: Session, trip_id: int, spec: SeedTrip) -> SeedIds:
    """Insert the people, wallets, currencies and countries; return the ids they got."""
    people = [
        Person(trip_id=trip_id, name=name, color=color, default_weight_scaled=weight, sort_order=i)
        for i, (name, color, weight) in enumerate(PEOPLE)
    ]
    currencies = [
        TripCurrency(trip_id=trip_id, code=code, symbol=symbol, is_primary=is_primary)
        for code, symbol, is_primary in spec.currencies
    ]
    countries = [
        TripCountry(trip_id=trip_id, name=name, code=code, is_default=is_default)
        for name, code, is_default in spec.countries
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


def add_stays(session: Session, trip_id: int, ids: SeedIds, spec: SeedTrip) -> list[int]:
    """Insert the stays; return the ids they got."""
    stays = [
        Stay(
            trip_id=trip_id,
            name=name,
            check_in=check_in,
            check_out=check_out,
            url=url,
            country_id=resolve(ids.countries, country_key),
            city=city,
            lat=lat,
            lon=lon,
        )
        for name, check_in, check_out, url, country_key, city, lat, lon in spec.stays
    ]
    session.add_all(stays)
    session.flush()
    return [stay.id for stay in stays]


def add_item(  # noqa: PLR0913, PLR0917
    session: Session,
    trip: Trip,
    ids: SeedIds,
    labels: dict[str, Label],
    stay_ids: list[int],
    spec: SeedItem,
) -> LineItem:
    """Insert one seeded line item, in the trip's zone, with its shares and label links."""
    item = LineItem(
        trip_id=trip.id,
        occurred_at=spec.occurred_at,
        occurred_tz=trip.timezone,
        name=spec.name,
        note=None,
        city=spec.city,
        currency_id=resolve(ids.currencies, spec.currency_key),
        amount_minor=spec.amount_minor,
        payer_id=resolve(ids.people, spec.payer_key),
        wallet_id=resolve(ids.wallets, spec.wallet_key),
        country_id=resolve(ids.countries, spec.country_key),
        stay_id=resolve(stay_ids, spec.stay_key) if spec.stay_key else None,
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


def add_transfer(session: Session, trip: Trip, ids: SeedIds, spec: SeedTransfer) -> WalletTransfer:
    """Insert one seeded wallet transfer, in the trip's zone; return it."""
    transfer = WalletTransfer(
        trip_id=trip.id,
        occurred_at=spec.occurred_at,
        occurred_tz=trip.timezone,
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


def settle(session: Session, trip: Trip, ids: SeedIds, spec: SeedSettlement) -> None:
    """Store a seeded agreement: target and settled_at on the trip, a rate on each currency."""
    rates = {resolve(ids.currencies, key): rate for key, rate in spec.rates}
    for currency in trip.currencies:
        currency.settlement_rate_scaled = rates.get(currency.id)
    trip.settlement_currency_id = resolve(ids.currencies, spec.target_key)
    trip.settled_at = spec.settled_at
    session.flush()


def add_trip(session: Session, spec: SeedTrip) -> Trip:
    """Insert one seeded trip with everything under it; return the trip."""
    trip = Trip(
        slug=spec.slug,
        name=spec.name,
        start_date=spec.start_date,
        end_date=spec.end_date,
        timezone=spec.timezone,
        note=None,
        archived=False,
        created_at=spec.created_at,
        updated_at=spec.updated_at,
    )
    session.add(trip)
    session.flush()

    ids = add_roster(session, trip.id, spec)

    labels = {
        name: Label(trip_id=trip.id, name=name, name_norm=name, color="#6c757d")
        for name in spec.labels
    }
    session.add_all(labels.values())
    session.flush()

    stay_ids = add_stays(session, trip.id, ids, spec)
    for item in spec.items:
        add_item(session, trip, ids, labels, stay_ids, item)
    for transfer in spec.transfers:
        add_transfer(session, trip, ids, transfer)
    session.flush()

    if spec.settlement is not None:
        session.refresh(trip)
        settle(session, trip, ids, spec.settlement)
    return trip


def seed_demo(session: Session) -> list[Trip]:
    """Insert every demo trip, with its roster, labels, stays, items and transfers; return them."""
    return [add_trip(session, spec) for spec in TRIPS]


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
