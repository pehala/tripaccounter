"""Functional tests for the wallets report and wallet CRUD."""


def test_wallets_report_lists_every_wallet_untracked_empty(client, trip, wallets):
    """An untracked wallet (the default Card) always reports an empty balances list."""
    response = client.get(f"/api/v1/trips/{trip['slug']}/wallets")

    assert response.status_code == 200
    body = response.json()["wallets"]
    assert len(body) == len(wallets)
    for wallet in body:
        if not wallet["tracked"]:
            assert wallet["balances"] == []


def test_wallets_report_tracked_wallet_shows_funded_and_spent_balance(
    client, trip, person_id, default_wallet_of, item_body
):
    """Funding a tracked wallet then spending from it nets `received - spent`."""
    petr = person_id("Petr")
    card = default_wallet_of(petr)["id"]
    cash = client.post(
        f"/api/v1/trips/{trip['slug']}/wallets",
        json={"person_id": petr, "name": "Cash", "tracked": True},
    ).json()["wallet"]

    client.post(
        f"/api/v1/trips/{trip['slug']}/transfers",
        json={
            "from_wallet_id": card,
            "from_amount": "20000",
            "from_currency_id": trip["currencies"][0]["id"],
            "to_wallet_id": cash["id"],
        },
    )
    client.post(
        f"/api/v1/trips/{trip['slug']}/items",
        json=item_body(amount="18400.00", payer_id=petr, wallet_id=cash["id"]),
    )

    report = client.get(f"/api/v1/trips/{trip['slug']}/wallets").json()["wallets"]
    cash_report = next(w for w in report if w["id"] == cash["id"])
    assert cash_report["balances"] == [
        {
            "currency_code": "ISK",
            "currency_id": trip["currencies"][0]["id"],
            "received": 20000,
            "sent": 0,
            "spent": 18400,
            "balance": 1600,
        }
    ]


def test_wallets_report_overcharge_is_a_negative_balance(
    client, trip, person_id, default_wallet_of, item_body
):
    """Spending more than a tracked wallet ever received leaves a negative balance."""
    ann = person_id("Ann")
    envelope = client.post(
        f"/api/v1/trips/{trip['slug']}/wallets",
        json={"person_id": ann, "name": "Envelope", "tracked": True},
    ).json()["wallet"]

    client.post(
        f"/api/v1/trips/{trip['slug']}/items",
        json=item_body(
            amount="480.00",
            payer_id=ann,
            wallet_id=envelope["id"],
            currency_id=trip["currencies"][1]["id"],
        ),
    )

    report = client.get(f"/api/v1/trips/{trip['slug']}/wallets").json()["wallets"]
    envelope_report = next(w for w in report if w["id"] == envelope["id"])
    assert envelope_report["balances"] == [
        {
            "currency_code": "EUR",
            "currency_id": trip["currencies"][1]["id"],
            "received": 0,
            "sent": 0,
            "spent": 480,
            "balance": -480,
        }
    ]


def test_wallets_report_exchange_debits_one_currency_credits_another(
    client, trip, person_id, default_wallet_of
):
    """An exchange in one wallet is a `sent` row in one currency, `received` in another."""
    petr = person_id("Petr")
    cash = client.post(
        f"/api/v1/trips/{trip['slug']}/wallets",
        json={"person_id": petr, "name": "Cash", "tracked": True},
    ).json()["wallet"]
    isk, eur = trip["currencies"][0]["id"], trip["currencies"][1]["id"]

    client.post(
        f"/api/v1/trips/{trip['slug']}/transfers",
        json={
            "from_wallet_id": cash["id"],
            "from_amount": "20",
            "from_currency_id": eur,
            "to_wallet_id": cash["id"],
            "to_amount": "2800",
            "to_currency_id": isk,
        },
    )

    report = client.get(f"/api/v1/trips/{trip['slug']}/wallets").json()["wallets"]
    cash_report = next(w for w in report if w["id"] == cash["id"])
    by_currency = {row["currency_id"]: row for row in cash_report["balances"]}
    assert by_currency[eur]["sent"] == 20
    assert by_currency[eur]["balance"] == -20
    assert by_currency[isk]["received"] == 2800
    assert by_currency[isk]["balance"] == 2800


def test_wallets_report_currency_order_is_primary_then_code(
    client, trip, person_id, default_wallet_of
):
    """Balance rows are ordered primary currency first, then by code, not by insertion."""
    petr = person_id("Petr")
    cash = client.post(
        f"/api/v1/trips/{trip['slug']}/wallets",
        json={"person_id": petr, "name": "Cash", "tracked": True},
    ).json()["wallet"]
    isk, eur = trip["currencies"][0]["id"], trip["currencies"][1]["id"]

    # Fund the EUR side first, then the ISK side - insertion order is reversed
    # from the report order (ISK is primary, so it leads).
    client.post(
        f"/api/v1/trips/{trip['slug']}/transfers",
        json={
            "from_wallet_id": default_wallet_of(petr)["id"],
            "from_amount": "10",
            "from_currency_id": eur,
            "to_wallet_id": cash["id"],
        },
    )
    client.post(
        f"/api/v1/trips/{trip['slug']}/transfers",
        json={
            "from_wallet_id": default_wallet_of(petr)["id"],
            "from_amount": "1000",
            "from_currency_id": isk,
            "to_wallet_id": cash["id"],
        },
    )

    report = client.get(f"/api/v1/trips/{trip['slug']}/wallets").json()["wallets"]
    cash_report = next(w for w in report if w["id"] == cash["id"])
    assert [row["currency_id"] for row in cash_report["balances"]] == [isk, eur]


def test_create_wallet_duplicate_name_is_409(client, trip, person_id):
    """Two wallets with the same name for the same person conflict."""
    petr = person_id("Petr")
    client.post(
        f"/api/v1/trips/{trip['slug']}/wallets",
        json={"person_id": petr, "name": "Cash", "tracked": True},
    )
    response = client.post(
        f"/api/v1/trips/{trip['slug']}/wallets",
        json={"person_id": petr, "name": "Cash", "tracked": False},
    )
    assert response.status_code == 409
    assert response.json()["error"]["fields"]["name"] == {
        "code": "duplicate",
        "params": {"name": "Cash"},
    }


def test_update_wallet_is_default_moves_the_flag(client, trip, person_id, default_wallet_of):
    """Making a new wallet the default un-defaults the old one."""
    petr = person_id("Petr")
    cash = client.post(
        f"/api/v1/trips/{trip['slug']}/wallets",
        json={"person_id": petr, "name": "Cash", "tracked": True},
    ).json()["wallet"]

    client.patch(f"/api/v1/trips/{trip['slug']}/wallets/{cash['id']}", json={"is_default": True})

    updated_trip = client.get(f"/api/v1/trips/{trip['slug']}").json()["trip"]
    petr_wallets = [w for w in updated_trip["wallets"] if w["person_id"] == petr]
    assert sum(1 for w in petr_wallets if w["is_default"]) == 1
    assert next(w for w in petr_wallets if w["id"] == cash["id"])["is_default"] is True


def test_delete_default_wallet_is_409(client, trip, default_wallet_of, people):
    """A person's default wallet can't be deleted while it holds that role."""
    card = default_wallet_of(people[0]["id"])
    response = client.delete(f"/api/v1/trips/{trip['slug']}/wallets/{card['id']}")
    assert response.status_code == 409
    assert response.json()["error"]["fields"]["id"]["code"] == "is_default"


def test_delete_wallet_in_use_by_item_is_409(client, trip, person_id, item_body):
    """A wallet referenced by an item can't be deleted."""
    petr = person_id("Petr")
    cash = client.post(
        f"/api/v1/trips/{trip['slug']}/wallets",
        json={"person_id": petr, "name": "Cash", "tracked": True},
    ).json()["wallet"]
    client.post(
        f"/api/v1/trips/{trip['slug']}/items", json=item_body(payer_id=petr, wallet_id=cash["id"])
    )

    response = client.delete(f"/api/v1/trips/{trip['slug']}/wallets/{cash['id']}")
    assert response.status_code == 409
    assert response.json()["error"]["fields"]["id"] == {
        "code": "in_use",
        "params": {"count": 1, "name": "Cash"},
    }


def test_wallet_list_is_default_then_name(client, trip, person_id):
    """A person's wallets lead with their default `Card`, the rest follow by name."""
    petr = person_id("Petr")
    for name in ("Purse", "Cash"):
        client.post(f"/api/v1/trips/{trip['slug']}/wallets", json={"person_id": petr, "name": name})

    wallets = client.get(f"/api/v1/trips/{trip['slug']}").json()["trip"]["wallets"]

    assert [w["name"] for w in wallets if w["person_id"] == petr] == ["Card", "Cash", "Purse"]
