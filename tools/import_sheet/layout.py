"""Which column index holds what.

Header text is not stable, so nothing is matched against it: the line-item block on
the left has fixed indexes, and the only thing that varies is how many people the
sheet splits between.
"""

from dataclasses import dataclass
from datetime import UTC

COLUMN_NAME = 0
COLUMN_DATE = 1
COLUMN_CATEGORY = 2
COLUMN_PAYER = 3
COLUMN_AMOUNT = 4
COLUMN_CURRENCY = 5
COLUMN_COUNTRY = 6
FIRST_OWED_COLUMN = 9


@dataclass(frozen=True)
class Layout:
    """How to read one sheet: its column indexes, its wall-clock zone, its implied year."""

    people: tuple[str, ...]
    owed: tuple[int, ...]
    note: int
    zone: object = UTC
    year: int | None = None

    @classmethod
    def for_people(cls, names, zone=UTC, year=None):
        """Place N owed columns from index 9, two apart, with the note column after them."""
        owed = tuple(FIRST_OWED_COLUMN + 2 * i for i in range(len(names)))
        return cls(tuple(names), owed, FIRST_OWED_COLUMN + 2 * len(names), zone, year)

    def check_fits(self, rows):
        """Raise if the note column this roster implies falls outside the sheet."""
        narrow = [number for number, row in rows if len(row) <= self.note]
        if narrow:
            raise SystemExit(
                f"--people lists {len(self.people)} names, which puts the note column at "
                f"{self.note}, past the width of {len(narrow)} row(s) starting at row {narrow[0]}"
            )
