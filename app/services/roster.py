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


# ---- The shared guards -------------------------------------------------------
# `scope` is the clause naming the rows a rule applies to - `Person.trip_id == 5`,
# `Wallet.person_id == 3` - and `column` carries its own model, so every call
# fits one line. A wider signature would make `ruff format` explode each call
# site to one argument per line.


def ensure_unique(session: Session, column, value, scope, exclude_id: int | None = None) -> None:
    """Raise `DuplicateError` if another row under `scope` already holds `value` in `column`."""
    model = column.class_
    clauses = [scope, column == value]
    if exclude_id is not None:
        clauses.append(model.id != exclude_id)
    if session.execute(select(model.id).where(*clauses)).first():
        raise DuplicateError(name=value)


def roster_size(session: Session, model, scope) -> int:
    """Return the number of rows under `scope`, the position a newly added row takes."""
    return session.execute(select(func.count()).select_from(model).where(scope)).scalar_one()


def clear_flag(session: Session, column, scope) -> None:
    """Clear a boolean flag on every row under `scope`, before one row claims it."""
    table = column.class_.__table__
    session.execute(table.update().where(scope).values({column.key: False}))


def reference_count(session: Session, statement) -> int:
    """Return the count a `select(func.count())` statement yields."""
    return session.execute(statement).scalar_one()


def assert_free(count: int, name: str) -> None:
    """Raise `InUseError` when a row about to be deleted is still referenced."""
    if count:
        raise InUseError(count=count, name=name)


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
    scope = Person.trip_id == trip.id
    ensure_unique(session, Person.name, name, scope)
    count = roster_size(session, Person, scope)
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
        ensure_unique(session, Person.name, name, Person.trip_id == person.trip_id, person.id)
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
    paid = select(func.count()).select_from(LineItem).where(LineItem.payer_id == person.id)
    shared = select(func.count()).select_from(ItemShare).where(ItemShare.person_id == person.id)
    moved = (
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
    )
    for statement in (paid, shared, moved):
        assert_free(reference_count(session, statement), person.name)
    session.delete(person)
    session.flush()


def create_currency(
    session: Session, trip: Trip, code: str, symbol: str | None, is_primary: bool | None
) -> TripCurrency:
    """Create a currency on the trip, raising on an invalid code or duplicate."""
    if not CODE_RE.match(code):
        raise InvalidCodeError()
    code = code.upper()
    scope = TripCurrency.trip_id == trip.id
    ensure_unique(session, TripCurrency.code, code, scope)
    count = roster_size(session, TripCurrency, scope)
    if is_primary:
        clear_flag(session, TripCurrency.is_primary, scope)
    currency = TripCurrency(
        trip_id=trip.id,
        code=code,
        symbol=symbol,
        is_primary=bool(is_primary) or count == 0,
    )
    session.add(currency)
    session.flush()
    return currency


def update_currency(session: Session, currency: TripCurrency, symbol, is_primary) -> TripCurrency:
    """Apply the given field updates to a currency."""
    if symbol is not None:
        currency.symbol = symbol
    if is_primary:
        clear_flag(session, TripCurrency.is_primary, TripCurrency.trip_id == currency.trip_id)
        currency.is_primary = True
    session.flush()
    return currency


def delete_currency(session: Session, currency: TripCurrency) -> None:
    """Delete a currency, raising if any item or transfer still uses it."""
    spent = select(func.count()).select_from(LineItem).where(LineItem.currency_id == currency.id)
    moved = (
        select(func.count())
        .select_from(WalletTransfer)
        .where(
            or_(
                WalletTransfer.from_currency_id == currency.id,
                WalletTransfer.to_currency_id == currency.id,
            )
        )
    )
    for statement in (spent, moved):
        assert_free(reference_count(session, statement), currency.code)
    session.delete(currency)
    session.flush()


# ---- Country ------------------------------------------------------------------


def create_country(
    session: Session, trip: Trip, name: str, code: str | None, is_default: bool | None
) -> TripCountry:
    """Create a country on the trip, raising on a duplicate name."""
    scope = TripCountry.trip_id == trip.id
    ensure_unique(session, TripCountry.name, name, scope)
    count = roster_size(session, TripCountry, scope)
    if is_default:
        clear_flag(session, TripCountry.is_default, scope)
    country = TripCountry(
        trip_id=trip.id,
        name=name,
        code=code.upper() if code else None,
        is_default=bool(is_default) or count == 0,
    )
    session.add(country)
    session.flush()
    return country


def update_country(session: Session, country: TripCountry, name, code, is_default) -> TripCountry:
    """Apply the given field updates to a country, raising on a duplicate name."""
    scope = TripCountry.trip_id == country.trip_id
    if name is not None and name != country.name:
        ensure_unique(session, TripCountry.name, name, scope, country.id)
        country.name = name
    if code is not None:
        country.code = code.upper() if code else None
    if is_default:
        clear_flag(session, TripCountry.is_default, scope)
        country.is_default = True
    session.flush()
    return country


def delete_country(session: Session, country: TripCountry) -> None:
    """Delete a country, raising if any item still uses it."""
    visited = select(func.count()).select_from(LineItem).where(LineItem.country_id == country.id)
    assert_free(reference_count(session, visited), country.name)
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
    scope = Wallet.person_id == person.id
    ensure_unique(session, Wallet.name, name, scope)
    wallet = Wallet(
        trip_id=trip.id,
        person_id=person.id,
        name=name,
        tracked=bool(tracked),
        is_default=False,
    )
    session.add(wallet)
    session.flush()
    return wallet


def update_wallet(session: Session, wallet: Wallet, name, tracked, is_default) -> Wallet:
    """Apply the given field updates to a wallet, raising on an invalid/duplicate name."""
    scope = Wallet.person_id == wallet.person_id
    if name is not None and name != wallet.name:
        _validate_wallet_name(name)
        ensure_unique(session, Wallet.name, name, scope, wallet.id)
        wallet.name = name
    if tracked is not None:
        wallet.tracked = tracked
    if is_default:
        clear_flag(session, Wallet.is_default, scope)
        wallet.is_default = True
    session.flush()
    return wallet


def delete_wallet(session: Session, wallet: Wallet) -> None:
    """Delete a wallet, raising if it is a person's default or still referenced."""
    if wallet.is_default:
        raise IsDefaultError()
    spent = select(func.count()).select_from(LineItem).where(LineItem.wallet_id == wallet.id)
    moved = (
        select(func.count())
        .select_from(WalletTransfer)
        .where(
            or_(
                WalletTransfer.from_wallet_id == wallet.id,
                WalletTransfer.to_wallet_id == wallet.id,
            )
        )
    )
    total = reference_count(session, spent) + reference_count(session, moved)
    assert_free(total, wallet.name)
    session.delete(wallet)
    session.flush()
