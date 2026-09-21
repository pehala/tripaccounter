"""Shared fixtures for backend functional tests.

Every fixture builds its state through the API - `trip` is one `POST /trips`, the
roster fixtures index into its response, `item_body` builds a valid write body a
test overrides one field of. A test therefore holds exactly what a client holds,
and its setup is itself a check that the write path accepts it.
"""

from pathlib import Path

import pytest
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from alembic import command
from app.clock import current_time
from app.db import get_session
from app.main import app

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
ALEMBIC_SCRIPT_LOCATION = REPO_ROOT / "alembic"


@pytest.fixture(scope="session")
def engine():
    """Build an in-memory SQLite engine, schema created by the real Alembic migration.

    Not `metadata.create_all` - so a migration bug fails tests the same way
    it would fail `make migrate`.
    """
    eng = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    alembic_cfg = Config()
    alembic_cfg.set_main_option("script_location", str(ALEMBIC_SCRIPT_LOCATION))
    with eng.connect() as connection:
        alembic_cfg.attributes["connection"] = connection
        command.upgrade(alembic_cfg, "head")
    return eng


@pytest.fixture()
def session(engine):
    """Yield a SQLAlchemy session bound to a rolled-back-after transaction."""
    with engine.connect() as connection:
        transaction = connection.begin()
        factory = sessionmaker(bind=connection, autoflush=False, expire_on_commit=False)
        db_session = factory()
        yield db_session
        db_session.close()
        transaction.rollback()


@pytest.fixture(scope="session", autouse=True)
def error_codes():
    """Collect every error code the test session's requests come back with."""
    return set()


@pytest.fixture()
def client(session, error_codes, monkeypatch):
    """Build a TestClient wired to `session`, recording error codes it sees."""

    def override_get_session():
        yield session

    monkeypatch.setitem(app.dependency_overrides, get_session, override_get_session)

    class RecordingClient(TestClient):
        def request(self, *args, **kwargs):
            response = super().request(*args, **kwargs)
            if response.status_code >= 400:
                try:
                    body = response.json()
                except ValueError:
                    body = {}
                error = body.get("error") or {}
                if error.get("code"):
                    error_codes.add(error["code"])
                for field_error in (error.get("fields") or {}).values():
                    if field_error.get("code"):
                        error_codes.add(field_error["code"])
            return response

    with RecordingClient(app) as test_client:
        yield test_client


@pytest.fixture()
def frozen_clock(monkeypatch):
    """Return a function that overrides `current_time` to a fixed datetime."""

    def _freeze(dt):
        monkeypatch.setitem(app.dependency_overrides, current_time, lambda: dt)

    return _freeze


@pytest.fixture()
def trip(client):
    """Return the trip JSON from one `POST /trips` - 4 people, ISK + EUR primary, one country.

    Prefer the narrower `people` / `currencies` / `countries` /
    `country` fixtures below when a test only needs one roster.
    """
    body = {
        "name": "Iceland 2026",
        "start_date": "2026-09-12",
        "end_date": "2026-09-21",
        "people": [
            {"name": "Petr"},
            {"name": "Ann"},
            {"name": "Bob"},
            {"name": "Eva", "default_weight": "0.5"},
        ],
        "currencies": [{"code": "ISK", "is_primary": True}, {"code": "EUR"}],
        "countries": [{"name": "Iceland", "code": "IS"}],
    }
    response = client.post("/api/v1/trips", json=body)
    assert response.status_code == 201, response.text
    return response.json()["trip"]


@pytest.fixture()
def people(trip):
    """List the trip's four people, in `sort_order`: Petr, Ann, Bob, Eva (weight 0.5)."""
    return trip["people"]


@pytest.fixture()
def person_id(people):
    """Return a function that finds a person's id by name."""

    def _find(name):
        return next(p["id"] for p in people if p["name"] == name)

    return _find


@pytest.fixture()
def currencies(trip):
    """List the trip's currencies: ISK (primary) then EUR."""
    return trip["currencies"]


@pytest.fixture()
def countries(trip):
    """List the trip's countries: Iceland only."""
    return trip["countries"]


@pytest.fixture()
def currency(currencies):
    """Return the trip's primary currency, ISK."""
    return currencies[0]


@pytest.fixture()
def country(countries):
    """Return the trip's only country, Iceland."""
    return countries[0]


@pytest.fixture()
def wallets(trip):
    """List the trip's wallets: each person's default `Card`, in owner roster order."""
    return trip["wallets"]


@pytest.fixture()
def default_wallet_of(wallets):
    """Return a function that finds a person's default wallet by person id."""

    def _find(person_id):
        return next(w for w in wallets if w["person_id"] == person_id and w["is_default"])

    return _find


@pytest.fixture()
def transfer_body(default_wallet_of, people, currencies):
    """Return a function that builds a valid transfer POST body, with overrides."""

    def _build(**overrides):
        body = {
            "from_wallet_id": default_wallet_of(people[0]["id"])["id"],
            "from_amount": "100.00",
            "from_currency_id": currencies[0]["id"],
            "to_wallet_id": default_wallet_of(people[1]["id"])["id"],
            "occurred_at": "2026-09-14T12:00:00",
            "note": None,
        }
        body.update(overrides)
        return body

    return _build


@pytest.fixture()
def item_body(trip, people, currencies, countries):
    """Return a function that builds a valid item POST body, with overrides."""

    def _build(**overrides):
        body = {
            "name": "Test item",
            "amount": "100.00",
            "currency_id": currencies[0]["id"],
            "payer_id": people[0]["id"],
            "country_id": countries[0]["id"],
            "occurred_at": "2026-09-14T12:00:00",
            "labels": [],
            "map_url": None,
            "lat": None,
            "lon": None,
            "split_mode": "equal",
            "shares": None,
        }
        body.update(overrides)
        return body

    return _build


@pytest.fixture()
def items_two_same_day_one_earlier(client, trip, item_body):
    """Create three items: two posted for 2026-07-02, one for 2026-07-01.

    The earlier item sets up the occurred_at/id tie-break ordering test.
    """
    dates = ("2026-07-01T09:00:00", "2026-07-02T09:00:00", "2026-07-02T09:00:00")
    return [
        client.post(f"/api/v1/trips/{trip['slug']}/items", json=item_body(occurred_at=d)).json()[
            "item"
        ]
        for d in dates
    ]


@pytest.fixture()
def scenario_items(client, trip, person_id, item_body):
    """Create one shared, richer batch of items in the standard `trip`.

    Pre-created for every functional test whose behaviour only shows up once
    several items exist: stats grouping (`by_day`/`by_country`/`by_person`/
    `by_label`), label normalization/ordering, and balance suggestions. Each
    test reads only the slice of this batch its own assertion needs; none of
    it is created inline in a test body.
    """

    def _post(**overrides):
        overrides.setdefault("occurred_at", "2026-07-02T10:00:00")
        return client.post(
            f"/api/v1/trips/{trip['slug']}/items", json=item_body(**overrides)
        ).json()["item"]

    return {
        "day1_labelled": _post(
            amount="100.00", occurred_at="2026-07-01T09:00:00", labels=["dining", "fun"]
        ),
        "day1_evening": _post(amount="20.00", occurred_at="2026-07-01T20:00:00"),
        "day2_unlabelled": _post(amount="50.00", occurred_at="2026-07-02T09:00:00"),
        "food_casing_titlecase": _post(amount="10.00", labels=["Food"]),
        "food_casing_lower": _post(amount="10.00", labels=["food"]),
        "food_casing_padded": _post(amount="10.00", labels=[" food "]),
        "label_b_and_a": _post(amount="10.00", labels=["b", "a"]),
        "label_b_only": _post(amount="10.00", labels=["b"]),
        "balance_eva_pays": _post(amount="184.00", payer_id=person_id("Eva")),
        "balance_bob_pays": _post(amount="79.00", payer_id=person_id("Bob")),
    }
