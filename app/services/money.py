"""Integer money arithmetic. No parsing, no rounding, no formatting.

Hundredths (minor units) are the stored scale for anything a human typed.
Micro-units (10^-6) are the scale for anything computed (a view expression).
`to_wire` is the one place either scale turns into a JSON number, at the
serializer edge; nothing downstream of it ever feeds back into a column.
"""

AMOUNT_SCALE = 100
WEIGHT_SCALE = 10_000
MICRO_SCALE = 1_000_000
MICRO_PER_MINOR = MICRO_SCALE // AMOUNT_SCALE


def to_hundredths(amount) -> int:
    """Decimal -> int hundredths. Exact: amount is already <= 2 decimal places."""
    scaled = amount * AMOUNT_SCALE
    return int(scaled)


def scale_weight(weight) -> int:
    """Decimal -> int, weight scaled by 10**4."""
    scaled = weight * WEIGHT_SCALE
    return int(scaled)


def to_wire(value: int, scale: int) -> int | float:
    """Int minor units -> a plain JSON number, dividing once, at the edge."""
    if value % scale == 0:
        return value // scale
    return value / scale
