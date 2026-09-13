"""The grammars one sheet cell can be written in: numbers and dates.

Pure string handling with no knowledge of the sheet's shape, so every case here is
testable by calling it with the text a cell held.
"""

from collections import Counter
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation

DATE_ONLY_HOUR = 12
NBSP = "\u00a0"  # the sheet groups thousands with a non-breaking space
FORMATS_WITH_YEAR = ("%d.%m.%Y %H:%M:%S", "%d.%m.%Y %H:%M", "%d.%m.%Y")
FORMATS_WITHOUT_YEAR = ("%d.%m. %H:%M", "%d.%m %H:%M")


def parse_decimal(raw):
    """Read a sheet number, or None if the cell is blank or not a number.

    The sheet groups thousands with a non-breaking space and marks the decimal with
    a comma, neither of which `Decimal` accepts.
    """
    text = raw.strip().replace(NBSP, "").replace(",", ".")
    if not text:
        return None
    try:
        return Decimal(text)
    except InvalidOperation:
        return None


def canonical_amount(value):
    """Render a Decimal as the canonical two-decimal string the amount grammar accepts."""
    return f"{value:.2f}"


def parse_naive(text, year=None):
    """Parse a sheet date into a naive local datetime, or None if no shape matches.

    `year` supplies the one a cell omits; without it, only cells that state their
    own year parse. A cell with no time of day is placed at midday, which keeps it
    on the intended calendar day for viewers in any timezone.
    """
    candidates = [(text, shape) for shape in FORMATS_WITH_YEAR]
    if year is not None:
        candidates += [(f"{text} {year}", f"{shape} %Y") for shape in FORMATS_WITHOUT_YEAR]
    for value, shape in candidates:
        try:
            naive = datetime.strptime(value, shape)  # noqa: DTZ007 - localized by the caller
        except ValueError:
            continue
        return naive if "%H" in shape else naive.replace(hour=DATE_ONLY_HOUR, minute=0)
    return None


def dominant_year(texts):
    """Return the year most date cells state, which is the one a year-less cell meant."""
    years = Counter(
        naive.year for text in texts if (naive := parse_naive(text.strip())) is not None
    )
    return years.most_common(1)[0][0] if years else datetime.now(UTC).year


def parse_occurred_at(raw, zone, year):
    """Read a sheet date as local wall clock and return the UTC instant it names."""
    naive = parse_naive(raw.strip(), year)
    return None if naive is None else naive.replace(tzinfo=zone).astimezone(UTC)
