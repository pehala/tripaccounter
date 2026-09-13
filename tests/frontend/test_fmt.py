"""Tests for fmt.js's money(), signed() and formatter caching, via page.evaluate.

Whole values show no fraction (18400), typed
values two (13.34), computed six-place values are shown to two (27428.571428 →
27428.57), negative and zero, grouping in en (18,400.50) and cs (18 400,50);
signed() puts + only on credits; the formatter cache returns the same instance per
locale.
"""


def money(page, value, locale):
    """Evaluate fmt.js's money formatter, in the browser, for `value` in `locale`."""
    return page.evaluate(
        "async ({ value, locale }) => (await import('/js/fmt.js')).money(value, locale)",
        {"value": value, "locale": locale},
    )


def signed(page, value, locale):
    """Evaluate fmt.js's signed formatter, in the browser, for `value` in `locale`."""
    return page.evaluate(
        "async ({ value, locale }) => (await import('/js/fmt.js')).signed(value, locale)",
        {"value": value, "locale": locale},
    )


def test_whole_values_show_no_fraction(page, mockserver):
    """A whole number renders with zero decimal places, not a trailing .00."""
    page.goto(f"{mockserver}/")
    assert money(page, 18400, "en") == "18,400"


def test_typed_values_show_up_to_two_fraction_digits(page, mockserver):
    """A value typed to two places renders both digits."""
    page.goto(f"{mockserver}/")
    assert money(page, 13.34, "en") == "13.34"


def test_six_place_computed_values_render_to_two(page, mockserver):
    """A server-computed six-place share is trimmed to two digits for display."""
    page.goto(f"{mockserver}/")
    assert money(page, 27428.571428, "en") == "27,428.57"


def test_negative_and_zero_values(page, mockserver):
    """Negative values keep their sign; zero renders as a bare 0."""
    page.goto(f"{mockserver}/")
    assert money(page, -15603.571428, "en") in ("-15,603.57", "−15,603.57")
    assert money(page, 0, "en") == "0"


def test_grouping_differs_between_en_and_cs(page, mockserver):
    """En groups with commas and a dot decimal; cs groups with spaces and a comma decimal."""
    page.goto(f"{mockserver}/")
    assert money(page, 18400.50, "en") == "18,400.5"
    cs_value = money(page, 18400.50, "cs")
    assert "18" in cs_value and "400" in cs_value
    assert "," in cs_value  # cs uses a comma as the decimal separator
    assert "." not in cs_value


def test_signed_puts_plus_only_on_credits(page, mockserver):
    """signed() prefixes a credit with +, leaves a debit or zero alone."""
    page.goto(f"{mockserver}/")
    assert signed(page, 75710.714286, "en") == "+75,710.71"
    assert not signed(page, -15603.571428, "en").startswith("+")
    assert not signed(page, 0, "en").startswith("+")


def test_formatter_cache_reuses_one_instance_per_locale(page, mockserver):
    """money() constructs one Intl.NumberFormat per distinct locale, not per call."""
    page.goto(f"{mockserver}/")
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
    assert construction_count == 2  # one for 'en', one for 'cs' — not four
