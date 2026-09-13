"""Tests for fmt.js's money(), signed() and formatter caching, via page.evaluate.

Whole values show no fraction, typed values two, computed six-place values are
trimmed to two, negative and zero keep their shape, grouping follows the locale;
signed() puts + only on credits; the formatter cache returns one instance per locale.
"""

import pytest


@pytest.mark.parametrize(
    ("value", "locale", "expected"),
    [
        pytest.param(18400, "en", "18,400", id="whole-no-fraction"),
        pytest.param(13.34, "en", "13.34", id="two-typed-decimals"),
        pytest.param(27428.571428, "en", "27,428.57", id="six-place-to-two"),
        pytest.param(-15603.571428, "en", "-15,603.57", id="negative"),
        pytest.param(0, "en", "0", id="zero"),
        pytest.param(18400.50, "en", "18,400.5", id="en-grouping"),
        pytest.param(18400.50, "cs", "18\u00a0400,5", id="cs-grouping"),
    ],
)
def test_money(js, value, locale, expected):
    """money() shows whole values bare, trims six-place values to two, groups per locale."""
    assert js("fmt.js", "money", value, locale) == expected


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        pytest.param(75710.714286, "+75,710.71", id="credit-plus"),
        pytest.param(-15603.571428, "-15,603.57", id="debit-no-plus"),
        pytest.param(0, "0", id="zero-no-plus"),
    ],
)
def test_signed_puts_plus_only_on_credits(js, value, expected):
    """signed() prefixes a credit with +, leaves a debit or zero alone."""
    assert js("fmt.js", "signed", value, "en") == expected


def test_formatter_cache_reuses_one_instance_per_locale(page, js):
    """money() constructs one Intl.NumberFormat per distinct locale, not per call."""
    construction_count = page.evaluate(
        """async () => {
            let calls = 0;
            const OriginalNumberFormat = Intl.NumberFormat;
            Intl.NumberFormat = function (...args) {
                calls += 1;
                return new OriginalNumberFormat(...args);
            };
            const { money } = await import('/js/fmt.js');
            money(1, 'en');
            money(2, 'en');
            money(3, 'en');
            money(4, 'cs');
            Intl.NumberFormat = OriginalNumberFormat;
            return calls;
        }"""
    )
    assert construction_count == 2
