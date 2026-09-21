"""Fixtures the map tab's suites share.

The pins the canned trip draws, the two page fixtures, and one helper for the cases
`trip.json` cannot express — several expenses at one coordinate, expenses on
different days — which are served as a per-test stub rather than by editing the
fixture every other suite reads.
"""

import pytest

CONTROLS = "Filters and selection"
NEEDLE = "filter by name or label"
MESSINN_PIN = '[data-pin="64.14930,-21.94030"]'
FUEL_PIN = '[data-pin="63.93330,-20.99000"]'


@pytest.fixture
def map_page(open_trip):
    """Return the page with the trip loaded on the Map tab."""
    return open_trip("map")


@pytest.fixture(scope="session")
def shared_map_page(shared_trip):
    """Return the session's read-only Map tab."""
    return shared_trip("map")


@pytest.fixture
def serve_items(stub, fixture_data):
    """Return `serve_items(items)`: serve this trip's item list with `items` in its place."""

    def install(items):
        stub(
            "**/api/v1/trips/*/items",
            lambda request: (200, {**fixture_data["items"], "items": items}),
        )

    return install
