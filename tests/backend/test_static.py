"""Functional tests for static file and SPA-route serving."""


def test_root_serves_index_html(client):
    """GET / returns static/index.html."""
    response = client.get("/")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]


def test_trip_route_serves_index_html_regardless_of_slug(client):
    """GET /t/{slug} returns index.html; the backend never looks at the slug."""
    response = client.get("/t/does-not-exist-at-all")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]


def test_api_never_returns_html(client, trip):
    """Nothing under /api/v1 returns HTML, even on a 404."""
    response = client.get("/api/v1/trips/nope")
    assert "text/html" not in response.headers["content-type"]
    assert response.headers["content-type"].startswith("application/json")
