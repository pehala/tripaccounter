"""Functional tests for the demo seed: it loads, and the API reads it back.

`seed_demo` is called directly because the seed has no endpoint - it is what
`make seed` runs. Everything it wrote is then asserted through `client`.
"""

import pytest

from app.seed import seed_demo

SLUG = "iceland-2026"


def test_seed_demo_trip_reads_back_with_its_full_roster(client, session):
    """The seeded trip is readable by slug and carries the roster the demo describes."""
    seed_demo(session)

    trip = client.get(f"/api/v1/trips/{SLUG}").json()["trip"]

    assert trip["name"] == "Iceland 2026"
    assert [person["name"] for person in trip["people"]] == ["Petr", "Ann", "Bob", "Eva"]
    assert [currency["code"] for currency in trip["currencies"]] == ["ISK", "DKK", "EUR"]
    assert [country["name"] for country in trip["countries"]] == ["Iceland", "Denmark"]
    assert len(trip["wallets"]) == 6


def test_seed_demo_items_envelope_carries_every_seeded_row(client, session):
    """The seeded items and transfers all come back on the items envelope."""
    seed_demo(session)

    envelope = client.get(f"/api/v1/trips/{SLUG}/items").json()

    assert len(envelope["items"]) == 5
    assert len(envelope["transfers"]) == 3


@pytest.mark.parametrize(
    "report",
    [
        pytest.param("balances", id="balances"),
        pytest.param("stats", id="stats"),
        pytest.param("wallets", id="wallets"),
        pytest.param("labels", id="labels"),
    ],
)
def test_seed_demo_aggregates_compute_over_the_seeded_rows(client, session, report):
    """Every aggregate endpoint answers for the seeded trip."""
    seed_demo(session)

    response = client.get(f"/api/v1/trips/{SLUG}/{report}")

    assert response.status_code == 200, response.text
