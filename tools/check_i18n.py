"""Static i18n validator — no Node, no browser (design/FRONTEND.md §4 rule 7).

Checks, purely against the source text:
1. every catalog under static/js/i18n/ has exactly the key set of en.js
2. every catalog file is registered in i18n/index.js's LANGS, and vice versa —
   a catalog with perfect keys but no LANGS entry is unreachable, dead code
3. every literal t('key') call under static/js/ resolves to a catalog key
4. every en.js key is used somewhere: a literal call, a plural family (t()
   called with {n} picks '<key>.<CLDR category>'), or a dynamic prefix —
   `t('prefix.' + expr)` or `` t(`prefix.${expr}`) `` — whose prefix the key
   starts with (err.<code>, lang.<xx>, split.mode.<mode>, ...)
5. every {code} in API.md's error tables has a matching err.<code> key

Run directly (`python -m tools.check_i18n`) or via `make lint`.
"""

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
I18N_DIR = ROOT / "static" / "js" / "i18n"
JS_ROOT = ROOT / "static" / "js"
API_MD = ROOT / "design" / "API.md"

KEY_VALUE_RE = re.compile(r"'([a-zA-Z0-9_.]+)'\s*:\s*(?:'(?:[^'\\]|\\.)*'|\"(?:[^\"\\]|\\.)*\")")
# The quote must end the argument (','/')' next) — 'err.' + expr is a
# concatenation, not a literal key, and must NOT match here.
LITERAL_CALL_RE = re.compile(r"\bt\(\s*'([a-zA-Z0-9_.]+)'\s*(?=[,)])")
# t('prefix.' + expr) and t(`prefix.${expr}`) — a key built at runtime, never
# a literal string a static scan can match in full.
DYNAMIC_CONCAT_RE = re.compile(r"\bt\(\s*'([a-zA-Z0-9_.]+\.)'\s*\+")
DYNAMIC_TEMPLATE_RE = re.compile(r"\bt\(\s*`([a-zA-Z0-9_.]+\.)\$\{")
# A dotted identifier quoted anywhere outside a t() call — e.g. an array of
# [key, i18n-key] pairs indirected through a loop variable before it reaches
# t(). Weaker signal than a literal call, used only to avoid false "unused"
# flags on keys referenced by name rather than passed to t() directly.
QUOTED_DOTTED_RE = re.compile(r"'([a-zA-Z0-9_]+(?:\.[a-zA-Z0-9_]+)+)'")
PLURAL_CATEGORIES = ("zero", "one", "two", "few", "many", "other")
# CLDR cardinal-plural categories each locale actually needs — restricted to the
# ones reachable for an integer `n` (the only kind of count this app ever passes
# to t()), so e.g. cs.'many' (fractional numbers only) is deliberately excluded.
# A key(`t`) family always carries '.other'; a locale missing a required category
# silently falls back to the raw key (see i18n/index.js's t()) — that's the bug
# this table exists to catch. Unlisted locales default to ('one', 'other').
INTEGER_PLURAL_CATEGORIES = {
    "en": ("one", "other"),
    "cs": ("one", "few", "other"),
}


LANGS_ENTRY_RE = re.compile(r"([a-zA-Z0-9_-]+)\s*:\s*(?:'(?:[^'\\]|\\.)*'|\"(?:[^\"\\]|\\.)*\")")


def catalog_keys(path: Path) -> set[str]:
    """Return every key defined in one i18n catalog file."""
    return set(KEY_VALUE_RE.findall(path.read_text()))


def registered_langs() -> set[str]:
    """Return every language code registered in i18n/index.js's LANGS."""
    text = (I18N_DIR / "index.js").read_text()
    m = re.search(r"LANGS\s*=\s*\{(.*?)\}", text, re.DOTALL)
    if not m:
        return set()
    return set(LANGS_ENTRY_RE.findall(m.group(1)))


def literal_call_keys() -> set[str]:
    """Return every key passed to t() as a literal string across static/js/."""
    keys = set()
    for path in JS_ROOT.rglob("*.js"):
        if path.parent == I18N_DIR:
            continue
        keys |= set(LITERAL_CALL_RE.findall(path.read_text()))
    return keys


def quoted_dotted_keys() -> set[str]:
    """Return every dotted key quoted anywhere in static/js/, not just inside t() calls."""
    keys = set()
    for path in JS_ROOT.rglob("*.js"):
        if path.parent == I18N_DIR:
            continue
        keys |= set(QUOTED_DOTTED_RE.findall(path.read_text()))
    return keys


def dynamic_prefixes() -> set[str]:
    """Return every key prefix built at runtime via concatenation or a template literal."""
    prefixes = set()
    for path in JS_ROOT.rglob("*.js"):
        if path.parent == I18N_DIR:
            continue
        text = path.read_text()
        prefixes |= set(DYNAMIC_CONCAT_RE.findall(text))
        prefixes |= set(DYNAMIC_TEMPLATE_RE.findall(text))
    return prefixes


def api_error_codes() -> set[str]:
    """Every backticked code in a markdown table column literally named `code`."""
    lines = API_MD.read_text().splitlines()
    codes: set[str] = set()
    i = 0
    while i < len(lines):
        line = lines[i]
        if line.strip().startswith("|") and "code" in line:
            header = [c.strip().strip("`") for c in line.strip().strip("|").split("|")]
            if "code" in header:
                col = header.index("code")
                j = i + 2  # skip the header separator row
                while j < len(lines) and lines[j].strip().startswith("|"):
                    cells = [c.strip() for c in lines[j].strip().strip("|").split("|")]
                    if col < len(cells):
                        codes |= set(re.findall(r"`([a-z][a-z_]*)`", cells[col]))
                    j += 1
        i += 1
    return codes


def plural_family_problems(catalogs: dict[str, set[str]], en_keys: set[str]) -> list[str]:
    """Find plural-coverage gaps en.js's key set alone won't show.

    Catches two ways a locale can be missing plural coverage: a locale needing a CLDR
    category (e.g. cs's '.few') that isn't defined — t() then falls back to the raw key
    for that count — and that same category being mistaken for an "extra" key.
    """
    problems: list[str] = []
    # A '.other' key is CLDR's mandatory catch-all — every plural family has one,
    # so this reliably finds every family's base regardless of which optional
    # categories (.one, .few, ...) it also defines.
    plural_bases = {key[: -len(".other")] for key in en_keys if key.endswith(".other")}

    def is_locale_plural_category(key: str) -> bool:
        base, _, category = key.rpartition(".")
        return base in plural_bases and category in PLURAL_CATEGORIES

    for lang, keys in catalogs.items():
        extra = {k for k in keys - en_keys if not is_locale_plural_category(k)}
        if extra:
            problems.append(f"{lang}.js has keys en.js does not: {sorted(extra)}")

        required = INTEGER_PLURAL_CATEGORIES.get(lang, ("one", "other"))
        for base in sorted(plural_bases):
            missing_categories = [cat for cat in required if f"{base}.{cat}" not in keys]
            if missing_categories:
                plural = "y" if len(missing_categories) == 1 else "ies"
                problems.append(
                    f"{lang}.js is missing plural categor{plural} for '{base}': "
                    f"{missing_categories} — t() falls back to the raw key for that count"
                )
    return problems


def main() -> int:  # noqa: PLR0912
    """Run every catalog/usage/error-code check and print the combined result."""
    problems: list[str] = []

    catalogs = {p.stem: catalog_keys(p) for p in sorted(I18N_DIR.glob("*.js")) if p.stem != "index"}
    if "en" not in catalogs:
        problems.append("no static/js/i18n/en.js catalog found")
        print("\n".join(problems))
        return 1
    en_keys = catalogs["en"]

    langs = registered_langs()
    unregistered = catalogs.keys() - langs
    dangling = langs - catalogs.keys()
    if unregistered:
        problems.append(f"catalog file(s) not in i18n/index.js's LANGS: {sorted(unregistered)}")
    if dangling:
        problems.append(f"LANGS entry with no static/js/i18n/<lang>.js file: {sorted(dangling)}")

    for lang, keys in catalogs.items():
        if lang == "en":
            continue
        missing = en_keys - keys
        if missing:
            problems.append(f"{lang}.js is missing keys en.js has: {sorted(missing)}")
    problems.extend(plural_family_problems(catalogs, en_keys))

    dynamic = dynamic_prefixes()

    def is_dynamic(key: str) -> bool:
        return any(key.startswith(prefix) for prefix in dynamic)

    used = literal_call_keys()
    for key in sorted(used):
        if key in en_keys:
            continue
        if f"{key}.other" in en_keys:  # a plural family, referenced by its base
            continue
        problems.append(f"t('{key}') used in static/js/ but missing from en.js")

    codes = api_error_codes()
    expected_err_keys = {f"err.{code}" for code in codes}
    actual_err_keys = {k for k in en_keys if k.startswith("err.")}
    missing_err = expected_err_keys - actual_err_keys
    extra_err = actual_err_keys - expected_err_keys
    if missing_err:
        problems.append(f"API.md has error codes with no err.* catalog key: {sorted(missing_err)}")
    if extra_err:
        problems.append(
            f"catalog has err.* keys for codes API.md does not define: {sorted(extra_err)}"
        )
    if "err." not in dynamic:
        problems.append("no `t('err.' + code)` call found — err.* keys would be unreachable")

    # Usage evidence for the "is this key ever reached" check is deliberately
    # looser than the strict literal-call check above: a key indirected
    # through a local constant (TABS.map(([k, labelKey]) => t(labelKey))) is a
    # real usage, just not one a regex can trace through a variable.
    referenced = used | quoted_dotted_keys()
    for key in sorted(en_keys):
        if key in referenced or is_dynamic(key):
            continue
        base = key.rsplit(".", 1)[0] if key.rsplit(".", 1)[-1] in PLURAL_CATEGORIES else None
        if base and (base in referenced or is_dynamic(base)):
            continue
        problems.append(f"en.js key '{key}' is never used in static/js/")

    if problems:
        print("i18n check failed:\n- " + "\n- ".join(problems))
        return 1

    print(
        f"i18n check passed: {len(en_keys)} keys, {len(catalogs)} catalogs, "
        f"{len(codes)} API error codes"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
