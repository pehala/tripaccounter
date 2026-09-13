"""Best-effort coordinate extraction from a maps URL. Never fetches the URL."""

import re

_PATTERNS = [
    re.compile(r"@(-?\d+\.\d+),(-?\d+\.\d+)"),
    re.compile(r"!3d(-?\d+\.\d+)!4d(-?\d+\.\d+)"),
    re.compile(r"[?&]q=(-?\d+\.\d+),(-?\d+\.\d+)"),
]


def parse(url: str) -> tuple[str, str] | None:
    """Return the (lat, lon) pair found in a maps URL, or None if no pattern matches."""
    for pattern in _PATTERNS:
        match = pattern.search(url)
        if match:
            return match.group(1), match.group(2)
    return None
