"""Fixtures the Setup tab's suites share."""

import pytest


@pytest.fixture
def setup_card(setup_page, card):
    """Return `card(header_text)` with the trip loaded on the Setup tab."""
    return card
