// What the statistics page is showing — local only, one setting per trip: the
// dimension chain it groups by, which currency's section is on screen, whether
// that section is a list or a chart, and the date range it covers.
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

function rangeKey(slug) {
  return `stats-range:${slug}`;
}

// `{from, to}`, each an ISO date or null; inclusive at both ends.
export function getRange(slug) {
  try {
    const parsed = JSON.parse(localStorage.getItem(rangeKey(slug)));
    return { from: parsed?.from ?? null, to: parsed?.to ?? null };
  } catch {
    return { from: null, to: null };
  }
}

export function setRange(slug, range) {
  localStorage.setItem(rangeKey(slug), JSON.stringify(range));
  return range;
}

export function isDated(range) {
  return Boolean(range.from || range.to);
}

// The chains to ask the server for, in one request: every level of the picked chain
// also grouped by day, so a date range is a filter over rows already held — the page
// keeps the days inside it and sums each level over them alone, never over an
// overlapping dimension. The picked chain itself comes back as their prefixes.
export function requestChains(dims) {
  const chains = prefixes(dims).map((prefix) => (prefix.includes('day') ? prefix : [...prefix, 'day']));
  return [...new Map(chains.map((chain) => [chain.join(','), chain])).values()];
}

// Every level of a chain, from the bare currency level (`[]`) down to the chain
// itself: what the server answers for it, and what the page nests.
export function prefixes(dims) {
  return [...Array(dims.length + 1).keys()].map((depth) => dims.slice(0, depth));
}

// Rows whose re-keyed `keys` agree merge into one, amounts and item counts summed;
// a merged row sits where the first of its rows did.
export function mergeRows(rows, rekey) {
  const merged = new Map();
  for (const row of rows) {
    const keys = rekey(row.keys);
    const id = JSON.stringify(keys);
    const previous = merged.get(id);
    merged.set(id, {
      keys,
      amount: (previous?.amount ?? 0) + row.amount,
      item_count: (previous?.item_count ?? 0) + row.item_count,
    });
  }
  return [...merged.values()];
}
