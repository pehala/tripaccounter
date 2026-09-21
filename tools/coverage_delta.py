"""Render the coverage change between two `coverage json` reports as markdown.

The base report comes first and the branch's second, so the arrow reads left to
right. Files that appeared or vanished are always listed; `make coverage` writes the
reports this reads and the CI job turns the output into the pull request's comment.
"""

import json
import sys
from pathlib import Path

# A file whose percentage shifts by less than this moved because its statement count
# changed, not because a different amount of it is tested.
NOISE = 0.1


def percentages(path):
    """Return a `coverage json` report's per-file covered percentages and its total."""
    report = json.loads(Path(path).read_text())
    files = {name: data["summary"]["percent_covered"] for name, data in report["files"].items()}
    return files, report["totals"]["percent_covered"]


def moved_files(base, head):
    """Yield (name, before, after) per file that appeared, vanished, or moved past NOISE."""
    for name in sorted(base.keys() | head.keys()):
        before, after = base.get(name), head.get(name)
        if before is None or after is None or abs(after - before) >= NOISE:
            yield name, before, after


def cell(value):
    """Format a percentage, or an em dash when the file is in only one of the reports."""
    return "—" if value is None else f"{value:.1f}%"


def delta(before, after):
    """Describe a file's movement: appeared, vanished, or the signed difference."""
    if before is None:
        return "new"
    if after is None:
        return "gone"
    return f"{after - before:+.1f}"


def render(base_path, head_path):
    """Return the markdown comparing the base report against the branch's."""
    base, base_total = percentages(base_path)
    head, head_total = percentages(head_path)
    lines = [
        "## Backend coverage",
        "",
        f"**{cell(base_total)} → {cell(head_total)}** ({head_total - base_total:+.1f} pp)",
        "",
    ]
    rows = list(moved_files(base, head))
    if not rows:
        return "\n".join([*lines, f"No file moved by more than {NOISE} pp.", ""])
    lines += ["| File | Base | PR | Δ |", "|---|---:|---:|---:|"]
    lines += [
        f"| `{name}` | {cell(before)} | {cell(after)} | {delta(before, after)} |"
        for name, before, after in rows
    ]
    return "\n".join([*lines, ""])


def main():
    """Write the markdown report for the two report paths given on the command line."""
    print(render(*sys.argv[1:3]), end="")


if __name__ == "__main__":
    main()
