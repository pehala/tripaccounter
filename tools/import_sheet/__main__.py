"""The command line: parse the arguments, print the report, commit only on --apply."""

import argparse
import sys
from collections import Counter
from zoneinfo import ZoneInfo

from app.db import SessionLocal
from tools.import_sheet.layout import (
    COLUMN_AMOUNT,
    COLUMN_CATEGORY,
    COLUMN_CITY,
    COLUMN_COUNTRY,
    COLUMN_CURRENCY,
    COLUMN_DATE,
    COLUMN_NAME,
    COLUMN_PAYER,
)
from tools.import_sheet.planning import build_plan
from tools.import_sheet.writing import apply, create_trip

DESCRIPTION = "Import a CSV expense sheet into a trip, in one transaction."


def describe_layout(plan):
    """Render the resolved index map, so a wrong index shows up before anything is written."""
    row, layout = plan.sample, plan.layout
    if not row:
        return []
    occurred_at = plan.items[0].occurred_at if plan.items else "?"
    targets = [
        (COLUMN_NAME, "name", row[COLUMN_NAME][:48]),
        (COLUMN_DATE, "occurred_at", f"{row[COLUMN_DATE]} -> {occurred_at}"),
        (COLUMN_CATEGORY, "labels", row[COLUMN_CATEGORY]),
        (COLUMN_PAYER, "payer", row[COLUMN_PAYER]),
        (COLUMN_AMOUNT, "amount", row[COLUMN_AMOUNT]),
        (COLUMN_CURRENCY, "currency", row[COLUMN_CURRENCY]),
        (COLUMN_CITY, "city", row[COLUMN_CITY]),
        (COLUMN_COUNTRY, "country", row[COLUMN_COUNTRY]),
    ]
    targets += [
        (index, f"owed[{person}]", row[index])
        for person, index in zip(layout.people, layout.owed, strict=True)
    ]
    targets.append((layout.note, "note", row[layout.note]))
    return [
        f"col {index:>2} {(plan.header[index] if index < len(plan.header) else ''):<14}"
        f" -> {target:<14} | {value}"
        for index, target, value in targets
    ]


def report(plan):
    """Print the index map, the roster, the split census and every problem found."""
    print("\n".join(describe_layout(plan)))
    print()
    print(f"people     {', '.join(plan.people)}")
    print(f"currencies {', '.join(plan.currencies)}  (primary: {plan.currencies[0]})")
    print(f"countries  {', '.join(plan.countries)}  (named by ISO code; rename in Setup)")
    modes = Counter(f"{item.split_mode}/{len(item.shares)}" for item in plan.items)
    census = "  ".join(f"{mode}: {count}" for mode, count in sorted(modes.items()))
    print(f"items      {len(plan.items)}  {census}")
    for item in plan.items:
        if item.adjustment:
            print(f"  adjusted row {item.row}: {item.name[:40]} — {item.adjustment}")
    if plan.problems:
        sys.stdout.flush()
        print(f"\n{len(plan.problems)} problem(s); nothing written:", file=sys.stderr)
        for problem in plan.problems:
            print(f"  {problem}", file=sys.stderr)


def build_parser():
    """Build the command-line parser."""
    parser = argparse.ArgumentParser(prog="python -m tools.import_sheet", description=DESCRIPTION)
    parser.add_argument("csv_path", metavar="CSV")
    parser.add_argument("trip_name", metavar="TRIP_NAME")
    parser.add_argument("--people", nargs="+", required=True, metavar="NAME")
    parser.add_argument("--start-date")
    parser.add_argument("--end-date")
    parser.add_argument("--tz", default="Europe/Prague")
    parser.add_argument("--dry-run", action="store_true")
    return parser


def main():
    """Read the sheet and import it in one transaction, unless --dry-run rolls it back."""
    args = build_parser().parse_args()
    plan = build_plan(args.csv_path, args.people, ZoneInfo(args.tz))
    report(plan)
    if plan.problems:
        return 2

    with SessionLocal() as session:
        trip = create_trip(session, args.trip_name, args.start_date, args.end_date)
        apply(session, plan, trip)
        slug = trip.slug  # read while attached: a rollback below would detach the instance
        if args.dry_run:
            session.rollback()
            print(f"\ndry run: {len(plan.items)} items would land in /t/{slug}; nothing written")
        else:
            session.commit()
            print(f"\nimported {len(plan.items)} items into /t/{slug}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
