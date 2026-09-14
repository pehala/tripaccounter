import { html } from '../h.js';
import { t } from '../i18n/index.js';
import { money } from '../fmt.js';
import { Avatar } from './Avatar.js';
import { LabelBadge } from './LabelBadge.js';

export function ItemRow({ item, trip, locale, onSelect }) {
  const payer = trip.people.find((p) => p.id === item.payer_id);
  const country = trip.countries.find((c) => c.id === item.country_id);
  const wallet = (trip.wallets || []).find((w) => w.id === item.wallet_id);
  const walletIsPayerDefault = wallet && payer && wallet.person_id === payer.id && wallet.is_default;
  const time = item.occurred_at.slice(11, 16);
  const hasMap = Boolean(item.map_url || (item.lat && item.lon));
  const mapLabel = item.map_url ? t('items.map') : `${item.lat}, ${item.lon}`;

  return html`
    <a href="#" class="list-group-item list-group-item-action d-flex gap-3"
       onClick=${(e) => { e.preventDefault(); onSelect?.(item); }}>
      <span class="flex-grow-1 min-w-0">
        <span class="d-block fw-semibold item-line">${item.name}</span>
        <small class="text-body-secondary d-block item-line">${country ? `${country.flag} ${country.name} · ` : ''}${time} · <${Avatar} person=${payer} /> ${t('items.paid_by', { name: payer?.name || '' })}${wallet && !walletIsPayerDefault ? ` · ${wallet.name}` : ''}${hasMap ? html` · <i class="bi bi-geo-alt-fill text-primary"></i> ${mapLabel}` : ''}${item.labels.length > 0 ? html` · ${item.labels.map((name) => html`<${LabelBadge} key=${name} name=${name} />`)}` : ''}</small>
        <small class="owed num d-block item-line">
          ${trip.people.map((person) => {
            const share = item.split.shares.find((s) => s.person_id === person.id);
            if (share?.owed === null || share?.owed === undefined) return '';
            return html`
              <span key=${person.id}>
                <${Avatar} person=${person} />${money(share.owed, locale)} ${item.currency_code}
              </span>
            `;
          })}
        </small>
      </span>
      <span class="text-end num text-nowrap fw-semibold">${money(item.amount, locale)} ${item.currency_code}</span>
    </a>
  `;
}
