"""Tests for fmt.js's parse(), via page.evaluate.

Page.evaluate on fmt.parse: in en,
`18,400.50` -> `18400.50`, `1,000` -> `1000`; in cs, `18 400,50` -> `18400.50`,
`1 000` -> `1000`, `0,5` -> `0.5`; `abc`, `1.2.3`, `` -> null and the input shows
err.invalid_amount client-side before any request; a non-breaking space groups
like a space.
"""

import pytest


def parse(page, text, locale):
    """Evaluate fmt.js's parse function, in the browser, for `text` in `locale`."""
    return page.evaluate(
        "async ({ text, locale }) => (await import('/js/fmt.js')).parse(text, locale)",
        {"text": text, "locale": locale},
    )


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("18,400.50", "18400.50"),
        ("1,000", "1000"),
        ("18400.5", "18400.5"),
        ("-5", "-5"),
    ],
)
def test_parses_english_grouped_input(page, mockserver, text, expected):
    """English input with comma grouping and a dot decimal parses to a canonical decimal."""
    page.goto(f"{mockserver}/")
    assert parse(page, text, "en") == expected


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("18 400,50", "18400.50"),
        ("1 000", "1000"),
        ("0,5", "0.5"),
    ],
)
def test_parses_czech_grouped_input(page, mockserver, text, expected):
    """Czech input with space grouping and a comma decimal parses to a canonical decimal."""
    page.goto(f"{mockserver}/")
    assert parse(page, text, "cs") == expected


@pytest.mark.parametrize("text", ["abc", "1.2.3", "", "  ", None])
def test_unparseable_input_returns_null(page, mockserver, text):
    """Garbage, multi-dot, empty or missing input all parse to null, never NaN or a guess."""
    page.goto(f"{mockserver}/")
    assert parse(page, text, "en") is None


def test_non_breaking_space_groups_like_a_plain_space(page, mockserver):
    """A non-breaking space (the char some locales' NumberFormat actually emits) groups too."""
    page.goto(f"{mockserver}/")
    assert parse(page, "18 400,50", "cs") == "18400.50"
    assert parse(page, "18 400,50", "cs") == "18400.50"
