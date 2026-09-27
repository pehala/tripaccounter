"""Functional tests for `GET /trips/{slug}/exchange-rates`: effective rate per person and pair."""

import pytest

DAY1 = "2026-09-13T12:00:00"
DAY2 = "2026-09-14T12:00:00"


@pytest.fixture()
def currency_ids(client, trip, currencies):
    """Map currency code to id: the trip's ISK and EUR, plus an added CZK."""
    czk = client.post(f"/api/v1/trips/{trip['slug']}/currencies", json={"code": "CZK"})
    assert czk.status_code == 201, czk.text
    return {c["code"]: c["id"] for c in [*currencies, czk.json()["currency"]]}


@pytest.fixture()
def record(client, trip, default_wallet_of, item_body, currency_ids):
    """Return a function posting one person's exchanges and spends.

    Each person gets their `Card` plus tracked `Cash` and `Envelope`. A transfer is
    `(occurred_at, from_wallet, amount, code, to_wallet, amount, code)`, a spend
    `(wallet, amount, code)`.
    """

    def post(person_id, transfers=(), spends=()):
        wallets = {"Card": default_wallet_of(person_id)["id"]}
        for name in ("Cash", "Envelope"):
            response = client.post(
                f"/api/v1/trips/{trip['slug']}/wallets",
                json={"person_id": person_id, "name": name, "tracked": True},
            )
            assert response.status_code == 201, response.text
            wallets[name] = response.json()["wallet"]["id"]
        for (
            occurred_at,
            from_wallet,
            from_amount,
            from_code,
            to_wallet,
            to_amount,
            to_code,
        ) in transfers:
            response = client.post(
                f"/api/v1/trips/{trip['slug']}/transfers",
                json={
                    "from_wallet_id": wallets[from_wallet],
                    "from_amount": from_amount,
                    "from_currency_id": currency_ids[from_code],
                    "to_wallet_id": wallets[to_wallet],
                    "to_amount": to_amount,
                    "to_currency_id": currency_ids[to_code],
                    "occurred_at": occurred_at,
                },
            )
            assert response.status_code == 201, response.text
        for wallet, amount, code in spends:
            response = client.post(
                f"/api/v1/trips/{trip['slug']}/items",
                json=item_body(
                    amount=amount,
                    payer_id=person_id,
                    wallet_id=wallets[wallet],
                    currency_id=currency_ids[code],
                ),
            )
            assert response.status_code == 201, response.text

    return post


@pytest.fixture()
def get_rates(client, trip):
    """Return a function that fetches the trip's exchange rates."""

    def get():
        return client.get(f"/api/v1/trips/{trip['slug']}/exchange-rates")

    return get


@pytest.mark.parametrize(
    ("history", "expected"),
    [
        pytest.param(
            {"transfers": [(DAY1, "Card", "200", "EUR", "Card", "300", "ISK")], "spends": []},
            [("EUR", "ISK", 0.666666666, 0, None)],
            id="untracked-wallet-holds-nothing-rate-floored",
        ),
        pytest.param(
            {
                "transfers": [(DAY1, "Card", "150", "EUR", "Cash", "21200", "ISK")],
                "spends": [("Cash", "19000", "ISK")],
            },
            [("EUR", "ISK", 0.007075471, 2200, 0.007075471)],
            id="leftover-priced-apart-from-spent",
        ),
        pytest.param(
            {
                "transfers": [
                    (DAY2, "Card", "100", "EUR", "Cash", "10000", "ISK"),
                    (DAY1, "Card", "100", "EUR", "Cash", "14000", "ISK"),
                ],
                "spends": [("Cash", "20000", "ISK")],
            },
            [("EUR", "ISK", 0.008, 4000, 0.01)],
            id="spent-uses-oldest-lot-first",
        ),
        pytest.param(
            {
                "transfers": [
                    (DAY1, "Card", "20", "EUR", "Cash", "18", "CZK"),
                    (DAY2, "Card", "5", "EUR", "Cash", "4", "CZK"),
                ],
                "spends": [("Cash", "15", "CZK")],
            },
            [("EUR", "CZK", 1.111111111, 7, 1.19047619)],
            id="leftover-spans-two-lots",
        ),
        pytest.param(
            {
                "transfers": [(DAY1, "Cash", "20", "EUR", "Cash", "150", "CZK")],
                "spends": [("Cash", "100", "CZK")],
            },
            [("EUR", "CZK", 0.133333333, 50, 0.133333333)],
            id="exchange-inside-one-wallet",
        ),
        pytest.param(
            {
                "transfers": [
                    (DAY1, "Card", "150", "EUR", "Cash", "21200", "ISK"),
                    (DAY2, "Cash", "2200", "ISK", "Card", "14", "EUR"),
                ],
                "spends": [("Cash", "19000", "ISK")],
            },
            [("EUR", "ISK", 0.007075471, 0, None)],
            id="changed-back-is-neither-spent-nor-held",
        ),
        pytest.param(
            {
                "transfers": [(DAY1, "Card", "100", "EUR", "Cash", "10000", "ISK")],
                "spends": [("Cash", "8000", "ISK"), ("Envelope", "500", "ISK")],
            },
            [("EUR", "ISK", 0.01, 2000, 0.01)],
            id="overcharged-wallet-holds-nothing",
        ),
        pytest.param(
            {
                "transfers": [
                    (DAY1, "Card", "100", "EUR", "Cash", "15000", "ISK"),
                    (DAY2, "Card", "1000", "CZK", "Cash", "5000", "ISK"),
                ],
                "spends": [("Cash", "16000", "ISK")],
            },
            [("CZK", "ISK", 0.2, 4000, 0.2), ("EUR", "ISK", 0.006666666, 0, None)],
            id="lots-from-two-funding-currencies-share-one-queue",
        ),
        pytest.param(
            {
                "transfers": [
                    (DAY1, "Card", "20000", "ISK", "Cash", "20000", "ISK"),
                    (DAY1, "Card", "100", "EUR", "Cash", "10000", "ISK"),
                    (DAY2, "Cash", "2000", "ISK", "Card", "10", "EUR"),
                ],
                "spends": [("Cash", "5000", "ISK")],
            },
            [("EUR", "ISK", None, 8000, 0.01)],
            id="held-capped-at-what-was-exchanged",
        ),
        pytest.param(
            {"transfers": [(DAY1, "Card", "100", "EUR", "Cash", "14000", "ISK")], "spends": []},
            [("EUR", "ISK", None, 14000, 0.007142857)],
            id="nothing-spent-no-rate",
        ),
        pytest.param(
            {
                "transfers": [
                    (DAY1, "Card", "100", "EUR", "Cash", "14000", "ISK"),
                    (DAY2, "Cash", "14000", "ISK", "Card", "101", "EUR"),
                ],
                "spends": [],
            },
            [("ISK", "EUR", None, 0, None)],
            id="changed-back-more-than-bought-no-rate",
        ),
        pytest.param(
            {
                "transfers": [(DAY1, "Card", "20000", "ISK", "Cash", "20000", "ISK")],
                "spends": [("Cash", "100", "ISK")],
            },
            [],
            id="plain-transfer-no-row",
        ),
    ],
)
def test_exchange_rate_per_pair(person_id, record, get_rates, history, expected):
    """One person's exchanges price what was spent and what is held, first in first out."""
    petr = person_id("Petr")
    record(petr, **history)

    response = get_rates()

    assert response.status_code == 200
    assert response.json() == {
        "exchange_rates": [
            {
                "person_id": petr,
                "from_currency_code": from_code,
                "to_currency_code": to_code,
                "rate": rate,
                "leftover": leftover,
                "leftover_rate": leftover_rate,
            }
            for from_code, to_code, rate, leftover, leftover_rate in expected
        ]
    }


def test_exchange_rate_rows_per_person_in_roster_order(person_id, record, get_rates):
    """Each person gets their own row, and another person's cash never counts as held."""
    petr, ann = person_id("Petr"), person_id("Ann")
    record(
        ann,
        [(DAY1, "Card", "100", "EUR", "Cash", "12500", "ISK")],
        [("Cash", "12500", "ISK")],
    )
    record(
        petr,
        [(DAY1, "Card", "100", "EUR", "Cash", "14000", "ISK")],
        [("Cash", "10000", "ISK")],
    )

    assert get_rates().json()["exchange_rates"] == [
        {
            "person_id": petr,
            "from_currency_code": "EUR",
            "to_currency_code": "ISK",
            "rate": 0.007142857,
            "leftover": 4000,
            "leftover_rate": 0.007142857,
        },
        {
            "person_id": ann,
            "from_currency_code": "EUR",
            "to_currency_code": "ISK",
            "rate": 0.008,
            "leftover": 0,
            "leftover_rate": None,
        },
    ]
