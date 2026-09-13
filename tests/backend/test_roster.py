"""Functional tests for the people/currencies/countries roster endpoints."""


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


def test_list_orders_are_sort_order(client, trip, people):
    """People, currencies and countries list in sort_order."""
    response = client.get(f"/api/v1/trips/{trip['slug']}/people").json()["people"]
    assert [p["sort_order"] for p in response] == [0, 1, 2, 3]
    assert [p["name"] for p in response] == [p["name"] for p in people]
