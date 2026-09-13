import { t } from '../i18n/index.js';

// mode + weights -> "equally, 4 ways" / "equally, 3 of 4" / "shares 1·1·1·0.5" / "exact amounts".
// UI wording lives here, not in the API — split.mode and split.shares are the only inputs.
export function splitSummary(split) {
  const total = split.shares.length;
  const active = split.shares.filter((s) => s.weight !== null);
  const n = active.length;

  if (split.mode === 'exact') return t('split.exact');
  if (split.mode === 'shares') return t('split.weights', { weights: active.map((s) => s.weight).join('·') });
  return n === total ? t('split.equal', { n }) : t('split.equal_partial', { n, total });
}
