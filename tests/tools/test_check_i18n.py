"""Tests for tools/check_i18n.py: the static i18n validator described in its own module docstring.

Pure-parsing functions are called directly against tiny synthetic files. `main` is exercised
end to end against a small catalog/JS/API.md tree written under `tmp_path`, with the module's
directory constants monkeypatched to point at it — this is the only way to see the five checks
combine the way `make lint` actually runs them, without touching the real static/js/ tree.
"""

import pytest

from tools import check_i18n

EN_JS = """export default {
  'app.title': 'Trip',
  'err.not_found': 'Not found',
  'item.count.one': '{n} item',
  'item.count.other': '{n} items',
};
"""
CS_JS = """export default {
  'app.title': 'Výlet',
  'err.not_found': 'Nenalezeno',
  'item.count.one': '{n} položka',
  'item.count.few': '{n} položky',
  'item.count.other': '{n} položek',
};
"""
INDEX_JS = """export const LANGS = {
  en: 'English',
  cs: 'Čeština',
};
"""
APP_JS = """t('app.title');
t('err.' + code);
t('item.count', {n: n});
"""
API_MD = """| field | code |
| --- | --- |
| amount | `not_found` |
"""


# --- fixtures ---


@pytest.fixture
def project(tmp_path, monkeypatch):
    """Point check_i18n's directory constants at an empty tree under tmp_path; return a writer."""
    i18n_dir = tmp_path / "static" / "js" / "i18n"
    api_md = tmp_path / "design" / "API.md"
    i18n_dir.mkdir(parents=True)
    api_md.parent.mkdir(parents=True)
    monkeypatch.setattr(check_i18n, "I18N_DIR", i18n_dir)
    monkeypatch.setattr(check_i18n, "JS_ROOT", tmp_path / "static" / "js")
    monkeypatch.setattr(check_i18n, "API_MD", api_md)

    def write(path, text):
        target = tmp_path / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text)

    return write


@pytest.fixture
def baseline(project):
    """Write a catalog/JS/API.md tree that passes every check in main() cleanly."""
    project("static/js/i18n/en.js", EN_JS)
    project("static/js/i18n/cs.js", CS_JS)
    project("static/js/i18n/index.js", INDEX_JS)
    project("static/js/app.js", APP_JS)
    project("design/API.md", API_MD)
    return project


# --- catalog_keys ---


def test_catalog_keys_returns_every_quoted_key(project, tmp_path):
    """catalog_keys reads every 'key': value pair's key, single- or double-quoted value alike."""
    catalog = tmp_path / "static/js/i18n/en.js"
    project(
        "static/js/i18n/en.js", "export default {\n  'app.title': 'Trip',\n  'err.x': \"Y\",\n};\n"
    )

    assert check_i18n.catalog_keys(catalog) == {"app.title", "err.x"}


# --- registered_langs ---


def test_registered_langs_parses_the_langs_block(project):
    """Every `code: '...'` entry inside LANGS = {...} is a registered language."""
    project("static/js/i18n/index.js", INDEX_JS)

    assert check_i18n.registered_langs() == {"en", "cs"}


def test_registered_langs_with_no_langs_block_is_empty(project):
    """A file with no LANGS assignment registers no languages, rather than erroring."""
    project("static/js/i18n/index.js", "export const OTHER = {};\n")

    assert check_i18n.registered_langs() == set()


# --- literal_call_keys ---


def test_literal_call_keys_matches_literal_t_calls(project):
    """A literal string argument to t(), with or without a trailing options object, is a key."""
    project("static/js/app.js", "t('app.title'); t('item.count', {n: 1});")

    assert check_i18n.literal_call_keys() == {"app.title", "item.count"}


def test_literal_call_keys_skips_files_inside_the_i18n_directory(project):
    """A quoted key inside a catalog itself is not usage evidence."""
    project("static/js/i18n/en.js", "t('should.not.count')")
    project("static/js/app.js", "t('counts')")

    assert check_i18n.literal_call_keys() == {"counts"}


def test_literal_call_keys_ignores_a_concatenated_key(project):
    """t('err.' + code) builds its key at runtime; it must not be mistaken for a literal one."""
    project("static/js/app.js", "t('err.' + code)")

    assert check_i18n.literal_call_keys() == set()


# --- quoted_dotted_keys ---


def test_quoted_dotted_keys_finds_dotted_strings_outside_t_calls(project):
    """A key referenced by name outside t(), such as through a lookup table, still counts."""
    project("static/js/app.js", "const TABS = [['a', 'tab.first']];")

    assert check_i18n.quoted_dotted_keys() == {"tab.first"}


# --- dynamic_prefixes ---


def test_dynamic_prefixes_finds_concatenation_and_template_forms(project):
    """Both t('prefix.' + expr) and t(`prefix.${expr}`) contribute their prefix."""
    project("static/js/app.js", "t('err.' + code); t(`lang.${code}`);")

    assert check_i18n.dynamic_prefixes() == {"err.", "lang."}


# --- api_error_codes ---


def test_api_error_codes_reads_the_code_column(project):
    """Backticked codes in a markdown table column literally named `code` are collected."""
    project("design/API.md", API_MD)

    assert check_i18n.api_error_codes() == {"not_found"}


def test_api_error_codes_ignores_a_table_with_no_code_column(project):
    """A table without a `code` header contributes nothing, even if a cell looks code-shaped."""
    project("design/API.md", "| field | note |\n| --- | --- |\n| amount | `not_found` |\n")

    assert check_i18n.api_error_codes() == set()


# --- plural_family_problems ---


def test_plural_family_problems_flags_a_missing_required_category(project):
    """Cs needs '.few' for an integer count; a catalog missing it is flagged by name."""
    en_keys = {"item.count.one", "item.count.other"}
    catalogs = {"en": en_keys, "cs": {"item.count.other"}}

    problems = check_i18n.plural_family_problems(catalogs, en_keys)

    assert any("item.count" in p and "few" in p for p in problems)


def test_plural_family_problems_does_not_flag_a_legitimate_plural_category_as_extra(project):
    """Cs's '.few' key is a real CLDR category, not a key en.js lacks."""
    en_keys = {"item.count.one", "item.count.other"}
    catalogs = {
        "en": en_keys,
        "cs": {"item.count.one", "item.count.few", "item.count.other"},
    }

    problems = check_i18n.plural_family_problems(catalogs, en_keys)

    assert not any("keys en.js does not" in p for p in problems)


# --- main ---


def test_main_passes_a_consistent_tree(baseline, capsys):
    """A catalog/JS/API.md tree with matching keys, langs and usage passes with exit code 0."""
    assert check_i18n.main() == 0
    assert "i18n check passed" in capsys.readouterr().out


def test_main_fails_with_no_en_catalog(project, capsys):
    """A tree with no en.js is refused outright, before any other check runs."""
    project("static/js/i18n/cs.js", CS_JS)

    assert check_i18n.main() == 1
    assert "no static/js/i18n/en.js catalog found" in capsys.readouterr().out


def test_main_flags_a_catalog_not_registered_in_langs(baseline, project, capsys):
    """A catalog file with no LANGS entry is unreachable, dead code."""
    project("static/js/i18n/index.js", "export const LANGS = {\n  en: 'English',\n};\n")

    assert check_i18n.main() == 1
    assert "catalog file(s) not in i18n/index.js's LANGS: ['cs']" in capsys.readouterr().out


def test_main_flags_a_dangling_langs_entry(baseline, project, capsys):
    """A LANGS entry with no matching catalog file names the phantom language."""
    project(
        "static/js/i18n/index.js",
        "export const LANGS = {\n  en: 'English',\n  cs: 'Čeština',\n  de: 'Deutsch',\n};\n",
    )

    assert check_i18n.main() == 1
    assert "LANGS entry with no static/js/i18n/<lang>.js file: ['de']" in capsys.readouterr().out


def test_main_flags_a_catalog_missing_a_key_en_js_has(baseline, project, capsys):
    """A non-en catalog missing one of en.js's keys is named, key and all."""
    project("static/js/i18n/cs.js", CS_JS.replace("  'item.count.other': '{n} položek',\n", ""))

    assert check_i18n.main() == 1
    assert "cs.js is missing keys en.js has: ['item.count.other']" in capsys.readouterr().out


def test_main_flags_a_literal_call_key_missing_from_en_js(baseline, project, capsys):
    """t('missing.key') with no catalog entry is reported by the exact key used."""
    project("static/js/app.js", APP_JS + "t('missing.key');\n")

    assert check_i18n.main() == 1
    out = capsys.readouterr().out
    assert "t('missing.key') used in static/js/ but missing from en.js" in out


def test_main_flags_an_en_js_key_never_used(baseline, project, capsys):
    """An en.js key with no literal call, plural reference or dynamic prefix is dead."""
    project(
        "static/js/i18n/en.js",
        EN_JS.replace("'app.title': 'Trip',", "'app.title': 'Trip',\n  'app.unused': 'X',"),
    )
    project(
        "static/js/i18n/cs.js",
        CS_JS.replace("'app.title': 'Výlet',", "'app.title': 'Výlet',\n  'app.unused': 'X',"),
    )

    assert check_i18n.main() == 1
    assert "en.js key 'app.unused' is never used in static/js/" in capsys.readouterr().out


def test_main_flags_error_code_catalog_mismatch(baseline, project, capsys):
    """API.md and the err.* keys disagreeing is reported both ways: missing and extra."""
    project("design/API.md", "| field | code |\n| --- | --- |\n| amount | `other_code` |\n")

    assert check_i18n.main() == 1
    out = capsys.readouterr().out
    assert "API.md has error codes with no err.* catalog key: ['err.other_code']" in out
    assert "catalog has err.* keys for codes API.md does not define: ['err.not_found']" in out
