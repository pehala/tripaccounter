"""Functional tests for static file and SPA-route serving.

Two modes: without `TA_BUILD_ID` the assets sit unversioned at `/`, with one they move
under `/s/{build_id}/` so a proxy can cache them permanently (`DEPLOY.md`). The safety
property is that the two mounts never overlap.
"""

import pytest
from fastapi.testclient import TestClient

from app.main import create_app

BUILD_ID = "testbuild1"


@pytest.fixture
def versioned_client(monkeypatch):
    """Return a client over an app built with `BUILD_ID`, mounting assets under the prefix."""
    monkeypatch.setenv("TA_BUILD_ID", BUILD_ID)
    return TestClient(create_app())


# --- the index page ---------------------------------------------------------------


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


def test_index_is_revalidated_on_every_load(client):
    """index.html names the current build, so a client must never hold it without asking."""
    assert client.get("/").headers["cache-control"] == "no-cache"


def test_index_with_a_matching_etag_returns_an_empty_304(client):
    """A repeat load costs one conditional request and no body."""
    etag = client.get("/").headers["etag"]

    response = client.get("/", headers={"if-none-match": etag})

    assert response.status_code == 304
    assert response.content == b""


# --- no build id: today's behaviour ------------------------------------------------


@pytest.mark.parametrize("path", ["/app.css", "/js/app.js", "/favicon.svg"])
def test_assets_are_served_at_the_root_without_a_build_id(client, path):
    """Unversioned, the assets stay exactly where the frontend's source references them."""
    assert client.get(path).status_code == 200


def test_unversioned_assets_carry_no_cache_control(client):
    """Dev has no proxy and no cache header anywhere in the request path."""
    assert "cache-control" not in client.get("/js/app.js").headers


def test_index_references_unversioned_assets_without_a_build_id(client):
    """With no build to name, index.html is served exactly as it sits on disk."""
    body = client.get("/").text

    assert '<link href="/app.css" rel="stylesheet">' in body
    assert '<script type="module" src="/js/app.js"></script>' in body


# --- with a build id: the versioned mount ------------------------------------------


@pytest.mark.parametrize("path", ["/app.css", "/js/app.js", "/favicon.svg"])
def test_build_id_moves_assets_under_the_version_prefix(versioned_client, path):
    """Every asset gains the build id, which is what makes its URL cacheable forever."""
    assert versioned_client.get(f"/s/{BUILD_ID}{path}").status_code == 200


@pytest.mark.parametrize("path", ["/app.css", "/js/app.js", "/favicon.svg"])
def test_build_id_leaves_no_unversioned_copy(versioned_client, path):
    """The two mounts never overlap: an uncacheable copy of an asset must be unreachable."""
    assert versioned_client.get(path).status_code == 404


def test_index_references_the_versioned_assets(versioned_client):
    """index.html is the manifest — it is the only file that names the build id."""
    body = versioned_client.get("/").text

    assert f'<link href="/s/{BUILD_ID}/app.css" rel="stylesheet">' in body
    assert f'<script type="module" src="/s/{BUILD_ID}/js/app.js"></script>' in body


def test_cdn_references_are_left_alone(versioned_client):
    """Only root-relative references are ours; an absolute CDN URL must survive untouched."""
    body = versioned_client.get("/").text

    assert '"https://cdn.jsdelivr.net/npm/preact@10.29.8/dist/preact.module.js"' in body
    assert "https://cdn.jsdelivr.net/npm/bootstrap@5.3.8/dist/css/bootstrap.min.css" in body


@pytest.mark.parametrize(
    "path",
    ["/js/h.js", "/js/views/Trip.js", "/js/components/Shell.js", "/js/i18n/cs.js"],
)
def test_relative_imports_resolve_under_the_prefix(versioned_client, path):
    """A module's `import './h.js'` inherits the prefix, which is why no JS is ever rewritten."""
    assert versioned_client.get(f"/s/{BUILD_ID}{path}").status_code == 200


def test_versioned_assets_carry_no_cache_control(versioned_client):
    """`immutable` is the proxy's header; the app sets none, so nginx cannot duplicate it."""
    assert "cache-control" not in versioned_client.get(f"/s/{BUILD_ID}/js/app.js").headers


def test_index_is_never_immutable_under_a_build_id(versioned_client):
    """Caching the page that names the build id would make the next deploy unreachable."""
    assert versioned_client.get("/").headers["cache-control"] == "no-cache"
