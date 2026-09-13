"""Tests for components/splitSummary.js, via page.evaluate.

All four phrases in both locales: the phrase is built from catalog keys and
Intl.PluralRules, never concatenated words.
"""

import pytest


def shares(*weights):
    """Build a `split.shares` array with the given weights, in roster order."""
    return [{"person_id": i + 1, "weight": w, "owed": None} for i, w in enumerate(weights)]


EQUAL_ALL_FOUR = {"mode": "equal", "shares": shares("1", "1", "1", "1")}
EQUAL_PARTIAL = {"mode": "equal", "shares": shares("1", "1", "1", None)}
SHARES_MODE = {"mode": "shares", "shares": shares("1", "1", "1", "0.5")}
EXACT_MODE = {"mode": "exact", "shares": shares("1", "1", "1", "1")}


@pytest.mark.parametrize(
    ("split", "locale", "expected"),
    [
        pytest.param(EQUAL_ALL_FOUR, "en", "equally, 4 ways", id="equal-all-en"),
        pytest.param(EQUAL_ALL_FOUR, "cs", "rovným dílem, 4 lidé", id="equal-all-cs"),
        pytest.param(EQUAL_PARTIAL, "en", "equally, 3 of 4", id="equal-partial-en"),
        pytest.param(EQUAL_PARTIAL, "cs", "rovným dílem, 3 z 4", id="equal-partial-cs"),
        pytest.param(SHARES_MODE, "en", "shares 1·1·1·0.5", id="shares-en"),
        pytest.param(SHARES_MODE, "cs", "podíly 1·1·1·0.5", id="shares-cs"),
        pytest.param(EXACT_MODE, "en", "exact amounts", id="exact-en"),
        pytest.param(EXACT_MODE, "cs", "přesné částky", id="exact-cs"),
    ],
)
def test_split_summary_phrase(js, split, locale, expected):
    """Each mode/weight combination produces the exact catalog phrase in each locale."""
    assert js("components/splitSummary.js", "splitSummary", split, locale=locale) == expected
