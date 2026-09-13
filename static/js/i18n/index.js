import en from './en.js';
import cs from './cs.js';

export const LANGS = { en: 'English', cs: 'Čeština' };
const CATALOGS = { en, cs };

const listeners = new Set();
export function onLocaleChange(fn) { listeners.add(fn); return () => listeners.delete(fn); }

function detect() {
  const stored = localStorage.getItem('lang');
  if (stored in CATALOGS) return stored;
  for (const lang of navigator.languages || []) {
    const prefix = lang.slice(0, 2);
    if (prefix in CATALOGS) return prefix;
  }
  return 'en';
}

let locale = detect();
document.documentElement.lang = locale;

export function getLocale() { return locale; }

export function setLocale(next) {
  if (!(next in CATALOGS)) return;
  locale = next;
  localStorage.setItem('lang', next);
  document.documentElement.lang = next;
  listeners.forEach((fn) => fn());
}

function interpolate(str, params) {
  return str.replace(/\{(\w+)\}/g, (_, name) => (name in params ? params[name] : `{${name}}`));
}

function lookup(cat, key) {
  const debug = location.search.includes('debug');
  if (key in cat) return cat[key];
  if (cat !== en && key in en) return en[key];
  return debug ? key : (en[key] ?? key);
}

const pluralRules = {};
function ruleFor(loc) {
  return pluralRules[loc] ??= new Intl.PluralRules(loc);
}

export function t(key, params = {}) {
  const cat = CATALOGS[locale];
  const pluralKey = `${key}.${params.n !== undefined ? ruleFor(locale).select(params.n) : ''}`;
  const known = key in cat || key in en || (params.n !== undefined && (pluralKey in cat || pluralKey in en));
  // A code the catalog does not know (a backend addition the frontend hasn't
  // caught up on yet — see design/FRONTEND.md §4 rule 4, design/API.md §4): render the
  // code and its params instead of the bare, unreadable dotted key. Every code
  // API.md actually defines has a real catalog entry (test_i18n.py), so this
  // path is a forward-compatibility net, not the common case.
  if (!known && key.startsWith('err.')) {
    const code = key.slice('err.'.length);
    const rendered = Object.entries(params).map(([name, value]) => `${name} ${value}`).join(', ');
    return rendered ? `${code} · ${rendered}` : code;
  }
  const resolved = params.n !== undefined && (pluralKey in cat || pluralKey in en)
    ? lookup(cat, pluralKey)
    : lookup(cat, key);
  return interpolate(resolved, params);
}
