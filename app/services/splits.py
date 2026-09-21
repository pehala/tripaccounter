"""Build and resolve item splits.

The floor-division expression here is the same one the `share_owed` SQL view
computes — a preview and a saved item must never disagree, so there is
exactly one definition of a share.
"""

from decimal import Decimal

from app.services.errors.fields import (
    DuplicatePersonError,
    EmptyError,
    NotInTripError,
    SumMismatchError,
)
from app.services.money import (
    AMOUNT_SCALE,
    MICRO_PER_MINOR,
    MICRO_SCALE,
    WEIGHT_SCALE,
    to_hundredths,
    to_wire,
)
from app.services.parsing import parse_amount, parse_weight


def build_shares(
    mode: str,
    shares_in: list[dict],
    valid_person_ids: list[int],
    amount: Decimal,
    currency_code: str,
) -> list[dict]:
    """Validate a write body's `shares` and turn it into rows ready to persist.

    Rows are `{person_id, weight_scaled, owed_minor, exact}`. Raises
    `FieldError` for every rule in API.md §4 that applies to `shares`.
    `shares_in` is never None here — "omitted means equal over all active
    people" is resolved by the caller, which knows the roster; this function
    only validates. `mode` is `equal`, `shares` or `exact`: the `Literal` both
    write schemas validate, so `exact` is the remaining case.
    """
    if len(shares_in) == 0:
        raise EmptyError()

    seen: set[int] = set()
    rows: list[dict] = []
    for raw in shares_in:
        if not isinstance(raw, dict) or "person_id" not in raw:
            raise EmptyError()
        person_id = raw["person_id"]
        if person_id in seen:
            raise DuplicatePersonError()
        seen.add(person_id)
        if person_id not in valid_person_ids:
            raise NotInTripError()

        if mode == "equal":
            rows.append(
                {
                    "person_id": person_id,
                    "weight_scaled": WEIGHT_SCALE,
                    "owed_minor": None,
                    "exact": False,
                }
            )
        elif mode == "shares":
            weight = parse_weight(raw.get("weight"))
            rows.append(
                {
                    "person_id": person_id,
                    "weight_scaled": int(weight * WEIGHT_SCALE),
                    "owed_minor": None,
                    "exact": False,
                }
            )
        else:
            share_amount = parse_amount(raw.get("amount"), allow_zero=True)
            rows.append(
                {
                    "person_id": person_id,
                    "weight_scaled": WEIGHT_SCALE,
                    "owed_minor": to_hundredths(share_amount),
                    "exact": True,
                }
            )

    if mode == "exact":
        total = sum(row["owed_minor"] for row in rows)
        expected = to_hundredths(amount)
        if total != expected:
            raise SumMismatchError(diff=abs(expected - total), currency_code=currency_code)

    return rows


def rows_from_shares(shares) -> list[dict]:
    """Return persisted `ItemShare` rows in the row form the rest of this module speaks.

    `{person_id, weight_scaled, owed_minor, exact}` - what `build_shares`
    produces and `resolve_shares_wire` consumes.
    """
    return [
        {
            "person_id": share.person_id,
            "weight_scaled": share.weight_scaled,
            "owed_minor": share.owed_minor,
            "exact": share.split_mode_exact,
        }
        for share in shares
    ]


def format_weight(weight_scaled: int) -> str:
    """Return the scaled weight as a plain decimal string, trimmed of trailing zeros."""
    value = (Decimal(weight_scaled) / WEIGHT_SCALE).normalize()
    if value == value.to_integral_value():
        return str(int(value))
    return format(value, "f")


def format_amount(amount_minor: int) -> str:
    """Return the minor units as the canonical decimal string a write body carries.

    The counterpart of `format_weight` for an `exact` row, and the only way
    stored money re-enters a write path: `money.to_wire` produces a JSON
    number, which `parse_amount` rejects.
    """
    return format(Decimal(amount_minor) / AMOUNT_SCALE, "f")


def resolve_shares_wire(
    roster_ids_sorted: list[int], rows: list[dict], amount_minor: int
) -> list[dict]:
    """Build the `split.shares` array: one entry per active person in roster order.

    Nulls for anyone left out of the item.
    """
    by_person = {row["person_id"]: row for row in rows}
    total_weight_scaled = sum(row["weight_scaled"] for row in rows)

    resolved = []
    for person_id in roster_ids_sorted:
        row = by_person.get(person_id)
        if row is None:
            resolved.append({"person_id": person_id, "weight": None, "owed": None})
            continue

        if row["exact"]:
            owed_wire = to_wire(row["owed_minor"], AMOUNT_SCALE)
        else:
            owed_micro = (
                amount_minor * MICRO_PER_MINOR * row["weight_scaled"]
            ) // total_weight_scaled
            owed_wire = to_wire(owed_micro, MICRO_SCALE)

        resolved.append(
            {
                "person_id": person_id,
                "weight": format_weight(row["weight_scaled"]),
                "owed": owed_wire,
            }
        )
    return resolved
