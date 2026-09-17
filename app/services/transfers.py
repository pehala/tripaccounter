"""Wallet transfers: ref validation and the plain/exchange write rules.

A transfer has two typed sides. `to_amount`/`to_currency_id` default to the
from side on create, so a plain transfer only ever sends one amount; on
update, an omitted `to_amount` mirrors the (possibly just-changed) from side
only while the transfer stays plain (`from_currency_id == to_currency_id`) -
an exchange keeps whatever `to_amount` it already had (WALLETS.md §9 story 5).
"""

from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy.orm import Session

from app.models.roster import TripCurrency
from app.models.trip import Trip
from app.models.wallets import Wallet, WalletTransfer
from app.schemas.requests import TransferWrite
from app.services.errors.base import FieldError
from app.services.errors.fields import (
    CrossOwnerExchangeError,
    NotInTripError,
    RequiredError,
    SameWalletError,
)
from app.services.money import AMOUNT_SCALE, to_hundredths
from app.services.scope import in_trip, ref_error


@dataclass
class ResolvedTransfer:
    """The final values a write settles on, after the create/update defaulting rule."""

    from_wallet_id: int | None
    from_currency_id: int | None
    from_amount: Decimal | None
    to_wallet_id: int | None
    to_currency_id: int | None
    to_amount: Decimal | None


def resolve_write(body: TransferWrite, existing: WalletTransfer | None) -> ResolvedTransfer:
    """Apply the create/update defaulting rule, without validating the result."""
    if existing is None:
        from_wallet_id = body.from_wallet_id
        from_currency_id = body.from_currency_id
        from_amount = body.from_amount
        to_wallet_id = body.to_wallet_id
        to_currency_id = (
            body.to_currency_id if body.to_currency_id is not None else from_currency_id
        )
        to_amount = body.to_amount if body.to_amount is not None else from_amount
        return ResolvedTransfer(
            from_wallet_id, from_currency_id, from_amount, to_wallet_id, to_currency_id, to_amount
        )

    from_wallet_id = (
        body.from_wallet_id if body.from_wallet_id is not None else existing.from_wallet_id
    )
    from_currency_id = (
        body.from_currency_id if body.from_currency_id is not None else existing.from_currency_id
    )
    from_amount = (
        body.from_amount
        if body.from_amount is not None
        else Decimal(existing.from_amount_minor) / AMOUNT_SCALE
    )
    to_wallet_id = body.to_wallet_id if body.to_wallet_id is not None else existing.to_wallet_id
    to_currency_id = (
        body.to_currency_id if body.to_currency_id is not None else existing.to_currency_id
    )
    if body.to_amount is not None:
        to_amount = body.to_amount
    elif to_currency_id == from_currency_id:
        # Now (or still) a plain transfer: the to side mirrors the from side.
        to_amount = from_amount
    else:
        # Still an exchange with no new to_amount: keep the one on file.
        to_amount = Decimal(existing.to_amount_minor) / AMOUNT_SCALE
    return ResolvedTransfer(
        from_wallet_id, from_currency_id, from_amount, to_wallet_id, to_currency_id, to_amount
    )


def validate(
    session: Session, trip: Trip, resolved: ResolvedTransfer, *, creating: bool
) -> dict[str, FieldError]:
    """Validate a resolved write's refs and cross-field rules; return its field errors."""
    fields: dict[str, FieldError] = {}

    # Both wallets are required on every write; a currency only on create, since
    # `resolve_write` carries the stored one forward on a patch.
    for field, model, row_id, required in (
        ("from_wallet_id", Wallet, resolved.from_wallet_id, True),
        ("to_wallet_id", Wallet, resolved.to_wallet_id, True),
        ("from_currency_id", TripCurrency, resolved.from_currency_id, creating),
    ):
        error = ref_error(session, model, row_id, trip.id, required=required)
        if error:
            fields[field] = error

    from_wallet = in_trip(session, Wallet, resolved.from_wallet_id, trip.id)
    to_wallet = in_trip(session, Wallet, resolved.to_wallet_id, trip.id)

    to_currency_missing = (
        resolved.to_currency_id is not None
        and "from_currency_id" not in fields
        and in_trip(session, TripCurrency, resolved.to_currency_id, trip.id) is None
    )
    if to_currency_missing:
        fields["to_currency_id"] = NotInTripError()

    if resolved.from_amount is None and creating:
        fields["from_amount"] = RequiredError()

    if fields:
        return fields

    if (
        resolved.from_wallet_id == resolved.to_wallet_id
        and resolved.from_currency_id == resolved.to_currency_id
    ):
        fields["to_wallet_id"] = SameWalletError()
        return fields

    if (
        resolved.from_currency_id != resolved.to_currency_id
        and from_wallet.person_id != to_wallet.person_id
    ):
        fields["to_currency_id"] = CrossOwnerExchangeError()

    return fields


def apply_write(transfer: WalletTransfer, resolved: ResolvedTransfer, occurred_at, note) -> None:
    """Write a validated, resolved transfer's fields onto the model instance."""
    transfer.from_wallet_id = resolved.from_wallet_id
    transfer.from_currency_id = resolved.from_currency_id
    transfer.from_amount_minor = to_hundredths(resolved.from_amount)
    transfer.to_wallet_id = resolved.to_wallet_id
    transfer.to_currency_id = resolved.to_currency_id
    transfer.to_amount_minor = to_hundredths(resolved.to_amount)
    if occurred_at is not None:
        transfer.occurred_at = occurred_at
    if note is not None:
        transfer.note = note
