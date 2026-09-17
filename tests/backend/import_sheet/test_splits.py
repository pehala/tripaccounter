"""Inferring a split mode from the amount and the per-person owed cells."""

from decimal import Decimal

import pytest

from tools.import_sheet import infer_split


def test_infer_split_equal_over_everyone_who_owes():
    """Identical non-zero shares that sum to the amount are an equal split."""
    owed = [("Ann", Decimal("620.00")), ("Bob", Decimal("620.00"))]

    assert infer_split(Decimal("1240.00"), owed) == (
        "equal",
        [{"person_id": "Ann"}, {"person_id": "Bob"}],
        None,
    )


def test_infer_split_equal_leaves_out_whoever_owes_nothing():
    """A zero share means that person is not in the split at all, not that they owe 0."""
    owed = [("Ann", Decimal("0.00")), ("Bob", Decimal("13.00"))]

    assert infer_split(Decimal("13.00"), owed) == ("equal", [{"person_id": "Bob"}], None)


def test_infer_split_equal_absorbs_a_sheet_that_rounded_each_share_up():
    """3.34 + 3.34 for 6.67 is an equal split the sheet rounded, not an exact one that fails."""
    owed = [("Ann", Decimal("3.34")), ("Bob", Decimal("3.34"))]

    mode, shares, adjustment = infer_split(Decimal("6.67"), owed)

    assert (mode, adjustment) == ("equal", None)
    assert shares == [{"person_id": "Ann"}, {"person_id": "Bob"}]


def test_infer_split_exact_when_shares_differ_and_sum():
    """Unequal shares that sum to the amount are written as an exact split."""
    owed = [("Ann", Decimal("10.00")), ("Bob", Decimal("20.00"))]

    assert infer_split(Decimal("30.00"), owed) == (
        "exact",
        [
            {"person_id": "Ann", "amount": "10.00"},
            {"person_id": "Bob", "amount": "20.00"},
        ],
        None,
    )


def test_infer_split_nudges_the_largest_share_by_one_minor_unit():
    """An unequal split one cent over the amount loses the cent off its largest share."""
    owed = [("Ann", Decimal("1.48")), ("Bob", Decimal("3.48"))]

    mode, shares, adjustment = infer_split(Decimal("4.95"), owed)

    assert mode == "exact"
    assert shares == [
        {"person_id": "Ann", "amount": "1.48"},
        {"person_id": "Bob", "amount": "3.47"},
    ]
    assert adjustment == "Bob 3.48 -> 3.47"


@pytest.mark.parametrize(
    ("amount", "owed"),
    [
        pytest.param(
            Decimal("1.00"),
            [("Ann", Decimal("1.00")), ("Bob", Decimal("1.00"))],
            id="both-owe-the-whole-amount",
        ),
        pytest.param(
            Decimal("7.70"),
            [("Ann", Decimal("7.70")), ("Bob", Decimal("3.85"))],
            id="shares-overshoot",
        ),
        pytest.param(
            Decimal("5.00"),
            [("Ann", Decimal("0.00")), ("Bob", Decimal("0.00"))],
            id="nobody-owes-anything",
        ),
    ],
)
def test_infer_split_reports_amounts_that_fit_no_mode(amount, owed):
    """Shares that are neither equal nor summing yield no mode, so the row is reported."""
    mode, shares, reason = infer_split(amount, owed)

    assert (mode, shares) == (None, None)
    assert reason
