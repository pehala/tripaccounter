"""Resolve a sheet into the item writes it stands for, collecting problems as it goes.

Nothing here touches a database. A row that cannot be read becomes a `Problem`
rather than an exception, so one run reports everything wrong with a sheet instead
of stopping at the first bad cell.
"""

import csv
import re
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from pathlib import Path

from tools.import_sheet.cells import (
    canonical_amount,
    dominant_year,
    parse_decimal,
    parse_occurred_at,
)
from tools.import_sheet.layout import (
    COLUMN_AMOUNT,
    COLUMN_CATEGORY,
    COLUMN_CITY,
    COLUMN_COUNTRY,
    COLUMN_CURRENCY,
    COLUMN_DATE,
    COLUMN_NAME,
    COLUMN_PAYER,
    Layout,
)

NAME_MAX_LENGTH = 200
MINOR_UNIT = Decimal("0.01")
CURRENCY_RE = re.compile(r"^[A-Za-z]{3}$")
COUNTRY_RE = re.compile(r"^[A-Za-z]{2}$")


@dataclass(frozen=True)
class Problem:
    """One reason the sheet cannot be imported, tied to the row that caused it."""

    row: int
    name: str
    code: str
    detail: str

    def __str__(self):
        """Render the problem as one report line."""
        return f"row {self.row:>4}  {self.code:<16} {self.name[:40]:<42} {self.detail}"


@dataclass(frozen=True)
class PlannedItem:
    """One sheet row resolved into the fields an item write needs."""

    row: int
    name: str
    note: str | None
    city: str | None
    occurred_at: datetime
    amount: str
    currency_code: str
    country_code: str
    payer: str
    item_labels: tuple[str, ...]
    split_mode: str
    shares: tuple[dict, ...]
    adjustment: str | None = None


@dataclass
class Plan:
    """Everything read out of one sheet: the roster to create, the items, the problems."""

    layout: Layout
    header: list[str] = field(default_factory=list)
    sample: list[str] = field(default_factory=list)
    currencies: list[str] = field(default_factory=list)
    countries: list[str] = field(default_factory=list)
    items: list[PlannedItem] = field(default_factory=list)
    problems: list[Problem] = field(default_factory=list)

    @property
    def people(self):
        """Return the roster the sheet was read against, in owed-column order."""
        return self.layout.people


def infer_split(amount, owed):
    """Resolve one row's owed amounts into a split mode and its shares.

    `owed` is `[(person, Decimal)]` in roster order. Returns
    `(mode, shares, adjustment)`, where `adjustment` describes a one-minor-unit
    correction, or `(None, None, reason)` when the amounts fit no mode.
    """
    active = [(person, value) for person, value in owed if value != 0]
    if not active:
        return None, None, "every share is zero"

    total = sum(value for _, value in active)
    distinct = {value for _, value in active}
    equally = [{"person_id": person} for person, _ in active]

    if len(distinct) == 1 and abs(total - amount) <= MINOR_UNIT * len(active):
        return "equal", equally, None

    if total == amount:
        exact = [
            {"person_id": person, "amount": canonical_amount(value)} for person, value in active
        ]
        return "exact", exact, None

    if abs(total - amount) == MINOR_UNIT:
        largest = max(range(len(active)), key=lambda i: active[i][1])
        corrected = list(active)
        person, value = corrected[largest]
        corrected[largest] = (person, value + amount - total)
        exact = [
            {"person_id": person, "amount": canonical_amount(value)} for person, value in corrected
        ]
        return "exact", exact, f"{person} {value} -> {corrected[largest][1]}"

    return None, None, f"shares total {total}, amount {amount}"


def read_sheet(path):
    """Read the export, returning its header and the rows that carry an item name."""
    with Path(path).open(encoding="utf-8", newline="") as handle:
        table = list(csv.reader(handle))
    if not table:
        return [], []
    rows = [(number, row) for number, row in enumerate(table[1:], 2) if row[COLUMN_NAME].strip()]
    return table[0], rows


def plan_row(number, row, layout, problems):
    """Turn one sheet row into a PlannedItem, appending to `problems` instead of raising."""
    name = row[COLUMN_NAME].strip()

    def report(code, detail):
        problems.append(Problem(number, name, code, detail))

    if len(name) > NAME_MAX_LENGTH:
        report("name_too_long", f"{len(name)} characters")
    occurred_at = parse_occurred_at(row[COLUMN_DATE], layout.zone, layout.year)
    if occurred_at is None:
        report("bad_date", f"{row[COLUMN_DATE]!r}")
    amount = parse_decimal(row[COLUMN_AMOUNT])
    if amount is None or amount <= 0:
        report("bad_amount", f"{row[COLUMN_AMOUNT]!r}")
    currency = row[COLUMN_CURRENCY].strip().upper()
    if not CURRENCY_RE.match(currency):
        report("bad_currency", f"{row[COLUMN_CURRENCY]!r}")
    country = row[COLUMN_COUNTRY].strip().upper()
    if not COUNTRY_RE.match(country):
        report("bad_country", f"{row[COLUMN_COUNTRY]!r}")
    category = row[COLUMN_CATEGORY].strip()
    if category and re.search(r"\s", category):
        report("label_whitespace", f"{category!r}")

    owed = []
    unreadable = False
    for person, index in zip(layout.people, layout.owed, strict=True):
        value = parse_decimal(row[index])
        if value is None and row[index].strip():
            report("bad_share", f"{person}: {row[index]!r}")
            unreadable = True
        owed.append((person, value or Decimal(0)))
    if unreadable or amount is None or occurred_at is None:
        return None
    mode, shares, adjustment = infer_split(amount, owed)
    if mode is None:
        report("bad_split", adjustment)
        return None

    return PlannedItem(
        row=number,
        name=name,
        note=row[layout.note].strip() or None,
        city=row[COLUMN_CITY].strip() or None,
        occurred_at=occurred_at,
        amount=canonical_amount(amount),
        currency_code=currency,
        country_code=country,
        payer=row[COLUMN_PAYER].strip(),
        item_labels=(category,) if category else (),
        split_mode=mode,
        shares=tuple(shares),
        adjustment=adjustment,
    )


def build_plan(path, people, zone):
    """Read the sheet and resolve every row, collecting problems rather than stopping."""
    header, rows = read_sheet(path)
    year = dominant_year([row[COLUMN_DATE] for _, row in rows])
    layout = Layout.for_people(people, zone, year)
    layout.check_fits(rows)
    plan = Plan(layout=layout, header=header, sample=rows[0][1] if rows else [])

    for number, row in rows:
        item = plan_row(number, row, layout, plan.problems)
        if item is not None:
            plan.items.append(item)

    strangers = {item.payer for item in plan.items} - set(layout.people)
    plan.problems += [
        Problem(0, "", "unknown_payer", f"{payer!r} is not in --people {list(layout.people)}")
        for payer in sorted(strangers)
    ]

    seen = Counter(item.currency_code for item in plan.items)
    plan.currencies = [code for code, _ in seen.most_common()]
    plan.countries = sorted({item.country_code for item in plan.items})
    return plan
