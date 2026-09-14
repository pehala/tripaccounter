// User-typed exchange rates for the stats Total section — local only, never
// sent to the server or stored with the trip (design/FRONTEND.md §4 rule 1).
// { target: currencyId|null, values: { [currencyId]: rawString } }; switching
// target clears values, since a rate typed against one target lies against another.
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
