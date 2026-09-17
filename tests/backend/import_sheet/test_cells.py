"""Reading one cell: the decimal grammar, the canonical amount, and the date shapes.

These are pure arithmetic over combinatorial inputs, so they are called directly,
like `test_money.py`.
"""

from decimal import Decimal
from zoneinfo import ZoneInfo

import pytest

from tests.backend.import_sheet.conftest import PRAGUE
from tools.import_sheet import canonical_amount, parse_decimal, parse_occurred_at


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        pytest.param("1 240,00", Decimal("1240.00"), id="nbsp-grouped"),
        pytest.param("10,7", Decimal("10.7"), id="one-decimal"),
        pytest.param("697,00", Decimal("697.00"), id="plain"),
        pytest.param("", None, id="blank-cell"),
        pytest.param("?", None, id="not-a-number"),
    ],
)
def test_parse_decimal(raw, expected):
    """A sheet number with NBSP grouping and a comma decimal becomes an exact Decimal."""
    assert parse_decimal(raw) == expected


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        pytest.param(Decimal("10.7"), "10.70", id="pads-to-two-places"),
        pytest.param(Decimal(1162), "1162.00", id="whole"),
    ],
)
def test_canonical_amount_matches_the_amount_grammar(value, expected):
    """A Decimal renders as the two-decimal string app.services.parsing accepts."""
    assert canonical_amount(value) == expected


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        pytest.param("9.9.2026 19:45:00", "2026-09-09T17:45:00+00:00", id="date-time-seconds"),
        pytest.param("7.9.2026", "2026-09-07T10:00:00+00:00", id="date-only-takes-midday"),
        pytest.param("8.9 10:15", "2026-09-08T08:15:00+00:00", id="year-less"),
        pytest.param("8.9. 10:15", "2026-09-08T08:15:00+00:00", id="year-less-trailing-dot"),
    ],
)
def test_parse_occurred_at_local_wall_clock_to_utc(raw, expected):
    """Each date shape resolves to the UTC instant its Prague wall clock names."""
    assert parse_occurred_at(raw, PRAGUE, 2026).isoformat() == expected


def test_parse_occurred_at_honours_the_zone():
    """The same wall clock in a different zone is a different instant."""
    assert parse_occurred_at("8.9 10:15", ZoneInfo("UTC"), 2026).isoformat() == (
        "2026-09-08T10:15:00+00:00"
    )


@pytest.mark.parametrize(
    "raw", [pytest.param("", id="empty"), pytest.param("last tuesday", id="prose")]
)
def test_parse_occurred_at_unparsable_is_none(raw):
    """A cell the importer cannot read yields None, so the row becomes a reported problem."""
    assert parse_occurred_at(raw, PRAGUE, 2026) is None
