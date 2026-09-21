"""Functional tests for the people/currencies/countries roster endpoints."""

import pytest


def test_duplicate_person_name_is_409(client, trip, people):
    """A duplicate person name within a trip is a conflict."""
    response = client.post(f"/api/v1/trips/{trip['slug']}/people", json={"name": people[0]["name"]})
    assert response.status_code == 409
    assert response.json() == {
        "error": {
            "code": "conflict",
            "params": {},
            "fields": {"name": {"code": "duplicate", "params": {"name": people[0]["name"]}}},
        }
    }


def test_delete_referenced_person_is_409_in_use(client, trip, people, item_body):
    """Deleting a person referenced by an item's share is blocked."""
    client.post(f"/api/v1/trips/{trip['slug']}/items", json=item_body())
    person_id = people[0]["id"]

    response = client.delete(f"/api/v1/trips/{trip['slug']}/people/{person_id}")
    assert response.status_code == 409
    body = response.json()
    assert body["error"]["code"] == "conflict"
    assert body["error"]["fields"]["id"]["code"] == "in_use"


def test_patch_person_active_false_hides_from_new_splits(client, trip, people, item_body):
    """Deactivating a person keeps existing items, drops them from new equal splits."""
    person_id = people[0]["id"]

    response = client.patch(
        f"/api/v1/trips/{trip['slug']}/people/{person_id}", json={"active": False}
    )
    assert response.status_code == 200
    assert response.json()["person"]["active"] is False

    body = item_body(amount="90.00", payer_id=people[1]["id"])
    del body["shares"]
    item = client.post(f"/api/v1/trips/{trip['slug']}/items", json=body).json()["item"]
    active_shares = [s for s in item["split"]["shares"] if s["owed"] is not None]
    assert len(active_shares) == 3
    assert person_id not in [s["person_id"] for s in active_shares]


def test_currency_code_must_be_three_letters(client, trip):
    """A malformed currency code is invalid_code."""
    response = client.post(f"/api/v1/trips/{trip['slug']}/currencies", json={"code": "US"})
    assert response.status_code == 422
    assert response.json() == {
        "error": {
            "code": "validation_error",
            "params": {},
            "fields": {"code": {"code": "invalid_code", "params": {}}},
        }
    }


def test_duplicate_currency_code_is_409(client, trip, currency):
    """Adding a currency code already on the trip conflicts."""
    response = client.post(
        f"/api/v1/trips/{trip['slug']}/currencies", json={"code": currency["code"]}
    )
    assert response.status_code == 409
    body = response.json()
    assert body["error"]["code"] == "conflict"
    assert body["error"]["fields"]["code"]["code"] == "duplicate"


def test_delete_referenced_currency_is_409(client, trip, currency, item_body):
    """A currency used by an item cannot be deleted."""
    client.post(f"/api/v1/trips/{trip['slug']}/items", json=item_body())

    response = client.delete(f"/api/v1/trips/{trip['slug']}/currencies/{currency['id']}")
    assert response.status_code == 409
    body = response.json()
    assert body["error"]["code"] == "conflict"
    assert body["error"]["fields"]["id"]["code"] == "in_use"


def test_duplicate_country_name_is_409(client, trip, country):
    """A country name collision within a trip conflicts."""
    response = client.post(
        f"/api/v1/trips/{trip['slug']}/countries", json={"name": country["name"]}
    )
    assert response.status_code == 409
    assert response.json() == {
        "error": {
            "code": "conflict",
            "params": {},
            "fields": {"name": {"code": "duplicate", "params": {"name": country["name"]}}},
        }
    }


def test_delete_referenced_country_is_409(client, trip, country, item_body):
    """A country used by an item cannot be deleted."""
    client.post(f"/api/v1/trips/{trip['slug']}/items", json=item_body())

    response = client.delete(f"/api/v1/trips/{trip['slug']}/countries/{country['id']}")
    assert response.status_code == 409
    body = response.json()
    assert body["error"]["code"] == "conflict"
    assert body["error"]["fields"]["id"]["code"] == "in_use"


def test_country_flag_derived_from_code(client, trip):
    """A country with an ISO code gets a derived flag; without one, null."""
    response = client.post(
        f"/api/v1/trips/{trip['slug']}/countries", json={"name": "Denmark", "code": "DK"}
    )
    assert response.json()["country"]["flag"] == "🇩🇰"

    response = client.post(f"/api/v1/trips/{trip['slug']}/countries", json={"name": "Somewhere"})
    assert response.json()["country"]["flag"] is None


def test_people_list_follows_sort_order_not_row_age(client, trip, people):
    """Reversing the roster's sort_order reverses the list, which row age alone would not."""
    for position, person in enumerate(reversed(people)):
        response = client.patch(
            f"/api/v1/trips/{trip['slug']}/people/{person['id']}", json={"sort_order": position}
        )
        assert response.status_code == 200, response.text

    listed = client.get(f"/api/v1/trips/{trip['slug']}/people").json()["people"]
    assert [person["name"] for person in listed] == ["Eva", "Bob", "Ann", "Petr"]
    assert [person["sort_order"] for person in listed] == [0, 1, 2, 3]


def test_people_tied_on_sort_order_fall_back_to_name(client, trip, person_id):
    """Two people on the same `sort_order` order by name, so the roster stays total."""
    client.patch(f"/api/v1/trips/{trip['slug']}/people/{person_id('Petr')}", json={"sort_order": 1})

    listed = client.get(f"/api/v1/trips/{trip['slug']}/people").json()["people"]

    assert [person["name"] for person in listed] == ["Ann", "Petr", "Bob", "Eva"]


def test_currencies_list_is_primary_then_code_not_row_age(client, trip):
    """The currency list leads with the primary, then by code - neither is row age."""
    client.post(f"/api/v1/trips/{trip['slug']}/currencies", json={"code": "DKK"})

    listed = client.get(f"/api/v1/trips/{trip['slug']}/currencies").json()["currencies"]

    assert [currency["code"] for currency in listed] == ["ISK", "DKK", "EUR"]


def test_currencies_list_follows_a_moved_primary(client, trip, currencies):
    """Making EUR primary moves it to the front, which code order alone would not."""
    eur = next(currency for currency in currencies if currency["code"] == "EUR")
    client.patch(f"/api/v1/trips/{trip['slug']}/currencies/{eur['id']}", json={"is_primary": True})

    listed = client.get(f"/api/v1/trips/{trip['slug']}/currencies").json()["currencies"]

    assert [currency["code"] for currency in listed] == ["EUR", "ISK"]


def test_countries_list_is_default_then_name_not_row_age(client, trip):
    """The country list leads with the default, then by name - neither is row age."""
    client.post(f"/api/v1/trips/{trip['slug']}/countries", json={"name": "Denmark", "code": "DK"})

    listed = client.get(f"/api/v1/trips/{trip['slug']}/countries").json()["countries"]

    assert [entry["name"] for entry in listed] == ["Iceland", "Denmark"]


def test_countries_list_follows_a_moved_default(client, trip):
    """Making Denmark the default moves it ahead of Iceland, which name order would not."""
    added = client.post(
        f"/api/v1/trips/{trip['slug']}/countries", json={"name": "Denmark", "code": "DK"}
    ).json()["country"]
    client.patch(f"/api/v1/trips/{trip['slug']}/countries/{added['id']}", json={"is_default": True})

    listed = client.get(f"/api/v1/trips/{trip['slug']}/countries").json()["countries"]

    assert [entry["name"] for entry in listed] == ["Denmark", "Iceland"]


def test_create_person_gets_a_default_card_wallet(client, trip):
    """Every new person gets an untracked, default `Card` wallet, server-side."""
    response = client.post(f"/api/v1/trips/{trip['slug']}/people", json={"name": "Frank"})
    person_id = response.json()["person"]["id"]

    updated_trip = client.get(f"/api/v1/trips/{trip['slug']}").json()["trip"]
    franks_wallets = [w for w in updated_trip["wallets"] if w["person_id"] == person_id]

    assert len(franks_wallets) == 1
    assert franks_wallets[0] == {
        "id": franks_wallets[0]["id"],
        "person_id": person_id,
        "name": "Card",
        "tracked": False,
        "is_default": True,
    }


def test_delete_person_referenced_by_transfer_is_409_in_use(
    client, trip, person_id, default_wallet_of
):
    """A person whose wallet appears in a transfer can't be deleted, even with no items."""
    ann, bob = person_id("Ann"), person_id("Bob")
    client.post(
        f"/api/v1/trips/{trip['slug']}/transfers",
        json={
            "from_wallet_id": default_wallet_of(ann)["id"],
            "from_amount": "50",
            "from_currency_id": trip["currencies"][0]["id"],
            "to_wallet_id": default_wallet_of(bob)["id"],
        },
    )

    response = client.delete(f"/api/v1/trips/{trip['slug']}/people/{ann}")
    assert response.status_code == 409
    assert response.json()["error"]["fields"]["id"]["code"] == "in_use"


def test_delete_currency_referenced_by_transfer_is_409_in_use(
    client, trip, person_id, default_wallet_of, currencies
):
    """A currency used only by a transfer, never an item, still can't be deleted."""
    ann, bob = person_id("Ann"), person_id("Bob")
    eur = currencies[1]["id"]
    client.post(
        f"/api/v1/trips/{trip['slug']}/transfers",
        json={
            "from_wallet_id": default_wallet_of(ann)["id"],
            "from_amount": "50",
            "from_currency_id": eur,
            "to_wallet_id": default_wallet_of(bob)["id"],
        },
    )

    response = client.delete(f"/api/v1/trips/{trip['slug']}/currencies/{eur}")
    assert response.status_code == 409
    assert response.json()["error"]["fields"]["id"]["code"] == "in_use"


def test_patch_person_renames_and_reweights(client, trip, person_id):
    """A PATCH carrying a new name and default weight writes both."""
    response = client.patch(
        f"/api/v1/trips/{trip['slug']}/people/{person_id('Petr')}",
        json={"name": "Petra", "default_weight": "1.5"},
    )

    assert response.status_code == 200
    person = response.json()["person"]
    assert person["name"] == "Petra"
    assert person["initial"] == "P"
    assert person["default_weight"] == "1.5"


def test_patch_person_onto_another_persons_name_is_409(client, trip, people, person_id):
    """Renaming someone to a name already on the roster conflicts; their own name does not."""
    petr = person_id("Petr")

    response = client.patch(
        f"/api/v1/trips/{trip['slug']}/people/{petr}", json={"name": people[1]["name"]}
    )

    assert response.status_code == 409
    assert response.json() == {
        "error": {
            "code": "conflict",
            "params": {},
            "fields": {"name": {"code": "duplicate", "params": {"name": people[1]["name"]}}},
        }
    }
    unchanged = client.patch(f"/api/v1/trips/{trip['slug']}/people/{petr}", json={"name": "Petr"})
    assert unchanged.status_code == 200


def test_patch_currency_symbol(client, trip, currency):
    """A PATCH carrying a symbol writes it, leaving the code alone."""
    response = client.patch(
        f"/api/v1/trips/{trip['slug']}/currencies/{currency['id']}", json={"symbol": "kr"}
    )

    assert response.status_code == 200
    assert response.json()["currency"] == {
        "id": currency["id"],
        "code": "ISK",
        "symbol": "kr",
        "is_primary": True,
    }


def test_patch_country_renames_and_uppercases_the_code(client, trip, country):
    """A PATCH writes the new name and upper-cases the ISO code, which drives the flag."""
    response = client.patch(
        f"/api/v1/trips/{trip['slug']}/countries/{country['id']}",
        json={"name": "Danmark", "code": "dk"},
    )

    assert response.status_code == 200
    updated = response.json()["country"]
    assert updated["name"] == "Danmark"
    assert updated["code"] == "DK"
    assert updated["flag"] == "🇩🇰"


def test_patch_country_onto_another_countrys_name_is_409(client, trip, country):
    """Renaming a country to one the trip already has conflicts."""
    added = client.post(f"/api/v1/trips/{trip['slug']}/countries", json={"name": "Denmark"}).json()[
        "country"
    ]

    response = client.patch(
        f"/api/v1/trips/{trip['slug']}/countries/{added['id']}", json={"name": country["name"]}
    )

    assert response.status_code == 409
    assert response.json()["error"]["fields"]["name"] == {
        "code": "duplicate",
        "params": {"name": country["name"]},
    }


@pytest.mark.parametrize(
    ("collection", "resource", "body"),
    [
        pytest.param("people", "person", {"name": "Frank"}, id="person"),
        pytest.param("currencies", "currency", {"code": "DKK"}, id="currency"),
        pytest.param("countries", "country", {"name": "Denmark"}, id="country"),
    ],
)
def test_delete_unreferenced_roster_row_removes_it(client, trip, collection, resource, body):
    """A roster row nothing references deletes with 204, and its id stops resolving."""
    created = client.post(f"/api/v1/trips/{trip['slug']}/{collection}", json=body).json()[resource]

    response = client.delete(f"/api/v1/trips/{trip['slug']}/{collection}/{created['id']}")

    assert response.status_code == 204
    assert response.content == b""
    gone = client.delete(f"/api/v1/trips/{trip['slug']}/{collection}/{created['id']}")
    assert gone.status_code == 404
    assert gone.json() == {"error": {"code": "not_found", "params": {"resource": resource}}}


def test_create_country_as_default_moves_the_flag(client, trip, country):
    """A country created with `is_default` takes the flag off the one that held it."""
    client.post(
        f"/api/v1/trips/{trip['slug']}/countries",
        json={"name": "Denmark", "code": "DK", "is_default": True},
    )

    listed = client.get(f"/api/v1/trips/{trip['slug']}/countries").json()["countries"]

    assert [(entry["name"], entry["is_default"]) for entry in listed] == [
        ("Denmark", True),
        (country["name"], False),
    ]
