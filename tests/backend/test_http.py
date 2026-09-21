"""Functional tests for HTTP-layer behaviour: malformed input, content types."""

import pytest
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


def test_api_get_repeated_with_its_etag_is_an_empty_304(client, trip):
    """An unchanged API GET revalidates to a bodiless 304, so a repeat load costs nothing."""
    first = client.get(f"/api/v1/trips/{trip['slug']}")
    assert first.status_code == 200
    assert first.headers["cache-control"] == "no-cache"

    second = client.get(
        f"/api/v1/trips/{trip['slug']}", headers={"if-none-match": first.headers["etag"]}
    )

    assert second.status_code == 304
    assert second.content == b""
    assert "content-length" not in second.headers


def test_api_etag_changes_after_a_write(client, trip):
    """A write moves the ETag, so a client holding the old one gets the new body."""
    before = client.get(f"/api/v1/trips/{trip['slug']}").headers["etag"]
    client.patch(f"/api/v1/trips/{trip['slug']}", json={"note": "changed"})

    response = client.get(f"/api/v1/trips/{trip['slug']}", headers={"if-none-match": before})

    assert response.status_code == 200
    assert response.json()["trip"]["note"] == "changed"


@pytest.mark.parametrize(
    ("method", "path", "body"),
    [
        pytest.param("post", "people", {"name": 5}, id="wrong-type-in-body"),
        pytest.param("patch", "people/not-an-int", {"name": "Zed"}, id="non-integer-path-id"),
    ],
)
def test_input_no_catalog_code_describes_is_400(client, trip, method, path, body):
    """A pydantic failure with no catalog code of its own is a bad_request, not a 422."""
    response = getattr(client, method)(f"/api/v1/trips/{trip['slug']}/{path}", json=body)

    assert response.status_code == 400
    assert response.json() == {"error": {"code": "bad_request", "params": {}}}


def test_openapi_422_is_the_error_envelope_not_fastapis(client):
    """The generated spec answers 422 with this API's own envelope, and drops FastAPI's."""
    schema = client.get("/openapi.json").json()

    item_post = schema["paths"]["/api/v1/trips/{slug}/items"]["post"]
    assert item_post["responses"]["422"]["content"]["application/json"]["schema"] == {
        "$ref": "#/components/schemas/ErrorEnvelope"
    }
    assert "HTTPValidationError" not in schema["components"]["schemas"]
