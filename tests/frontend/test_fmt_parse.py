"""Tests for fmt.js's parse(), via page.evaluate.

Locale text becomes a canonical decimal string: en `18,400.50` -> `18400.50`, cs
`18 400,50` -> `18400.50` with either a plain or a non-breaking space as the group
separator; garbage, multi-dot, empty or missing input parse to null.
"""

import pytest


@pytest.mark.parametrize(
    ("text", "locale", "expected"),
    [
        pytest.param("18,400.50", "en", "18400.50", id="en-grouped"),
        pytest.param("1,000", "en", "1000", id="en-thousands"),
        pytest.param("18400.5", "en", "18400.5", id="en-plain"),
        pytest.param("-5", "en", "-5", id="en-negative"),
        pytest.param("18 400,50", "cs", "18400.50", id="cs-grouped"),
        pytest.param("18\u00a0400,50", "cs", "18400.50", id="cs-grouped-nbsp"),
        pytest.param("1 000", "cs", "1000", id="cs-thousands"),
        pytest.param("0,5", "cs", "0.5", id="cs-decimal"),
        pytest.param("abc", "en", None, id="garbage"),
        pytest.param("1.2.3", "en", None, id="multi-dot"),
        pytest.param("", "en", None, id="empty"),
        pytest.param("  ", "en", None, id="blank"),
        pytest.param(None, "en", None, id="missing"),
    ],
)
def test_parse(js, text, locale, expected):
    """Locale-grouped input parses to a canonical decimal; unparseable input is null, not NaN."""
    assert js("fmt.js", "parse", text, locale) == expected
