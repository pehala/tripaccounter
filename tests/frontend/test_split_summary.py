"""Tests for components/splitSummary.js, via page.evaluate.

All four phrases in both locales:
`equally, 4 ways` / `rovným dílem, 4 lidé`, `equally, 3 of 4`, `shares
1·1·1·0.5`, `exact amounts` — the phrase is built from keys + Intl.PluralRules,
never concatenated words.
"""

import pytest


def split_summary(page, split, locale):
    """Evaluate splitSummary.js's splitSummary(split) in the browser, after setLocale()."""
    return page.evaluate(
        """async ({ split, locale }) => {
            const { setLocale } = await import('/js/i18n/index.js');
            setLocale(locale);
            const { splitSummary } = await import('/js/components/splitSummary.js');
            return splitSummary(split);
        }""",
        {"split": split, "locale": locale},
    )


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
        (EQUAL_ALL_FOUR, "en", "equally, 4 ways"),
        (EQUAL_ALL_FOUR, "cs", "rovným dílem, 4 lidé"),
        (EQUAL_PARTIAL, "en", "equally, 3 of 4"),
        (EQUAL_PARTIAL, "cs", "rovným dílem, 3 z 4"),
        (SHARES_MODE, "en", "shares 1·1·1·0.5"),
        (SHARES_MODE, "cs", "podíly 1·1·1·0.5"),
        (EXACT_MODE, "en", "exact amounts"),
        (EXACT_MODE, "cs", "přesné částky"),
    ],
)
def test_split_summary_phrase(page, mockserver, split, locale, expected):
    """Each mode/weight combination produces the exact catalog phrase in each locale."""
    page.goto(f"{mockserver}/")
    assert split_summary(page, split, locale) == expected
