"""Write `app.openapi()` to `openapi.json` at the repo root.

The routers and `app/schemas/` are the source; this is their snapshot, kept in
the tree so a shape change shows up as a reviewable diff in the commit that makes
it. `make openapi` regenerates it and `make openapi-check` is the CI gate.

Keys are sorted so a regeneration produces a diff rather than a reshuffle.
"""

import json
from pathlib import Path

from app.main import app

OUTPUT = Path(__file__).resolve().parent.parent / "openapi.json"


def main() -> None:
    """Regenerate the committed OpenAPI snapshot from the running app's schema."""
    OUTPUT.write_text(json.dumps(app.openapi(), indent=2, sort_keys=True) + "\n")
    print(OUTPUT)


if __name__ == "__main__":
    main()
