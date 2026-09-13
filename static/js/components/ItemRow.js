import { html } from '../h.js';
import { t } from '../i18n/index.js';
import { money } from '../fmt.js';
import { Avatar } from './Avatar.js';
import { LabelBadge } from './LabelBadge.js';
import { splitSummary } from './splitSummary.js';

export function ItemRow({ item, trip, locale, onSelect }) {
  const payer = trip.people.find((p) => p.id === item.payer_id);
  const country = trip.countries.find((c) => c.id === item.country_id);
  const time = item.occurred_at.slice(11, 16);
  const hasMap = Boolean(item.map_url || (item.lat && item.lon));
  const mapLabel = item.map_url ? t('items.map') : `${item.lat}, ${item.lon}`;

  return html`
    <a href="#" class="list-group-item list-group-item-action d-flex gap-3"
       onClick=${(e) => { e.preventDefault(); onSelect?.(item); }}>
      <span class="flex-grow-1 min-w-0">
        <span class="d-block fw-semibold">${item.name}</span>
        <small class="text-body-secondary d-block">${country ? `${country.flag} ${country.name} · ` : ''}${time} · <${Avatar} person=${payer} /> ${t('items.paid_by', { name: payer?.name || '' })}${hasMap ? html` · <i class="bi bi-geo-alt-fill text-primary"></i> ${mapLabel}` : ''}</small>
        <small class="owed num d-block mt-1">
          ${trip.people.map((person) => {
            const share = item.split.shares.find((s) => s.person_id === person.id);
            const owed = share?.owed;
            return html`
              <span key=${person.id} class=${owed === null || owed === undefined ? 'opacity-50' : ''}>
                <${Avatar} person=${person} />${owed === null || owed === undefined ? '—' : money(owed, locale)}
              </span>
            `;
          })}
        </small>
        ${item.labels.length > 0 && html`
          <span class="mt-1 d-block">
            ${item.labels.map((name) => html`<${LabelBadge} key=${name} name=${name} />`)}
          </span>
        `}
        <small class="text-body-secondary d-block mt-1">${splitSummary(item.split)}</small>
      </span>
      <span class="text-end num text-nowrap fw-semibold">${money(item.amount, locale)} ${item.currency_code}</span>
    </a>
  `;
}
