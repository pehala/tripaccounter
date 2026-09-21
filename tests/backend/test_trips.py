"""Functional tests for creating and reading trips."""

import re


def test_create_trip_returns_embedded_rosters(client):
    """201 body carries the embedded people/currencies/countries."""
    response = client.post(
        "/api/v1/trips",
        json={
            "name": "Iceland 2026",
            "people": [{"name": "Petr"}, {"name": "Ann"}],
            "currencies": [{"code": "ISK", "is_primary": True}],
            "countries": [{"name": "Iceland", "code": "IS"}],
        },
    )

    assert response.status_code == 201, response.text
    trip = response.json()["trip"]
    assert trip["slug"] == "iceland-2026"
    assert [p["name"] for p in trip["people"]] == ["Petr", "Ann"]
    assert trip["currencies"][0]["code"] == "ISK"
    assert trip["currencies"][0]["is_primary"] is True
    assert trip["countries"][0]["flag"] == "🇮🇸"
    assert trip["countries"][0]["item_count"] == 0


def test_create_trip_labels_absent_means_empty(client):
    """No `labels` in the body means the trip starts with none — the server seeds nothing."""
    response = client.post(
        "/api/v1/trips",
        json={
            "name": "Empty labels",
            "people": [{"name": "Petr"}],
            "currencies": [{"code": "ISK"}],
            "countries": [{"name": "Iceland"}],
        },
    )
    slug = response.json()["trip"]["slug"]

    labels = client.get(f"/api/v1/trips/{slug}/labels").json()["labels"]
    assert labels == []


def test_create_trip_with_labels_seeds_them_with_zero_use(client):
    """Explicit `labels` creates them with use_count 0."""
    response = client.post(
        "/api/v1/trips",
        json={
            "name": "Labelled trip",
            "people": [{"name": "Petr"}],
            "currencies": [{"code": "ISK"}],
            "countries": [{"name": "Iceland"}],
            "labels": ["food", "fun"],
        },
    )
    slug = response.json()["trip"]["slug"]

    labels = client.get(f"/api/v1/trips/{slug}/labels").json()["labels"]
    assert {label["name"] for label in labels} == {"food", "fun"}
    assert all(label["use_count"] == 0 for label in labels)


def test_create_trip_missing_roster_is_422_empty(client):
    """Zero people/currencies/countries fails per-field with `empty`."""
    response = client.post(
        "/api/v1/trips",
        json={"name": "Bad trip", "people": [], "currencies": [], "countries": []},
    )

    assert response.status_code == 422
    assert response.json() == {
        "error": {
            "code": "validation_error",
            "params": {},
            "fields": {
                "people": {"code": "empty", "params": {}},
                "currencies": {"code": "empty", "params": {}},
                "countries": {"code": "empty", "params": {}},
            },
        }
    }


def test_create_trip_slug_collision_chain(client):
    """Same name three times gets slug, slug-2, slug-3."""
    body = {
        "name": "Road Trip",
        "people": [{"name": "Petr"}],
        "currencies": [{"code": "ISK"}],
        "countries": [{"name": "Iceland"}],
    }
    slugs = [client.post("/api/v1/trips", json=body).json()["trip"]["slug"] for _ in range(3)]
    assert slugs == ["road-trip", "road-trip-2", "road-trip-3"]


def test_get_trip_unknown_slug_is_404(client):
    """An unknown slug is a 404 not_found with the resource name."""
    response = client.get("/api/v1/trips/does-not-exist")
    assert response.status_code == 404
    assert response.json() == {"error": {"code": "not_found", "params": {"resource": "trip"}}}


def test_patch_trip_cannot_move_slug(trip, client):
    """PATCH ignores a `slug` field even implicitly - only documented fields move."""
    response = client.patch(f"/api/v1/trips/{trip['slug']}", json={"name": "Renamed"})
    assert response.status_code == 200
    updated = response.json()["trip"]
    assert updated["slug"] == trip["slug"]
    assert updated["name"] == "Renamed"


def test_delete_trip_cascades(trip, client):
    """DELETE removes the trip; a second GET is 404."""
    response = client.delete(f"/api/v1/trips/{trip['slug']}")
    assert response.status_code == 204
    assert response.content == b""

    response = client.get(f"/api/v1/trips/{trip['slug']}")
    assert response.status_code == 404
    assert response.json() == {"error": {"code": "not_found", "params": {"resource": "trip"}}}


def test_list_trips_carries_counts_not_embedded_lists(trip, client):
    """GET /trips summary has people_count/item_count, no embedded rosters."""
    response = client.get("/api/v1/trips")
    assert response.status_code == 200
    row = next(t for t in response.json()["trips"] if t["slug"] == trip["slug"])
    assert row["people_count"] == 4
    assert row["item_count"] == 0
    assert "people" not in row
    assert "currencies" not in row


def test_list_trips_orders_by_end_date_desc_undated_last(client):
    """Trips sort by end_date descending; a trip with no end date sinks below every dated one."""

    def make(name, end_date=None):
        body = {
            "name": name,
            "people": [{"name": "Petr"}],
            "currencies": [{"code": "ISK"}],
            "countries": [{"name": "Iceland"}],
        }
        if end_date:
            body["end_date"] = end_date
        return client.post("/api/v1/trips", json=body).json()["trip"]["slug"]

    early = make("Early", "2026-01-10")
    undated = make("Undated")
    late = make("Late", "2026-06-15")

    slugs = [row["slug"] for row in client.get("/api/v1/trips").json()["trips"]]
    assert [s for s in slugs if s in {early, undated, late}] == [late, early, undated]


def test_trip_payload_orders_people_and_wallets_by_sort_order(client, trip, people):
    """The trip payload follows the roster's sort_order, and each wallet follows its owner."""
    for position, person in enumerate(reversed(people)):
        response = client.patch(
            f"/api/v1/trips/{trip['slug']}/people/{person['id']}", json={"sort_order": position}
        )
        assert response.status_code == 200, response.text

    body = client.get(f"/api/v1/trips/{trip['slug']}").json()["trip"]
    assert [person["name"] for person in body["people"]] == ["Eva", "Bob", "Ann", "Petr"]
    assert [wallet["person_id"] for wallet in body["wallets"]] == [
        person["id"] for person in body["people"]
    ]


def test_patch_trip_writes_dates_note_and_archived(trip, client):
    """PATCH writes each optional trip field a body carries, leaving the name alone."""
    response = client.patch(
        f"/api/v1/trips/{trip['slug']}",
        json={
            "start_date": "2026-09-13",
            "end_date": "2026-09-22",
            "note": "flights booked",
            "archived": True,
        },
    )

    assert response.status_code == 200
    updated = response.json()["trip"]
    assert updated["name"] == trip["name"]
    assert updated["start_date"] == "2026-09-13"
    assert updated["end_date"] == "2026-09-22"
    assert updated["note"] == "flights booked"
    assert updated["archived"] is True


def test_trip_name_with_no_ascii_letters_gets_a_random_slug(client):
    """A name that folds away to nothing still gets a usable, unique slug."""
    response = client.post(
        "/api/v1/trips",
        json={
            "name": "日本",
            "people": [{"name": "Petr"}],
            "currencies": [{"code": "JPY"}],
            "countries": [{"name": "Japan"}],
        },
    )

    assert response.status_code == 201, response.text
    assert re.fullmatch(r"[0-9a-f]{8}", response.json()["trip"]["slug"])
