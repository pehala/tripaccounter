"""JSON-driven mock API for the Playwright suite.

A fixture file declares its routes under ``routes`` — one key per URL — and the
engine serves them. Every body and error envelope comes from the file: a value
starting with ``#/`` is an RFC 6901 JSON Pointer into the same file, served by
identity; anything else is a literal body; ``"collection"`` expands into REST
operations over a pointed list. Statuses follow the method unless a literal body
carries ``"$status"``. Paths nothing declares are served from ``static/``.
Nothing here knows what a trip, a split or a balance is (``design/FRONTEND.md`` §6).
"""

import itertools
import json
import threading
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Self
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[2]
STATIC = ROOT / "static"
FIRST_ID = 1000
POINTER_PREFIX = "#/"
ECHO = "$echo"
STATUS = "$status"
ID_SEGMENT = "{id}"
STATUS_BY_METHOD = {
    "GET": HTTPStatus.OK,
    "POST": HTTPStatus.CREATED,
    "PATCH": HTTPStatus.OK,
    "DELETE": HTTPStatus.NO_CONTENT,
}
ERRORS = {"not_found": HTTPStatus.NOT_FOUND, "bad_request": HTTPStatus.BAD_REQUEST}
COLLECTION_FIELDS = {"collection", "item", "defaults", "insert", "extra"}
COLLECTION_OPERATIONS = (
    ("GET", (), "read"),
    ("POST", (), "create"),
    ("PATCH", (ID_SEGMENT,), "update"),
    ("DELETE", (ID_SEGMENT,), "delete"),
)
CONTENT_TYPES = {".html": "text/html", ".css": "text/css", ".js": "text/javascript"}
INDEX_PATHS = ("/", "/trips/new")

Response = tuple[int, Any]
Operation = Callable[[dict, str | None], Response]


def is_pointer(value: Any) -> bool:
    """Tell whether a route value is a JSON Pointer into the fixture rather than a literal."""
    return isinstance(value, str) and value.startswith(POINTER_PREFIX)


def resolve_pointer(data: Any, pointer: str) -> Any:
    """Return the object an RFC 6901 pointer in ``#/a/b/0`` form names inside data, by identity."""
    if not is_pointer(pointer):
        raise ValueError(f"{pointer!r} is not a '#/...' JSON Pointer")
    target = data
    for raw_token in pointer[len(POINTER_PREFIX) :].split("/"):
        token = raw_token.replace("~1", "/").replace("~0", "~")
        target = target[int(token)] if isinstance(target, list) else target[token]
    return target


def contains_echo(node: Any) -> bool:
    """Tell whether a literal body carries the ``"$echo"`` marker anywhere below it."""
    if isinstance(node, dict):
        return any(contains_echo(value) for value in node.values())
    if isinstance(node, list):
        return any(contains_echo(value) for value in node)
    return node == ECHO


def fill_echo(node: Any, body: dict, ids: Iterator[int]) -> Any:
    """Return node with every ``"$echo"`` replaced by the request body plus a counter id."""
    if isinstance(node, dict):
        return {key: fill_echo(value, body, ids) for key, value in node.items()}
    if isinstance(node, list):
        return [fill_echo(value, body, ids) for value in node]
    if node == ECHO:
        return {**body, "id": body["id"] if "id" in body else next(ids)}
    return node


def status_of(method: str, value: Any) -> int:
    """Return the status a declared value answers: its ``$status`` key, else the method default."""
    if isinstance(value, dict) and STATUS in value:
        return int(value[STATUS])
    return int(STATUS_BY_METHOD[method])


def body_of(value: Any) -> Any:
    """Return a declared literal without its ``$status`` directive."""
    if isinstance(value, dict):
        return {key: item for key, item in value.items() if key != STATUS}
    return value


def payload_of(envelope: dict) -> Any:
    """Return the single value of a ``{key: payload}`` response envelope."""
    if not isinstance(envelope, dict) or len(envelope) != 1:
        raise ValueError(f"PATCH target must be a one-key envelope, got {list(envelope)!r}")
    return next(iter(envelope.values()))


def iter_operations(routes: dict) -> Iterator[tuple[str, tuple[str, ...], dict]]:
    """Yield ``(method, segments, spec)`` for every operation the routes declare.

    A method key on a route is one operation with ``spec = {"method", "value"}``; a
    ``collection`` route expands into its four REST operations, whose spec is the route
    itself plus ``"op"``. Member operations carry the ``{id}`` segment.
    """
    for path, route in routes.items():
        segments = tuple(path.strip("/").split("/"))
        if "collection" in route:
            for method, tail, operation in COLLECTION_OPERATIONS:
                yield method, (*segments, *tail), {**route, "op": operation}
        else:
            for method, value in route.items():
                yield method, segments, {"method": method, "value": value}


@dataclass
class Collection:
    """REST operations over one pointed list of rows."""

    rows: list
    key: str
    item_key: str
    defaults: dict
    insert: str
    ids: Iterator[int]
    not_found: Response
    extra: dict

    def find(self, rid: str | None) -> dict | None:
        """Return the row whose id renders as rid in a URL, or None."""
        return next((row for row in self.rows if str(row.get("id")) == rid), None)

    def read(self, body: dict, rid: str | None) -> Response:
        """Answer the list under its envelope key, plus any declared sibling fields."""
        return HTTPStatus.OK, {self.key: self.rows, **self.extra}

    def create(self, body: dict, rid: str | None) -> Response:
        """Store defaults + body under a fresh id and answer 201 with the row."""
        row = {**self.defaults, **body, "id": next(self.ids)}
        if self.insert == "head":
            self.rows.insert(0, row)
        else:
            self.rows.append(row)
        return HTTPStatus.CREATED, {self.item_key: row}

    def update(self, body: dict, rid: str | None) -> Response:
        """Merge body into the row with that id and answer it, or ``not_found``."""
        row = self.find(rid)
        if row is None:
            return self.not_found
        row.update(body)
        return HTTPStatus.OK, {self.item_key: row}

    def delete(self, body: dict, rid: str | None) -> Response:
        """Remove the row with that id and answer 204, or ``not_found``."""
        row = self.find(rid)
        if row is None:
            return self.not_found
        self.rows.remove(row)
        return HTTPStatus.NO_CONTENT, None


@dataclass
class Declared:
    """One method on one path: an optional merge into the fixture, then the declared value."""

    status: int
    value: Any
    merge_into: dict | None
    echo: bool
    ids: Iterator[int]

    def __call__(self, body: dict, rid: str | None) -> Response:
        """Apply the merge and answer the value, echo-filled when it carries the marker."""
        if self.merge_into is not None:
            self.merge_into.update(body)
        value = fill_echo(self.value, body, self.ids) if self.echo else self.value
        return self.status, value


@dataclass(frozen=True)
class Route:
    """One method + path template bound to the operation that answers it."""

    method: str
    segments: tuple[str, ...]
    handler: Operation

    def match(self, method: str, segments: tuple[str, ...]) -> tuple[bool, str | None]:
        """Return ``(matched, id_segment)`` for a request's method and path segments."""
        if method != self.method or len(segments) != len(self.segments):
            return False, None
        rid = None
        for expected, actual in zip(self.segments, segments, strict=True):
            if expected == ID_SEGMENT:
                rid = actual
            elif expected != actual:
                return False, None
        return True, rid


class Router:
    """Routes compiled from one fixture's ``routes`` and ``errors``, sharing its objects."""

    def __init__(self, data: dict) -> None:
        """Compile data["routes"]; data["errors"] must name ``not_found`` and ``bad_request``."""
        errors = data["errors"]
        for name in ERRORS:
            if name not in errors:
                raise KeyError(f"fixture 'errors' declares no {name!r} body")
        self.not_found: Response = (ERRORS["not_found"], errors["not_found"])
        self.bad_request: Response = (ERRORS["bad_request"], errors["bad_request"])
        self.ids = itertools.count(FIRST_ID)
        collections: dict[int, Collection] = {}
        self.routes = [
            Route(method, segments, self.operation_for(spec, data, collections))
            for method, segments, spec in iter_operations(data["routes"])
        ]
        self.routes.sort(key=lambda route: route.segments.count(ID_SEGMENT))

    def operation_for(self, spec: dict, data: dict, collections: dict) -> Operation:
        """Build the callable for one operation spec, reusing one Collection per route."""
        if "collection" in spec:
            unknown = set(spec) - COLLECTION_FIELDS - {"op"}
            if unknown:
                raise KeyError(
                    f"collection {spec['collection']!r} has unknown fields {sorted(unknown)}"
                )
            pointer = spec["collection"]
            if pointer not in collections:
                collections[pointer] = Collection(
                    rows=resolve_pointer(data, pointer),
                    key=pointer.rsplit("/", 1)[1],
                    item_key=spec["item"],
                    defaults=spec.get("defaults", {}),
                    insert=spec.get("insert", "tail"),
                    ids=self.ids,
                    not_found=self.not_found,
                    extra={
                        key: resolve_pointer(data, value) if is_pointer(value) else value
                        for key, value in spec.get("extra", {}).items()
                    },
                )
            return getattr(collections[pointer], spec["op"])
        method, value = spec["method"], spec["value"]
        status = status_of(method, value)
        if not is_pointer(value):
            return Declared(status, body_of(value), None, contains_echo(value), self.ids)
        target = resolve_pointer(data, value)
        merge_into = payload_of(target) if method == "PATCH" else None
        return Declared(status, target, merge_into, False, self.ids)

    def dispatch(self, method: str, path: str, body: dict) -> Response | None:
        """Answer from the first matching route, or None when nothing declares the path."""
        segments = tuple(path.strip("/").split("/"))
        for route in self.routes:
            matched, rid = route.match(method, segments)
            if matched:
                return route.handler(body, rid)
        return None


class Handler(BaseHTTPRequestHandler):
    """Serve one fixture's routes and ``static/`` over HTTP; instantiate via make_handler."""

    router: Router

    def handle_request(self) -> None:
        """Answer a declared route, else a static file, else the fixture's ``not_found``."""
        path = urlsplit(self.path).path
        try:
            body = self.read_body()
        except (ValueError, TypeError):
            self.send_json(*self.router.bad_request)
            return
        response = self.router.dispatch(self.command, path, body)
        if response is not None:
            self.send_json(*response)
        elif not self.serve_static(path):
            self.send_json(*self.router.not_found)

    do_GET = do_POST = do_PATCH = do_DELETE = handle_request

    def read_body(self) -> dict:
        """Parse the request body as a JSON object; an absent body is an empty object.

        Raises ValueError for unparsable JSON and TypeError for a non-object value.
        """
        length = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(length) if length else b"{}"
        body = json.loads(raw)
        if not isinstance(body, dict):
            raise TypeError("request body is not a JSON object")
        return body

    def send_json(self, status: int, body: Any) -> None:
        """Send body as JSON with the status, or headers only when body is None."""
        self.send_response(status)
        if body is None:
            self.end_headers()
            return
        payload = json.dumps(body).encode()
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def serve_static(self, path: str) -> bool:
        """Serve a file under static/ (client-side routes map to index.html); False if none."""
        if path in INDEX_PATHS or path.startswith("/t/"):
            path = "/index.html"
        file_path = (STATIC / path.lstrip("/")).resolve()
        if STATIC not in file_path.parents or not file_path.is_file():
            return False
        payload = file_path.read_bytes()
        self.send_response(HTTPStatus.OK)
        content_type = CONTENT_TYPES.get(file_path.suffix, "application/octet-stream")
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)
        return True

    def log_message(self, fmt: str, *args: Any) -> None:
        """Keep the test output free of per-request access lines."""


def make_handler(data: dict) -> type[Handler]:
    """Return a Handler class bound to a Router over this fixture dict and nothing else."""
    return type("FixtureHandler", (Handler,), {"router": Router(data)})


class MockServer:
    """One fixture served on a free localhost port for the duration of a ``with`` block."""

    def __init__(self, data: dict) -> None:
        """Bind a server for this fixture dict on an ephemeral port; entering it starts serving."""
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(data))
        # shutdown() returns only after serve_forever's next poll; the default 0.5 s
        # would be paid by every test's teardown.
        self.thread = threading.Thread(
            target=self.server.serve_forever, kwargs={"poll_interval": 0.01}, daemon=True
        )
        self.url = f"http://127.0.0.1:{self.server.server_address[1]}"

    def __enter__(self) -> Self:
        """Serve requests in the background and return self."""
        self.thread.start()
        return self

    def __exit__(self, *exc_info: object) -> None:
        """Stop serving, wait for the thread to finish and close the listening socket."""
        self.server.shutdown()
        self.thread.join()
        self.server.server_close()
