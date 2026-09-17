"""People / currencies / countries / wallets: the uniform CRUD validations."""

import re

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.models.items import ItemShare, LineItem
from app.models.roster import Person, TripCountry, TripCurrency
from app.models.trip import Trip
from app.models.wallets import Wallet, WalletTransfer
from app.services.errors.fields import (
    DuplicateError,
    InUseError,
    InvalidCodeError,
    IsDefaultError,
    RequiredError,
    TooLongError,
)
from app.services.labels import PALETTE

CODE_RE = re.compile(r"^[A-Za-z]{3}$")

DEFAULT_WALLET_NAME = "Card"
WALLET_NAME_MAX = 60


def _validate_wallet_name(name: str) -> None:
    if len(name.strip()) < 1:
        raise RequiredError()
    if len(name) > WALLET_NAME_MAX:
        raise TooLongError(max=WALLET_NAME_MAX)


# ---- Person ------------------------------------------------------------------


def create_person(
    session: Session, trip: Trip, name: str, default_weight, color: str | None
) -> Person:
    """Create a person on the trip's roster, raising on a duplicate name."""
    exists = session.execute(
        select(Person.id).where(Person.trip_id == trip.id, Person.name == name)
    ).first()
    if exists:
        raise DuplicateError(name=name)

    count = session.execute(
        select(func.count()).select_from(Person).where(Person.trip_id == trip.id)
    ).scalar_one()
    person = Person(
        trip_id=trip.id,
        name=name,
        color=color or PALETTE[count % len(PALETTE)],
        default_weight_scaled=int(default_weight * 10000) if default_weight is not None else 10000,
        sort_order=count,
        active=True,
    )
    session.add(person)
    session.flush()
    create_default_wallet(session, person)
    return person


def update_person(  # noqa: PLR0913, PLR0917
    session: Session, person: Person, name, default_weight, active, sort_order
) -> Person:
    """Apply the given field updates to a person, raising on a duplicate name."""
    if name is not None and name != person.name:
        exists = session.execute(
            select(Person.id).where(
                Person.trip_id == person.trip_id, Person.name == name, Person.id != person.id
            )
        ).first()
        if exists:
            raise DuplicateError(name=name)
        person.name = name
    if default_weight is not None:
        person.default_weight_scaled = int(default_weight * 10000)
    if active is not None:
        person.active = active
    if sort_order is not None:
        person.sort_order = sort_order
    session.flush()
    return person


def delete_person(session: Session, person: Person) -> None:
    """Delete a person, raising if they still pay/share any item or hold a wallet in a transfer."""
    referenced = session.execute(
        select(func.count()).select_from(LineItem).where(LineItem.payer_id == person.id)
    ).scalar_one()
    if referenced:
        raise InUseError(count=referenced, name=person.name)
    share_count = session.execute(
        select(func.count()).select_from(ItemShare).where(ItemShare.person_id == person.id)
    ).scalar_one()
    if share_count:
        raise InUseError(count=share_count, name=person.name)
    transfer_count = session.execute(
        select(func.count())
        .select_from(WalletTransfer)
        .join(
            Wallet,
            or_(
                WalletTransfer.from_wallet_id == Wallet.id,
                WalletTransfer.to_wallet_id == Wallet.id,
            ),
        )
        .where(Wallet.person_id == person.id)
    ).scalar_one()
    if transfer_count:
        raise InUseError(count=transfer_count, name=person.name)
    session.delete(person)
    session.flush()


# ---- Currency ------------------------------------------------------------------


def create_currency(
    session: Session, trip: Trip, code: str, symbol: str | None, is_primary: bool | None
) -> TripCurrency:
    """Create a currency on the trip, raising on an invalid code or duplicate."""
    if not CODE_RE.match(code):
        raise InvalidCodeError()
    code = code.upper()
    exists = session.execute(
        select(TripCurrency.id).where(TripCurrency.trip_id == trip.id, TripCurrency.code == code)
    ).first()
    if exists:
        raise DuplicateError(name=code)

    count = session.execute(
        select(func.count()).select_from(TripCurrency).where(TripCurrency.trip_id == trip.id)
    ).scalar_one()
    if is_primary:
        session.execute(
            TripCurrency.__table__.update()
            .where(TripCurrency.trip_id == trip.id)
            .values(is_primary=False)
        )
    currency = TripCurrency(
        trip_id=trip.id,
        code=code,
        symbol=symbol,
        is_primary=bool(is_primary) or count == 0,
        sort_order=count,
    )
    session.add(currency)
    session.flush()
    return currency


def update_currency(
    session: Session, currency: TripCurrency, symbol, is_primary, sort_order
) -> TripCurrency:
    """Apply the given field updates to a currency."""
    if symbol is not None:
        currency.symbol = symbol
    if is_primary:
        session.execute(
            TripCurrency.__table__.update()
            .where(TripCurrency.trip_id == currency.trip_id)
            .values(is_primary=False)
        )
        currency.is_primary = True
    if sort_order is not None:
        currency.sort_order = sort_order
    session.flush()
    return currency


def delete_currency(session: Session, currency: TripCurrency) -> None:
    """Delete a currency, raising if any item or transfer still uses it."""
    referenced = session.execute(
        select(func.count()).select_from(LineItem).where(LineItem.currency_id == currency.id)
    ).scalar_one()
    if referenced:
        raise InUseError(count=referenced, name=currency.code)
    transfer_count = session.execute(
        select(func.count())
        .select_from(WalletTransfer)
        .where(
            or_(
                WalletTransfer.from_currency_id == currency.id,
                WalletTransfer.to_currency_id == currency.id,
            )
        )
    ).scalar_one()
    if transfer_count:
        raise InUseError(count=transfer_count, name=currency.code)
    session.delete(currency)
    session.flush()


# ---- Country ------------------------------------------------------------------


def create_country(
    session: Session, trip: Trip, name: str, code: str | None, is_default: bool | None
) -> TripCountry:
    """Create a country on the trip, raising on a duplicate name."""
    exists = session.execute(
        select(TripCountry.id).where(TripCountry.trip_id == trip.id, TripCountry.name == name)
    ).first()
    if exists:
        raise DuplicateError(name=name)

    count = session.execute(
        select(func.count()).select_from(TripCountry).where(TripCountry.trip_id == trip.id)
    ).scalar_one()
    if is_default:
        session.execute(
            TripCountry.__table__.update()
            .where(TripCountry.trip_id == trip.id)
            .values(is_default=False)
        )
    country = TripCountry(
        trip_id=trip.id,
        name=name,
        code=code.upper() if code else None,
        is_default=bool(is_default) or count == 0,
        sort_order=count,
    )
    session.add(country)
    session.flush()
    return country


def update_country(  # noqa: PLR0913, PLR0917
    session: Session, country: TripCountry, name, code, is_default, sort_order
) -> TripCountry:
    """Apply the given field updates to a country, raising on a duplicate name."""
    if name is not None and name != country.name:
        exists = session.execute(
            select(TripCountry.id).where(
                TripCountry.trip_id == country.trip_id,
                TripCountry.name == name,
                TripCountry.id != country.id,
            )
        ).first()
        if exists:
            raise DuplicateError(name=name)
        country.name = name
    if code is not None:
        country.code = code.upper() if code else None
    if is_default:
        session.execute(
            TripCountry.__table__.update()
            .where(TripCountry.trip_id == country.trip_id)
            .values(is_default=False)
        )
        country.is_default = True
    if sort_order is not None:
        country.sort_order = sort_order
    session.flush()
    return country


def delete_country(session: Session, country: TripCountry) -> None:
    """Delete a country, raising if any item still uses it."""
    referenced = session.execute(
        select(func.count()).select_from(LineItem).where(LineItem.country_id == country.id)
    ).scalar_one()
    if referenced:
        raise InUseError(count=referenced, name=country.name)
    session.delete(country)
    session.flush()


def country_item_counts(session: Session, trip_id: int) -> dict[int, int]:
    """Return the number of items in each country for the trip."""
    rows = session.execute(
        select(LineItem.country_id, func.count(LineItem.id))
        .where(LineItem.trip_id == trip_id)
        .group_by(LineItem.country_id)
    ).all()
    return dict(rows)


# ---- Wallet ------------------------------------------------------------------


def create_default_wallet(session: Session, person: Person) -> Wallet:
    """Create a person's default wallet, `Card`, untracked - `roster.create_person`'s own doing.

    The one seeded user-visible string in `app/` (WALLETS.md "Default wallet"),
    alongside the server-assigned `initial` and ISO country names.
    """
    wallet = Wallet(
        trip_id=person.trip_id,
        person_id=person.id,
        name=DEFAULT_WALLET_NAME,
        tracked=False,
        is_default=True,
        sort_order=0,
    )
    session.add(wallet)
    session.flush()
    return wallet


def default_wallet(session: Session, person_id: int) -> Wallet:
    """Return a person's default wallet."""
    return session.execute(
        select(Wallet).where(Wallet.person_id == person_id, Wallet.is_default == True)  # noqa: E712
    ).scalar_one()


def create_wallet(
    session: Session, trip: Trip, person: Person, name: str, tracked: bool | None
) -> Wallet:
    """Create a wallet for a person, raising on a missing/too-long/duplicate name."""
    _validate_wallet_name(name)
    exists = session.execute(
        select(Wallet.id).where(Wallet.person_id == person.id, Wallet.name == name)
    ).first()
    if exists:
        raise DuplicateError(name=name)

    count = session.execute(
        select(func.count()).select_from(Wallet).where(Wallet.person_id == person.id)
    ).scalar_one()
    wallet = Wallet(
        trip_id=trip.id,
        person_id=person.id,
        name=name,
        tracked=bool(tracked),
        is_default=False,
        sort_order=count,
    )
    session.add(wallet)
    session.flush()
    return wallet


def update_wallet(  # noqa: PLR0913, PLR0917
    session: Session, wallet: Wallet, name, tracked, is_default, sort_order
) -> Wallet:
    """Apply the given field updates to a wallet, raising on an invalid/duplicate name."""
    if name is not None and name != wallet.name:
        _validate_wallet_name(name)
        exists = session.execute(
            select(Wallet.id).where(
                Wallet.person_id == wallet.person_id, Wallet.name == name, Wallet.id != wallet.id
            )
        ).first()
        if exists:
            raise DuplicateError(name=name)
        wallet.name = name
    if tracked is not None:
        wallet.tracked = tracked
    if is_default:
        session.execute(
            Wallet.__table__.update()
            .where(Wallet.person_id == wallet.person_id)
            .values(is_default=False)
        )
        wallet.is_default = True
    if sort_order is not None:
        wallet.sort_order = sort_order
    session.flush()
    return wallet


def delete_wallet(session: Session, wallet: Wallet) -> None:
    """Delete a wallet, raising if it is a person's default or still referenced."""
    if wallet.is_default:
        raise IsDefaultError()
    item_count = session.execute(
        select(func.count()).select_from(LineItem).where(LineItem.wallet_id == wallet.id)
    ).scalar_one()
    transfer_count = session.execute(
        select(func.count())
        .select_from(WalletTransfer)
        .where(
            or_(
                WalletTransfer.from_wallet_id == wallet.id,
                WalletTransfer.to_wallet_id == wallet.id,
            )
        )
    ).scalar_one()
    total = item_count + transfer_count
    if total:
        raise InUseError(count=total, name=wallet.name)
    session.delete(wallet)
    session.flush()
