"""Derive a flag emoji from an ISO-3166 alpha-2 country code."""


def flag_from_code(code: str | None) -> str | None:
    """ISO-3166 alpha-2 -> the flag emoji, via the regional indicator pair."""
    if not code or len(code) != 2 or not code.isalpha():
        return None
    return "".join(chr(0x1F1E6 + ord(letter) - ord("A")) for letter in code.upper())
