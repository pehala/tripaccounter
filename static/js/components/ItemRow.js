import { html } from '../h.js';
import { t } from '../i18n/index.js';
import { money, wallTime } from '../fmt.js';
import { Avatar } from './Avatar.js';
import { EditButton } from './EditButton.js';
import { LabelBadge } from './LabelBadge.js';

export function ItemRow({ item, trip, locale, onSelect }) {
  const payer = trip.people.find((p) => p.id === item.payer_id);
  const country = trip.countries.find((c) => c.id === item.country_id);
  const wallet = (trip.wallets || []).find((w) => w.id === item.wallet_id);
  const stay = (trip.stays || []).find((candidate) => candidate.id === item.stay_id);
  const walletIsPayerDefault = wallet && payer && wallet.person_id === payer.id && wallet.is_default;
  const time = wallTime(item.occurred_at);
  const hasMap = Boolean(item.map_url || (item.lat && item.lon));
  const mapHref = item.map_url
    || `https://www.google.com/maps/search/?api=1&query=${item.lat},${item.lon}`;

  return html`
    <div class="list-group-item item-row d-flex gap-3 py-2 px-3">
      <span class="flex-grow-1 min-w-0">
        <span class="d-block fw-semibold lh-sm">${item.name}</span>
        <small class="text-body-secondary d-block lh-sm">${country ? `${country.flag} ${country.name} · ` : ''}${item.city ? `${item.city} · ` : ''}${time} · <${Avatar} person=${payer} /> ${t('items.paid_by', { name: payer?.name || '' })}${wallet && !walletIsPayerDefault ? ` · ${wallet.name}` : ''}${stay ? html` · <a class="item-stay" href="/t/${trip.slug}/stays#stay-${stay.id}"><i class="bi bi-house-door"></i> ${stay.name}</a>` : ''}${hasMap ? html` · <a href=${mapHref} target="_blank" rel="noopener noreferrer"><i class="bi bi-geo-alt-fill"></i> ${t('items.map')}</a>` : ''}${item.labels.length > 0 ? html` · ${item.labels.map((name) => html`<${LabelBadge} key=${name} name=${name} />`)}` : ''}</small>
        <small class="owed num d-block lh-base">
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
      <span class="d-flex flex-column align-items-end gap-1">
        <span class="text-end num text-nowrap fw-semibold">${money(item.amount, locale)} ${item.currency_code}</span>
        <${EditButton} onClick=${() => onSelect?.(item)} />
      </span>
    </div>
  `;
}
