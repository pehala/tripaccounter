import { useState } from 'preact/hooks';
import { getLocale } from './i18n/index.js';
import { parse } from './fmt.js';
import { rateFor } from './convert.js';

// The Total's target currency and rates, one set per trip, shared by the
// balances and statistics pages (design/FRONTEND.md §4 rule 1).
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

// The server's rate grammar: ≤ 9 integer digits, ≤ 9 fraction digits.
const RATE_RE = /^[0-9]{1,9}(\.[0-9]{1,9})?$/;

// A settled trip's stored rates, else this browser's typed ones. `ready` matches
// the server's `missing_rate` rule, `settleable` its `invalid_rate` rule too.
export function useTotalRates(store) {
  const [local, setLocal] = useState(() => getRatesState(store.slug));
  const trip = store.trip;
  const locale = getLocale();
  const settlement = trip.settlement ?? null;

  const primary = trip.currencies.find((c) => c.is_primary) || trip.currencies[0];
  const targetId = settlement ? settlement.target_currency_id : local.target;
  const target = trip.currencies.find((c) => c.id === targetId) || primary;
  const values = settlement
    ? Object.fromEntries(settlement.rates.map((row) => [row.currency_id, row.rate]))
    : local.values;
  const ready = trip.currencies.every((c) => rateFor(c.id, target.id, values, locale) !== null);
  const settleable = ready && trip.currencies.every(
    (c) => c.id === target.id || RATE_RE.test(parse(values[c.id], locale) ?? ''));

  return {
    target,
    values,
    ready,
    settleable,
    settlement,
    onTargetChange(currencyId) {
      if (!settlement) setLocal(setTargetCurrency(store.slug, currencyId));
    },
    onRateChange(currencyId, value) {
      if (!settlement) setLocal(setRateValue(store.slug, currencyId, value));
    },
    settlementBody() {
      return {
        target_currency_id: target.id,
        rates: trip.currencies
          .filter((c) => c.id !== target.id)
          .map((c) => ({ currency_id: c.id, rate: parse(values[c.id], locale) })),
      };
    },
  };
}
