"""Functional tests for the trip export endpoint."""

import csv
import io

import pytest


@pytest.fixture()
def two_person_item(client, trip, people, item_body):
    """Create the two-person item the CSV/JSON parity tests compare against.

    The second sharer is deactivated afterwards: a person keeps the shares they
    already carry, and export resolves against the whole roster, so both shares
    stay in the file.
    """
    item = client.post(
        f"/api/v1/trips/{trip['slug']}/items",
        json=item_body(
            name="Layover lunch",
            amount="120.00",
            note="Split at the gate",
            labels=["food", "airport"],
            shares=[{"person_id": people[0]["id"]}, {"person_id": people[1]["id"]}],
        ),
    ).json()["item"]
    client.patch(f"/api/v1/trips/{trip['slug']}/people/{people[1]['id']}", json={"active": False})
    return item


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


def test_csv_export_header_and_first_row_are_the_contract(client, trip, people, two_person_item):
    """The header row is pinned literally, because a client parses it."""
    created = two_person_item

    response = client.get(f"/api/v1/trips/{trip['slug']}/export", params={"format": "csv"})
    reader = csv.DictReader(io.StringIO(response.text))

    assert reader.fieldnames == [
        "item_id",
        "name",
        "note",
        "occurred_at",
        "currency_code",
        "amount",
        "payer_id",
        "wallet_id",
        "country_id",
        "labels",
        "map_url",
        "lat",
        "lon",
        "created_at",
        "updated_at",
        "person_name",
        "weight",
        "owed",
    ]
    assert next(reader) == {
        "item_id": str(created["id"]),
        "name": "Layover lunch",
        "note": "Split at the gate",
        "occurred_at": created["occurred_at"],
        "currency_code": "ISK",
        "amount": "120",
        "payer_id": str(people[0]["id"]),
        "wallet_id": str(trip["wallets"][0]["id"]),
        "country_id": str(created["country_id"]),
        "labels": "airport;food",
        "map_url": "",
        "lat": "",
        "lon": "",
        "created_at": created["created_at"],
        "updated_at": created["updated_at"],
        "person_name": people[0]["name"],
        "weight": "1",
        "owed": "60",
    }


def test_csv_export_blank_optional_fields_are_empty_not_the_string_none(client, trip, item_body):
    """An item with no note/map_url/lat/lon exports empty fields, not the word 'None'."""
    client.post(f"/api/v1/trips/{trip['slug']}/items", json=item_body(name="Dinner"))

    response = client.get(f"/api/v1/trips/{trip['slug']}/export", params={"format": "csv"})
    row = next(csv.DictReader(io.StringIO(response.text)))

    assert row["note"] == ""
    assert row["map_url"] == ""
    assert row["lat"] == ""
    assert row["lon"] == ""
    assert row["labels"] == ""


def test_json_export_is_share_grained_like_the_csv(client, trip, people, two_person_item):
    """JSON export has the same grain as the CSV: one row per share, not one per item."""
    created = two_person_item

    response = client.get(f"/api/v1/trips/{trip['slug']}/export", params={"format": "json"})

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/json")

    body = response.json()
    assert body["trip"]["slug"] == trip["slug"]
    assert len(body["items"]) == 2
    assert body["items"][0] == {
        "item_id": created["id"],
        "name": "Layover lunch",
        "note": "Split at the gate",
        "occurred_at": created["occurred_at"],
        "currency_code": "ISK",
        "amount": 120,
        "payer_id": people[0]["id"],
        "wallet_id": created["wallet_id"],
        "country_id": created["country_id"],
        "labels": ["airport", "food"],
        "map_url": None,
        "lat": None,
        "lon": None,
        "created_at": created["created_at"],
        "updated_at": created["updated_at"],
        "person_name": people[0]["name"],
        "weight": "1",
        "owed": 60,
    }
    assert [item["item_id"] for item in body["items"]] == [created["id"], created["id"]]
    assert body["transfers"] == []


def test_csv_and_json_export_carry_the_same_rows(client, trip, people, two_person_item):
    """CSV and JSON export are identical except for the format, deactivated sharer included."""
    csv_text = client.get(f"/api/v1/trips/{trip['slug']}/export", params={"format": "csv"}).text
    json_rows = client.get(
        f"/api/v1/trips/{trip['slug']}/export", params={"format": "json"}
    ).json()["items"]
    csv_rows = list(csv.DictReader(io.StringIO(csv_text)))

    assert len(csv_rows) == len(json_rows) == 2
    assert [row["person_name"] for row in json_rows] == [people[0]["name"], people[1]["name"]]
    assert [row["owed"] for row in json_rows] == [60, 60]
    for csv_row, json_row in zip(csv_rows, json_rows, strict=True):
        assert csv_row["item_id"] == str(json_row["item_id"])
        assert csv_row["name"] == json_row["name"]
        assert csv_row["note"] == json_row["note"]
        assert csv_row["labels"] == ";".join(json_row["labels"])
        assert csv_row["person_name"] == json_row["person_name"]
        assert csv_row["weight"] == json_row["weight"]
        assert csv_row["owed"] == str(json_row["owed"])


def test_export_rows_are_oldest_first(client, trip, people, item_body):
    """Export reads as a chronological sheet, whatever the items endpoint answers in."""
    for name, occurred_at in (
        ("Layover lunch", "2026-09-14T12:00:00"),
        ("Dinner at Messinn", "2026-09-12T19:00:00"),
        ("Blue Lagoon", "2026-09-13T10:00:00"),
    ):
        client.post(
            f"/api/v1/trips/{trip['slug']}/items",
            json=item_body(
                name=name,
                occurred_at=occurred_at,
                shares=[{"person_id": people[0]["id"]}],
            ),
        )

    response = client.get(f"/api/v1/trips/{trip['slug']}/export", params={"format": "csv"})

    rows = list(csv.DictReader(io.StringIO(response.text)))
    assert [row["name"] for row in rows] == ["Dinner at Messinn", "Blue Lagoon", "Layover lunch"]


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
