"""People / currencies / countries: the uniform CRUD validations."""

import re

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import ItemShare, LineItem, Person, Trip, TripCountry, TripCurrency
from app.services.errors import DuplicateError, InUseError, InvalidCodeError
from app.services.labels import PALETTE

CODE_RE = re.compile(r"^[A-Za-z]{3}$")


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
    """Delete a person, raising if they still pay or share any item."""
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
    """Delete a currency, raising if any item still uses it."""
    referenced = session.execute(
        select(func.count()).select_from(LineItem).where(LineItem.currency_id == currency.id)
    ).scalar_one()
    if referenced:
        raise InUseError(count=referenced, name=currency.code)
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
