"""Tests for tools/coverage_delta.py: two coverage reports in, one markdown table out.

`render` is called directly because the tool has no HTTP surface and no database — it
reads two JSON files and returns a string, which is the whole of what it promises.
"""

import json

import pytest

from tools.coverage_delta import render


@pytest.fixture
def report(tmp_path):
    """Return `report(name, total, files) -> path`, writing a minimal `coverage json` file."""

    def write(name, total, files):
        path = tmp_path / f"{name}.json"
        path.write_text(
            json.dumps(
                {
                    "files": {
                        filename: {"summary": {"percent_covered": percent}}
                        for filename, percent in files.items()
                    },
                    "totals": {"percent_covered": total},
                }
            )
        )
        return path

    return write


def test_render_states_the_total_as_a_left_to_right_arrow(report):
    """The headline carries the base total, the branch total and the signed change."""
    base = report("base", 81.3, {"app/db.py": 59.0})
    head = report("head", 83.3, {"app/db.py": 59.0})

    assert "**81.3% → 83.3%** (+2.0 pp)" in render(base, head)


def test_render_lists_a_file_whose_coverage_moved(report):
    """A file past the noise floor gets a row with both percentages and the difference."""
    base = report("base", 81.3, {"app/services/roster.py": 64.0})
    head = report("head", 83.3, {"app/services/roster.py": 81.2})

    assert "| `app/services/roster.py` | 64.0% | 81.2% | +17.2 |" in render(base, head)


@pytest.mark.parametrize(
    ("before", "after"),
    [pytest.param(64.0, 64.05, id="up-by-0.05"), pytest.param(64.0, 63.95, id="down-by-0.05")],
)
def test_render_omits_a_file_that_moved_less_than_a_tenth_of_a_point(report, before, after):
    """A sub-0.1 pp shift is a statement count changing, so the row would be noise."""
    base = report("base", 81.3, {"app/db.py": before})
    head = report("head", 81.3, {"app/db.py": after})

    assert "app/db.py" not in render(base, head)


def test_render_marks_a_file_absent_from_the_base_as_new(report):
    """A file the branch adds has no base percentage, so the cell is an em dash."""
    base = report("base", 81.3, {})
    head = report("head", 83.3, {"app/db_views.py": 96.4})

    assert "| `app/db_views.py` | — | 96.4% | new |" in render(base, head)


def test_render_marks_a_file_missing_from_the_branch_as_gone(report):
    """A file the branch deletes is still listed, so a drop in the total is attributable."""
    base = report("base", 81.3, {"app/retired.py": 12.0})
    head = report("head", 83.3, {})

    assert "| `app/retired.py` | 12.0% | — | gone |" in render(base, head)


def test_render_writes_no_table_when_nothing_moved(report):
    """With every file inside the noise floor the report is the total alone, not an empty table."""
    base = report("base", 83.3, {"app/db.py": 59.0})
    head = report("head", 83.3, {"app/db.py": 59.0})

    output = render(base, head)

    assert "No file moved by more than 0.1 pp." in output
    assert "| File |" not in output
