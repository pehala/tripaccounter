"""Functional tests for the trip export endpoint."""

import csv
import io


def test_csv_export_one_row_per_share(client, trip, people, item_body):
    """CSV is share-grained: an item split four ways is four rows, not one."""
    client.post(
        f"/api/v1/trips/{trip['slug']}/items",
        json=item_body(name="Dinner at Messinn", amount="184.00"),
    )
    client.post(
        f"/api/v1/trips/{trip['slug']}/items",
        json=item_body(
            name="Layover lunch",
            amount="120.00",
            shares=[{"person_id": people[0]["id"]}, {"person_id": people[1]["id"]}],
        ),
    )

    response = client.get(f"/api/v1/trips/{trip['slug']}/export", params={"format": "csv"})

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")
    assert "attachment" in response.headers["content-disposition"]

    rows = list(csv.DictReader(io.StringIO(response.text)))
    # Four people on the first item, two on the second.
    assert len(rows) == 6
    assert [row["name"] for row in rows] == ["Dinner at Messinn"] * 4 + ["Layover lunch"] * 2


def test_csv_export_header_and_first_row_are_the_contract(client, trip, people, item_body):
    """The header row is pinned literally, because a client parses it."""
    client.post(
        f"/api/v1/trips/{trip['slug']}/items",
        json=item_body(
            name="Layover lunch",
            amount="480.00",
            shares=[{"person_id": people[0]["id"]}, {"person_id": people[1]["id"]}],
        ),
    )

    response = client.get(f"/api/v1/trips/{trip['slug']}/export", params={"format": "csv"})
    reader = csv.DictReader(io.StringIO(response.text))

    assert reader.fieldnames == [
        "item_id",
        "name",
        "occurred_at",
        "currency_code",
        "amount",
        "payer_id",
        "wallet_id",
        "country_id",
        "person_id",
        "weight",
        "owed",
    ]
    first = next(reader)
    assert first["name"] == "Layover lunch"
    assert first["currency_code"] == "ISK"
    assert first["amount"] == "480"
    assert first["payer_id"] == str(people[0]["id"])
    assert first["wallet_id"] == str(trip["wallets"][0]["id"])
    assert first["person_id"] == str(people[0]["id"])
    assert first["weight"] == "1"
    assert first["owed"] == "240"


def test_json_export_contains_trip_and_items(client, trip, item_body):
    """JSON export carries the same trip and items blocks the API returns."""
    created = client.post(
        f"/api/v1/trips/{trip['slug']}/items", json=item_body(name="Dinner at Messinn")
    ).json()["item"]

    response = client.get(f"/api/v1/trips/{trip['slug']}/export", params={"format": "json"})

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/json")

    body = response.json()
    assert body["trip"]["slug"] == trip["slug"]
    assert len(body["items"]) == 1
    assert body["items"][0] == created
    assert body["transfers"] == []


def test_export_of_empty_trip_is_not_500(client, trip):
    """A trip with no items exports a header and nothing else."""
    response = client.get(f"/api/v1/trips/{trip['slug']}/export", params={"format": "csv"})
    assert response.status_code == 200
    rows = list(csv.DictReader(io.StringIO(response.text)))
    assert rows == []


def test_export_unknown_format_is_400(client, trip):
    """An unsupported format value is a bad_request."""
    response = client.get(f"/api/v1/trips/{trip['slug']}/export", params={"format": "xml"})
    assert response.status_code == 400
