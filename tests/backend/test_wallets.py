"""Functional tests for the wallets report and wallet CRUD."""


def test_wallets_report_lists_every_wallet_untracked_empty(client, trip_url, wallets):
    """An untracked wallet (the default Card) always reports an empty balances list."""
    response = client.get(f"{trip_url}/wallets")

    assert response.status_code == 200
    body = response.json()["wallets"]
    assert len(body) == len(wallets)
    for wallet in body:
        if not wallet["tracked"]:
            assert wallet["balances"] == []


def test_wallets_report_tracked_wallet_shows_funded_and_spent_balance(  # noqa: PLR0913, PLR0917 (the fixtures are the setup)
    client, currencies, person_id, default_wallet_of, item_body, trip_url, create
):
    """Funding a tracked wallet then spending from it nets `received - spent`."""
    petr = person_id("Petr")
    card = default_wallet_of(petr)["id"]
    cash = create("wallets", {"person_id": petr, "name": "Cash", "tracked": True})

    create(
        "transfers",
        {
            "from_wallet_id": card,
            "from_amount": "20000",
            "from_currency_id": currencies[0]["id"],
            "to_wallet_id": cash["id"],
        },
    )
    create("items", item_body(amount="18400.00", payer_id=petr, wallet_id=cash["id"]))

    report = client.get(f"{trip_url}/wallets").json()["wallets"]
    cash_report = next(w for w in report if w["id"] == cash["id"])
    assert cash_report["balances"] == [
        {
            "currency_code": "ISK",
            "currency_id": currencies[0]["id"],
            "received": 20000,
            "sent": 0,
            "spent": 18400,
            "balance": 1600,
        }
    ]


def test_wallets_report_overcharge_is_a_negative_balance(  # noqa: PLR0913, PLR0917 (the fixtures are the setup)
    client, currencies, person_id, default_wallet_of, item_body, trip_url, create
):
    """Spending more than a tracked wallet ever received leaves a negative balance."""
    ann = person_id("Ann")
    envelope = create("wallets", {"person_id": ann, "name": "Envelope", "tracked": True})

    create(
        "items",
        item_body(
            amount="480.00",
            payer_id=ann,
            wallet_id=envelope["id"],
            currency_id=currencies[1]["id"],
        ),
    )

    report = client.get(f"{trip_url}/wallets").json()["wallets"]
    envelope_report = next(w for w in report if w["id"] == envelope["id"])
    assert envelope_report["balances"] == [
        {
            "currency_code": "EUR",
            "currency_id": currencies[1]["id"],
            "received": 0,
            "sent": 0,
            "spent": 480,
            "balance": -480,
        }
    ]


def test_wallets_report_exchange_debits_one_currency_credits_another(  # noqa: PLR0913, PLR0917 (the fixtures are the setup)
    client, currencies, person_id, default_wallet_of, trip_url, create
):
    """An exchange in one wallet is a `sent` row in one currency, `received` in another."""
    petr = person_id("Petr")
    cash = create("wallets", {"person_id": petr, "name": "Cash", "tracked": True})
    isk, eur = currencies[0]["id"], currencies[1]["id"]

    create(
        "transfers",
        {
            "from_wallet_id": cash["id"],
            "from_amount": "20",
            "from_currency_id": eur,
            "to_wallet_id": cash["id"],
            "to_amount": "2800",
            "to_currency_id": isk,
        },
    )

    report = client.get(f"{trip_url}/wallets").json()["wallets"]
    cash_report = next(w for w in report if w["id"] == cash["id"])
    by_currency = {row["currency_id"]: row for row in cash_report["balances"]}
    assert by_currency[eur]["sent"] == 20
    assert by_currency[eur]["balance"] == -20
    assert by_currency[isk]["received"] == 2800
    assert by_currency[isk]["balance"] == 2800


def test_wallets_report_one_currency_sums_received_sent_and_spent(  # noqa: PLR0913, PLR0917 (the fixtures are the setup)
    client, currencies, person_id, default_wallet_of, item_body, trip_url, create
):
    """A wallet funded, sending some on and spending in one currency reports all three sums."""
    petr = person_id("Petr")
    card = default_wallet_of(petr)["id"]
    cash = create("wallets", {"person_id": petr, "name": "Cash", "tracked": True})
    isk = currencies[0]["id"]
    for from_wallet, to_wallet, amount in ((card, cash["id"], "20000"), (cash["id"], card, "3000")):
        create(
            "transfers",
            {
                "from_wallet_id": from_wallet,
                "from_amount": amount,
                "from_currency_id": isk,
                "to_wallet_id": to_wallet,
            },
        )
    create("items", item_body(amount="12500", payer_id=petr, wallet_id=cash["id"]))

    report = client.get(f"{trip_url}/wallets").json()["wallets"]
    cash_report = next(w for w in report if w["id"] == cash["id"])
    assert cash_report["balances"] == [
        {
            "currency_code": "ISK",
            "currency_id": isk,
            "received": 20000,
            "sent": 3000,
            "spent": 12500,
            "balance": 4500,
        }
    ]


def test_wallets_report_currency_order_is_primary_then_code(  # noqa: PLR0913, PLR0917 (the fixtures are the setup)
    client, currencies, person_id, default_wallet_of, trip_url, create
):
    """Balance rows are ordered primary currency first, then by code, not by insertion."""
    petr = person_id("Petr")
    cash = create("wallets", {"person_id": petr, "name": "Cash", "tracked": True})
    isk, eur = currencies[0]["id"], currencies[1]["id"]

    # Fund the EUR side first, then the ISK side - insertion order is reversed
    # from the report order (ISK is primary, so it leads).
    create(
        "transfers",
        {
            "from_wallet_id": default_wallet_of(petr)["id"],
            "from_amount": "10",
            "from_currency_id": eur,
            "to_wallet_id": cash["id"],
        },
    )
    create(
        "transfers",
        {
            "from_wallet_id": default_wallet_of(petr)["id"],
            "from_amount": "1000",
            "from_currency_id": isk,
            "to_wallet_id": cash["id"],
        },
    )

    report = client.get(f"{trip_url}/wallets").json()["wallets"]
    cash_report = next(w for w in report if w["id"] == cash["id"])
    assert [row["currency_id"] for row in cash_report["balances"]] == [isk, eur]


def test_create_wallet_duplicate_name_is_409(client, trip_url, person_id, create):
    """Two wallets with the same name for the same person conflict."""
    petr = person_id("Petr")
    create("wallets", {"person_id": petr, "name": "Cash", "tracked": True})
    response = client.post(
        f"{trip_url}/wallets",
        json={"person_id": petr, "name": "Cash", "tracked": False},
    )
    assert response.status_code == 409
    assert response.json()["error"]["fields"]["name"] == {
        "code": "duplicate",
        "params": {"name": "Cash"},
    }


def test_update_wallet_is_default_moves_the_flag(
    client, person_id, default_wallet_of, trip_url, create
):
    """Making a new wallet the default un-defaults the old one."""
    petr = person_id("Petr")
    cash = create("wallets", {"person_id": petr, "name": "Cash", "tracked": True})

    client.patch(f"{trip_url}/wallets/{cash['id']}", json={"is_default": True})

    updated_trip = client.get(f"{trip_url}").json()["trip"]
    petr_wallets = [w for w in updated_trip["wallets"] if w["person_id"] == petr]
    assert sum(1 for w in petr_wallets if w["is_default"]) == 1
    assert next(w for w in petr_wallets if w["id"] == cash["id"])["is_default"] is True


def test_delete_default_wallet_is_409(client, trip_url, default_wallet_of, people):
    """A person's default wallet can't be deleted while it holds that role."""
    card = default_wallet_of(people[0]["id"])
    response = client.delete(f"{trip_url}/wallets/{card['id']}")
    assert response.status_code == 409
    assert response.json()["error"]["fields"]["id"]["code"] == "is_default"


def test_delete_wallet_in_use_by_item_is_409(client, trip_url, person_id, item_body, create):
    """A wallet referenced by an item can't be deleted."""
    petr = person_id("Petr")
    cash = create("wallets", {"person_id": petr, "name": "Cash", "tracked": True})
    create("items", item_body(payer_id=petr, wallet_id=cash["id"]))

    response = client.delete(f"{trip_url}/wallets/{cash['id']}")
    assert response.status_code == 409
    assert response.json()["error"]["fields"]["id"] == {
        "code": "in_use",
        "params": {"count": 1, "name": "Cash"},
    }


def test_wallet_list_is_default_then_name(client, person_id, trip_url, create):
    """A person's wallets lead with their default `Card`, the rest follow by name."""
    petr = person_id("Petr")
    for name in ("Purse", "Cash"):
        create("wallets", {"person_id": petr, "name": name})

    wallets = client.get(f"{trip_url}").json()["trip"]["wallets"]

    assert [w["name"] for w in wallets if w["person_id"] == petr] == ["Card", "Cash", "Purse"]


def test_patch_wallet_renames_and_tracks(client, trip_url, person_id, create):
    """A PATCH carrying a new name and `tracked` writes both."""
    petr = person_id("Petr")
    cash = create("wallets", {"person_id": petr, "name": "Cash"})

    response = client.patch(
        f"{trip_url}/wallets/{cash['id']}",
        json={"name": "Envelope", "tracked": True},
    )

    assert response.status_code == 200
    assert response.json()["wallet"] == {
        "id": cash["id"],
        "person_id": petr,
        "name": "Envelope",
        "tracked": True,
        "is_default": False,
    }


def test_patch_wallet_onto_another_wallet_of_the_same_person_is_409(
    client, trip_url, person_id, create
):
    """Renaming a wallet to a name its owner already uses conflicts."""
    petr = person_id("Petr")
    cash = create("wallets", {"person_id": petr, "name": "Cash"})

    response = client.patch(f"{trip_url}/wallets/{cash['id']}", json={"name": "Card"})

    assert response.status_code == 409
    assert response.json()["error"]["fields"]["name"] == {
        "code": "duplicate",
        "params": {"name": "Card"},
    }


def test_patch_wallet_blank_name_is_required(client, trip_url, person_id, create):
    """A rename to a blank name is rejected, like a create with one."""
    petr = person_id("Petr")
    cash = create("wallets", {"person_id": petr, "name": "Cash"})

    response = client.patch(f"{trip_url}/wallets/{cash['id']}", json={"name": "   "})

    assert response.status_code == 422
    assert response.json()["error"]["fields"]["name"] == {"code": "required", "params": {}}


def test_delete_unused_wallet_removes_it(client, trip_url, person_id, create):
    """A wallet no item or transfer references deletes, and its id stops resolving."""
    petr = person_id("Petr")
    cash = create("wallets", {"person_id": petr, "name": "Cash"})

    response = client.delete(f"{trip_url}/wallets/{cash['id']}")

    assert response.status_code == 204
    gone = client.delete(f"{trip_url}/wallets/{cash['id']}")
    assert gone.json() == {"error": {"code": "not_found", "params": {"resource": "wallet"}}}
