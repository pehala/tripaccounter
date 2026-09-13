"""Direct-call tests for money scaling, wire conversion, rounding, and settlement."""

from decimal import Decimal

import pytest

from app.services.money import (
    AMOUNT_SCALE,
    MICRO_SCALE,
    WEIGHT_SCALE,
    scale_weight,
    to_hundredths,
    to_wire,
)
from app.services.settle import round_nets_to_minor, suggest_transfers


@pytest.mark.parametrize(
    ("amount", "expected"),
    [
        pytest.param(Decimal("18400.50"), 1840050, id="two-decimals"),
        pytest.param(Decimal(18400), 1840000, id="whole"),
        pytest.param(Decimal("0.05"), 5, id="sub-unit"),
    ],
)
def test_to_hundredths_exact(amount, expected):
    """A canonical decimal amount becomes exact hundredths, never a float."""
    assert to_hundredths(amount) == expected


@pytest.mark.parametrize(
    ("weight", "expected"),
    [
        pytest.param(Decimal(1), 10000, id="one"),
        pytest.param(Decimal("0.5"), 5000, id="half"),
        pytest.param(Decimal("1.0001"), 10001, id="four-places"),
    ],
)
def test_scale_weight_exact(weight, expected):
    """Weight scales by 10**4 exactly, matching WEIGHT_SCALE."""
    assert scale_weight(weight) == expected
    assert WEIGHT_SCALE == 10000


@pytest.mark.parametrize(
    ("value", "scale", "expected", "expected_type"),
    [
        pytest.param(1840000, AMOUNT_SCALE, 18400, int, id="whole-hundredths"),
        pytest.param(1840050, AMOUNT_SCALE, 18400.5, float, id="fractional-hundredths"),
        pytest.param(13333333, MICRO_SCALE, 13.333333, float, id="micro-fraction"),
        pytest.param(4600000000, MICRO_SCALE, 4600, int, id="whole-micro"),
    ],
)
def test_to_wire_type_and_value(value, scale, expected, expected_type):
    """to_wire yields an int for whole values and a float otherwise, never the other way."""
    result = to_wire(value, scale)
    assert result == expected
    assert type(result) is expected_type


def test_to_wire_negative_whole_is_int():
    """A negative but whole value is still an int, not a float."""
    result = to_wire(-1840000, AMOUNT_SCALE)
    assert result == -18400
    assert type(result) is int


def test_round_nets_to_minor_zero_sums_stay_zero():
    """Nets already at zero net_micro round to zero minor units."""
    nets = {1: 0, 2: 0}
    sort_order = {1: 0, 2: 1}
    result = round_nets_to_minor(nets, sort_order)
    assert result == {1: 0, 2: 0}
    assert sum(result.values()) == 0


def test_round_nets_to_minor_zero_sum_correction_deterministic():
    """Three people with a rounding-ambiguous split still sum to exactly zero.

    The correction applies to the largest rounding error, ties by sort_order.
    """
    # -1/3, -1/3, +2/3 of a currency unit, in micro units: -3333.33.., -3333.33.., 6666.66..
    nets = {1: -33333333, 2: -33333333, 3: 66666667}
    sort_order = {1: 0, 2: 1, 3: 2}

    result = round_nets_to_minor(nets, sort_order)

    assert sum(result.values()) == 0
    assert result[3] == 6667


def test_round_nets_to_minor_is_deterministic_by_sort_order():
    """Two people tied on rounding error break the tie by sort_order, lowest first."""
    # exact minor units: 1.5 and -0.5; banker's rounding gives 2 and 0, sum 2,
    # so two one-cent corrections are needed and both candidates tie on error.
    nets = {10: 15000, 20: -5000}
    sort_order = {10: 0, 20: 1}
    result = round_nets_to_minor(nets, sort_order)
    assert result == {10: 1, 20: -1}
    assert sum(result.values()) == 0


def test_suggest_transfers_sums_to_zero_and_matches_largest_first():
    """Greedy min-cash-flow matches the largest creditor with the largest debtor."""
    net_minor = {1: -500, 2: -300, 3: 800}
    sort_order = {1: 0, 2: 1, 3: 2}

    transfers = suggest_transfers(net_minor, sort_order)

    assert sum(t["amount"] for t in transfers if t["to_person_id"] == 3) == 800
    assert len(transfers) <= len(net_minor) - 1
    net_after = dict.fromkeys(net_minor, 0)
    for pid, amount in net_minor.items():
        net_after[pid] += amount
    for transfer in transfers:
        net_after[transfer["from_person_id"]] += transfer["amount"]
        net_after[transfer["to_person_id"]] -= transfer["amount"]
    assert all(v == 0 for v in net_after.values())


def test_suggest_transfers_already_settled_yields_empty():
    """A trip where every net is already zero produces no suggestions."""
    assert suggest_transfers({1: 0, 2: 0}, {1: 0, 2: 1}) == []
