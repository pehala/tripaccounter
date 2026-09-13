"""Functional tests for HTTP-layer behaviour: malformed input, content types."""

from fastapi.testclient import TestClient

from app.routers import trips


def test_malformed_json_is_400(client, trip):
    """Malformed JSON in the body is a bad_request, not a 422 with a message."""
    response = client.post(
        f"/api/v1/trips/{trip['slug']}/items",
        content=b"{not json",
        headers={"content-type": "application/json"},
    )
    assert response.status_code == 400
    assert response.json() == {"error": {"code": "bad_request", "params": {}}}


def test_unknown_fields_in_write_body_are_rejected(client, trip):
    """An unrecognised field in a write body is rejected, not silently dropped."""
    response = client.post(
        f"/api/v1/trips/{trip['slug']}/people", json={"name": "Zed", "surprise": 1}
    )
    assert response.status_code == 400
    assert response.json() == {"error": {"code": "bad_request", "params": {}}}


def test_unknown_slug_is_404_not_found(client):
    """An unknown trip slug is 404 not_found with the resource name."""
    response = client.get("/api/v1/trips/nope")
    assert response.status_code == 404
    assert response.json()["error"]["params"] == {"resource": "trip"}


def test_delete_returns_204_with_empty_body(client, trip):
    """DELETE responses are 204 with no body."""
    response = client.delete(f"/api/v1/trips/{trip['slug']}")
    assert response.status_code == 204
    assert response.content == b""


def test_unhandled_exception_is_500_with_ref(client, trip, monkeypatch):
    """An unhandled exception becomes a 500 internal_error carrying a `ref`."""

    def boom(*_args, **_kwargs):
        raise RuntimeError("kaboom")

    monkeypatch.setattr(trips.TripSummaryOut, "from_trip", boom)

    with TestClient(client.app, raise_server_exceptions=False) as raw_client:
        response = raw_client.get("/api/v1/trips")

    assert response.status_code == 500
    body = response.json()
    assert body["error"]["code"] == "internal_error"
    assert "ref" in body["error"]["params"]
