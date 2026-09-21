"""Tests for tools/dump_openapi.py: `main` writes app.openapi() to OUTPUT, sorted and pretty.

`main` is called directly with OUTPUT monkeypatched to a tmp_path file — the tool has no
argument surface, so its whole contract is "read the app's schema, write it".
"""

import json

from app.main import app
from tools import dump_openapi


def test_main_writes_the_apps_openapi_schema(tmp_path, monkeypatch, capsys):
    """The written file parses as JSON identical to app.openapi(), sorted and newline-terminated."""
    target = tmp_path / "openapi.json"
    monkeypatch.setattr(dump_openapi, "OUTPUT", target)

    dump_openapi.main()

    assert json.loads(target.read_text()) == app.openapi()
    assert target.read_text() == json.dumps(app.openapi(), indent=2, sort_keys=True) + "\n"
    assert capsys.readouterr().out == f"{target}\n"
