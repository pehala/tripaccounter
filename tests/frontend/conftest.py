"""Fixtures for the Playwright suite.

Fixture-seeded mock servers and route-stubbing helpers, no DB or `app.*` import.
"""

import json
import threading
from http.server import ThreadingHTTPServer
from pathlib import Path

import pytest

from tools.mockserver import Handler

# Canned responses. `trip.json` is the resting state every view test opens; the
# rest are purpose-built - an empty trip for the empty states, markup in every
# user-supplied string for escaping, one file per error envelope. Every value in
# them is written out by hand, copied from what the backend actually produced.
FIXTURES = Path(__file__).parent / "fixtures"


def load_fixture(name="trip.json"):
    """Load and parse a named fixture file from tests/frontend/fixtures/."""
    return json.loads((FIXTURES / name).read_text())


@pytest.fixture
def fixture_data():
    """Return a fresh copy of fixtures/trip.json, private to this test."""
    return load_fixture()


@pytest.fixture
def slug(fixture_data):
    """Return the trip's slug from the fixture data."""
    return fixture_data["trip"]["trip"]["slug"]


@pytest.fixture
def mockserver(fixture_data):
    """tools.mockserver on a free port, seeded with this test's own fixture copy."""
    handler_cls = type("TestHandler", (Handler,), {"fixture": fixture_data})
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler_cls)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    port = server.server_address[1]
    try:
        yield f"http://127.0.0.1:{port}"
    finally:
        server.shutdown()
        thread.join()


@pytest.fixture
def trip_url(mockserver, slug):
    """Return the mockserver URL for this test's trip page."""
    return f"{mockserver}/t/{slug}"


@pytest.fixture
def make_mockserver():
    """Return a factory that starts a mockserver from a fixture file or a dict.

    Accepts either a fixtures/ filename or an in-memory dict; every instance
    started this way is torn down at teardown.
    """
    started = []

    def _make(name_or_data):
        data = load_fixture(name_or_data) if isinstance(name_or_data, str) else name_or_data
        handler_cls = type("TestHandler", (Handler,), {"fixture": data})
        server = ThreadingHTTPServer(("127.0.0.1", 0), handler_cls)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        started.append((server, thread))
        return f"http://127.0.0.1:{server.server_address[1]}", data

    yield _make
    for server, thread in started:
        server.shutdown()
        thread.join()


@pytest.fixture
def page(page):
    """Pin the browser's locale to `en` regardless of the runner's own OS/browser locale."""
    page.add_init_script("window.localStorage.setItem('lang', 'en')")
    return page


@pytest.fixture
def browser_context_args(browser_context_args):
    """Pin the browser's timezone to UTC so date/time formatting is deterministic across runners."""
    return {**browser_context_args, "timezone_id": "UTC"}


@pytest.fixture
def stub(page):
    """Return a helper that fulfils requests matching a URL glob via a callback.

    The callback is `responder(request) -> (status, body) | None`; fulfilled
    request bodies are recorded in call order.
    """

    def _stub(pattern, responder):
        calls = []

        def handler(route):
            request = route.request
            result = responder(request)
            if result is None:
                route.continue_()
                return
            calls.append(request.post_data_json if request.method in ("POST", "PATCH") else None)
            status, body = result
            route.fulfill(status=status, content_type="application/json", body=json.dumps(body))

        page.route(pattern, handler)
        return calls

    return _stub
