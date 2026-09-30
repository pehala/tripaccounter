import { useEffect, useState } from 'preact/hooks';
import { html } from '../h.js';
import { useStore, reload } from '../store.js';
import { t, getLocale } from '../i18n/index.js';
import { dateRange, money } from '../fmt.js';
import { ItemModal } from '../components/ItemModal.js';
import { Loading } from '../components/Loading.js';
import { StayModal } from '../components/StayModal.js';

// Totals and their per-night figures come from the server, one per currency
// (design/FRONTEND.md §4 rule 1); nothing here divides or adds an amount.
function StayCard({ stay, trip, locale, onEdit, onAddExpense }) {
  const country = trip.countries.find((c) => c.id === stay.country_id);
  const where = [country && `${country.flag ?? ''} ${country.name}`.trim(), stay.city].filter(Boolean).join(' · ');
  return html`
    <div class="card shadow-sm mb-3 stay-card">
      <div class="card-header d-flex align-items-center gap-2">
        <i class="bi bi-house-door"></i>
        <span class="fw-semibold flex-grow-1">${stay.name}</span>
        <button type="button" class="btn btn-sm btn-link py-0" aria-label=${t('stay.edit_title')}
                onClick=${onEdit}><i class="bi bi-pencil"></i></button>
      </div>
      <div class="card-body py-2">
        <div class="small text-body-secondary">
          ${dateRange(stay.check_in, stay.check_out, locale)} · ${t('stays.nights', { n: stay.nights })}${where && ` · ${where}`}
        </div>
        ${stay.url && html`
          <a class="small" href=${stay.url} target="_blank" rel="noopener noreferrer">
            <i class="bi bi-box-arrow-up-right"></i> ${t('stays.booking')}</a>
        `}
        ${stay.note && html`<div class="small mt-1">${stay.note}</div>`}
        <div class="mt-2">
          ${stay.totals.length === 0 && html`<small class="text-body-secondary">${t('stays.no_items')}</small>`}
          ${stay.totals.map((total) => html`
            <div key=${total.currency_id} class="d-flex align-items-baseline gap-2 stay-total">
              <span class="num fw-semibold">${money(total.amount, locale)} ${total.currency_code}</span>
              ${total.per_night !== null && html`
                <small class="num text-body-secondary stay-per-night">
                  ${t('stays.per_night', { amount: `${money(total.per_night, locale)} ${total.currency_code}` })}
                </small>
              `}
            </div>
          `)}
          ${stay.item_count > 0 && html`
            <small class="text-body-secondary">${t('stays.items', { n: stay.item_count })}</small>
          `}
        </div>
      </div>
      <div class="card-footer py-1">
        <button type="button" class="btn btn-sm btn-link px-0" onClick=${onAddExpense}>
          <i class="bi bi-plus-lg"></i> ${t('stays.add_expense')}</button>
      </div>
    </div>
  `;
}

export function Stays() {
  const store = useStore();
  const locale = getLocale();
  const [stayModal, setStayModal] = useState(undefined); // undefined = closed, null = new, stay = edit
  const [expenseStay, setExpenseStay] = useState(null);

  // An item save clears store.stays (invalidateMoneyViews), so a total the
  // modal just changed is refetched while the tab is still open.
  useEffect(() => {
    if (!store.stays) reload('stays');
  }, [store.slug, store.stays]);

  if (!store.stays) return html`<${Loading} />`;

  // A stay write changes the trip's embedded list the item form picks from, and a
  // delete detaches items, so both are re-read alongside the stays themselves.
  async function staysChanged() {
    await Promise.all([reload('stays'), reload('trip'), store.items && reload('items')]);
  }

  function addExpense(stay) {
    if (!store.labels) reload('labels');
    setExpenseStay(stay);
  }

  return html`
    <div class="stays-content d-flex align-items-center gap-2 mb-3">
      <button class="btn btn-primary px-4" onClick=${() => setStayModal(null)}>
        <i class="bi bi-plus-lg"></i> ${t('stays.add')}</button>
    </div>
    ${store.stays.length === 0 && html`<p class="text-body-secondary">${t('stays.empty')}</p>`}
    ${store.stays.map((stay) => html`
      <${StayCard} key=${stay.id} stay=${stay} trip=${store.trip} locale=${locale}
                   onEdit=${() => setStayModal(stay)} onAddExpense=${() => addExpense(stay)} />
    `)}

    ${stayModal !== undefined && html`
      <${StayModal} trip=${store.trip} stay=${stayModal} onSaved=${staysChanged}
                    onClose=${() => setStayModal(undefined)} />
    `}
    ${expenseStay && html`
      <${ItemModal} trip=${store.trip} labels=${store.labels || []} entry=${null} stay=${expenseStay}
                    onClose=${() => setExpenseStay(null)} />
    `}
  `;
}
