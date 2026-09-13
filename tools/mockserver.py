"""Frontend-owned mock API. Serves static/ and a canned trip under /api/v1.

No arithmetic, ever (design/FRONTEND.md §6): writes echo the posted body back with
an id and a status code; the in-memory fixture is patched so a re-read after a
write stays consistent, but nothing here computes a split, a balance or a stat.
"""

import copy
import itertools
import json
import re
import sys
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STATIC = ROOT / "static"
FIXTURE = ROOT / "tests" / "frontend" / "fixtures" / "trip.json"

_ids = itertools.count(1000)

# {res}: (singular key for the response envelope, list getter into the fixture).
# people/currencies/countries live embedded in the trip; labels are their own
# top-level fixture block (API.md §3 "People / Currencies / Countries / Labels").
RESOURCES = {
    "people": ("person", lambda fx: fx["trip"]["trip"]["people"]),
    "currencies": ("currency", lambda fx: fx["trip"]["trip"]["currencies"]),
    "countries": ("country", lambda fx: fx["trip"]["trip"]["countries"]),
    "labels": ("label", lambda fx: fx["labels"]["labels"]),
}

# Cosmetic-only defaults a real backend assigns and the mock never computes
# (design/FRONTEND.md §6): an added person still needs an avatar to render.
_PEOPLE_DEFAULTS = {"active": True, "color": "#6c757d"}


def load_fixture():
    """Load the fixture trip from disk."""
    return json.loads(FIXTURE.read_text())


class Handler(BaseHTTPRequestHandler):
    """Serve the fixture trip and static/ over HTTP, mutating the in-memory fixture on writes."""

    fixture = load_fixture()

    def _json(self, status, body):
        payload = json.dumps(body).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def _no_content(self):
        self.send_response(HTTPStatus.NO_CONTENT)
        self.end_headers()

    def _static(self, path):
        if path == "/" or path.startswith("/t/") or path == "/trips/new":
            path = "/index.html"
        file_path = (STATIC / path.lstrip("/")).resolve()
        if STATIC not in file_path.parents or not file_path.is_file():
            self.send_response(HTTPStatus.NOT_FOUND)
            self.end_headers()
            return
        content_type = {
            ".html": "text/html",
            ".css": "text/css",
            ".js": "text/javascript",
        }.get(file_path.suffix, "application/octet-stream")
        body = file_path.read_bytes()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        """Route a GET to a fixture endpoint, a 404, or a static file."""
        slug = self.fixture["trip"]["trip"]["slug"]
        routes = {
            "/api/v1/trips": lambda: self._json(200, {"trips": [self._trip_summary()]}),
            f"/api/v1/trips/{slug}": lambda: self._json(200, self.fixture["trip"]),
            f"/api/v1/trips/{slug}/items": lambda: self._json(200, self.fixture["items"]),
            f"/api/v1/trips/{slug}/labels": lambda: self._json(200, self.fixture["labels"]),
            f"/api/v1/trips/{slug}/balances": lambda: self._json(200, self.fixture["balances"]),
            f"/api/v1/trips/{slug}/stats": lambda: self._json(200, self.fixture["stats"]),
        }
        fn = routes.get(self.path)
        if fn:
            fn()
        elif self.path.startswith("/api/v1/"):
            self._json(404, {"error": {"code": "not_found", "params": {"resource": "route"}}})
        else:
            self._static(self.path)

    def do_POST(self):
        """Handle a POST as a create against the fixture, responding 201."""
        self._write(HTTPStatus.CREATED)

    def do_PATCH(self):
        """Handle a PATCH as an update against the fixture, responding 200."""
        self._write(HTTPStatus.OK)

    def do_DELETE(self):
        """Remove the matching item or resource row from the fixture."""
        m = re.match(r"/api/v1/trips/[^/]+/items/(\d+)$", self.path)
        if m:
            items = self.fixture["items"]["items"]
            self.fixture["items"]["items"] = [i for i in items if i["id"] != int(m.group(1))]
            return self._no_content()

        m = re.match(r"/api/v1/trips/[^/]+/(people|currencies|countries|labels)/(\d+)$", self.path)
        if m:
            resource, res_id = m.groups()
            _, get_list = RESOURCES[resource]
            lst = get_list(self.fixture)
            lst[:] = [row for row in lst if row["id"] != int(res_id)]
        self._no_content()

    def _write(self, status):
        length = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(length) or b"{}")

        if self.path == "/api/v1/trips" and self.command == "POST":
            # Not added to self.fixture: the mock only ever serves the one demo
            # trip under do_GET's routes, so visiting the new slug 404s — same
            # as a real client hitting a trip this mock never heard of.
            slug = re.sub(r"[^a-z0-9]+", "-", body.get("name", "trip").lower()).strip("-") or "trip"
            trip = {**body, "id": next(_ids), "slug": slug, "archived": False}
            self._json(status, {"trip": trip})
            return

        m = re.match(r"/api/v1/trips/[^/]+/items(?:/(\d+))?$", self.path)
        if m and self.command == "POST":
            item = {**body, "id": next(_ids)}
            self.fixture["items"]["items"].insert(0, item)
            self._json(status, {"item": item})
            return
        if m and m.group(1):
            item_id = int(m.group(1))
            items = self.fixture["items"]["items"]
            for i, existing in enumerate(items):
                if existing["id"] == item_id:
                    items[i] = {**existing, **body}
                    self._json(status, {"item": items[i]})
                    return

        m = re.match(r"/api/v1/trips/([^/]+)$", self.path)
        if m and self.command == "PATCH":
            self.fixture["trip"]["trip"].update(body)
            self._json(status, {"trip": self.fixture["trip"]["trip"]})
            return

        m = re.match(
            r"/api/v1/trips/[^/]+/(people|currencies|countries|labels)(?:/(\d+))?$", self.path
        )
        if m:
            resource, res_id = m.groups()
            singular, get_list = RESOURCES[resource]
            lst = get_list(self.fixture)
            if self.command == "POST":
                defaults = _PEOPLE_DEFAULTS if resource == "people" else {}
                row = {**defaults, **body, "id": next(_ids)}
                lst.append(row)
                self._json(status, {singular: row})
                return
            if res_id:
                rid = int(res_id)
                for i, existing in enumerate(lst):
                    if existing["id"] == rid:
                        lst[i] = {**existing, **body}
                        self._json(status, {singular: lst[i]})
                        return

        # anything unmatched: echo back verbatim so a write never hard-fails
        self._json(status, {**body, "id": body.get("id", next(_ids))})

    def _trip_summary(self):
        trip = copy.deepcopy(self.fixture["trip"]["trip"])
        people = trip.pop("people")
        trip.pop("currencies")
        trip.pop("countries")
        trip["people_count"] = len(people)
        trip["item_count"] = len(self.fixture["items"]["items"])
        return trip

    def log_message(self, fmt, *args):
        """Suppress the default per-request access logging."""


def main():
    """Start the mock server on the port given as argv[1], or 8001."""
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8001
    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    print(f"mockserver on http://127.0.0.1:{port}")
    server.serve_forever()


if __name__ == "__main__":
    main()
