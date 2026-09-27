// What the statistics page is showing — local only, one setting per trip: the
// dimension chain it groups by, which currency's section is on screen, and
// whether that section is a list or a chart.
// `currency` is never in the chain (the server groups by it whatever is asked
// for, design/STATS.md §3), and the shown currency never reaches the server at
// all: every grouping carries every currency, so picking one is a filter.
const DEFAULT = ['day'];

function key(slug) {
  return `breakdown:${slug}`;
}

export function getDims(slug) {
  try {
    const parsed = JSON.parse(localStorage.getItem(key(slug)));
    return Array.isArray(parsed) ? parsed : DEFAULT;
  } catch {
    return DEFAULT;
  }
}

export function setDims(slug, dims) {
  localStorage.setItem(key(slug), JSON.stringify(dims));
  return dims;
}

function currencyKey(slug) {
  return `stats-currency:${slug}`;
}

// `'total'` or a currency id; null when nothing has been picked yet, which
// leaves the caller to fall back on the trip's primary currency.
export function getShownCurrency(slug) {
  const raw = localStorage.getItem(currencyKey(slug));
  if (raw === null) return null;
  return raw === 'total' ? 'total' : Number(raw);
}

export function setShownCurrency(slug, shown) {
  localStorage.setItem(currencyKey(slug), String(shown));
  return shown;
}

function viewKey(slug) {
  return `stats-view:${slug}`;
}

// `'list'` or `'chart'` — how a section renders the rows it already has.
export function getView(slug) {
  return localStorage.getItem(viewKey(slug)) === 'chart' ? 'chart' : 'list';
}

export function setView(slug, view) {
  localStorage.setItem(viewKey(slug), view);
  return view;
}
