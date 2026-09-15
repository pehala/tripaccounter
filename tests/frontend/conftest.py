"""Fixtures for the Playwright suite.

One fixture-seeded mock server (tests/frontend/mockapi.py) per test, navigation and
modal fixtures on top of it, route stubs for writes and errors, and a session-scoped
trip page per tab for the tests that only read it. No DB, no `app.*`.
"""

import json
from fnmatch import fnmatchcase
from pathlib import Path
from urllib.parse import urlsplit

import pytest
from playwright.sync_api import expect

from tests.frontend.mockapi import MockServer

# Canned responses. `trip.json` is the resting state every view test opens; the
# rest are purpose-built - an empty trip for the empty states, markup in every
# user-supplied string for escaping, one file per error envelope. Every value in
# them is written out by hand, copied from what the backend actually produced.
FIXTURES = Path(__file__).parent / "fixtures"

# Tab link text -> (URL path segment, locator visible once that tab has finished rendering).
# The landmarks are visible at every viewport width, so phone-width tests can use them.
TABS = {
    "Items": ("items", lambda page: page.get_by_placeholder("filter by name or label")),
    "Balances": ("balances", lambda page: page.locator(".balances-content").first),
    "Statistics": ("stats", lambda page: page.locator(".stats-content").first),
    "Setup": ("setup", lambda page: page.get_by_text("People", exact=True)),
}
TAB_PARAMS = [pytest.param(name, id=path) for name, (path, _) in TABS.items()]
TAB_BY_PATH = {path: name for name, (path, _) in TABS.items()}


# Bootstrap's modal fade and collapse resolve on CSS transition end; waiting for
# `.modal.show` or `#split-body.show` cost a test up to 1.4 s of pure animation.
NO_TRANSITIONS = """document.addEventListener('DOMContentLoaded', () => {
  const style = document.createElement('style');
  style.textContent =
    '*, *::before, *::after { transition: none !important; animation: none !important; }';
  document.head.appendChild(style);
});"""


def load_fixture(name):
    """Parse a file under fixtures/, e.g. "trip.json" or "errors/409_in_use.json"."""
    return json.loads((FIXTURES / name).read_text())


# --- data -------------------------------------------------------------------------


@pytest.fixture
def fixture_name(request):
    """Name of the fixture file the mock serves; override per module or parametrize indirectly."""
    return getattr(request, "param", "trip.json")


@pytest.fixture
def fixture_data(fixture_name):
    """Return a fresh parse of `fixture_name`, private to this test; override to mutate it."""
    return load_fixture(fixture_name)


@pytest.fixture
def slug(fixture_data):
    """Return the served trip's slug."""
    return fixture_data["trip"]["trip"]["slug"]


@pytest.fixture
def mockserver(fixture_data):
    """Return the base URL of a mock API serving this test's `fixture_data`."""
    with MockServer(fixture_data) as server:
        yield server.url


@pytest.fixture
def trip_url(mockserver, slug):
    """Return the mockserver URL for this test's trip page, without a tab segment."""
    return f"{mockserver}/t/{slug}"


# --- browser ----------------------------------------------------------------------


@pytest.fixture
def page(page):
    """Pin the browser's locale to `en` and turn off CSS transitions so Bootstrap settles at once.

    Without the pin the runner's OS locale would leak in; without the transitions every
    modal and collapse wait would pay Bootstrap's animation time.
    """
    page.add_init_script("window.localStorage.setItem('lang', 'en')")
    page.add_init_script(NO_TRANSITIONS)
    return page


@pytest.fixture
def browser_context_args(browser_context_args):
    """Pin the browser's timezone to UTC so date/time formatting is deterministic across runners."""
    return {**browser_context_args, "timezone_id": "UTC"}


@pytest.fixture
def stub(page):
    """Return a helper that fulfils requests matching a URL glob via a callback.

    The callback is `responder(request) -> (status, body) | (status, body, content_type)
    | None`; None lets the request through to the mock. Bodies are JSON-encoded unless
    a non-JSON `content_type` is given, in which case `body` is sent as text. Fulfilled
    POST/PATCH request bodies are recorded in call order; other methods record None.
    """

    def install(pattern, responder):
        calls = []

        def handler(route):
            request = route.request
            result = responder(request)
            if result is None:
                route.continue_()
                return
            calls.append(request.post_data_json if request.method in ("POST", "PATCH") else None)
            status, body, *rest = result
            content_type = rest[0] if rest else "application/json"
            if content_type == "application/json":
                body = json.dumps(body)
            route.fulfill(status=status, content_type=content_type, body=body)

        page.route(pattern, handler)
        return calls

    return install


@pytest.fixture
def count_requests(page):
    """Return `count_requests(path_glob, method=None) -> list[Request]`, growing live.

    Matches `fnmatch` against the URL path: "*/api/v1/*" is every API call, "*/items"
    is the collection and not "*/items/preview-split". Attach it right before the
    action under test; earlier requests are not counted.
    """

    def attach(path_glob, method=None):
        seen = []

        def record(request):
            path_matches = fnmatchcase(urlsplit(request.url).path, path_glob)
            if path_matches and method in (None, request.method):
                seen.append(request)

        page.on("request", record)
        return seen

    return attach


@pytest.fixture(scope="session")
def js(browser):
    """Return `js(module, name, *args, locale=None)`: call an export of /js/<module>.

    Evaluates `(await import('/js/<module>'))[name](...args)` in a document served by
    the mock; with `locale`, calls i18n `setLocale(locale)` first. For inputs and
    actions only: never compute an expected value with it, write the literal.

    One document for the whole session: a call renders nothing and every call site
    names its own locale, so there is no page state to carry between tests. A test
    that needs a module imported for the first time asks for `page` and `mockserver`.
    """
    context = browser.new_context(timezone_id="UTC")
    page = context.new_page()
    with MockServer(load_fixture("trip.json")) as server:
        page.goto(f"{server.url}/")

        def call(module, name, *args, locale=None):
            return page.evaluate(
                """async ({ module, name, args, locale }) => {
                    if (locale) (await import('/js/i18n/index.js')).setLocale(locale);
                    return (await import(`/js/${module}`))[name](...args);
                }""",
                {"module": module, "name": name, "args": list(args), "locale": locale},
            )

        yield call
    context.close()


# --- navigation -------------------------------------------------------------------


@pytest.fixture
def open_trip(page, trip_url):
    """Return `open_trip(tab=None) -> page`: load the trip at `/tab`, wait for the tab.

    A factory rather than a page fixture, so a test can register a stub on a baseline
    GET before the first navigation.
    """

    def go(tab=None):
        page.goto(trip_url if tab is None else f"{trip_url}/{tab}")
        expect(TABS[TAB_BY_PATH[tab or "items"]][1](page)).to_be_visible()
        return page

    return go


@pytest.fixture
def open_tab(page):
    """Return `open_tab(name) -> page`: click the nav link and wait for that tab's landmark."""

    def go(name):
        page.get_by_role("link", name=name).click()
        expect(page.locator(".nav-link.active")).to_have_text(name)
        expect(TABS[name][1](page)).to_be_visible()
        return page

    return go


@pytest.fixture
def items_page(open_trip):
    """Return the page with the trip loaded on the Items tab."""
    return open_trip()


@pytest.fixture
def balances_page(open_trip):
    """Return the page with the trip loaded on the Balances tab."""
    return open_trip("balances")


@pytest.fixture
def stats_page(open_trip):
    """Return the page with the trip loaded on the Statistics tab."""
    return open_trip("stats")


@pytest.fixture
def setup_page(open_trip):
    """Return the page with the trip loaded on the Setup tab."""
    return open_trip("setup")


# --- shared read-only pages ---------------------------------------------------------


@pytest.fixture(scope="session")
def shared_trip(browser):
    """Return `shared_trip(tab=None) -> page`: one trip.json page per tab, built once.

    A test on one of these pages may read it and may leave it in a state any other
    test on the same page reaches too — expanding a collapse is such a change, typing
    into a filter, navigating or writing the URL hash is not. A test that needs the
    resting state asks for `items_page`, `balances_page` or `stats_page` instead and
    gets a page of its own.
    """
    data = load_fixture("trip.json")
    slug = data["trip"]["trip"]["slug"]
    context = browser.new_context(timezone_id="UTC")
    context.add_init_script("window.localStorage.setItem('lang', 'en')")
    context.add_init_script(NO_TRANSITIONS)
    pages = {}

    with MockServer(data) as server:

        def go(tab=None):
            if tab not in pages:
                page = context.new_page()
                url = f"{server.url}/t/{slug}"
                page.goto(url if tab is None else f"{url}/{tab}")
                expect(TABS[TAB_BY_PATH[tab or "items"]][1](page)).to_be_visible()
                pages[tab] = page
            return pages[tab]

        yield go

    context.close()


@pytest.fixture(scope="session")
def shared_items_page(shared_trip):
    """Return the session's read-only Items tab."""
    return shared_trip()


@pytest.fixture(scope="session")
def shared_balances_page(shared_trip):
    """Return the session's read-only Balances tab."""
    return shared_trip("balances")


@pytest.fixture(scope="session")
def shared_stats_page(shared_trip):
    """Return the session's read-only Statistics tab."""
    return shared_trip("stats")


@pytest.fixture
def card(page):
    """Return `card(header_text)`: the `.card` whose `.card-header` contains that text."""

    def find(header_text):
        return page.locator(".card").filter(has=page.locator(".card-header", has_text=header_text))

    return find


# --- item modal -------------------------------------------------------------------


@pytest.fixture
def new_item_modal(items_page):
    """Return the `.modal.show` locator of the new-expense modal, opened from the Items tab."""
    items_page.get_by_role("button", name="Expense").click()
    modal = items_page.locator(".modal.show")
    modal.wait_for()
    return modal


@pytest.fixture
def split_expanded(new_item_modal):
    """Return the `#split-body` locator of the new-expense modal with its split section open."""
    new_item_modal.locator('[data-bs-target="#split-body"]').click()
    body = new_item_modal.locator("#split-body.show")
    body.wait_for()
    return body


@pytest.fixture
def open_edit_modal(items_page):
    """Return `open_edit_modal(item_name) -> modal`: click that row, wait for the edit modal."""

    def go(item_name):
        items_page.locator("a.list-group-item-action", has_text=item_name).first.click()
        modal = items_page.locator(".modal.show")
        modal.wait_for()
        return modal

    return go
