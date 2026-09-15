"""The example sheet and the row builders the importer tests share.

`fixtures/sheet.csv` is the worked example of the format: an invented trip whose 24
rows carry no real data and cover every case the importer distinguishes. The tests
import that file rather than inventing sheets inline, so the committed example and
the behaviour it documents cannot drift apart. Variants are built by overriding one
cell of it, which keeps one source of truth for what a row looks like.
"""

import csv
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

SAMPLE = Path(__file__).parent.parent / "fixtures" / "sheet.csv"
PRAGUE = ZoneInfo("Europe/Prague")
PEOPLE = ["Ann", "Bob"]

with SAMPLE.open(encoding="utf-8", newline="") as handle:
    SAMPLE_ROWS = list(csv.reader(handle))
HEADER = SAMPLE_ROWS[0]
BASE_ROW = SAMPLE_ROWS[3]  # ITEM3 — an equal two-way EUR row paid by Ann


@pytest.fixture()
def sheet(tmp_path):
    """Return a builder writing a CSV with the example header and the given data rows."""

    def build(rows, header=None):
        target = tmp_path / "sheet.csv"
        with target.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(header or HEADER)
            writer.writerows(rows)
        return target

    return build


@pytest.fixture()
def row():
    """Return a builder for one sheet row, overriding cells of the example by index."""

    def build(**overrides):
        cells = list(BASE_ROW)
        for index, value in overrides.items():
            cells[int(index)] = value
        return cells

    return build
