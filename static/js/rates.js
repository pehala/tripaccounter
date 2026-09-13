// User-typed exchange rates for the statistics combined view — never sent to
// the server, never stored with the trip (design/FRONTEND.md §4 rule 1).
// One object per trip, keyed by currency_id, values are raw typed strings so
// the input can hold "" or a partial "1." while typing.
function key(slug) {
  return `rates:${slug}`;
}

export function getRates(slug) {
  try {
    return JSON.parse(localStorage.getItem(key(slug))) || {};
  } catch {
    return {};
  }
}

export function setRate(slug, currencyId, value) {
  const rates = getRates(slug);
  if (value) rates[currencyId] = value;
  else delete rates[currencyId];
  localStorage.setItem(key(slug), JSON.stringify(rates));
  return rates;
}
