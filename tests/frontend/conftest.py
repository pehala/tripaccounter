"""Fixtures for the Playwright suite.

Fixture-seeded mock servers (tests/frontend/mockapi.py) and route-stubbing helpers,
no DB or `app.*` import.
"""

import json
from contextlib import ExitStack
from pathlib import Path

import pytest

from tests.frontend.mockapi import MockServer

# Canned responses. `trip.json` is the resting state every view test opens; the
# rest are purpose-built - an empty trip for the empty states, markup in every
# user-supplied string for escaping, one file per error envelope. Every value in
# them is written out by hand, copied from what the backend actually produced.
FIXTURES = Path(__file__).parent / "fixtures"


def load_fixture(name):
    """Load and parse a named fixture file from tests/frontend/fixtures/."""
    return json.loads((FIXTURES / name).read_text())


@pytest.fixture
def fixture_data():
    """Return a fresh copy of the resting-state fixture, private to this test."""
    return load_fixture("trip.json")


@pytest.fixture
def slug(fixture_data):
    """Return the trip's slug from the fixture data."""
    return fixture_data["trip"]["trip"]["slug"]


@pytest.fixture
def mockserver(make_mockserver, fixture_data):
    """Return the base URL of a mock API serving this test's own `fixture_data`."""
    return make_mockserver(data=fixture_data)[0]


@pytest.fixture
def trip_url(mockserver, slug):
    """Return the mockserver URL for this test's trip page."""
    return f"{mockserver}/t/{slug}"


@pytest.fixture
def make_mockserver():
    """Return a factory that serves a fixture on a free port and returns `(url, data)`.

    Pass either `name`, a file under fixtures/, or `data`, a dict to serve as is. Every
    server started this way is stopped at teardown.
    """
    with ExitStack() as servers:

        def _make(name=None, data=None):
            if data is None:
                data = load_fixture(name)
            return servers.enter_context(MockServer(data)).url, data

        yield _make


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
