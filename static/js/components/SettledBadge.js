import { html } from '../h.js';
import { t } from '../i18n/index.js';
import { dateWithYear } from '../fmt.js';

export function SettledBadge({ settlement, locale }) {
  if (!settlement) return null;
  return html`
    <span class="badge text-bg-success settled-badge">
      <i class="bi bi-lock-fill"></i> ${t('settlement.settled_on', { date: dateWithYear(settlement.settled_at, locale) })}
    </span>
  `;
}
