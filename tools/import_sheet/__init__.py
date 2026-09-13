"""Import a CSV expense sheet into a trip, in one transaction.

    uv run python -m tools.import_sheet SHEET.csv "Trip name" --people Ann Bob \
        [--start-date 2026-09-01] [--end-date 2026-09-30] [--tz Europe/Prague] [--dry-run]

Columns are addressed by index, because header text is not stable. The layout is
fixed except for how many people there are, and that comes from ``--people``: N
names occupy the owed columns at ``9 + 2*i`` (each followed by a spreadsheet helper
column), and the note column follows at ``9 + 2*N``. Everything to the right of the
note column is the sheet's own summary block, and is never read.

Every run creates its own trip, so importing the same sheet twice gives two trips
rather than one with everything doubled; there is no upsert to get wrong.

A run imports. ``--dry-run`` takes the same path in full — every service call,
foreign key and check constraint — and rolls back at the end instead of committing,
so it reports exactly what an import would do without writing any of it.

Either way a sheet with a problem in it is reported and nothing is written at all:
the import is one transaction, so it lands whole or not at all.

| Module | Holds |
|---|---|
| `layout` | the column indexes, and the roster size that shifts them |
| `cells` | the grammars a cell can be written in: numbers and dates |
| `planning` | sheet rows resolved into item writes, or into problems |
| `writing` | those writes persisted onto a new trip |
| `__main__` | the CLI, and the report it prints |
"""

from tools.import_sheet.cells import (
    canonical_amount,
    dominant_year,
    parse_decimal,
    parse_naive,
    parse_occurred_at,
)
from tools.import_sheet.layout import Layout
from tools.import_sheet.planning import (
    Plan,
    PlannedItem,
    Problem,
    build_plan,
    infer_split,
    plan_row,
    read_sheet,
)
from tools.import_sheet.writing import apply, create_roster, create_trip

__all__ = [
    "Layout",
    "Plan",
    "PlannedItem",
    "Problem",
    "apply",
    "build_plan",
    "canonical_amount",
    "create_roster",
    "create_trip",
    "dominant_year",
    "infer_split",
    "parse_decimal",
    "parse_naive",
    "parse_occurred_at",
    "plan_row",
    "read_sheet",
]
