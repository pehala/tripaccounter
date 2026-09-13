// User-typed exchange rates for the statistics Total section — never sent to
// the server, never stored with the trip (design/FRONTEND.md §4 rule 1).
// One object per trip: { target: currencyId|null, values: { [currencyId]: string } }.
// `target` is which currency everything converts into (defaults to the trip's
// primary when null); `values` are raw typed strings, relative to `target`, so
// an input can hold "" or a partial "1." while typing. Switching `target`
// clears `values` — a rate typed against one target means something different
// against another, so stale values would silently lie.
function key(slug) {
  return `rates:${slug}`;
}

function save(slug, state) {
  localStorage.setItem(key(slug), JSON.stringify(state));
  return state;
}

export function getRatesState(slug) {
  try {
    const parsed = JSON.parse(localStorage.getItem(key(slug)));
    return { target: parsed?.target ?? null, values: parsed?.values ?? {} };
  } catch {
    return { target: null, values: {} };
  }
}

export function setTargetCurrency(slug, targetId) {
  return save(slug, { target: targetId, values: {} });
}

export function setRateValue(slug, currencyId, value) {
  const state = getRatesState(slug);
  const values = { ...state.values };
  if (value) values[currencyId] = value;
  else delete values[currencyId];
  return save(slug, { ...state, values });
}
