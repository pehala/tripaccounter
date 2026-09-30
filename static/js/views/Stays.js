import { useEffect, useState } from 'preact/hooks';
import { html } from '../h.js';
import { useStore, reload } from '../store.js';
import { t, getLocale } from '../i18n/index.js';
import { dateRange, money } from '../fmt.js';
import { stayMatches } from '../filter.js';
import { ItemRow } from '../components/ItemRow.js';
import { ItemModal } from '../components/ItemModal.js';
import { EditButton } from '../components/EditButton.js';
import { Loading } from '../components/Loading.js';
import { StayModal } from '../components/StayModal.js';

// Per-night figures come from the server, one per currency
// (design/FRONTEND.md §4 rule 1); nothing here divides or adds an amount.
function StayCard({ stay, trip, items, locale, onEdit, onSelectItem }) {
  const country = trip.countries.find((c) => c.id === stay.country_id);
  const where = country && `${country.flag ?? ''} ${country.name}`.trim();
  return html`
    <div id="stay-${stay.id}" class="card shadow-sm mb-3 stay-card">
      <div class="card-header d-flex align-items-center gap-2">
        <i class="bi bi-house-door"></i>
        <span class="flex-grow-1">
          <span class="fw-semibold">${stay.name}</span>
          ${stay.city && html`<small class="text-body-secondary ms-2 stay-city">${stay.city}</small>`}
        </span>
        <${EditButton} onClick=${onEdit} />
      </div>
      <div class="card-body py-2">
        <div class="small text-body-secondary">
          ${dateRange(stay.check_in, stay.check_out, locale)} · ${t('stays.nights', { n: stay.nights })}${where && ` · ${where}`}${stay.url && html` ·
          <a class="ms-1" href=${stay.url} target="_blank" rel="noopener noreferrer">
            <i class="bi bi-box-arrow-up-right"></i> ${t('stays.booking')}</a>`}
        </div>
        ${stay.note && html`<div class="small mt-1">${stay.note}</div>`}
        <div class="mt-2">
          ${stay.totals.filter((total) => total.per_night !== null).map((total) => html`
            <div key=${total.currency_id} class="num fw-semibold stay-per-night">
              ${t('stays.per_night', { amount: `${money(total.per_night, locale)} ${total.currency_code}` })}
            </div>
          `)}
        </div>
      </div>
      ${items.length > 0 && html`
        <div class="list-group list-group-flush border-top stay-items">
          ${items.map((item) => html`
            <${ItemRow} key=${item.id} item=${item} trip=${trip} locale=${locale} onSelect=${onSelectItem} />
          `)}
        </div>
      `}
    </div>
  `;
}

export function Stays() {
  const store = useStore();
  const locale = getLocale();
  const [stayModal, setStayModal] = useState(undefined); // undefined = closed, null = new, stay = edit
  const [editEntry, setEditEntry] = useState(null);
  const [filter, setFilter] = useState('');

  // An item save clears store.stays (invalidateMoneyViews), so a total the
  // modal just changed is refetched while the tab is still open.
  useEffect(() => {
    if (!store.stays) reload('stays');
  }, [store.slug, store.stays]);

  // The expenses listed under each stay come from the same feed as the Expenses tab.
  useEffect(() => {
    if (!store.items) reload('items');
    if (!store.labels) reload('labels');
  }, [store.slug]);

  const ready = Boolean(store.stays && store.items);
  // An item row links here with #stay-<id>; the cards only exist once the data has loaded.
  useEffect(() => {
    if (ready && location.hash) document.querySelector(location.hash)?.scrollIntoView();
  }, [ready]);

  if (!ready) return html`<${Loading} />`;

  // A stay write changes the trip's embedded list the item form picks from, and a
  // delete detaches items, so both are re-read alongside the stays themselves.
  async function staysChanged() {
    await Promise.all([reload('stays'), reload('trip'), store.items && reload('items')]);
  }

  const needle = filter.trim().toLowerCase();
  const stayItems = (stay) => store.items.filter((item) => item.stay_id === stay.id);
  const visible = needle
    ? store.stays.filter((stay) => stayMatches(
      stay, store.trip.countries.find((c) => c.id === stay.country_id), stayItems(stay), needle))
    : store.stays;

  return html`
    <div class="stays-content d-flex align-items-center gap-2 mb-3">
      <button class="btn btn-primary px-4" onClick=${() => setStayModal(null)}>
        <i class="bi bi-plus-lg"></i> ${t('stays.add')}</button>
      <div class="input-group input-group-sm ms-auto" style="max-width:16rem">
        <span class="input-group-text bg-body"><i class="bi bi-search"></i></span>
        <input class="form-control" placeholder=${t('stays.filter_placeholder')}
               value=${filter} onInput=${(e) => setFilter(e.target.value)} />
      </div>
    </div>
    ${store.stays.length === 0 && html`<p class="text-body-secondary">${t('stays.empty')}</p>`}
    ${store.stays.length > 0 && visible.length === 0 && html`<p class="text-body-secondary">${t('stays.no_match')}</p>`}
    ${visible.map((stay) => html`
      <${StayCard} key=${stay.id} stay=${stay} trip=${store.trip} locale=${locale}
                   items=${stayItems(stay)}
                   onSelectItem=${(item) => setEditEntry({ kind: 'item', row: item })}
                   onEdit=${() => setStayModal(stay)} />
    `)}

    ${stayModal !== undefined && html`
      <${StayModal} trip=${store.trip} stay=${stayModal} onSaved=${staysChanged}
                    onClose=${() => setStayModal(undefined)} />
    `}
    ${editEntry && html`
      <${ItemModal} trip=${store.trip} labels=${store.labels || []} entry=${editEntry}
                    onClose=${() => setEditEntry(null)} />
    `}
  `;
}
