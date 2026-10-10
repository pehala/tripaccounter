// One Intl.*Format instance per locale (perf: design/FRONTEND.md §4 rule 6).
// Day/month formatted separately and joined "day month" ourselves — Intl's
// combined order is locale-dependent (US puts month first); this app is always day-first.
// A day is a bare YYYY-MM-DD with no zone: it is read as UTC midnight and formatted in
// UTC, so every viewer sees the same calendar day whatever their own zone is.
const dayFmts = {};
function dayFmt(locale) {
  return dayFmts[locale] ??= new Intl.DateTimeFormat(locale, { day: 'numeric', timeZone: 'UTC' });
}
const monthFmts = {};
function monthFmt(locale) {
  return monthFmts[locale] ??= new Intl.DateTimeFormat(locale, { month: 'short', timeZone: 'UTC' });
}
const weekdayFmts = {};
function weekdayFmt(locale) {
  return weekdayFmts[locale] ??= new Intl.DateTimeFormat(locale, { weekday: 'short', timeZone: 'UTC' });
}

const numberFmts = {};
function numberFmt(locale) {
  return numberFmts[locale] ??= new Intl.NumberFormat(locale, { maximumFractionDigits: 2 });
}

const rateFmts = {};
function rateFmt(locale) {
  return rateFmts[locale] ??= new Intl.NumberFormat(locale, { maximumSignificantDigits: 6, useGrouping: false });
}

// An exchange rate: six significant digits, no grouping, so parse() reads it back
// as the typed value it becomes in the Total's rate form.
export function rate(value, locale) {
  return rateFmt(locale).format(value);
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

export function date(day, locale) {
  const d = new Date(day);
  return `${dayFmt(locale).format(d)} ${monthFmt(locale).format(d)}`;
}

export function weekday(day, locale) {
  return weekdayFmt(locale).format(new Date(day));
}

// A real instant (the build time, a `Z` string), shown in the viewer's own zone. Rows
// never come through here: their times are wall times, read by wallClock below.
const localDayFmts = {};
const localMonthFmts = {};
const timeFmts = {};
export function dateTime(iso, locale) {
  const d = new Date(iso);
  const day = localDayFmts[locale] ??= new Intl.DateTimeFormat(locale, { day: 'numeric' });
  const month = localMonthFmts[locale] ??= new Intl.DateTimeFormat(locale, { month: 'short' });
  const time = timeFmts[locale] ??= new Intl.DateTimeFormat(locale, { hour: 'numeric', minute: '2-digit' });
  return `${day.format(d)} ${month.format(d)}, ${time.format(d)}`;
}

// A row's time is a wall time, "YYYY-MM-DDTHH:mm:ss", already in the trip's zone: the
// digits are read as they are, never through a Date (design/TIMEZONES.md §1).
export function wallTime(wall) {
  return wall.slice(11, 16);
}

export function wallClock(wall, locale) {
  return `${date(wall.slice(0, 10), locale)}, ${wallTime(wall)}`;
}

// The wall time a <input type="datetime-local"> wants ("YYYY-MM-DDTHH:mm") is the
// row's own string cut to the minute, and what the input holds goes back unchanged:
// the server resolves it in the trip's zone. Rule 8: a component never parses or
// formats a date by hand.
export function toInputValue(wall) {
  return wall ? wall.slice(0, 16) : '';
}

export function fromInputValue(value) {
  return value || null;
}

const nowFmts = {};
// The current instant as a wall time in `zone`, in the shape toInputValue returns.
export function nowIn(zone) {
  const fmt = nowFmts[zone] ??= new Intl.DateTimeFormat('en-CA', {
    timeZone: zone, hourCycle: 'h23',
    year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit',
  });
  const p = Object.fromEntries(fmt.formatToParts(new Date()).map(({ type, value }) => [type, value]));
  return `${p.year}-${p.month}-${p.day}T${p.hour}:${p.minute}`;
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
  if (start.getUTCMonth() === end.getUTCMonth() && start.getUTCFullYear() === end.getUTCFullYear()) {
    return `${dayFmt(locale).format(start)}–${date(endIso, locale)}`;
  }
  return `${date(startIso, locale)} – ${date(endIso, locale)}`;
}
