"""index.html's CDN dependencies are pinned and verifiable. No browser.

Every CDN <script> and <link> in
index.html carries integrity and crossorigin and an exact pinned version; no
@latest, no floating range.
"""

import re
from pathlib import Path

INDEX = (Path(__file__).parent.parent.parent / "static" / "index.html").read_text()

CDN_HOSTS = ("cdn.jsdelivr.net", "code.jquery.com", "cdnjs.cloudflare.com")


def cdn_tags():
    """Every <script src=...> or <link href=...> pointing at a CDN, as its full tag text."""
    tags = re.findall(r"<(?:script|link)\b[^>]*>", INDEX)
    return [tag for tag in tags if any(host in tag for host in CDN_HOSTS)]


def test_at_least_one_cdn_dependency_is_declared():
    """A regression that removed every CDN tag would make every other assertion here vacuous."""
    assert len(cdn_tags()) >= 3


def test_every_cdn_tag_has_integrity_and_crossorigin():
    """Subresource integrity is what makes a compromised CDN tag inert rather than executed."""
    for tag in cdn_tags():
        assert 'integrity="sha' in tag, f"missing integrity: {tag}"
        assert "crossorigin=" in tag, f"missing crossorigin: {tag}"


def test_no_cdn_tag_uses_a_floating_version():
    """@latest or a bare unpinned path defeats the point of pinning at all."""
    for tag in cdn_tags():
        assert "@latest" not in tag, f"floating version: {tag}"


VERSION_PATTERN = re.compile(r"@(\d+\.\d+\.\d+)/")


def test_every_cdn_tag_names_an_exact_semver():
    """Every dependency is pinned to a concrete x.y.z, not a range or a tag."""
    for tag in cdn_tags():
        match = VERSION_PATTERN.search(tag)
        assert match, f"no exact version pin found: {tag}"


def test_import_map_pins_preact_and_htm_with_exact_versions():
    """The ES module import map is the one place preact/htm are resolved; it must pin too."""
    import_map_match = re.search(r'<script type="importmap">(.*?)</script>', INDEX, re.DOTALL)
    assert import_map_match, "no <script type=importmap> found"
    body = import_map_match.group(1)
    for module in ("preact", "preact/hooks", "htm"):
        assert f'"{module}"' in body, f"import map missing entry for {module}"
    assert VERSION_PATTERN.search(body), "import map has no pinned version"
    assert "@latest" not in body
