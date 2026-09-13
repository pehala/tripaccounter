"""Tests for tests/frontend/mockapi.py: the fixture's routes are the whole contract of the mock.

Driven over HTTP against a tiny inline fixture whose envelopes are deliberately not
the real API's, so a passing test proves the shape came from the JSON and not from
Python.
"""

import copy

import httpx
import pytest

from tests.frontend.mockapi import MockServer, make_handler

PETR = {"id": 1, "name": "Petr", "active": True}
MINI = {
    "trip": {"trip": {"slug": "t", "name": "Mini", "people": [PETR]}},
    "trips": {"trips": [{"slug": "t", "name": "Mini", "people_count": 1}]},
    "items": {"items": [{"id": 7, "name": "Old"}]},
    "routes": {
        "/api/v1/trips": {"GET": "#/trips", "POST": {"trip": "$echo"}},
        "/api/v1/trips/t": {"GET": "#/trip", "PATCH": "#/trip"},
        "/api/v1/trips/t/people": {
            "collection": "#/trip/trip/people",
            "item": "person",
            "defaults": {"active": True, "color": "#6c757d"},
        },
        "/api/v1/trips/t/people/self": {"PATCH": {"literal": "sibling"}},
        "/api/v1/trips/t/items": {"collection": "#/items/items", "item": "item", "insert": "head"},
        "/api/v1/trips/t/items/gone": {"DELETE": None},
        "/api/v1/trips/t/items/preview": {"POST": {"$status": 200, "total": 0}},
    },
    "errors": {"not_found": {"gone": True}, "bad_request": {"unreadable": True}},
}
PEOPLE = "/api/v1/trips/t/people"
NOT_FOUND = {"gone": True}


@pytest.fixture
def client():
    """Return an httpx client against a mock server built from a private copy of MINI."""
    with (
        MockServer(copy.deepcopy(MINI)) as server,
        httpx.Client(base_url=server.url) as client,
    ):
        yield client


# --- declared methods ---


def test_pointer_value_serves_the_pointed_block(client):
    """A method whose value is a JSON Pointer answers the pointed block verbatim with 200."""
    response = client.get("/api/v1/trips/t")

    assert response.status_code == 200
    assert response.json() == MINI["trip"]


def test_literal_post_body_answers_201_with_echo_filled(client):
    """A literal body on POST answers 201, with "$echo" replaced by request body + counter id."""
    response = client.post("/api/v1/trips", json={"name": "Norway"})

    assert response.status_code == 201
    assert response.json() == {"trip": {"name": "Norway", "id": 1000}}


def test_echo_keeps_the_request_id_and_spends_no_counter_value(client):
    """A body carrying its own id is echoed with it, and the next created row still gets 1000."""
    kept = client.post("/api/v1/trips", json={"id": 5})
    fresh = client.post("/api/v1/trips", json={})

    assert kept.json() == {"trip": {"id": 5}}
    assert fresh.json() == {"trip": {"id": 1000}}


def test_literal_delete_without_body_answers_204(client):
    """A DELETE declared with a null value answers 204 and no content."""
    response = client.delete("/api/v1/trips/t/items/gone")

    assert response.status_code == 204
    assert response.content == b""


def test_status_directive_in_a_literal_overrides_the_method_default(client):
    """A literal carrying "$status": 200 answers 200 without the directive, not the POST 201."""
    response = client.post("/api/v1/trips/t/items/preview", json={})

    assert response.status_code == 200
    assert response.json() == {"total": 0}


def test_patch_on_pointer_merges_into_the_envelope_payload(client):
    """PATCH on a pointer merges the body into the envelope's payload; the next GET agrees."""
    response = client.patch("/api/v1/trips/t", json={"name": "Renamed"})

    expected = {"trip": {"slug": "t", "name": "Renamed", "people": [PETR]}}
    assert response.status_code == 200
    assert response.json() == expected
    assert client.get("/api/v1/trips/t").json() == expected


def test_query_string_is_ignored_when_matching(client):
    """A query string does not stop a path from matching its declared route."""
    assert client.get(f"{PEOPLE}?x=1").status_code == 200


def test_declared_path_beats_collection_member_route(client):
    """A path declared next to a collection wins over the collection's {id} match."""
    response = client.patch(f"{PEOPLE}/self", json={})

    assert response.status_code == 200
    assert response.json() == {"literal": "sibling"}


# --- collection ---


def test_collection_get_lists_rows_under_the_pointers_last_token(client):
    """The collection GET answers the rows under the last token of the pointer."""
    assert client.get(PEOPLE).json() == {"people": [PETR]}


def test_collection_post_appends_row_with_defaults_and_fresh_id(client):
    """A POST stores defaults + body under a counter id at the tail, seen via the trip pointer."""
    response = client.post(PEOPLE, json={"name": "Zoe"})

    zoe = {"active": True, "color": "#6c757d", "name": "Zoe", "id": 1000}
    assert response.status_code == 201
    assert response.json() == {"person": zoe}
    assert client.get("/api/v1/trips/t").json()["trip"]["people"] == [PETR, zoe]


def test_collection_insert_head_prepends_the_new_row(client):
    """A collection declared with insert: head puts a created row first."""
    client.post("/api/v1/trips/t/items", json={"name": "New"})

    assert client.get("/api/v1/trips/t/items").json() == {
        "items": [{"name": "New", "id": 1000}, {"id": 7, "name": "Old"}]
    }


def test_collection_patch_merges_into_row_shared_with_trip(client):
    """A PATCH by string id merges into the row the trip GET also serves."""
    response = client.patch(f"{PEOPLE}/1", json={"active": False})

    assert response.status_code == 200
    assert response.json() == {"person": {"id": 1, "name": "Petr", "active": False}}
    assert client.get("/api/v1/trips/t").json()["trip"]["people"][0]["active"] is False


def test_collection_delete_removes_row_and_answers_204(client):
    """A DELETE by id answers 204 with no body and the row is gone from the list."""
    response = client.delete(f"{PEOPLE}/1")

    assert response.status_code == 204
    assert response.content == b""
    assert client.get(PEOPLE).json() == {"people": []}


@pytest.mark.parametrize(
    "method", [pytest.param("PATCH", id="patch"), pytest.param("DELETE", id="delete")]
)
def test_collection_unknown_id_answers_not_found(client, method):
    """A member operation on an id no row has answers errors.not_found verbatim."""
    response = client.request(method, f"{PEOPLE}/999", json={})

    assert response.status_code == 404
    assert response.json() == NOT_FOUND


# --- undeclared and unreadable requests ---


@pytest.mark.parametrize(
    "method",
    [pytest.param(m, id=m.lower()) for m in ("GET", "POST", "PATCH", "DELETE")],
)
def test_undeclared_path_answers_not_found_for_every_method(client, method):
    """Any method on a path the routes do not declare answers errors.not_found, never an echo."""
    response = client.request(method, "/api/v1/trips/does-not-exist", json={"name": "x"})

    assert response.status_code == 404
    assert response.json() == NOT_FOUND


@pytest.mark.parametrize(
    "raw",
    [pytest.param(b"not json", id="unparsable"), pytest.param(b"[1]", id="not-an-object")],
)
def test_malformed_json_body_answers_bad_request(client, raw):
    """A body that is not a JSON object answers errors.bad_request verbatim."""
    response = client.post(PEOPLE, content=raw, headers={"Content-Type": "application/json"})

    assert response.status_code == 400
    assert response.json() == {"unreadable": True}


def test_two_servers_share_neither_rows_nor_ids(client):
    """A second server built from its own dict restarts the id counter and sees no foreign rows."""
    client.post(PEOPLE, json={"name": "Zoe"})
    with (
        MockServer(copy.deepcopy(MINI)) as second,
        httpx.Client(base_url=second.url) as other,
    ):
        created = other.post(PEOPLE, json={"name": "Ann"}).json()
        people = other.get(PEOPLE).json()

    ann = {"active": True, "color": "#6c757d", "name": "Ann", "id": 1000}
    assert created["person"]["id"] == 1000
    assert people == {"people": [PETR, ann]}


@pytest.mark.parametrize(
    "errors",
    [
        pytest.param({"bad_request": {}}, id="no-not-found"),
        pytest.param({"not_found": {}}, id="no-bad-request"),
    ],
)
def test_fixture_missing_an_error_body_is_refused_at_build(errors):
    """A fixture that does not declare both error bodies is refused instead of getting a default."""
    with pytest.raises(KeyError, match="errors"):
        make_handler({"routes": {}, "errors": errors})


def test_collection_with_an_unknown_field_is_refused_at_build():
    """A misspelt collection field is refused instead of being ignored."""
    data = {
        "rows": {"rows": []},
        "routes": {"/api/v1/x": {"collection": "#/rows/rows", "item": "row", "default": {}}},
        "errors": {"not_found": {}, "bad_request": {}},
    }
    with pytest.raises(KeyError, match="unknown fields"):
        make_handler(data)


def test_patch_on_a_multi_key_envelope_is_refused_at_build():
    """PATCH on a pointer whose target is not a one-key envelope has no payload to merge into."""
    data = {
        "stats": {"stats": [], "day_count": 0},
        "routes": {"/api/v1/x": {"PATCH": "#/stats"}},
        "errors": {"not_found": {}, "bad_request": {}},
    }
    with pytest.raises(ValueError, match="one-key envelope"):
        make_handler(data)


# --- static files ---


@pytest.mark.parametrize(
    ("path", "status", "content_type"),
    [
        pytest.param("/", 200, "text/html", id="root"),
        pytest.param("/t/anything", 200, "text/html", id="trip-page"),
        pytest.param("/trips/new", 200, "text/html", id="new-trip-page"),
        pytest.param("/js/api.js", 200, "text/javascript", id="module"),
        pytest.param("/nope.js", 404, "application/json", id="missing"),
    ],
)
def test_undeclared_paths_serve_static_files_or_not_found(client, path, status, content_type):
    """Client-side routes serve index.html, assets serve typed, anything else is not_found."""
    response = client.get(path)

    assert response.status_code == status
    assert response.headers["content-type"] == content_type
