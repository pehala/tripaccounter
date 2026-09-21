// Shared money-combination math for a page's Total switch (statistics and
// balances both have one) — see design/FRONTEND.md §4 rule 1's exception.
// `rates.js` only persists the typed target/values; this is the arithmetic
// that turns them into a converted, combined figure.
import { parse } from './fmt.js';

// Rate a currency converts at, into whichever currency the Total is set to
// (`targetId` — any trip currency, not necessarily the primary): the target
// itself is always 1, any other currency needs a positive typed rate or the
// Total refuses to compute anything — the one place the frontend adds two
// amounts, and only once every operand is known.
export function rateFor(currencyId, targetId, values, locale) {
  if (currencyId === targetId) return 1;
  const raw = parse(values[currencyId], locale);
  const value = raw === null ? null : Number(raw);
  return value && value > 0 ? value : null;
}

export function convert(amount, rate) {
  return Math.round(amount * rate * 100) / 100;
}

// Only ever called once every currency has a confirmed rate; `rate === null`
// here would mean an incomplete total, which the caller never allows to
// render. `valueKey` is which field of each row to convert — stats' rows are
// `{..., amount}`, balances' people rows are `{..., net}`.
export function combineGroup(blocks, groupKey, rowKey, targetId, values, locale, valueKey = 'amount') {
  const totals = new Map();
  for (const block of blocks) {
    const rate = rateFor(block.currency_id, targetId, values, locale);
    if (rate === null) continue;
    for (const row of block[groupKey]) {
      const key = row[rowKey];
      totals.set(key, (totals.get(key) ?? 0) + convert(row[valueKey], rate));
    }
  }
  return totals;
}

// The statistics Total's version of the above: one grouping's rows arrive
// already grouped per currency, so combining them means dropping `currency_id`
// from the key and summing the converted amounts of everything that remains
// identical. Same exception, same all-or-nothing gate as `combineGroup`.
export function combineRows(rows, targetId, values, locale) {
  const totals = new Map();
  for (const row of rows) {
    const rate = rateFor(row.keys.currency_id, targetId, values, locale);
    if (rate === null) continue;
    const { currency_id, ...keys } = row.keys;
    const id = JSON.stringify(keys);
    const previous = totals.get(id);
    totals.set(id, {
      keys,
      amount: (previous?.amount ?? 0) + convert(row.amount, rate),
      item_count: (previous?.item_count ?? 0) + row.item_count,
    });
  }
  return [...totals.values()];
}

// Combines each currency's already-computed settle-up suggestions into one
// converted list — never a fresh minimum-transfer plan (that's `settle.py`'s
// job, not the client's). The same two people can owe each other in opposite
// directions across different currencies, so pairs are netted: converted
// amounts are summed signed, per unordered person pair, and a pair whose
// currencies cancel out simply drops from the result.
export function combineSuggestions(blocks, targetId, values, locale) {
  const totals = new Map();
  for (const block of blocks) {
    const rate = rateFor(block.currency_id, targetId, values, locale);
    if (rate === null) continue;
    for (const s of block.suggestions) {
      const amount = convert(s.amount, rate);
      const lo = Math.min(s.from_person_id, s.to_person_id);
      const hi = Math.max(s.from_person_id, s.to_person_id);
      const sign = s.from_person_id < s.to_person_id ? 1 : -1;
      const key = `${lo}:${hi}`;
      totals.set(key, (totals.get(key) ?? 0) + sign * amount);
    }
  }

  const result = [];
  for (const [key, signed] of totals) {
    const [lo, hi] = key.split(':').map(Number);
    const amount = Math.round(Math.abs(signed) * 100) / 100;
    if (amount === 0) continue;
    result.push(signed > 0 ? { from_person_id: lo, to_person_id: hi, amount } : { from_person_id: hi, to_person_id: lo, amount });
  }
  return result;
}
