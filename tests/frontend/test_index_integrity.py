"""index.html's CDN dependencies are pinned and verifiable. No browser.

Every CDN <script> and <link> in
index.html carries integrity and crossorigin and an exact pinned version; no
@latest, no floating range.
"""

import re
from pathlib import Path

import pytest

INDEX = (Path(__file__).parent.parent.parent / "static" / "index.html").read_text()

CDN_HOSTS = ("cdn.jsdelivr.net", "code.jquery.com", "cdnjs.cloudflare.com")
VERSION_PATTERN = re.compile(r"@(\d+\.\d+\.\d+)/")
PACKAGE_PATTERN = re.compile(r"npm/([^@/]+)@[^\"']*\.(css|js)")


def cdn_tags():
    """Every <script src=...> or <link href=...> pointing at a CDN, as its full tag text."""
    tags = re.findall(r"<(?:script|link)\b[^>]*>", INDEX)
    return [tag for tag in tags if any(host in tag for host in CDN_HOSTS)]


def package_name(tag):
    """Name a CDN tag by its npm package and asset kind (`bootstrap-css`), else by its host."""
    match = PACKAGE_PATTERN.search(tag)
    if match:
        return "-".join(match.groups())
    return next(host for host in CDN_HOSTS if host in tag)


CDN_TAGS = cdn_tags()
TAG_PARAMS = [pytest.param(tag, id=package_name(tag)) for tag in CDN_TAGS]


@pytest.fixture
def import_map():
    """Return the body of index.html's <script type="importmap">."""
    match = re.search(r'<script type="importmap">(.*?)</script>', INDEX, re.DOTALL)
    assert match, "no <script type=importmap> found"
    return match.group(1)


def test_at_least_one_cdn_dependency_is_declared():
    """A regression that removed every CDN tag would make every per-tag case here vanish."""
    assert len(CDN_TAGS) >= 3


@pytest.mark.parametrize("tag", TAG_PARAMS)
def test_cdn_tag_has_integrity_and_crossorigin(tag):
    """Subresource integrity is what makes a compromised CDN tag inert rather than executed."""
    assert 'integrity="sha' in tag
    assert "crossorigin=" in tag


@pytest.mark.parametrize("tag", TAG_PARAMS)
def test_cdn_tag_uses_no_floating_version(tag):
    """@latest or a bare unpinned path defeats the point of pinning at all."""
    assert "@latest" not in tag


@pytest.mark.parametrize("tag", TAG_PARAMS)
def test_cdn_tag_names_an_exact_semver(tag):
    """Every dependency is pinned to a concrete x.y.z, not a range or a tag."""
    assert VERSION_PATTERN.search(tag)


@pytest.mark.parametrize(
    "module", [pytest.param(m, id=m) for m in ("preact", "preact/hooks", "htm")]
)
def test_import_map_resolves_module(import_map, module):
    """The ES module import map is the one place preact/htm are resolved; each must be listed."""
    assert f'"{module}"' in import_map


def test_import_map_pins_exact_versions(import_map):
    """The import map's URLs name a concrete x.y.z and never @latest."""
    assert VERSION_PATTERN.search(import_map)
    assert "@latest" not in import_map
