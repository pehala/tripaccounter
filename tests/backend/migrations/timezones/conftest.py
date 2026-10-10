"""Fixtures the time zone migration tests share: trips with items and transfers."""

from datetime import UTC

import pytest
import sqlalchemy as sa

TABLES = ("line_item", "wallet_transfer")


@pytest.fixture(params=TABLES)
def table_name(request):
    """Run a test once for each table that carries `occurred_at`."""
    return request.param


@pytest.fixture(scope="module")
def instants(connection, table):
    """Return `instants(name)`: `{id: occurred_at}` of a table as UTC-aware datetimes."""

    def read(name):
        rows = connection.execute(sa.select(table(name).c["id", "occurred_at"])).all()
        return {row_id: at if at.tzinfo else at.replace(tzinfo=UTC) for row_id, at in rows}

    return read


@pytest.fixture(scope="module")
def insert_trip(connection, table):
    """Return `insert_trip(trip_id, occurred, **trip_columns)`.

    It inserts a trip with a two-person roster, and an item and a transfer per instant.
    """

    def build(trip_id, occurred, **trip_columns):
        """Insert a trip with a two-person roster, and an item and a transfer per instant."""
        base = trip_id * 100

        def insert(table_name, **values):
            connection.execute(sa.insert(table(table_name)).values(**values))

        insert(
            "trip", id=trip_id, slug=f"trip-{trip_id}", name="Trip", archived=False, **trip_columns
        )
        for offset in (0, 1):
            insert(
                "person",
                id=base + offset,
                trip_id=trip_id,
                name=f"Person {offset}",
                color="#000000",
                default_weight_scaled=10000,
                sort_order=offset,
                active=True,
            )
            insert(
                "wallet",
                id=base + offset,
                trip_id=trip_id,
                person_id=base + offset,
                name="Cash",
                tracked=False,
                is_default=True,
            )
        insert("trip_currency", id=base, trip_id=trip_id, code="ISK", is_primary=True)
        insert("trip_country", id=base, trip_id=trip_id, name="Iceland", is_default=True)
        for index, instant in enumerate(occurred):
            insert(
                "line_item",
                id=base + index,
                trip_id=trip_id,
                name="Coffee",
                currency_id=base,
                payer_id=base,
                country_id=base,
                wallet_id=base,
                split_mode="equal",
                amount_minor=100,
                occurred_at=instant,
            )
            insert(
                "wallet_transfer",
                id=base + index,
                trip_id=trip_id,
                from_wallet_id=base,
                from_currency_id=base,
                to_wallet_id=base + 1,
                to_currency_id=base,
                from_amount_minor=100,
                to_amount_minor=100,
                occurred_at=instant,
            )

    return build


@pytest.fixture(scope="module")
def old_instants(create_old_data, instants):
    """Return the instants as the database held them before the migration ran."""
    return {name: instants(name) for name in TABLES}
