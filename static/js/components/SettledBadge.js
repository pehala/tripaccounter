import { html } from '../h.js';
import { t } from '../i18n/index.js';
import { dateWithYear } from '../fmt.js';

// "Settled on 14 Sep 2026", wherever a settled trip's lock shows: the Total,
// each currency's balance block, the setup trip card.
export function SettledBadge({ settlement, locale }) {
  if (!settlement) return null;
  return html`
    <span class="badge text-bg-success settled-badge">
      <i class="bi bi-lock-fill"></i> ${t('settlement.settled_on', { date: dateWithYear(settlement.settled_at, locale) })}
    </span>
  `;
}
