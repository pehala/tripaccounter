// One Intl.*Format instance per locale (perf: design/FRONTEND.md §4 rule 6).
// Day/month formatted separately and joined "day month" ourselves — Intl's
// combined order is locale-dependent (US puts month first); this app is always day-first.
const dayFmts = {};
function dayFmt(locale) {
  return dayFmts[locale] ??= new Intl.DateTimeFormat(locale, { day: 'numeric' });
}
const monthFmts = {};
function monthFmt(locale) {
  return monthFmts[locale] ??= new Intl.DateTimeFormat(locale, { month: 'short' });
}

const numberFmts = {};
function numberFmt(locale) {
  return numberFmts[locale] ??= new Intl.NumberFormat(locale, { maximumFractionDigits: 2 });
}

// Grouping, separators and 0-2 fraction digits. Nothing else — never called on
// a value the client itself computed except the stats rate product (rule 1).
export function money(value, locale) {
  return numberFmt(locale).format(value);
}

export function signed(value, locale) {
  return value > 0 ? `+${money(value, locale)}` : money(value, locale);
}

// Canonical grammar the API accepts: "-?[0-9]+(.[0-9]{1,4})?". Turns whatever the
// user typed in the current locale into that shape, or null if it cannot.
export function parse(text, locale) {
  if (text === null || text === undefined) return null;
  const trimmed = String(text).trim();
  if (!trimmed) return null;
  const decimalSep = new Intl.NumberFormat(locale).format(1.1)[1];
  // Any run of whitespace (plain, non-breaking, narrow non-breaking) is a grouping separator.
  let cleaned = trimmed.replace(/\s+/gu, '');
  if (decimalSep === '.') cleaned = cleaned.replace(/,/g, '');
  else cleaned = cleaned.split(decimalSep).join('.');
  if (!/^-?[0-9]+(\.[0-9]+)?$/.test(cleaned)) return null;
  return cleaned;
}

export function date(iso, locale) {
  const d = new Date(iso);
  return `${dayFmt(locale).format(d)} ${monthFmt(locale).format(d)}`;
}

const timeFmts = {};
function timeFmt(locale) {
  return timeFmts[locale] ??= new Intl.DateTimeFormat(locale, { hour: 'numeric', minute: '2-digit' });
}

export function dateTime(iso, locale) {
  const d = new Date(iso);
  return `${date(iso, locale)}, ${timeFmt(locale).format(d)}`;
}

// UTC instant -> the viewer's local wall-clock value a <input type="datetime-local">
// wants ("YYYY-MM-DDTHH:mm"). The inverse of fromInputValue. Rule 8: a component
// never parses or formats a date by hand.
export function toInputValue(iso) {
  if (!iso) return '';
  const d = new Date(iso);
  const pad = (n) => String(n).padStart(2, '0');
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

// The reverse: a datetime-local value has no offset, so the Date constructor
// reads it as the browser's own local time — exactly what the picker showed.
export function fromInputValue(value) {
  if (!value) return null;
  const d = new Date(value);
  return Number.isNaN(d.getTime()) ? null : d.toISOString();
}

// error.params values are plain numbers/strings; the numbers still go through
// the locale formatter before they reach a translated sentence (rule 4).
export function fmtParams(params, locale) {
  const out = {};
  for (const [key, value] of Object.entries(params || {})) {
    out[key] = typeof value === 'number' ? money(value, locale) : value;
  }
  return out;
}

// "12–21 Sep" for one month, "28 Sep – 3 Oct" across months.
export function dateRange(startIso, endIso, locale) {
  if (!startIso) return '';
  if (!endIso || endIso === startIso) return date(startIso, locale);
  const start = new Date(startIso);
  const end = new Date(endIso);
  if (start.getMonth() === end.getMonth() && start.getFullYear() === end.getFullYear()) {
    return `${dayFmt(locale).format(start)}–${date(endIso, locale)}`;
  }
  return `${date(startIso, locale)} – ${date(endIso, locale)}`;
}
